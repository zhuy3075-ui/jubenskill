"""Transparent evolution audit logger (Req 15).

Append-only JSONL log with human-readable formatting.
Every evolution action is recorded with before/after state for auditability.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .models import EvolveLogEntry, _now_iso
from .file_ops import AtomicFileOps


class EvolveLogger:
    """Append-only evolution audit log."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_file = log_dir / "evolution.jsonl"
        self.lock_file = log_dir / ".log.lock"
        AtomicFileOps.ensure_dir(log_dir)

    def log(self, event_type: str, details: Dict,
            before: Optional[Dict] = None, after: Optional[Dict] = None,
            operator: str = "system") -> EvolveLogEntry:
        entry = EvolveLogEntry(
            timestamp=_now_iso(),
            event_type=event_type,
            details=details,
            before_state=before,
            after_state=after,
            operator=operator,
        )
        with AtomicFileOps.file_lock(self.lock_file):
            AtomicFileOps.append_jsonl(self.log_file, entry.to_dict())
        return entry

    def get_recent(self, n: int = 20) -> List[Dict]:
        return AtomicFileOps.read_jsonl(self.log_file, tail=n)

    def get_by_type(self, event_type: str, limit: int = 50) -> List[Dict]:
        all_entries = AtomicFileOps.read_jsonl(self.log_file)
        filtered = [e for e in all_entries if e.get("event_type") == event_type]
        return filtered[-limit:]

    def format_human_readable(self, entries: List[Dict]) -> str:
        lines = []
        for e in entries:
            ts = e.get("timestamp", "?")[:19]
            evt = e.get("event_type", "?")
            op = e.get("operator", "system")
            detail_str = ", ".join(
                f"{k}={v}" for k, v in (e.get("details") or {}).items()
            )
            lines.append(f"[{ts}] {evt} ({op}) {detail_str}")
        return "\n".join(lines)
