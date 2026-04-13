# 1. 创建所有目录结构 (包含嵌套的子目录)
mkdir -p docs \
    venv \
    models/bge-m3 \
    data/td/raw \
    data/td/normalized \
    data/lightrag \
    data/kuzu \
    data/tasks \
    repos/demo \
    repos/codebase \
    src/ingest \
    mcp \
    webhook \
    scripts \
    .claude/agents \
    tests \
    traces \
    logs

# 2. 创建根目录文件
touch README.md pyproject.toml .env.example CLAUDE.md .mcp.json

# 3. 创建 docs 目录文件
touch docs/architecture.md docs/deployment.md docs/mcp-api-reference.md docs/phases.md

# 4. 创建 data 目录的独立文件
touch data/golden_tds.yaml

# 5. 创建 src 及其子目录文件
touch src/__init__.py src/config.py src/lightrag_wrapper.py src/kuzu_graph.py src/customer_terms.yaml src/eval_join.py
touch src/ingest/__init__.py src/ingest/td_importer.py src/ingest/drain3_template.py src/ingest/code_parser.py

# 6. 创建 mcp 目录文件
touch mcp/__init__.py mcp/lightrag_server.py mcp/kuzu_server.py mcp/td_server.py mcp/config.py

# 7. 创建 webhook 目录文件
touch webhook/td_listener.py

# 8. 创建 scripts 目录文件
touch scripts/step01_env_check.ps1 \
      scripts/step02_install_deps.ps1 \
      scripts/step03_build_graph.ps1 \
      scripts/step04_ingest_td.ps1 \
      scripts/step05_start_services.ps1 \
      scripts/step06_eval_baseline.ps1 \
      scripts/step07_endtoend_demo.ps1 \
      scripts/golden_td_miner.py

# 9. 创建 .claude 智能体配置文件
touch .claude/agents/triage.md \
      .claude/agents/reproduce.md \
      .claude/agents/rca.md \
      .claude/agents/patch.md \
      .claude/agents/regression.md \
      .claude/agents/security.md \
      .claude/agents/docs.md

# 10. 创建 tests 测试文件
touch tests/test_lightrag.py tests/test_kuzu.py tests/test_mcp_tools.py tests/test_eval.py

echo "✅ 项目骨架创建完成！"