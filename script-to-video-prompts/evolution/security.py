"""Security guard — PII scrubbing, memory decay, injection prevention, learning boundaries.

Covers: Req 13 (decay/compression), Req 14 (privacy), P0-C (learning boundaries),
P1-G (conflict governance).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import MemoryEntry, _now_iso
from .file_ops import AtomicFileOps


class SecurityGuard:
    """Enforces privacy, decay, injection prevention, and learning boundaries."""

    DECAY_RATE = 0.95          # per day
    MIN_DECAY_SCORE = 0.1     # below this → candidate for removal

    # ------------------------------------------------------------------
    # PII patterns (P0-C / Req 14)
    # ------------------------------------------------------------------
    PII_PATTERNS: List[Tuple[re.Pattern, str]] = [
        (re.compile(r"\b1[3-9]\d{9}\b"), "[PHONE]"),
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
        (re.compile(r"\b\d{15}(\d{2}[\dXx])?\b"), "[ID_NUMBER]"),
        (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[CARD]"),
        (re.compile(r"(?:^|\b)(?:sk|pk|ak|token|key|secret|password|passwd|pwd)"
                     r"[-_]?[A-Za-z0-9_-]{16,}", re.I), "[SECRET_KEY]"),
    ]

    # Sensitive file patterns — never learn from these
    SENSITIVE_FILE_PATTERNS = [
        re.compile(r"\.env($|\.)"),
        re.compile(r"credentials", re.I),
        re.compile(r"secret", re.I),
        re.compile(r"\.pem$"),
        re.compile(r"\.key$"),
        re.compile(r"id_rsa"),
    ]

    # Sensitive content patterns — block from memory/log/archive
    SENSITIVE_CONTENT_PATTERNS = [
        re.compile(r"\b(api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*\S+", re.I),
        re.compile(r"\b(password|passwd|pwd)\s*[:=]\s*\S+", re.I),
        re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
        re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"),
    ]

    # Learning whitelist — only these structured fields may enter memory (P0-C)
    LEARNING_WHITELIST = {
        "style", "format", "platform", "genre", "tone", "aspect_ratio",
        "duration", "template", "pattern", "score", "scela_score",
        "shot_size", "camera_movement", "mood", "lighting", "transition",
        "visual_prompt", "optimized_prompt", "quality_score",
        "correction", "reflection", "rule_extracted",
    }

    # Absolute path pattern — never store
    ABS_PATH_PATTERN = re.compile(
        r"[A-Za-z]:\\[^\s\"']+|/(?:home|Users|root|etc|var|tmp)/[^\s\"']+")

    def __init__(self, logger=None):
        self.logger = logger

    # ------------------------------------------------------------------
    # PII scrubbing
    # ------------------------------------------------------------------

    def scrub_pii(self, text: str) -> str:
        """Remove PII from text before storage."""
        result = text
        for pattern, replacement in self.PII_PATTERNS:
            result = pattern.sub(replacement, result)
        # Also scrub absolute paths
        result = self.ABS_PATH_PATTERN.sub("[PATH]", result)
        return result

    def scrub_dict(self, data: Any, depth: int = 0) -> Any:
        """Recursively scrub PII from all string values."""
        if depth > 20:
            return data
        if isinstance(data, str):
            return self.scrub_pii(data)
        if isinstance(data, dict):
            return {k: self.scrub_dict(v, depth + 1) for k, v in data.items()}
        if isinstance(data, list):
            return [self.scrub_dict(v, depth + 1) for v in data]
        return data

    def contains_sensitive(self, text: str) -> List[str]:
        """Check if text contains sensitive content. Returns list of matched pattern names."""
        hits = []
        for pat, repl in self.PII_PATTERNS:
            if pat.search(text):
                hits.append(repl)
        for pat in self.SENSITIVE_CONTENT_PATTERNS:
            if pat.search(text):
                hits.append("[SENSITIVE_CONTENT]")
                break
        if self.ABS_PATH_PATTERN.search(text):
            hits.append("[ABS_PATH]")
        return hits

    def is_sensitive_file(self, filename: str) -> bool:
        """Check if a filename matches sensitive file patterns."""
        return any(p.search(filename) for p in self.SENSITIVE_FILE_PATTERNS)

    # ------------------------------------------------------------------
    # Learning boundary enforcement (P0-C)
    # ------------------------------------------------------------------

    def filter_learnable_fields(self, data: Dict) -> Dict:
        """Only allow whitelisted fields into memory."""
        return {k: v for k, v in data.items() if k in self.LEARNING_WHITELIST}

    def validate_memory_entry(self, entry: Dict) -> Tuple[bool, str]:
        """Validate entry against schema + security rules. Returns (ok, reason)."""
        # Check size
        import json
        serialized = json.dumps(entry, ensure_ascii=False)
        if len(serialized) > 50_000:
            return False, "entry_too_large"
        # Check for sensitive content
        hits = self.contains_sensitive(serialized)
        if hits:
            return False, f"sensitive_content_detected: {', '.join(hits)}"
        # Check required fields
        if "category" not in entry:
            return False, "missing_category"
        if entry.get("category") not in ("preference", "correction", "pattern", "rule"):
            return False, "invalid_category"
        return True, "ok"

    # ------------------------------------------------------------------
    # Memory decay (Req 13)
    # ------------------------------------------------------------------

    def apply_decay(self, entries: List[Dict]) -> Tuple[List[Dict], Dict]:
        """Apply time-based decay. Returns (surviving_entries, stats)."""
        now = datetime.now(timezone.utc)
        kept, removed = [], []
        for e in entries:
            last = e.get("last_accessed", e.get("created_at", ""))
            try:
                last_dt = datetime.fromisoformat(last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                last_dt = now
            days = max(0, (now - last_dt).total_seconds() / 86400)
            new_decay = e.get("decay_score", 1.0) * (self.DECAY_RATE ** days)
            e["decay_score"] = round(new_decay, 4)
            if new_decay >= self.MIN_DECAY_SCORE:
                kept.append(e)
            else:
                removed.append(e)
        stats = {"kept": len(kept), "removed": len(removed)}
        if self.logger and removed:
            self.logger.log("decay", stats)
        return kept, stats

    # ------------------------------------------------------------------
    # Memory compression with traceable summaries (P1-G)
    # ------------------------------------------------------------------

    def compress_memories(self, entries: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Merge similar memories. Returns (compressed, summaries_of_merged).
        Summaries are kept for traceability — never black-box discard."""
        if len(entries) < 2:
            return entries, []
        # Group by category + content hash prefix
        groups: Dict[str, List[Dict]] = {}
        for e in entries:
            key = e.get("category", "") + ":" + str(e.get("content", {}).get("key", ""))
            groups.setdefault(key, []).append(e)

        compressed, summaries = [], []
        for key, group in groups.items():
            if len(group) <= 1:
                compressed.extend(group)
                continue
            # Keep the highest-confidence / most-recent entry
            group.sort(key=lambda x: (
                -x.get("decay_score", 0),
                -x.get("access_count", 0),
            ))
            winner = group[0]
            merged_ids = [g.get("id", "?") for g in group[1:]]
            summary = {
                "action": "compressed",
                "kept_id": winner.get("id"),
                "merged_ids": merged_ids,
                "reason": f"duplicate_key:{key}",
                "timestamp": _now_iso(),
            }
            compressed.append(winner)
            summaries.append(summary)
        if self.logger and summaries:
            self.logger.log("compress", {"merged_count": len(summaries)})
        return compressed, summaries

    # ------------------------------------------------------------------
    # Conflict resolution (P1-G)
    # ------------------------------------------------------------------

    def detect_conflicts(self, entries: List[Dict]) -> List[Dict]:
        """Find contradictory memories (same key, different values)."""
        by_key: Dict[str, List[Dict]] = {}
        for e in entries:
            if e.get("category") == "preference":
                k = e.get("content", {}).get("key", "")
                if k:
                    by_key.setdefault(k, []).append(e)
        conflicts = []
        for k, group in by_key.items():
            if len(group) > 1:
                values = [g.get("content", {}).get("value") for g in group]
                if len(set(str(v) for v in values)) > 1:
                    conflicts.append({
                        "key": k,
                        "entries": group,
                        "values": values,
                        "high_impact": any(
                            g.get("content", {}).get("confidence", 0) > 0.8
                            for g in group
                        ),
                    })
        return conflicts

    def resolve_conflicts_auto(self, entries: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Auto-resolve low-impact conflicts. High-impact ones are flagged for user.
        Returns (resolved_entries, user_required_conflicts)."""
        conflicts = self.detect_conflicts(entries)
        user_required = []
        ids_to_remove = set()
        for c in conflicts:
            if c["high_impact"]:
                user_required.append(c)
                continue
            # Low impact: keep most recent + highest confidence
            group = c["entries"]
            group.sort(key=lambda x: (
                -x.get("content", {}).get("confidence", 0),
                -x.get("access_count", 0),
            ))
            for loser in group[1:]:
                ids_to_remove.add(loser.get("id"))
        resolved = [e for e in entries if e.get("id") not in ids_to_remove]
        if self.logger and ids_to_remove:
            self.logger.log("conflict_resolve", {
                "auto_resolved": len(ids_to_remove),
                "user_required": len(user_required),
            })
        return resolved, user_required

    # ------------------------------------------------------------------
    # Package scan (P0-C: pre-distribution sensitive scan)
    # ------------------------------------------------------------------

    def scan_directory(self, directory: Path) -> List[Dict]:
        """Scan all files in directory for sensitive content. Returns list of findings."""
        findings = []
        for fpath in directory.rglob("*"):
            if not fpath.is_file():
                continue
            if self.is_sensitive_file(fpath.name):
                findings.append({
                    "file": str(fpath),
                    "reason": "sensitive_filename",
                    "blocked": True,
                })
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            hits = self.contains_sensitive(content)
            if hits:
                findings.append({
                    "file": str(fpath),
                    "reason": f"sensitive_content: {', '.join(hits)}",
                    "blocked": True,
                })
        return findings
