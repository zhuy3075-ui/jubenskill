"""/evolve command router (Req 3).

Parses and dispatches /evolve commands to the appropriate engine methods.
"""
from __future__ import annotations

import shlex
from typing import Dict, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import EvolveEngine


class TriggerRouter:
    """Parse and dispatch /evolve commands."""

    COMMANDS = {
        "status": "显示进化系统状态",
        "learn": "强制从最近输出学习模式",
        "rollback": "列出快照或回滚到指定版本",
        "memory": "查看/管理存储的偏好和模式",
        "health": "运行完整性检查",
        "export": "一键打包分发",
        "log": "查看最近进化日志",
        "reset": "清除所有进化数据（需确认）",
        "help": "显示帮助信息",
    }

    def __init__(self, engine: EvolveEngine):
        self.engine = engine

    def parse(self, command: str) -> Tuple[str, Dict]:
        """Parse '/evolve <cmd> [args]' into (action, params)."""
        command = command.strip()
        if command.startswith("/evolve"):
            command = command[7:].strip()
        if not command:
            return "help", {}
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        action = parts[0].lower()
        params = {}
        if len(parts) > 1:
            params["args"] = parts[1:]
            # Parse key=value pairs
            for p in parts[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = v
        return action, params

    def dispatch(self, action: str, params: Dict) -> str:
        """Route to appropriate engine method."""
        handlers = {
            "status": lambda: self.engine.status(),
            "learn": lambda: self.engine.force_learn(),
            "rollback": lambda: self.engine.rollback(
                params.get("args", [None])[0] if params.get("args") else None),
            "memory": lambda: self.engine.show_memory(),
            "health": lambda: self.engine.health_check(),
            "export": lambda: self.engine.export_package(**params),
            "log": lambda: self.engine.show_log(
                int(params.get("n", "10"))),
            "reset": lambda: self.engine.reset(
                confirm="--confirm" in params.get("args", [])),
            "help": lambda: self.help(),
        }
        handler = handlers.get(action)
        if not handler:
            return f"未知命令: {action}\n\n{self.help()}"
        return handler()

    def help(self) -> str:
        lines = ["📖 进化系统命令列表：", ""]
        for cmd, desc in self.COMMANDS.items():
            lines.append(f"  /evolve {cmd:<12} {desc}")
        return "\n".join(lines)
