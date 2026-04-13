# ADR-0001 Windows 离线环境下放弃容器沙箱

状态:Accepted
日期:2026-04-12

## 背景

原方案在 OpenHands 侧通过 runc 或 Kata container 做 subagent 执行沙箱。Windows 10 目标环境既无 Docker Desktop 也无嵌套虚拟化授权,强隔离沙箱不可得。

## 决策

一阶段使用 Git worktree 加专用工作目录加 NTFS ACL 的轻量隔离:
- 每个 TD 任务一个 `repos/<module>/wt-<td_id>-<nonce>` worktree
- 通过 NTFS ACL 限定 Claude Code 子进程只能读写该 worktree
- OpenHands 退化为 Python runtime=local,直接在当前进程空间运行工具

## 后果

- 消除对 Docker 与虚拟化的依赖,Windows 10 即可跑
- 不具备恶意代码隔离能力,依赖 subagent 不越权
- 二阶段补救:引入 Linux 物理机或独立 ESXi 节点时切回 runc runtime,保留 worktree 作为业务隔离层
