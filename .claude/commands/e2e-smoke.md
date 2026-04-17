---
description: 执行端到端冒烟回归,产出 pass/fail 矩阵
---

请执行 `pwsh -File scripts\99_e2e_smoke.ps1`,捕获输出。

然后:
1. 解析形如 `[Action-X.Y] PASS|FAIL` 的行
2. 汇总成 Markdown 表格:Action、状态、附加信息
3. 对每个 FAIL,按 docs/mvp-bootstrap.md 对应 Action 的"排错指引"给出下一步建议
4. 最后打印 `Summary: N passed, M failed`

不要自行替换脚本逻辑。
