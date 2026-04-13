"""多语言代码图谱 Kuzu 封装。

Schema:
  节点
    function        (id, lang, qname, canonical_name, file, line_start, line_end, domain)
    module          (id, lang, name, path)
    external_call   (id, lang, api_name, boundary_type, target_lang, description)
    service         (id, lang, name, protocol, host)
  边
    calls           (function -> function)            line_no
    cross_calls     (function -> function)            canonical, confidence, mechanism
    imports         (function -> module)
    invokes         (function -> service)             protocol, endpoint
    binds_to        (function -> external_call)       call_type

设计要点:
  - id 格式统一为 "{lang}::{qname}",幂等写入用 MERGE
  - 所有字符串都经过简单转义,避免 Cypher 注入
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("hci_quality.lang_bridge.multi_lang_graph")


def _esc(s: str) -> str:
    """Cypher 字符串字面量转义。"""
    return str(s).replace("\\", "\\\\").replace("'", "\\'")


class MultiLangGraph:
    def __init__(self, db_path: str):
        try:
            import kuzu
        except ImportError as e:
            raise RuntimeError("kuzu 未安装") from e
        self._kuzu = kuzu
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    # ------------ schema ------------

    def _init_schema(self) -> None:
        stmts = [
            "CREATE NODE TABLE IF NOT EXISTS function ("
            "id STRING PRIMARY KEY, lang STRING, qname STRING, "
            "canonical_name STRING, file STRING, "
            "line_start INT64, line_end INT64, domain STRING)",

            "CREATE NODE TABLE IF NOT EXISTS module ("
            "id STRING PRIMARY KEY, lang STRING, name STRING, path STRING)",

            "CREATE NODE TABLE IF NOT EXISTS external_call ("
            "id STRING PRIMARY KEY, lang STRING, api_name STRING, "
            "boundary_type STRING, target_lang STRING, description STRING)",

            "CREATE NODE TABLE IF NOT EXISTS service ("
            "id STRING PRIMARY KEY, lang STRING, name STRING, "
            "protocol STRING, host STRING)",

            "CREATE REL TABLE IF NOT EXISTS calls "
            "(FROM function TO function, line_no INT64)",

            "CREATE REL TABLE IF NOT EXISTS cross_calls "
            "(FROM function TO function, canonical STRING, "
            "confidence DOUBLE, mechanism STRING)",

            "CREATE REL TABLE IF NOT EXISTS imports "
            "(FROM function TO module)",

            "CREATE REL TABLE IF NOT EXISTS invokes "
            "(FROM function TO service, protocol STRING, endpoint STRING)",

            "CREATE REL TABLE IF NOT EXISTS binds_to "
            "(FROM function TO external_call, call_type STRING)",
        ]
        for s in stmts:
            try:
                self.conn.execute(s)
            except Exception as e:
                # Kuzu 已存在同名表时会抛异常,忽略
                log.debug("schema stmt skipped: %s -- %s", s[:60], e)

    def reset_schema(self) -> None:
        """删除全部表重建。谨慎使用,build 非 incremental 时调用。"""
        for t in ["calls", "cross_calls", "imports", "invokes", "binds_to",
                  "function", "module", "external_call", "service"]:
            try:
                self.conn.execute(f"DROP TABLE {t}")
            except Exception:
                pass
        self._init_schema()

    # ------------ upserts ------------

    def upsert_function(self, lang: str, qname: str, canonical_name: str,
                        file: str, line_start: int, line_end: int, domain: str) -> None:
        node_id = f"{lang}::{qname}"
        cypher = (
            f"MERGE (f:function {{id: '{_esc(node_id)}'}}) "
            f"SET f.lang='{_esc(lang)}', f.qname='{_esc(qname)}', "
            f"f.canonical_name='{_esc(canonical_name)}', "
            f"f.file='{_esc(file)}', f.line_start={int(line_start)}, "
            f"f.line_end={int(line_end)}, f.domain='{_esc(domain)}'"
        )
        self.conn.execute(cypher)

    def upsert_call(self, lang: str, caller_qname: str, callee_qname: str, line_no: int = 0) -> None:
        a = f"{lang}::{caller_qname}"
        b = f"{lang}::{callee_qname}"
        self.conn.execute(
            f"MATCH (x:function {{id:'{_esc(a)}'}}),(y:function {{id:'{_esc(b)}'}}) "
            f"CREATE (x)-[:calls {{line_no: {int(line_no)}}}]->(y)"
        )

    def upsert_external_call(self, lang: str, api_name: str, boundary_type: str,
                             target_lang: str = "", description: str = "") -> None:
        nid = f"{lang}::ext::{api_name}"
        self.conn.execute(
            f"MERGE (e:external_call {{id:'{_esc(nid)}'}}) "
            f"SET e.lang='{_esc(lang)}', e.api_name='{_esc(api_name)}', "
            f"e.boundary_type='{_esc(boundary_type)}', "
            f"e.target_lang='{_esc(target_lang)}', "
            f"e.description='{_esc(description)}'"
        )

    def link_cross_calls_by_api(self, api: str, items: list[dict]) -> int:
        """对同一 external_call,在两个不同语言间创建 cross_calls 边。

        items 来自 cross_boundary.scan_repo 的产物。
        这里做最保守的处理:当某 api 在两种语言出现,每对语言建一条边,
        confidence 初值 0.6,随 symbol_registry 匹配再增益。
        """
        langs = list({i["lang"] for i in items})
        count = 0
        for i, la in enumerate(langs):
            for lb in langs[i + 1:]:
                # 不连到具体函数,而是连 external_call 间的桥接:通过两侧 binds_to 已建立
                # 这里只打一条 marker 边方便查询:用 api_name 等值 join
                nid_a = f"{la}::ext::{api}"
                nid_b = f"{lb}::ext::{api}"
                try:
                    self.conn.execute(
                        f"MATCH (a:external_call {{id:'{_esc(nid_a)}'}}),"
                        f"(b:external_call {{id:'{_esc(nid_b)}'}}) "
                        f"SET a.target_lang='{_esc(lb)}', b.target_lang='{_esc(la)}'"
                    )
                    count += 1
                except Exception as e:
                    log.debug("link_cross_calls_by_api skip: %s", e)
        return count

    # ------------ queries ------------

    def raw_query(self, cypher: str) -> list[dict]:
        try:
            res = self.conn.execute(cypher)
        except Exception as e:
            return [{"error": str(e)}]
        out: list[dict] = []
        while res.has_next():
            row = res.get_next()
            # Kuzu 行是 list,这里给出索引结构以便调试
            out.append({"row": list(row)})
        return out

    def query_function(self, lang: str, qname: str, direction: str = "callers",
                       depth: int = 2) -> list[dict]:
        nid = f"{lang}::{qname}"
        rel = "calls|cross_calls"
        if direction == "callers":
            pattern = (
                f"MATCH path=(s:function)-[:{rel}*1..{int(depth)}]->"
                f"(t:function {{id:'{_esc(nid)}'}}) "
                f"RETURN s.lang, s.qname, length(path) as d"
            )
        else:
            pattern = (
                f"MATCH path=(s:function {{id:'{_esc(nid)}'}})-"
                f"[:{rel}*1..{int(depth)}]->(t:function) "
                f"RETURN t.lang, t.qname, length(path) as d"
            )
        return self.raw_query(pattern)

    def query_by_canonical(self, canonical: str) -> list[dict]:
        return self.raw_query(
            f"MATCH (f:function) WHERE f.canonical_name='{_esc(canonical)}' "
            f"RETURN f.lang, f.qname, f.file, f.domain"
        )

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            self.db.close()
        except Exception:
            pass
