# 架构文档

本文是 hci-quality 系统的总体架构参照,是所有下游实现与文档冲突时的仲裁依据。本文的修订需走 ADR 流程,记录于 docs/adr。

---

## 一、设计原则

- 客户语言与工程实体共平面。TD 的自由文本与五语言代码的 AST、调用图须通过符号注册表互为可检索。
- 知识层与大脑层解耦。subagent 只认 MCP 工具接口,不感知底层存储。
- 让步须配对补救。任一一阶段简化决策,在 docs/roadmap.md 与 docs/adr 中记录二阶段补救动作。
- 可观测先于可运行。Phoenix 先上,评估脚本先写;没有轨迹的功能视为不存在。
- Windows 离线内网为头等约束。所有依赖从内网 PyPI、npm 镜像获取,所有 LLM 调用走 ANTHROPIC_BASE_URL 指向的内网网关。
- 多语言即头等问题。不对任何单语言组合做硬编码,所有"Perl 到 Go"之类的固定路径均改写为"任意语言到任意语言 via Symbol Registry"。

---

## 二、分层模型

系统按七层划分,层间耦合以接口契约为准。

```text
graph TB
    %% 图例置顶
    subgraph LEGEND[图例（Legend）]
        direction LR
        Ls[数据存储]:::store
        Lt[MCP工具]:::tool
        Lb[大脑子代理]:::brain
        Lo[观测评估]:::obs
    end

    subgraph L7[触发与产出层（Trigger and Output）]
        WH[FastAPI TD webhook接收器]
        CMT[TD评论回写]
    end

    subgraph L6[大脑层（Brain）]
        B[Claude Code CLI]:::brain
        S1[triage]:::brain
        S2[reproduce]:::brain
        S3[rca]:::brain
        S4[patch]:::brain
        S5[regression]:::brain
        S6[security]:::brain
        S7[docs]:::brain
    end

    subgraph L5[工具层（Tool Layer）]
        MT1[lightrag.search]:::tool
        MT2[codegraph.query]:::tool
        MT3[codegraph.cross_language_hop]:::tool
        MT4[td.read_normalized]:::tool
        MT5[codegraph.query_by_canonical]:::tool
    end

    subgraph L4[知识层（Knowledge Layer）]
        K1[LightRAG向量与实体]:::store
        K2[Kuzu多语言代码图]:::store
        K3[标准化TD JSON]:::store
        K4[bge-m3本地快照]:::store
        K5[符号注册表SymbolRegistry]:::store
    end

    subgraph L3[摄取与抽取层（Ingestion and Extraction）]
        I1[客户术语归一]
        I2[Drain3多语言日志模板]
        I3[tree-sitter五语言AST]
        I4[跨语言边界扫描]
        I5[堆栈错误码抽取]
    end

    subgraph L2[数据源层（Data Sources）]
        DS1[TD与iCare]
        DS2[Git仓库Perl+Go+Python+Java+C]
    end

    subgraph L1[观测与评估层（Observability and Eval 横切）]
        O1[Phoenix SQLite后端]:::obs
        O2[golden_tds.yaml]:::store
        O3[eval_join.py]:::obs
    end

    L7 --> L6
    L6 --> L5
    L5 --> L4
    L4 --> L3
    L3 --> L2
    L1 -.-> L6
    L1 -.-> L4
    L1 -.-> L5

    classDef store fill:#eaf4ff,stroke:#2b6cb0,color:#1a365d
    classDef tool fill:#f0fff4,stroke:#2f855a,color:#22543d
    classDef brain fill:#fff5f5,stroke:#c53030,color:#742a2a
    classDef obs fill:#fffaf0,stroke:#b7791f,color:#744210
```

---

## 三、部署视图

目标机为一台 Windows 10 物理机,所有组件均在同一主机内以进程形态运行。Phoenix、webhook、Claude CLI 子进程、MCP server 之间通过本机 loopback 与 stdio 互通,不依赖任何容器或虚拟化。

```text
graph TB
    subgraph Host[Windows 10主机（D:盘根 D slash opt-hci-quality slash mvp）]
        subgraph Daemons[常驻进程]
            P1[Phoenix Server<br>python -m phoenix.server.main]
            P2[Uvicorn webhook<br>hci_quality.webhook.td_listener]
        end

        subgraph OnDemand[按需子进程]
            C1[Claude CLI子进程<br>由webhook Popen启动]
            M1[MCP lightrag server<br>stdio]
            M2[MCP codegraph server<br>stdio]
            M3[MCP td server<br>stdio]
        end

        subgraph FS[本地文件系统]
            FS1[lightrag_storage 向量与实体索引]:::store
            FS2[data/codegraph.kuzu 调用图]:::store
            FS3[data/td/normalized]:::store
            FS4[traces/phoenix.sqlite]:::store
            FS5[models/bge-m3]:::store
            FS6[logs]:::store
        end
    end

    subgraph Extern[外部依赖]
        E1[内网PyPI镜像]
        E2[内网npm镜像]
        E3[内网LLM网关<br>ANTHROPIC_BASE_URL]
        E4[TD/iCare系统<br>REST API]
    end

    P2 -. 触发 .-> C1
    C1 -. stdio .-> M1
    C1 -. stdio .-> M2
    C1 -. stdio .-> M3
    M1 --> FS1
    M2 --> FS2
    M3 --> FS3
    P1 --> FS4
    M1 --> FS5
    C1 -.-> E3
    C1 -.->|OTEL HTTP| P1
    E4 ==>|webhook HTTP| P2
    C1 ==>|评论回写HTTP| E4

    classDef store fill:#eaf4ff,stroke:#2b6cb0,color:#1a365d
```

---

## 四、数据流

### 4.1 批量摄取(日级,离线)

```text
flowchart LR
    A[TD/iCare导出JSONL] --> B[客户术语归一化]
    B --> C[Drain3多语言日志模板]
    C --> D[堆栈与错误码抽取]
    D --> E[标准化TD JSON]
    D --> F[LightRAG chunks+metadata]
    G[bge-m3本地快照] -. embed .-> F
    H[Git仓库五语言源] --> I[tree-sitter AST]
    H --> J[跨语言边界扫描]
    I --> K[Kuzu图函数节点]
    J --> L[Kuzu图ExternalEntry与CROSSES_BOUNDARY]
    M[符号注册表SymbolRegistry] --> I
    M --> J
    M --> F
```

批量摄取每日运行一次,入口脚本是 scripts/03_ingest_td.ps1 与 scripts/04_build_codegraph.ps1。新增或变更代码仓时 scripts/04 以增量模式运行。

### 4.2 在线触发(事件级,秒级)

```text
sequenceDiagram
    autonumber
    participant TD as TD/iCare
    participant WH as FastAPI webhook
    participant CC as Claude Code CLI子进程
    participant T as triage子代理
    participant R as rca子代理
    participant P as patch子代理
    participant MCP as MCP stdio 工具
    participant PX as Phoenix轨迹后端

    TD->>WH: 新单事件（POST /td/webhook）
    WH->>WH: 1 校验schema落盘任务文件
    WH-->>TD: 2 立即返回202
    WH->>CC: 3 subprocess Popen claude -p
    CC->>T: 4 路由到triage
    T->>MCP: 5 td.read_normalized
    T->>MCP: 6 lightrag.search 历史相似
    T-->>CC: 7 结构化归并与相似TD清单
    CC->>R: 8 路由到rca
    R->>MCP: 9 codegraph.query 与 cross_language_hop
    R->>MCP: 10 lightrag.search 知识复用
    R-->>CC: 11 根因假设JSON
    CC->>P: 12 路由到patch
    P->>MCP: 13 codegraph.query 目标函数上下文
    P-->>CC: 14 补丁diff草稿
    CC->>PX: 15 OTEL span上报
    CC->>TD: 16 评论回写根因与补丁
```

---

## 五、组件契约

### 5.1 知识层

| 组件 | 存储形态 | 写入者 | 读取者 | 关键字段或 schema |
| --- | --- | --- | --- | --- |
| LightRAG | 本地文件 JSON 与向量索引 | ingest.lightrag_adapter | MCP lightrag.search | td_id, title, description, comments, severity, module, stack_qnames |
| 标准化 TD | data/td/normalized 下的 JSON | ingest.td_normalize | MCP td.read_normalized | 同上,结构化字段分离 |
| Kuzu 图库 | data/codegraph.kuzu 目录 | graph.kuzu_build、lang_bridge.multi_lang_graph | MCP codegraph.* | 节点 function、module、external_call、service;边 calls、cross_calls、imports、invokes、binds_to |
| bge-m3 快照 | models/bge-m3 | 运维一次性同步 | LightRAG embedding 通道 | 须 local_files_only=True |
| 符号注册表 | data/symbols.sqlite + 内存倒排 | lang_bridge.symbol_registry | graph 构建与 MCP 查询 | UnifiedSymbol、SymbolVariant |

### 5.2 三把钥匙

- 函数全限定名 qname。各语言统一以规范形式存储,见 §5.4。
- 客户术语归一字典 customer_terms.yaml。定义 canonical 与 aliases、owner_module。
- 跨语言边界 ExternalEntry。物理形态是共享 UDS 路径、gRPC service name、FFI 符号、subprocess argv 等;任何一端可识别的字符串都作为节点主键。

### 5.3 多语言支持

为避免把 Perl 到 Go 的单向链路硬编码,知识层与工具层引入 lang_bridge 子包。

- SymbolRegistry。自动解析五种语言的符号,生成 canonical_name,维护 (lang, qname) 到 canonical 的双向索引。
- MultiLangGraph。Kuzu schema 扩展为多语言形态,新增 external_call、service 两类节点与 invokes、binds_to 两种边。
- MultiLangLogParser。为每种语言维护独立 Drain3 模板树,首屏内置常见错误模式。
- MultiLangEval。hit@5、MRR、recall、cross_lang_acc 均按语言对拆分,加权汇总。

### 5.4 qname 规范

| 语言 | 形态 | 示例 |
| --- | --- | --- |
| Perl | `Pkg::Sub::sub_name` | `Net::DHCP::renew` |
| Go | `module_path.(Receiver).Method` 或 `module_path.Func` | `github.com/hci/net.(*DHCP).Renew` |
| Python | `package.module.Class.method` 或 `package.module.func` | `hci.net.dhcp.renew` |
| Java | `com.pkg.Class.method(signature)` | `com.hci.net.DHCPService.renew()` |
| C | `file.c::func` 或简单 `func` | `dhcp.c::dhcp_renew` |

所有 qname 由符号注册表同时保留原始形态与规范形态(canonical_name,形如 `network.dhcp.renew`),规范形态用于跨语言跳转。

### 5.5 MCP 工具层

所有 MCP server 通过 stdio 暴露,注册在根目录 `.mcp.json`。

| 工具名 | 输入 | 输出 | 后端 |
| --- | --- | --- | --- |
| lightrag.search | {query, top_k, mode} | [{td_id, score, snippet, metadata}] | LightRAG |
| codegraph.query | {qname, direction, depth} | 子图 JSON | Kuzu |
| codegraph.cross_language_hop | {from_qname, target_langs?} | 候选 {lang, qname, canonical, confidence} 列表 | Kuzu via SymbolRegistry |
| codegraph.query_by_canonical | {canonical} | 各语言变体清单 | SymbolRegistry |
| td.read_normalized | {td_id} | 单条结构化 TD | 标准化 TD JSON 目录 |

错误契约统一为:

```text
{"error": {"code": "<OPAQUE_CODE>", "message": "<user facing>", "hint": "<actionable>"}}
```

subagent 被训练为读 hint 做下一步决策,错误不穿透为异常。

### 5.6 大脑层

`.claude/agents/` 下七份 Markdown,每份遵循 Claude Code subagent 格式,声明 name、description、tools 白名单、model。模型路由的一阶段策略:全部走内网网关上的 claude-opus-4-6 与 claude-sonnet-4-6 两档,不启用 Haiku。

### 5.7 触发与产出层

- FastAPI webhook 端口 8088,路径 /td/webhook。反压由 HCIQ_MAX_PARALLEL 配合 asyncio Semaphore 实现,去重由 (td_id, 10 分钟窗口) 内存字典实现。
- 评论回写由 subagent 链尾调用 webhook.comment_writeback 模块完成,不由 webhook 接收器本身同步等待。

### 5.8 观测与评估层

- Phoenix OTLP HTTP endpoint http://localhost:6006/v1/traces,SQLite 位于 traces/phoenix.sqlite。
- eval_join 读 golden_tds.yaml 与 Phoenix span,输出 hit@1、hit@5、MRR 并按语言对拆分。
- golden_tds_mine 扫 git log,匹配 commit message 中 TD-XXXX 正则,交集 tree-sitter 函数区间得出 `{td_id: [qname,...]}`。

---

## 六、关键非功能属性

| 维度 | 目标 | 衡量方式 |
| --- | --- | --- |
| 冷启动时间 | 新环境到端到端跑通小于等于 90 分钟 | scripts/99_e2e_smoke.ps1 总耗时 |
| webhook 接收延迟 | P95 小于等于 200 毫秒,不含子进程 | Phoenix span webhook.accept |
| rca 端到端 | P50 小于等于 120 秒,P95 小于等于 300 秒 | Phoenix 根 span |
| LightRAG 召回 hit at 5 | 大于等于 0.70 | eval_join 月基线 |
| 代码图完整度 | Perl 函数节点覆盖大于等于 95% | 抽样 grep 与节点数比对 |
| 跨语言跳转准确率 | 各语言对 cross_lang_acc 大于等于 ADR-0006 表列阈值 | eval_join 按语言对 |
| 轨迹完整度 | 任何上主线 subagent 在 Phoenix 可见对应 project span | CI gate |

---

## 七、关键替换决策速查

| 原方案 | 修订后 | ADR |
| --- | --- | --- |
| runc 与 Kata 沙箱 | Git worktree 加 NTFS ACL | ADR-0001 |
| Langfuse docker-compose | Arize Phoenix pip 与 SQLite | ADR-0002 |
| Open SWE LangGraph | 自写 FastAPI webhook | ADR-0003 |
| OpenHands 作为"手" | Claude Code 内置工具 | ADR-0004 |
| 离线 wheel 搬运 | 内网 PyPI 镜像直装 | ADR-0005 |
| 手工 customer_terms 单向字典 | 符号注册表 SymbolRegistry 自动化 | ADR-0006 |

---

## 八、二阶段演进锚点

| 能力缺口 | 一阶段让步 | 二阶段触发条件 | 二阶段方案 |
| --- | --- | --- | --- |
| 强沙箱隔离 | Git worktree 加 ACL | subagent 首次误操作或引入第三方扩展 | Linux 物理机加 OpenHands runc |
| 向量库规模 | LightRAG 本地文件 | TD 大于 50 万条或查询 P95 大于 2 秒 | Milvus Standalone |
| 观测后端 | Phoenix 加 SQLite | 并发 subagent 大于 10 或 database is locked 频发 | Phoenix 加 PostgreSQL 或 Langfuse |
| 事件源 | 自写 FastAPI | 需接入 CI/CD、IM、邮件等多路事件 | Open SWE 或 RabbitMQ 或 Kafka |
| 多 Runner 并发 | 单机单 Python 进程 | 单机资源饱和 | Prefect 或 Temporal |

---

## 九、术语表

| 术语 | 定义 |
| --- | --- |
| TD | Trouble Description,客户或内测提交的缺陷单 |
| iCare | 内部 TD 管理系统 |
| qname | Fully Qualified Name,函数或方法的全限定名 |
| canonical_name | 跨语言统一命名,如 network.dhcp.renew |
| ExternalEntry | Kuzu 图中代表跨语言 IPC 挂接点的节点类型 |
| CROSSES_BOUNDARY | Kuzu 图中连接跨语言调用者与被调用者的边类型 |
| subagent | Claude Code 定义的具名角色化提示词加工具白名单 |
| MCP | Model Context Protocol,访问外部工具的标准协议 |
| golden TD | 从 git 历史挖出的 TD 到修复函数 qname 真值对 |

---

## 十、参考资料

详见 docs/references.md。
