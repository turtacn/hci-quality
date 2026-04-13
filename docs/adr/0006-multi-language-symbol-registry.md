# ADR-0006 引入多语言符号注册表 SymbolRegistry

状态:Accepted
日期:2026-04-12

## 背景

原方案 customer_terms.yaml 是单向手工字典,仅服务于 Perl 到 Go 的固定跨语言链路。实际代码仓涉及 Perl、Go、Python、Java、C 五种语言,跨语言组合达 N×M,手工字典不可维护,也无法覆盖 FFI、gRPC、subprocess、CGI 等多种边界形态。同时 Kuzu schema 的 ExternalEntry 加 CROSSES_BOUNDARY 单一边类型无法承载多机制跨语言调用。

## 决策

引入 `src/hci_quality/lang_bridge/` 子包,包含四个模块:

- symbol_registry 自动解析五语言符号,生成 canonical_name,维护 (lang, qname) 到 canonical 的双向索引;导出兼容旧格式的 YAML
- multi_lang_graph 扩展 Kuzu schema,新增 external_call、service 节点与 invokes、binds_to 两种边;保留 calls、cross_calls、imports 原有边
- multi_lang_log_parser 为五语言各自维护 Drain3 模板树,预填常见错误模式,提供 lang hint 与自动检测
- multi_lang_eval 把 hit@5、MRR、recall、cross_lang_acc 按语言对拆分,加权汇总

MCP 工具层新增 codegraph.query_by_canonical 与 codegraph.cross_language_hop 可选参数 target_langs,原 cross_lang 单向工具废弃。

## 后果

- 新增代码约 1400 行,但消除所有单语言硬编码
- 新语言接入只需实现一个 LanguageParser 子类,无需改 subagent 与 MCP server
- 评估指标细粒度化,能按语言对定位薄弱环节
- 迁移成本:已有 customer_terms.yaml 仍可作为 SymbolRegistry 的手工补充层,非零冲突

## 最小可行调整

若短期资源有限,可分五步上线:
1. customer_terms.yaml 替换为 symbol_registry.py 自动化
2. Kuzu schema 扩展 external_call 节点加 binds_to 边
3. MCP 增加 codegraph.query_by_canonical
4. Drain3 改多 parser 架构
5. 评估按语言对拆分

上述五项约为完整重构 40%,覆盖 80% 场景。
