"""Cross-environment detection & degradation (Req 10, P1-E).

Probe matrix detects runtime environment via env vars, directory signatures,
and capability APIs. Falls back to safe degraded mode on detection failure.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from .models import Environment


class EnvDetector:
    """Detect runtime environment and adapt behavior."""

    # Probe matrix: env_var → runtime name
    ENV_PROBES = [
        {"env_var": "CLAUDE_CODE", "runtime": "claude_code", "priority": 10},
        {"env_var": "CLAUDE_CODE_VERSION", "runtime": "claude_code", "priority": 10},
        {"env_var": "OPENHANDS_WORKSPACE", "runtime": "openhands", "priority": 9},
        {"env_var": "OPEN_HANDS", "runtime": "openhands", "priority": 9},
        {"env_var": "COZE_SKILL_ID", "runtime": "coze", "priority": 8},
        {"env_var": "COZE_BOT_ID", "runtime": "coze", "priority": 8},
    ]

    # Directory signature probes
    DIR_PROBES = [
        {"marker": ".claude", "runtime": "claude_code", "priority": 5},
        {"marker": ".openhands", "runtime": "openhands", "priority": 5},
    ]

    # Capability definitions per runtime
    CAPABILITIES = {
        "claude_code": ["file_read", "file_write", "shell", "network", "git"],
        "openhands": ["file_read", "file_write", "shell", "network"],
        "coze": ["file_read", "file_write", "network"],
        "standalone": ["file_read", "file_write", "shell", "network", "git"],
        "unknown": ["file_read"],  # most conservative
    }

    @classmethod
    def detect(cls, project_root: Path = None) -> Environment:
        """Detect current runtime environment. Returns Environment with
        degraded=True if detection is uncertain."""
        try:
            return cls._do_detect(project_root)
        except Exception:
            # Detection failure → safe degraded mode (P1-E)
            return Environment(
                runtime="unknown",
                os_name=platform.system().lower(),
                python_version=platform.python_version(),
                has_git=False,
                has_network=False,
                project_root=str(project_root or "."),
                capabilities=cls.CAPABILITIES["unknown"],
                degraded=True,
            )

    @classmethod
    def _do_detect(cls, project_root: Path = None) -> Environment:
        # Phase 1: Environment variable probes (highest priority)
        matches: Dict[str, int] = {}
        for probe in cls.ENV_PROBES:
            if os.environ.get(probe["env_var"]):
                rt = probe["runtime"]
                matches[rt] = max(matches.get(rt, 0), probe["priority"])

        # Phase 2: Directory signature probes
        root = project_root or Path.cwd()
        for probe in cls.DIR_PROBES:
            if (root / probe["marker"]).exists() or (root.parent / probe["marker"]).exists():
                rt = probe["runtime"]
                matches[rt] = max(matches.get(rt, 0), probe["priority"])

        # Resolve conflicts: highest priority wins
        if matches:
            runtime = max(matches, key=matches.get)
        else:
            runtime = "standalone"

        # Capability detection
        has_git = shutil.which("git") is not None
        has_network = cls._check_network()

        capabilities = list(cls.CAPABILITIES.get(runtime, cls.CAPABILITIES["unknown"]))
        if not has_git and "git" in capabilities:
            capabilities.remove("git")
        if not has_network and "network" in capabilities:
            capabilities.remove("network")

        return Environment(
            runtime=runtime,
            os_name=platform.system().lower(),
            python_version=platform.python_version(),
            has_git=has_git,
            has_network=has_network,
            project_root=str(root),
            capabilities=capabilities,
            degraded=False,
        )

    @staticmethod
    def _check_network() -> bool:
        """Quick network connectivity check."""
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2).close()
            return True
        except (OSError, socket.timeout):
            return False

    @staticmethod
    def adapt_behavior(env: Environment) -> Dict:
        """Return behavior adaptations for detected environment."""
        adaptations = {
            "can_write_files": "file_write" in env.capabilities,
            "can_use_shell": "shell" in env.capabilities,
            "can_use_git": env.has_git and "git" in env.capabilities,
            "can_use_network": env.has_network and "network" in env.capabilities,
            "safe_mode": env.degraded,
            "max_file_size_mb": 10 if not env.degraded else 1,
        }
        return adaptations
