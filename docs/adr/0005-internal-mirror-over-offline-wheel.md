# ADR-0005 用内网镜像替代离线 wheel 搬运

状态:Accepted
日期:2026-04-12

## 背景

原方案假设 Windows 10 机器完全断网,采取外网机 pip download、U 盘搬运、内网机 --no-index --find-links 的模式。现运维已配置内网 PyPI、npm、nuget 镜像,可直接 HTTPS 访问。离线 wheel 搬运引入版本漂移、Python 绑定、CUDA wheel 误拉等摩擦。

## 决策

- 依赖安装直接走 pip install 与 npm install 走内网镜像
- pyproject.toml 与 package.json 只声明版本范围
- CPU-only torch 通过内网镜像的二级 index URL 访问
- bge-m3 等 HuggingFace 大模型快照仍走外网拉、内网共享盘一次性同步

## 后果

- 降低 Day-0 部署复杂度,版本升级简单
- Claude CLI 脚本可直接消费,无需处理 U 盘挂载
- 依赖镜像 SLA;镜像宕机则部署中断,运维保证
- 新增依赖须先向镜像管理员申请同步
