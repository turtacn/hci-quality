# MVP 实操清单

本文档面向两类消费者:其一是 Claude CLI,其二是人工实施工程师。每个 Action 都给出命令、正确预期、错误预期、排错指引四段式。

---

## 一、前置假设

- 操作系统 Windows 10 x64
- 用户具备 `D:\opt-hci-quality` 读写权限
- 已安装且版本符合:pwsh 7.6.0、python 3.13.12、dotnet 8.0.125、git 2.9.0、node 22.22.1、npm 10.9.4、poetry 2.6.3、uv 0.11.3、pythonnet
- 内网 PyPI、npm、nuget 镜像已配置
- 运维已发放 ANTHROPIC_BASE_URL 与 ANTHROPIC_API_KEY
- 无 Docker、无嵌套虚拟化

---

## 二、调用约定

```text
cd D:\opt-hci-quality\mvp
claude -p "按 docs/mvp-bootstrap.md 从 Action-1.1 开始顺序执行。每完成一个 Action 做一次验收自检,失败则停止并输出排错建议,不要跳过。"
```

Claude 的自检逻辑:执行命令,比对正确预期中的标志性字符串或退出码,不匹配则走错误预期加排错指引路径。

---

## 三、Phase 1 基础环境与知识层

### 3.1 Action-1.1 创建工作根目录与完整文件骨架

命令:

```text
pwsh -File scripts\create_scaffold.ps1
```

该脚本用 New-Item 建目录,用 New-Item -ItemType File 建所有空文件,逐行打印 `[OK] <path>`。脚本本身由 claude -p 消费时可直接识别。若脚本不存在(尚未 git clone 完整仓库),则按下列等价命令序列由 claude -p 逐条执行:

```text
New-Item -ItemType Directory -Force -Path D:\opt-hci-quality\mvp | Out-Null
cd D:\opt-hci-quality\mvp
$dirs = @(
  "docs/adr","docs/diagrams",
  ".claude/agents",".claude/commands",
  "src/hci_quality/ingest","src/hci_quality/graph","src/hci_quality/lang_bridge",
  "src/hci_quality/mcp","src/hci_quality/webhook","src/hci_quality/eval",
  "src/hci_quality/obs","src/hci_quality/utils",
  "configs","scripts",
  "tests/unit","tests/integration",
  "data/td/raw","data/td/normalized","data/td/tasks","data/templates",
  "models","repos","logs","traces","mcp"
)
$dirs | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null; "[OK dir] $_" }

$files = @(
  "README.md","pyproject.toml",".mcp.json",".gitignore",".env.example","config.toml","LICENSE",
  "docs/architecture.md","docs/roadmap.md","docs/mvp-bootstrap.md","docs/operations.md","docs/references.md",
  "docs/adr/0001-no-docker-windows.md","docs/adr/0002-phoenix-over-langfuse.md",
  "docs/adr/0003-fastapi-over-open-swe.md","docs/adr/0004-claude-code-as-hands.md",
  "docs/adr/0005-internal-mirror-over-offline-wheel.md","docs/adr/0006-multi-language-symbol-registry.md",
  ".claude/agents/triage.md",".claude/agents/reproduce.md",".claude/agents/rca.md",
  ".claude/agents/patch.md",".claude/agents/regression.md",".claude/agents/security.md",".claude/agents/docs.md",
  ".claude/commands/mvp-bootstrap.md",".claude/commands/e2e-smoke.md",
  "src/hci_quality/__init__.py",
  "src/hci_quality/ingest/__init__.py","src/hci_quality/ingest/td_normalize.py",
  "src/hci_quality/ingest/term_dict.py","src/hci_quality/ingest/drain_parser.py",
  "src/hci_quality/ingest/stack_extract.py","src/hci_quality/ingest/lightrag_adapter.py",
  "src/hci_quality/graph/__init__.py","src/hci_quality/graph/tree_sitter_extract.py",
  "src/hci_quality/graph/kuzu_build.py","src/hci_quality/graph/cross_boundary.py",
  "src/hci_quality/lang_bridge/__init__.py","src/hci_quality/lang_bridge/symbol_registry.py",
  "src/hci_quality/lang_bridge/multi_lang_graph.py","src/hci_quality/lang_bridge/multi_lang_log_parser.py",
  "src/hci_quality/lang_bridge/multi_lang_eval.py",
  "src/hci_quality/mcp/__init__.py","src/hci_quality/mcp/_common.py",
  "src/hci_quality/mcp/lightrag_server.py","src/hci_quality/mcp/kuzu_server.py",
  "src/hci_quality/mcp/td_server.py",
  "src/hci_quality/webhook/__init__.py","src/hci_quality/webhook/td_listener.py",
  "src/hci_quality/webhook/comment_writeback.py",
  "src/hci_quality/eval/__init__.py","src/hci_quality/eval/golden_tds_mine.py","src/hci_quality/eval/eval_join.py",
  "src/hci_quality/obs/__init__.py","src/hci_quality/obs/phoenix_bootstrap.py",
  "src/hci_quality/utils/__init__.py","src/hci_quality/utils/logging_setup.py","src/hci_quality/utils/paths.py",
  "configs/customer_terms.yaml","configs/golden_tds.yaml","configs/module_owners.yaml","configs/logging.yaml",
  "scripts/01_bootstrap_env.ps1","scripts/02_verify_env.ps1","scripts/03_ingest_td.ps1",
  "scripts/04_build_codegraph.ps1","scripts/05_start_phoenix.ps1","scripts/06_start_webhook.ps1",
  "scripts/07_run_eval.ps1","scripts/99_e2e_smoke.ps1","scripts/create_scaffold.ps1",
  "tests/__init__.py","tests/unit/__init__.py","tests/unit/test_term_dict.py",
  "tests/unit/test_symbol_registry.py","tests/unit/test_cross_boundary.py",
  "tests/integration/__init__.py","tests/integration/test_mcp_roundtrip.py",
  "tests/integration/test_eval_join.py"
)
$files | ForEach-Object { New-Item -ItemType File -Force -Path $_ | Out-Null; "[OK file] $_" }
```

正确预期:每行以 `[OK dir]` 或 `[OK file]` 开头,总行数等于目录加文件数。最后 `Test-Path D:\opt-hci-quality\mvp\src\hci_quality\lang_bridge\symbol_registry.py` 输出 True。

错误预期:
- Access to the path is denied → 权限问题
- Cannot find drive → D 盘不存在

排错:
- 权限问题以管理员身份重开 pwsh 重试
- D 盘不存在联系运维确认挂载

### 3.2 Action-1.2 校验基础工具链

命令:

```text
pwsh -NoProfile -Command "python --version; node --version; npm --version; git --version; poetry --version; uv --version"
```

正确预期:

```text
Python 3.13.12
v22.22.1
10.9.4
git version 2.9.0
Poetry (version 2.6.3)
uv 0.11.3
```

错误预期:任一工具报 not recognized 或版本不符。

排错:
- 缺失工具回退到运维提供的离线安装包逐一补装
- 版本偏低禁用本系统,不"将就跑"

### 3.3 Action-1.3 创建 Python 虚拟环境

命令:

```text
cd D:\opt-hci-quality\mvp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.prefix)"
```

正确预期:输出 `D:\opt-hci-quality\mvp\.venv`。

错误预期:cannot be loaded because running scripts is disabled。

排错:单次放行执行策略 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`,不修改全局策略。

### 3.4 Action-1.4 安装 Python 依赖

命令:

```text
cd D:\opt-hci-quality\mvp
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev]"
python -c "import lightrag, kuzu, phoenix, fastapi, tree_sitter_languages, drain3, sentence_transformers, mcp; print('OK')"
```

正确预期:最后一行输出 OK,整体 3 至 8 分钟。

错误预期:
- Could not find a version that satisfies → 镜像未同步
- DLL load failed while importing _C → torch 非 CPU 版
- 耗时大于 20 分钟 → 误触发源码编译

排错:
- 镜像缺包找管理员补同步,或 --index-url 指定备用
- torch 显式 `pip install torch --index-url <内网 cpu torch 镜像>`
- 编译问题在 pyproject.toml 中添加 --only-binary=:all: 约束

### 3.5 Action-1.5 安装 Claude Code CLI

命令:

```text
npm config get registry
npm install -g @anthropic-ai/claude-code
claude --version
```

正确预期:npm registry 输出内网镜像 URL,claude 输出 claude-code x.y.z。

错误预期:
- 404 Not Found → 镜像未同步 scoped 包
- claude 无法识别为 cmdlet → npm 全局 bin 未入 PATH

排错:
- 404 联系镜像管理员同步 `@anthropic-ai/claude-code`
- PATH `npm config get prefix` 得到目录,确认加入 PATH 后重开 shell

### 3.6 Action-1.6 配置 LLM 网关环境变量

命令:

```text
setx ANTHROPIC_BASE_URL "https://<内网 LLM 网关>/v1"
setx ANTHROPIC_API_KEY "<内网 key>"
# 重开 shell 后
claude -p "回答:1+1 等于几?只回答数字。"
```

正确预期:输出 2 开头的短回复。

错误预期:
- authentication_error → key 错误或未生效
- connection refused 或 timeout → 网关不可达
- model_not_found → 网关不支持 Claude 模型别名

排错:
- key 错误重开 shell,确认 `$env:ANTHROPIC_API_KEY` 可打印
- 网关不可达用 Invoke-WebRequest 探测
- 模型别名检查网关管理页的 claude-sonnet-4-6 与 claude-opus-4-6 映射

### 3.7 Action-1.7 部署 bge-m3 本地快照

命令:

```text
robocopy \\internal-share\models\bge-m3 D:\opt-hci-quality\mvp\models\bge-m3 /E /NFL /NDL
$env:TRANSFORMERS_OFFLINE="1"
$env:HF_HUB_OFFLINE="1"
python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer(r'D:\opt-hci-quality\mvp\models\bge-m3', device='cpu'); print('embed_dim=', m.get_sentence_embedding_dimension())"
```

正确预期:输出 `embed_dim= 1024`。

错误预期:
- OSError Can't load tokenizer → 快照不全
- 卡住 30 秒以上 → 未走 offline,联网尝试

排错:
- 快照不全:重新 robocopy,或比对两端目录大小
- 联网挂起:环境变量 TRANSFORMERS_OFFLINE=1、HF_HUB_OFFLINE=1,代码 local_files_only=True

### 3.8 Action-1.8 导入 TD 历史样本

命令:

```text
cd D:\opt-hci-quality\mvp
.\.venv\Scripts\Activate.ps1
python -m hci_quality.ingest.td_normalize --input data\td\raw\td_last_3month.jsonl --output data\td\normalized --limit 200
python -m hci_quality.ingest.td_normalize --push-lightrag --limit 200
```

正确预期:
- data\td\normalized 下产生 200 个 TD-*.json
- 控制台打印 `LightRAG upsert done: 200 docs`

错误预期:
- KeyError 'td_id' → 原始 JSONL 字段命名不一致
- ConnectionError → sentence-transformers 尝试联网

排错:
- 字段不一致:编辑 ingest/td_normalize.py 字段映射,或先写 jq 预处理
- 联网尝试同 Action-1.7 排错

### 3.9 Action-1.9 语义检索冒烟

命令:

```text
python -c "from hci_quality.ingest.lightrag_adapter import search; [print(r) for r in search('客户机蓝屏无响应', top_k=5)]"
```

正确预期:打印 5 条 TD,title 与 query 主题相关。

错误预期:返回空或全不相关。

排错:
- 空:lightrag_storage 是否非空,否则 Action-1.8 未写入
- 全不相关:扩充 configs/customer_terms.yaml 同义词,重跑 ingest

Phase 1 验收关卡:以上 9 个 Action 全绿方可进入 Phase 2。

---

## 四、Phase 2 多语言代码侧贯通与 MCP 接线

### 4.1 Action-2.1 准备多语言源码工作树

命令:

```text
git clone --depth 1 <内网 Perl 仓>   D:\opt-hci-quality\mvp\repos\perl-main
git clone --depth 1 <内网 Go 仓>     D:\opt-hci-quality\mvp\repos\go-main
git clone --depth 1 <内网 Python 仓> D:\opt-hci-quality\mvp\repos\py-main
git clone --depth 1 <内网 Java 仓>   D:\opt-hci-quality\mvp\repos\java-main
git clone --depth 1 <内网 C 仓>      D:\opt-hci-quality\mvp\repos\c-main
```

正确预期:五个目录下 .git 可见,各目录源文件计数大于 10。

错误预期:fatal unable to access。

排错:确认 git 走内网 Gerrit 或 GitLab 的 SSH 或 https 凭据。

### 4.2 Action-2.2 构建多语言代码图

命令:

```text
cd D:\opt-hci-quality\mvp
.\.venv\Scripts\Activate.ps1
python -m hci_quality.graph.kuzu_build --source repos\perl-main --language perl
python -m hci_quality.graph.kuzu_build --source repos\go-main  --language go   --incremental
python -m hci_quality.graph.kuzu_build --source repos\py-main  --language python --incremental
python -m hci_quality.graph.kuzu_build --source repos\java-main --language java --incremental
python -m hci_quality.graph.kuzu_build --source repos\c-main   --language c    --incremental
python -m hci_quality.graph.cross_boundary --all-repos --incremental
```

正确预期:
- data\codegraph.kuzu 目录存在且大于 5 MB
- 最后一步打印 `CROSSES_BOUNDARY edges: N`,N 大于 0

错误预期:
- tree_sitter_languages 模块缺失 → 依赖未装
- N 等于 0 → 跨语言边界识别失败

排错:
- `pip show tree-sitter-languages` 确认版本
- N 等于 0 手工 grep 一个已知 UDS、gRPC service name 或 FFI 符号,检查 cross_boundary.py 正则或 AST 访问器

### 4.3 Action-2.3 图查询冒烟

命令:

```text
python -c "from hci_quality.graph.kuzu_build import query; print(query('MATCH (f:function) RETURN count(f) AS n'))"
python -c "from hci_quality.graph.kuzu_build import query; print(query('MATCH (e:external_call) RETURN count(e) AS n'))"
python -c "from hci_quality.lang_bridge.symbol_registry import SymbolRegistry; print(SymbolRegistry.load().stats())"
```

正确预期:
- function 数万级正常,external_call 大于 0
- SymbolRegistry.stats() 返回各语言计数

错误预期:function 数远低于仓库 `sub`、`def`、`func `、`public static` 关键字综合数。

排错:检查各语言 parser 对嵌套命名空间、方法接收者、匿名函数的处理。

### 4.4 Action-2.4 注册 MCP server

命令:

```text
Test-Path D:\opt-hci-quality\mvp\.mcp.json
claude
# Claude 交互会话中:
# /mcp
```

正确预期:/mcp 输出 lightrag、codegraph、td 三个 connected。

错误预期:任一 failed,或全部红。

排错:
- 单个 failed 直接运行 `python -m hci_quality.mcp.<server>` 看 stderr,常见为 stdout 污染 JSON-RPC
- 全失败改 .mcp.json 使用绝对路径 `D:\\opt-hci-quality\\mvp\\.venv\\Scripts\\python.exe`

### 4.5 Action-2.5 subagent 冒烟

命令:

```text
claude -p "分析 TD-<真实 ID>,使用 triage 和 rca 给出初步根因假设。"
```

正确预期:结构化回答含归并模块、相似历史 TD、根因候选 qname,耗时 1 至 5 分钟。

错误预期:跳过 subagent 泛泛作答,或报工具不可用。

排错:
- 未走 subagent 检查 `.claude/agents/*.md` 是否在根目录被识别
- 工具不可用前提是 Action-2.4 /mcp 已全绿

Phase 2 验收关卡:以上 5 个 Action 全绿方可进入 Phase 3。

---

## 五、Phase 3 闭环与触发

### 5.1 Action-3.1 启动 Phoenix

命令(另开 pwsh 窗口):

```text
cd D:\opt-hci-quality\mvp
.\.venv\Scripts\Activate.ps1
$env:PHOENIX_WORKING_DIR="D:\opt-hci-quality\mvp\traces"
python -m phoenix.server.main serve
```

正确预期:打印 Phoenix running at http://localhost:6006,浏览器可打开。

错误预期:
- Address already in use → 端口占用
- database is locked → traces 在网络盘

排错:
- 端口占用 `Get-NetTCPConnection -LocalPort 6006`,改 PHOENIX_PORT
- 网络盘改本地 SSD

### 5.2 Action-3.2 subagent 轨迹上报

命令:

```text
claude -p "分析 TD-<真实 ID>"
# 刷新 http://localhost:6006
```

正确预期:Phoenix UI 出现新 trace,root span 下有 subagent 与 MCP 工具子 span。

错误预期:UI 无新 trace。

排错:
- 各 MCP server 未调 phoenix_bootstrap.register
- OTEL_EXPORTER_OTLP_ENDPOINT 未设,setx 后重开 shell

### 5.3 Action-3.3 golden TD 与首轮评估

命令:

```text
python -m hci_quality.eval.golden_tds_mine --repos repos\perl-main,repos\go-main,repos\py-main,repos\java-main,repos\c-main --output configs\golden_tds.yaml
python -m hci_quality.eval.eval_join --golden configs\golden_tds.yaml --report logs\eval_baseline.json
Get-Content logs\eval_baseline.json
```

正确预期:
- golden_tds.yaml 大于等于 30 条
- eval_baseline.json 含 hit_at_1、hit_at_5、mrr、lang_pair_results
- overall_hit_at_5 大于等于 0.40

错误预期:
- 条目小于 10 → git log 未挖到足够 TD-ID
- hit_at_5 小于 0.40 → 知识层质量不足

排错:
- 挖掘不足:检查 TD-ID 正则,放宽大小写前缀,扩大扫描分支
- 评估低:回 Phase 2 扩充 customer_terms 与 symbol_registry,重跑 ingest

### 5.4 Action-3.4 启动 webhook

命令(另开 pwsh 窗口):

```text
cd D:\opt-hci-quality\mvp
.\.venv\Scripts\Activate.ps1
$env:HCIQ_MAX_PARALLEL="3"
uvicorn hci_quality.webhook.td_listener:app --host 0.0.0.0 --port 8088 --log-level info
```

正确预期:打印 Uvicorn running on 0.0.0.0:8088,下述 curl 返回 accepted:

```text
Invoke-RestMethod -Uri http://localhost:8088/td/webhook -Method POST -ContentType "application/json" -Body (@{td_id="TD-TEST-1"; title="dummy"; description="dummy"} | ConvertTo-Json)
```

错误预期:端口占用或 500。

排错:
- 端口改 18088 并同步更新 TD 管理后台
- 500 看 stderr 栈,常见是 data/td/tasks 目录缺失

### 5.5 Action-3.5 端到端闭环

命令:

```text
Invoke-RestMethod -Uri http://localhost:8088/td/webhook -Method POST -ContentType "application/json" -Body (@{td_id="TD-MVP-E2E-001"; title="HCI 集群 VCLS 心跳丢失"; description="客户机蓝屏,VCLS agent down"} | ConvertTo-Json)
```

正确预期,5 至 10 分钟内全部发生:
- data\td\tasks\TD-MVP-E2E-001-*.txt 落盘
- logs\webhook.log 出现 accepted td_id=TD-MVP-E2E-001
- Phoenix UI 出现对应 trace 含 triage、rca、patch 全链
- TD 系统该单评论区出现结构化根因报告,或至少 logs 下有对应 json

错误预期:按编号定位缺失环节。

排错:
- 1 缺:webhook 未收到,检查 URL 与防火墙
- 2 缺:落盘异常,看 uvicorn stderr
- 3 缺:subagent 未调起或 OTEL 未上报,回 Action-3.2
- 4 缺:TD 回写 API 未打通,看 logs/comment_writeback.log

Phase 3 验收关卡:以上 5 个 Action 全绿 = MVP 全链路通。

---

## 六、附录 一条命令回归全部 Action

```text
pwsh -File scripts\99_e2e_smoke.ps1
```

输出样式:

```text
[Action-1.2] PASS
[Action-1.7] PASS (embed_dim=1024)
[Action-2.3] PASS (functions=12843, external_calls=47)
[Action-3.1] FAIL (Phoenix not reachable at :6006)
Summary: 14 passed, 1 failed
```
