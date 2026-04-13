# 日常运维手册

本文档面向运维工程师,覆盖守护、升级、故障定位、容量管理四类操作。

---

## 一、常驻进程清单

| 进程 | 启动方式 | 端口 | 日志 | 存活判定 |
| --- | --- | --- | --- | --- |
| Phoenix | scripts/05_start_phoenix.ps1 | 6006 | 终端输出,可重定向到 logs/phoenix.log | curl http://localhost:6006 返回 200 |
| Webhook | scripts/06_start_webhook.ps1 | 8088 | logs/webhook.log | curl http://localhost:8088/healthz 返回 ok |
| MCP server | 由 Claude 子进程按需拉起,stdio | 无 | logs/mcp_*.log | 由 Claude 会话 /mcp 检查 |

推荐将两个常驻进程注册为 Windows 计划任务的 On-Startup 触发器,用 pwsh 启动。

---

## 二、每日例行

```text
03:00  python -m hci_quality.eval.eval_join --compare-baseline   回归评估
04:00  sqlite3 traces/phoenix.sqlite "VACUUM;"                    SQLite 压缩
05:00  pwsh scripts/99_e2e_smoke.ps1                              冒烟回归
周日 06:00  python -m hci_quality.eval.golden_tds_mine --incremental  挖掘新 golden
```

所有任务失败写 logs/cron.log 并发邮件到 module_owners.yaml 列出的责任人。

---

## 三、故障定位矩阵

| 现象 | 第一嫌疑 | 核查步骤 |
| --- | --- | --- |
| Claude 子进程卡死 | 内网 LLM 网关超时 | `Invoke-WebRequest $env:ANTHROPIC_BASE_URL/models`,看响应 |
| database is locked | SQLite 并发锁 | 确认 traces 在本地 SSD,VACUUM,降低并发 |
| hit@5 一夜之间掉 10% | golden TD 被污染 | `git diff HEAD~1 configs/golden_tds.yaml` |
| MCP 工具 hint 频繁 network | Kuzu 索引损坏 | `python -m hci_quality.graph.kuzu_build --repair` |
| webhook 积压 | HCIQ_MAX_PARALLEL 过低或 Claude 慢 | 观察 logs/webhook.log 队列长度,临时提高并发上限 |

---

## 四、升级流程

- 依赖升级:修改 pyproject.toml 版本范围,`uv pip compile` 更新锁,`uv pip sync`,跑 pytest,跑 99_e2e_smoke
- 模型切换:替换 models/bge-m3 前先在 A/B 分支跑 eval_join 对比 hit@5,退化超过 3% 回滚
- subagent 提示词升级:先改 .claude/agents/*.md,跑 eval_join,通过后 merge

---

## 五、容量边界

| 资源 | 一阶段上限 | 超过时的动作 |
| --- | --- | --- |
| LightRAG 向量数 | 50 万 | 迁 Milvus Standalone,见 ADR 二阶段补救 |
| Kuzu 图规模 | 500 万边 | 评估 Kuzu 持续性能或迁 Neo4j |
| Phoenix SQLite | 20 GB | 迁 PostgreSQL |
| 并发 Claude 子进程 | 3 | 迁 Prefect 或 Temporal |
