# ADR-0004 Claude Code 内置工具兼任"手"

状态:Accepted
日期:2026-04-12

## 背景

原架构中 OpenHands 扮演沙箱执行者,Claude Code 扮演调度大脑。在无 Docker 的 Windows 环境下 OpenHands 退化为 runtime=local 后,其文件读写与 Bash 执行能力与 Claude Code 内置工具高度重叠,保留两层只增加路由复杂度与轨迹噪声。

## 决策

一阶段合并大脑与手到 Claude Code:
- subagent 机制承担角色化与编排
- Claude Code 内置 Read、Write、Bash 工具承担文件与命令执行
- OpenHands 配置保留在 config.toml 中不启用,供二阶段即时恢复

## 后果

- 减少一层进程与框架,调试链路更短
- 单次 MVP 全链路跑通所需依赖更少
- 失去 OpenHands 的 action-observation 循环可视化
- 二阶段补救:Linux 节点引入后启用 OpenHands 接管长程自主任务
