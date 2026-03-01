"""Atomic file operations with locking for the evolution system.

Every JSON mutation goes through write→.tmp→os.replace() to prevent
corruption on crash.  A global file lock prevents concurrent writes.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator

# Cross-platform file locking
if sys.platform == "win32":
    import msvcrt

    def _lock(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(f):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _lock(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    def _unlock(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class AtomicFileOps:
    """Low-level safe I/O primitives used by all other evolution modules."""

    # ------------------------------------------------------------------
    # File locking (P0-B: global file lock to prevent concurrent writes)
    # ------------------------------------------------------------------

    @staticmethod
    @contextmanager
    def file_lock(lock_path: Path, timeout: float = 10.0) -> Generator:
        """Acquire an exclusive file lock.  Cross-platform (Windows + POSIX)."""
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = open(lock_path, "w")
        try:
            _lock(lock_file)
            yield lock_file
        finally:
            _unlock(lock_file)
            lock_file.close()

    # ------------------------------------------------------------------
    # JSON read / write
    # ------------------------------------------------------------------

    @staticmethod
    def read_json(path: Path) -> Any:
        """Read JSON with encoding fallback: utf-8 → utf-8-sig → gb18030."""
        if not path.exists():
            return None
        raw = path.read_bytes()
        for enc in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return json.loads(raw.decode(enc))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return None  # truly unreadable

    @staticmethod
    def write_json(path: Path, data: Any) -> None:
        """Atomic write: serialise → write to .tmp → os.replace()."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        closed = False
        try:
            os.write(fd, payload)
            os.close(fd)
            closed = True
            os.replace(tmp, str(path))
        except BaseException:
            if not closed:
                os.close(fd)
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    @staticmethod
    def append_jsonl(path: Path, entry: Dict) -> None:
        """Append a single JSON line to a JSONL file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    @staticmethod
    def read_jsonl(path: Path, tail: int = 0) -> list:
        """Read JSONL file.  If *tail* > 0, return only last N entries."""
        if not path.exists():
            return []
        lines = []
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    lines.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
        if tail > 0:
            lines = lines[-tail:]
        return lines

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------

    @staticmethod
    def file_hash(path: Path) -> str:
        """SHA-256 hex digest of file contents."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def data_hash(data: Any) -> str:
        """SHA-256 of JSON-serialised data (deterministic)."""
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def ensure_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
