# 开发路线图

十个阶段自底向上推进。每个 Phase 均有独立验收判据,上一 Phase 未绿灯前下一 Phase 不得动工。

---

## 一、总览

| Phase | 代号 | 目标 | 核心产出 | 预计工期 人日 |
| --- | --- | --- | --- | --- |
| 01 | Foundation | 环境、目录、脚本骨架 | scripts/02_verify_env.ps1 全绿 | 2 |
| 02 | Ingest-TD | TD 归一与 LightRAG 首批灌 | 样本可语义检索 | 3 |
| 03 | CodeGraph-Single-Lang | Perl 单语言 Kuzu 图 | qname 反查调用链 | 4 |
| 04 | CodeGraph-Multi-Lang | 加入 Go、Python、Java、C 与跨语言边 | canonical_name 多语言命中 | 6 |
| 05 | MCP-Wiring | 三个 MCP server 可用 | /mcp 全绿 | 3 |
| 06 | Subagents-Minimum | triage、rca、patch 上线 | 手工提问可出根因 | 4 |
| 07 | Observability | Phoenix 接全链路 | 每个 subagent 有 span | 2 |
| 08 | Eval-Golden | golden_tds 挖掘与首轮评估 | hit@5 基线 | 3 |
| 09 | Webhook-E2E | FastAPI 与 TD 回写 | 提交测试单评论自动落地 | 3 |
| 10 | Hardening | 七 subagent 全量与并发 | 连续 72h 无人值守 | 5 |

共约 35 人日,单人两到三个月,双人并行约 1.5 个月。

---

## 二、阶段细则

### 2.1 Phase 01 Foundation

目标:把 `D:\opt-hci-quality\mvp` 作为可复现工作根目录建起来,不触碰业务逻辑。

动作:
- 克隆本仓库到根目录
- 执行 scripts/02_verify_env.ps1 校验 pwsh、python、node、npm、git、poetry、uv 版本
- 执行 scripts/01_bootstrap_env.ps1 创建 venv 并安装 Python 依赖
- `npm install -g @anthropic-ai/claude-code` 走内网 npm
- 配置环境变量 ANTHROPIC_BASE_URL 与 ANTHROPIC_API_KEY

验收:
- `python -c "import lightrag, kuzu, phoenix"` 无 ImportError
- `claude -p "回答 1+1"` 返回数字开头
- `tree /F D:\opt-hci-quality\mvp` 与 README 目录清单一致

常见坑:
- torch 要走 CPU 镜像,避免拖 CUDA 版两三 G
- npm 的 scoped package 须确认 `@anthropic-ai` 被内网镜像同步

### 2.2 Phase 02 Ingest-TD

目标:导入 TD 近三个月历史数据到 LightRAG,验证语义检索可用性。

动作:
- 从 TD REST API 或 DB 导出 JSONL 到 data/td/raw
- 编辑 configs/customer_terms.yaml 写 30 至 50 条最高频术语
- 运行 `python -m hci_quality.ingest.td_normalize --input data/td/raw --output data/td/normalized`
- 运行 `python -m hci_quality.ingest.td_normalize --push-lightrag --limit 200` 先灌样本
- 交互检索:"客户机蓝屏无响应"应返回 Top-5 相似 TD

验收:
- data/td/normalized 下 TD-*.json 数量等于样本数
- lightrag_storage 下 vdb_entities.json 等文件存在
- 人工对 5 个 query 的 Top-5 相关性大于等于 3/5

常见坑:
- sentence-transformers 默认拖 CUDA torch,需要预先装 CPU torch
- bge-m3 首次加载失败多半是没传 local_files_only=True

### 2.3 Phase 03 CodeGraph-Single-Lang

目标:以 Perl 单语言为起点,构建 Kuzu 调用图。

动作:
- 准备 Perl 源码工作树到 repos/perl-main
- 实现 graph.tree_sitter_extract,用 tree-sitter-perl 解析 .pm/.pl
- 实现 graph.kuzu_build,创建 schema 并批量写入
- 运行 `python -m hci_quality.graph.kuzu_build --source repos/perl-main --language perl`
- 交互查询调用链

验收:
- data/codegraph.kuzu 目录非空,大于 1 MB
- 抽样 3 个已知函数调用链与人工 grep 交叉一致
- Perl 函数节点数大于等于仓库中 `sub ` 关键字数的 90%

常见坑:
- Perl 嵌套 package 易导致 qname 丢上下文,务必递归处理

### 2.4 Phase 04 CodeGraph-Multi-Lang

目标:加入 Go、Python、Java、C 四语言与跨语言边,符号注册表上线。

动作:
- 准备 repos/go-main、repos/py-main、repos/java-main、repos/c-main
- 实现 lang_bridge.symbol_registry 的 PerlParser、GoParser、PythonParser、JavaParser、CParser
- 实现 lang_bridge.multi_lang_graph,扩展 Kuzu schema 加 external_call、service 节点与 invokes、binds_to 边
- 运行 `python -m hci_quality.graph.kuzu_build --source repos/<lang>-main --language <lang> --incremental`(五次)
- 运行 `python -m hci_quality.graph.cross_boundary --all-repos --incremental`,扫 UDS、gRPC、FFI 符号、subprocess argv,建 CROSSES_BOUNDARY 边
- 运行 `python -m hci_quality.lang_bridge.symbol_registry --dump configs/symbol_registry.yaml` 备份

验收:
- 各语言函数节点数大于 0,canonical_name 覆盖率大于等于 80%
- 已知 10 个跨语言调用对的 ExternalEntry 识别准确率大于等于 90%
- Cypher 2-hop 查询可从 Perl qname 跳到 Go、Python 对应 qname

常见坑:
- UDS 路径可能在配置文件而非代码硬编码,首版接受 false negative,后续日志驱动补丁
- Go 的方法 qname 必须带接收者,否则与普通函数歧义
- Java 的包结构需要配置 base-package 识别领域包
- C 的 FFI 符号需要扫 cgo 注释、JNI 映射、Perl XS 文件

### 2.5 Phase 05 MCP-Wiring

目标:三个 MCP stdio server 上线,Claude 会话内可工具调用。

动作:
- 实现 mcp.lightrag_server、mcp.kuzu_server、mcp.td_server,每个不超过 180 行
- 编辑根目录 .mcp.json 注册三者
- 在 Claude 会话中 /mcp 显示三个 connected
- 手工调 lightrag.search、codegraph.query_by_canonical、td.read_normalized 各一次

验收:
- /mcp 输出三个 server 全绿
- 每个工具至少成功调用一次
- stdio 下进程 stdout 无污染,所有日志走 stderr 或文件

常见坑:
- stdio 下任何 stdout print 都会破坏 JSON-RPC
- Windows 路径反斜杠在 .mcp.json 中要双写转义

### 2.6 Phase 06 Subagents-Minimum

目标:上线 triage、rca、patch 三个 subagent,人工走完三步。

动作:
- 按 .claude/agents 模板写 triage.md、rca.md、patch.md
- 每个 subagent 声明工具白名单
- 在 Claude 会话中输入"分析 TD-12345",观察自动路由
- 对 5 条真实 TD 走完整链

验收:
- 5 条真实 TD 中 rca 根因命中率大于等于 2/5
- patch 生成的 diff 语法上可 apply

常见坑:
- subagent 间上下文靠主会话传递
- 提示词须明确职责边界,否则 rca 会直接跳到补丁

### 2.7 Phase 07 Observability

目标:Phoenix 接入全链路,所有 subagent 与 MCP span 完整上报。

动作:
- 启动 Phoenix(scripts/05)
- 在每个 MCP server main 入口调 obs.phoenix_bootstrap.register
- 环境变量 OTEL_EXPORTER_OTLP_ENDPOINT 指向 Phoenix
- 重跑 Phase 06 的 5 条 TD,在 Phoenix UI 查看 trace 树

验收:
- Phoenix UI 显示三个 project:lightrag、codegraph、td-mvp
- 每条 TD 对应 root span 下有完整子 span
- 重启 Phoenix 后历史 trace 仍在

常见坑:
- database is locked 多因 SQLite 放网络盘,强制本地 SSD
- setx 后要重开 shell 才生效

### 2.8 Phase 08 Eval-Golden

目标:从 git log 挖 golden TD,跑通离线评估。

动作:
- 实现 eval.golden_tds_mine,扫 TD-数字,对 commit 用 tree-sitter 抽被改函数 qname,写 configs/golden_tds.yaml
- 实现 eval.eval_join 按语言对分别计算 hit@1、hit@5、MRR 与 cross_lang_acc
- 首轮评估输出到 logs/eval_baseline.json
- 评估过程本身 emit trace 到 Phoenix

验收:
- golden_tds.yaml 条目大于等于 30
- eval_join 可重复执行,幂等
- 首轮 hit@5 大于等于 0.40,否则回 Phase 02 或 04 补数据

常见坑:
- commit message 中 TD 格式不统一,正则要宽容
- 被改函数判定:diff 行号区间交 tree-sitter 函数区间

### 2.9 Phase 09 Webhook-E2E

目标:TD 新单到根因报告回写评论全链路无人干预。

动作:
- 实现 webhook.td_listener FastAPI
- 实现 webhook.comment_writeback 调 TD REST API
- 启动 uvicorn(scripts/06)
- 在 TD 后台把新单 webhook 指向 :8088/td/webhook
- 人工提交测试单

验收:
- 测试单提交到评论落地 P95 小于等于 5 分钟
- 并发 3 条同时提交不冲突
- 重复 webhook 返回 208

常见坑:
- subprocess.Popen 不要 wait
- Windows 下单 worker 并发靠 asyncio 与 Popen 组合

### 2.10 Phase 10 Hardening

目标:补齐 reproduce、regression、security、docs 四个 subagent,72 小时无人值守。

动作:
- 补写四个 subagent 提示词,各做一次人工对齐
- Windows 计划任务:每夜 03 点跑 eval_join 与基线比对,退化 5% 邮件告警;每夜 04 点 VACUUM;每周日跑 golden_tds_mine --incremental
- 连续 72 小时不关机,记录失败任务数、trace 完整度、评论回写成功率

验收:
- 72 小时内处理 TD 大于等于 50 条,回写成功率大于等于 95%
- Python 进程 RSS 增长小于 20%
- 无 database is locked
- eval_join 基线对比退化不超过 5%

---

## 三、跨 Phase 的持续活动

- 周例:回归 eval_join,比对基线,讨论退化原因
- 月例:审查 .claude/agents 下提示词,根据 Phoenix bad trace 精修
- 季度:评估是否触发二阶段演进条件

---

## 四、风险与对策

| 风险 | 触发信号 | 对策 |
| --- | --- | --- |
| bge-m3 嵌入质量在中文 TD 上偏低 | hit@5 长期小于 0.50 | 考虑替换为 bge-large-zh 或堆叠 BM25 |
| Kuzu 在 Windows 上长时间运行内存泄漏 | 进程 RSS 持续增长 | 每夜重启 MCP server 或改用子进程池 |
| Phoenix SQLite 锁 | database is locked 频发 | 迁 PostgreSQL |
| Claude CLI 子进程卡死 | 超时计数上升 | 为 Popen 加 timeout,超时杀进程写失败 span |

---

## 五、参考资料

详见 docs/references.md。
