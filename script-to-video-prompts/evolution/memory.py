"""Persistent memory store (Req 1, 4, 6, P1-G).

Manages user preferences, correction records, prompt patterns, and archives.
All writes are atomic and go through SecurityGuard validation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    MemoryEntry, UserPreference, CorrectionRecord, PromptPattern,
    _now_iso, _uuid,
)
from .file_ops import AtomicFileOps
from .logger import EvolveLogger
from .security import SecurityGuard


class MemoryStore:
    """CRUD for all persistent evolution data."""

    MAX_ENTRIES_PER_CATEGORY = 1000

    def __init__(self, memory_dir: Path, logger: EvolveLogger,
                 security: SecurityGuard):
        self.memory_dir = memory_dir
        self.logger = logger
        self.security = security
        self.lock_file = memory_dir / ".memory.lock"
        AtomicFileOps.ensure_dir(memory_dir)
        self._prefs_file = memory_dir / "preferences.json"
        self._corrections_file = memory_dir / "corrections.json"
        self._patterns_file = memory_dir / "patterns.json"
        self._archive_dir = memory_dir.parent / "archive"
        AtomicFileOps.ensure_dir(self._archive_dir)

    # ------------------------------------------------------------------
    # Preferences (Req 1)
    # ------------------------------------------------------------------

    def get_preference(self, key: str) -> Optional[Dict]:
        prefs = self._load_prefs()
        for p in prefs:
            if p.get("content", {}).get("key") == key:
                p["last_accessed"] = _now_iso()
                p["access_count"] = p.get("access_count", 0) + 1
                self._save_prefs(prefs)
                return p
        return None

    def set_preference(self, key: str, value: Any,
                       confidence: float = 1.0) -> Tuple[bool, str]:
        """Set a preference. Returns (ok, reason)."""
        entry_data = {
            "id": _uuid(), "category": "preference",
            "content": {"key": key, "value": value, "confidence": confidence},
            "created_at": _now_iso(), "last_accessed": _now_iso(),
            "access_count": 0, "decay_score": 1.0, "source": "user",
        }
        ok, reason = self.security.validate_memory_entry(entry_data)
        if not ok:
            self.logger.log("memory_rejected", {
                "action": "set_preference", "key": key, "reason": reason,
            })
            return False, reason

        with AtomicFileOps.file_lock(self.lock_file):
            prefs = self._load_prefs()
            # Check for conflict
            existing = [p for p in prefs if p.get("content", {}).get("key") == key]
            if existing:
                old = existing[0]
                old_val = old.get("content", {}).get("value")
                if old_val != value:
                    old_conf = old.get("content", {}).get("confidence", 0)
                    if old_conf > 0.8 and confidence < old_conf:
                        # High-impact conflict — flag for user
                        return False, "high_impact_conflict"
                # Update existing
                old["content"]["value"] = value
                old["content"]["confidence"] = max(
                    old.get("content", {}).get("confidence", 0), confidence)
                old["last_accessed"] = _now_iso()
                old["access_count"] = old.get("access_count", 0) + 1
            else:
                prefs.append(entry_data)
            self._save_prefs(prefs)
        self.logger.log("preference_set", {"key": key})
        return True, "ok"

    def get_all_preferences(self) -> List[Dict]:
        return self._load_prefs()

    # ------------------------------------------------------------------
    # Corrections (Req 5)
    # ------------------------------------------------------------------

    def add_correction(self, record: CorrectionRecord) -> Tuple[bool, str]:
        entry_data = {
            "id": record.id, "category": "correction",
            "content": record.to_dict(),
            "created_at": _now_iso(), "last_accessed": _now_iso(),
            "access_count": 0, "decay_score": 1.0, "source": "reflection",
        }
        # Scrub PII from correction content
        entry_data = self.security.scrub_dict(entry_data)
        ok, reason = self.security.validate_memory_entry(entry_data)
        if not ok:
            return False, reason
        with AtomicFileOps.file_lock(self.lock_file):
            corrections = self._load_corrections()
            corrections.append(entry_data)
            self._evict_if_full(corrections, "correction")
            self._save_corrections(corrections)
        self.logger.log("correction_added", {"id": record.id})
        return True, "ok"

    def get_corrections(self, limit: int = 20) -> List[Dict]:
        return self._load_corrections()[-limit:]

    def find_relevant_corrections(self, context: str) -> List[Dict]:
        """Find corrections whose rule_extracted matches context keywords."""
        corrections = self._load_corrections()
        relevant = []
        ctx_lower = context.lower()
        for c in corrections:
            rule = c.get("content", {}).get("rule_extracted", "").lower()
            if rule and any(word in ctx_lower for word in rule.split()[:5]):
                relevant.append(c)
        return relevant[-10:]

    # ------------------------------------------------------------------
    # Patterns (Req 4)
    # ------------------------------------------------------------------

    def add_pattern(self, pattern: PromptPattern) -> Tuple[bool, str]:
        entry_data = {
            "id": pattern.pattern_id, "category": "pattern",
            "content": pattern.to_dict(),
            "created_at": _now_iso(), "last_accessed": _now_iso(),
            "access_count": 0, "decay_score": 1.0, "source": "auto",
        }
        entry_data = self.security.scrub_dict(entry_data)
        ok, reason = self.security.validate_memory_entry(entry_data)
        if not ok:
            return False, reason
        with AtomicFileOps.file_lock(self.lock_file):
            patterns = self._load_patterns()
            patterns.append(entry_data)
            self._evict_if_full(patterns, "pattern")
            self._save_patterns(patterns)
        self.logger.log("pattern_added", {"id": pattern.pattern_id})
        return True, "ok"

    def get_top_patterns(self, genre: str = None,
                         limit: int = 10) -> List[Dict]:
        patterns = self._load_patterns()
        if genre:
            patterns = [p for p in patterns
                        if p.get("content", {}).get("genre") == genre]
        patterns.sort(
            key=lambda x: x.get("content", {}).get("score", 0), reverse=True)
        return patterns[:limit]

    # ------------------------------------------------------------------
    # Archive (Req 6)
    # ------------------------------------------------------------------

    def archive_output(self, output: Dict, score: float,
                       title: str) -> Optional[str]:
        """Archive high-quality output. Returns archive ID or None."""
        if score < 0.85:
            return None
        aid = _uuid()
        archive_data = self.security.scrub_dict({
            "id": aid, "score": score, "title": title,
            "output": output, "archived_at": _now_iso(),
        })
        # Validate no sensitive content
        import json
        serialized = json.dumps(archive_data, ensure_ascii=False)
        hits = self.security.contains_sensitive(serialized)
        if hits:
            self.logger.log("archive_blocked", {
                "title": title, "reason": f"sensitive: {hits}",
            })
            return None
        fpath = self._archive_dir / f"{aid}_{title[:30]}.json"
        AtomicFileOps.write_json(fpath, archive_data)
        self.logger.log("archive_created", {"id": aid, "score": score})
        return aid

    def get_archived_examples(self, limit: int = 5) -> List[Dict]:
        archives = []
        for f in sorted(self._archive_dir.glob("*.json"), reverse=True):
            data = AtomicFileOps.read_json(f)
            if data:
                archives.append(data)
            if len(archives) >= limit:
                break
        return archives

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        return {
            "preferences": len(self._load_prefs()),
            "corrections": len(self._load_corrections()),
            "patterns": len(self._load_patterns()),
            "archives": len(list(self._archive_dir.glob("*.json"))),
        }

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def run_maintenance(self) -> Dict:
        """Run decay + compression + conflict resolution."""
        stats = {}
        with AtomicFileOps.file_lock(self.lock_file):
            for name, load_fn, save_fn in [
                ("preferences", self._load_prefs, self._save_prefs),
                ("corrections", self._load_corrections, self._save_corrections),
                ("patterns", self._load_patterns, self._save_patterns),
            ]:
                entries = load_fn()
                entries, decay_stats = self.security.apply_decay(entries)
                entries, summaries = self.security.compress_memories(entries)
                if name == "preferences":
                    entries, user_conflicts = self.security.resolve_conflicts_auto(entries)
                    stats[f"{name}_user_conflicts"] = len(user_conflicts)
                save_fn(entries)
                stats[f"{name}_kept"] = len(entries)
                stats[f"{name}_decayed"] = decay_stats.get("removed", 0)
                stats[f"{name}_compressed"] = len(summaries)
        self.logger.log("maintenance", stats)
        return stats

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _load_prefs(self) -> List[Dict]:
        return AtomicFileOps.read_json(self._prefs_file) or []

    def _save_prefs(self, data: List[Dict]) -> None:
        AtomicFileOps.write_json(self._prefs_file, data)

    def _load_corrections(self) -> List[Dict]:
        return AtomicFileOps.read_json(self._corrections_file) or []

    def _save_corrections(self, data: List[Dict]) -> None:
        AtomicFileOps.write_json(self._corrections_file, data)

    def _load_patterns(self) -> List[Dict]:
        return AtomicFileOps.read_json(self._patterns_file) or []

    def _save_patterns(self, data: List[Dict]) -> None:
        AtomicFileOps.write_json(self._patterns_file, data)

    def _evict_if_full(self, entries: List[Dict], category: str) -> None:
        if len(entries) > self.MAX_ENTRIES_PER_CATEGORY:
            entries.sort(key=lambda x: x.get("last_accessed", ""))
            excess = len(entries) - self.MAX_ENTRIES_PER_CATEGORY
            del entries[:excess]
            self.logger.log("eviction", {
                "category": category, "evicted": excess,
            })
