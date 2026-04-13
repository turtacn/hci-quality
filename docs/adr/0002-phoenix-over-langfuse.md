# ADR-0002 用 Arize Phoenix 替代 Langfuse

状态:Accepted
日期:2026-04-12

## 背景

Langfuse 的官方部署方式是 docker-compose,依赖 Postgres、ClickHouse、Redis、S3 四个服务。Windows 10 离线环境无 Docker,手撸四个依赖成本过高。

## 决策

一阶段采用 Arize Phoenix:
- 纯 pip 安装,默认 SQLite 后端
- `python -m phoenix.server.main serve` 一条命令拉起
- OTLP 协议兼容,subagent 与 MCP server 几乎无改造

## 后果

- 零容器依赖,30 秒拉起观测 UI
- SQLite 在高并发下可能 database is locked,需每夜 VACUUM
- 二阶段补救:并发 subagent 大于 10 或锁频发时迁 PostgreSQL,或顺势升级到 Langfuse
