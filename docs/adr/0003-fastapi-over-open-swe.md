# ADR-0003 用 FastAPI webhook 替代 Open SWE

状态:Accepted
日期:2026-04-12

## 背景

Open SWE 基于 LangGraph,离线部署需要 Node、LangGraph 运行时、Slack adapter,MVP 阶段成本过高。

## 决策

一阶段自写约 120 行 Python FastAPI 接收器:
- 唯一职责是接 TD 事件、落盘、subprocess.Popen 启动 claude -p、立即 202
- 反压由 HCIQ_MAX_PARALLEL 加 asyncio Semaphore 实现
- 去重基于 td_id 加 10 分钟窗口内存字典

## 后果

- 开发成本低,离线部署零额外依赖
- 单机单进程,水平扩展需要改造
- 二阶段补救:多路事件源需求出现时接入 Open SWE 或 RabbitMQ 或 Kafka
