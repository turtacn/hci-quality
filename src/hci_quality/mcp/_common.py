"""MCP server 公共工具。

stdio 传输下 stdout 必须保持纯净的 JSON-RPC,所有日志走 stderr 或文件。
标准错误契约:返回 {"error": {"code", "message", "hint"}}。
"""
from __future__ import annotations

import functools
import sys
import traceback
from typing import Any, Callable


def err(code: str, message: str, hint: str = "") -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "hint": hint}}


def safe_tool(tool_name: str) -> Callable:
    """装饰 MCP 工具函数,把任何异常转为标准错误契约,而非栈穿透到 JSON-RPC。"""
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except FileNotFoundError as e:
                return err("NOT_FOUND", str(e), "确认路径存在并已初始化")
            except ValueError as e:
                return err("BAD_INPUT", str(e), "检查工具参数类型")
            except Exception as e:
                print(f"[{tool_name}] unhandled: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                return err("INTERNAL", f"{type(e).__name__}: {e}",
                           "查看 logs/mcp_*.log 或 stderr")
        return wrapper
    return deco
