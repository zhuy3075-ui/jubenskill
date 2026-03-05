"""Micro-difference scorer with pairwise comparison and ELO updates."""
from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

from .file_ops import AtomicFileOps
from .models import _now_iso, _uuid


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class MicroScorer:
    """Track fine-grained quality changes via pairwise comparisons."""

    DIMENSIONS = [
        "scela_coverage",
        "consistency",
        "compliance",
        "shot_diversity",
        "mood_rhythm",
        "visual_precision",
        "platform_fit",
    ]
    DEFAULT_ELO = 1500.0
    K_AUTO = 16.0
    K_USER = 32.0
    K_HEURISTIC = 12.0
    MICRO_THRESHOLD = 0.02
    MARGIN_CLIP = 0.05
    SHADOW_ROUNDS = 10
    OBSERVE_ROUNDS = 30

    def __init__(self, scores_dir: Path, logger=None, security=None):
        self.scores_dir = scores_dir
        self.logger = logger
        self.security = security
        AtomicFileOps.ensure_dir(scores_dir)
        self._state_file = scores_dir / "state.json"
        self._elo_file = scores_dir / "elo_ratings.json"
        self._records_file = scores_dir / "records.jsonl"
        self._comparisons_file = scores_dir / "comparisons.jsonl"
        self._lock_file = scores_dir / ".scores.lock"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_generation(
        self,
        storyboard: Dict,
        quality_report,
        genre: str = "",
        platform: str = "",
        duration_seconds: float = 0.0,
        archive_id: str = "",
    ) -> Dict:
        """Record current generation and run compare/ELO by phase."""
        state = self._load_state()
        state["generation_count"] += 1
        state["phase"] = self._phase_for_count(state["generation_count"])
        elo = self._load_elo()

        dims = dict(getattr(quality_report, "dimension_scores", {}) or {})
        if not dims:
            dims = {
                "scela_coverage": float(getattr(quality_report, "scela_score", 0.0)),
                "consistency": float(getattr(quality_report, "consistency_score", 0.0)),
                "compliance": 1.0 if getattr(quality_report, "compliance_passed", True) else 0.0,
            }
            for d in self.DIMENSIONS:
                dims.setdefault(d, float(getattr(quality_report, "overall_score", 0.0)))

        record = {
            "record_id": _uuid(),
            "timestamp": _now_iso(),
            "phase": state["phase"],
            "genre": genre or "",
            "platform": (platform or "").lower(),
            "duration_bucket": self._duration_bucket(duration_seconds),
            "overall_score": float(getattr(quality_report, "overall_score", 0.0)),
            "dimension_scores": {k: float(v) for k, v in dims.items() if k in self.DIMENSIONS},
            "archive_id": archive_id or "",
            "title": (storyboard or {}).get("title", ""),
        }
        self._append_record(record)

        summary = {
            "phase": state["phase"],
            "record_id": record["record_id"],
            "generation_count": state["generation_count"],
            "compared": False,
            "opponent_record_id": "",
            "wins": 0,
            "losses": 0,
            "ties": 0,
        }

        if state["phase"] == "shadow":
            self._save_state(state)
            return summary

        opponent = self._pick_opponent(record)
        if not opponent:
            self._save_state(state)
            return summary

        comparisons = self._compare_records(record, opponent)
        if not comparisons:
            self._save_state(state)
            return summary

        for comp in comparisons:
            self._append_comparison(comp)
        state["comparisons_count"] += len(comparisons)

        elo = self._update_elo(elo, comparisons)
        self._save_elo(elo)
        self._save_state(state)

        summary["compared"] = True
        summary["opponent_record_id"] = opponent["record_id"]
        summary["wins"] = sum(1 for c in comparisons if c["winner"] == "new")
        summary["losses"] = sum(1 for c in comparisons if c["winner"] == "opponent")
        summary["ties"] = sum(1 for c in comparisons if c["winner"] == "tie")

        if self.logger:
            self.logger.log("score_compare", summary)
        return summary

    def get_state(self) -> Dict:
        return self._load_state()

    def get_elo_ratings(self) -> Dict[str, float]:
        elo = self._load_elo()
        return {k: round(float(v), 3) for k, v in elo.items()}

    def get_recent_comparisons(self, limit: int = 200) -> List[Dict]:
        return AtomicFileOps.read_jsonl(self._comparisons_file, tail=limit)

    def reset(self) -> Dict:
        for f in [
            self._state_file,
            self._elo_file,
            self._records_file,
            self._comparisons_file,
        ]:
            if f.exists():
                f.unlink()
        self._save_state({"generation_count": 0, "comparisons_count": 0, "phase": "shadow"})
        self._save_elo({d: self.DEFAULT_ELO for d in self.DIMENSIONS})
        return {"ok": True}

    def calibrate(self) -> Dict:
        """Rebuild ELO from persisted comparisons."""
        comps = AtomicFileOps.read_jsonl(self._comparisons_file)
        elo = {d: self.DEFAULT_ELO for d in self.DIMENSIONS}
        elo = self._update_elo(elo, comps)
        self._save_elo(elo)
        return {"ok": True, "comparisons": len(comps)}

    def compare_with_archive_id(self, archive_id: str) -> Dict:
        """Manual compare: latest record vs record tied to given archive_id."""
        if not archive_id:
            return {"ok": False, "reason": "archive_id_required"}
        records = AtomicFileOps.read_jsonl(self._records_file)
        if len(records) < 2:
            return {"ok": False, "reason": "not_enough_records"}
        target = None
        for r in reversed(records):
            if r.get("archive_id") == archive_id:
                target = r
                break
        if not target:
            return {"ok": False, "reason": "archive_id_not_found"}
        challenger = records[-1]
        if challenger.get("record_id") == target.get("record_id"):
            if len(records) < 2:
                return {"ok": False, "reason": "not_enough_records"}
            challenger = records[-2]
        comps = self._compare_records(challenger, target, source="heuristic")
        if not comps:
            return {"ok": False, "reason": "compare_failed"}
        elo = self._load_elo()
        elo = self._update_elo(elo, comps)
        self._save_elo(elo)
        for c in comps:
            self._append_comparison(c)
        return {
            "ok": True,
            "challenger": challenger.get("record_id", ""),
            "opponent": target.get("record_id", ""),
            "wins": sum(1 for c in comps if c["winner"] == "new"),
            "losses": sum(1 for c in comps if c["winner"] == "opponent"),
            "ties": sum(1 for c in comps if c["winner"] == "tie"),
        }

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _phase_for_count(self, n: int) -> str:
        if n <= self.SHADOW_ROUNDS:
            return "shadow"
        if n <= self.OBSERVE_ROUNDS:
            return "observe"
        return "active"

    def _duration_bucket(self, duration: float) -> str:
        if duration <= 0:
            return "unknown"
        if duration <= 5:
            return "short_4_5"
        if duration <= 10:
            return "short_6_10"
        if duration <= 15:
            return "short_11_15"
        return "long"

    def _pick_opponent(self, record: Dict) -> Optional[Dict]:
        records = AtomicFileOps.read_jsonl(self._records_file)
        if len(records) < 2:
            return None

        curr_id = record.get("record_id")
        candidates = [r for r in records if r.get("record_id") != curr_id]
        # Strict matching first.
        strict = [
            r
            for r in candidates
            if r.get("genre", "") == record.get("genre", "")
            and r.get("platform", "") == record.get("platform", "")
            and r.get("duration_bucket", "") == record.get("duration_bucket", "")
        ]
        pool = strict if strict else [
            r for r in candidates if r.get("platform", "") == record.get("platform", "")
        ]
        if not pool:
            pool = candidates
        # Top-K by score + recency.
        pool.sort(
            key=lambda r: (float(r.get("overall_score", 0.0)), str(r.get("timestamp", ""))),
            reverse=True,
        )
        top_k = pool[:5]
        if not top_k:
            return None
        # Stable random with deterministic seed from record id to avoid bias.
        seed = int(str(record.get("record_id", "0"))[:6], 16) if record.get("record_id") else 0
        rng = random.Random(seed)
        return rng.choice(top_k)

    def _compare_records(self, new_record: Dict, opp_record: Dict, source: str = "auto") -> List[Dict]:
        comparisons = []
        new_dims = new_record.get("dimension_scores", {})
        opp_dims = opp_record.get("dimension_scores", {})
        if not new_dims or not opp_dims:
            return comparisons
        for dim in self.DIMENSIONS:
            if dim not in new_dims or dim not in opp_dims:
                continue
            n = float(new_dims[dim])
            o = float(opp_dims[dim])
            margin = _clip(n - o, -self.MARGIN_CLIP, self.MARGIN_CLIP)
            winner = "tie"
            if abs(margin) >= self.MICRO_THRESHOLD:
                winner = "new" if margin > 0 else "opponent"
            comparisons.append(
                {
                    "id": _uuid(),
                    "timestamp": _now_iso(),
                    "dimension": dim,
                    "new_record_id": new_record.get("record_id", ""),
                    "opponent_record_id": opp_record.get("record_id", ""),
                    "new_score": round(n, 4),
                    "opponent_score": round(o, 4),
                    "winner": winner,
                    "margin": round(margin, 4),
                    "source": source,
                    "phase": new_record.get("phase", ""),
                }
            )
        return comparisons

    def _update_elo(self, elo: Dict[str, float], comparisons: List[Dict]) -> Dict[str, float]:
        for c in comparisons:
            dim = c.get("dimension")
            if dim not in self.DIMENSIONS:
                continue
            rn = float(elo.get(dim, self.DEFAULT_ELO))
            ro = self.DEFAULT_ELO  # opponent baseline proxy for stability
            expected = 1.0 / (1.0 + 10.0 ** ((ro - rn) / 400.0))
            winner = c.get("winner")
            if winner == "new":
                score = 1.0
            elif winner == "opponent":
                score = 0.0
            else:
                score = 0.5
            source = c.get("source", "auto")
            if source == "user":
                k = self.K_USER
            elif source == "heuristic":
                k = self.K_HEURISTIC
            else:
                k = self.K_AUTO
            rn2 = rn + k * (score - expected)
            elo[dim] = _clip(rn2, 1200.0, 1800.0)
        return elo

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _load_state(self) -> Dict:
        data = AtomicFileOps.read_json(self._state_file) or {}
        return {
            "generation_count": int(data.get("generation_count", 0)),
            "comparisons_count": int(data.get("comparisons_count", 0)),
            "phase": str(data.get("phase", "shadow")),
        }

    def _save_state(self, state: Dict) -> None:
        with AtomicFileOps.file_lock(self._lock_file):
            AtomicFileOps.write_json(self._state_file, state)

    def _load_elo(self) -> Dict[str, float]:
        data = AtomicFileOps.read_json(self._elo_file) or {}
        elo = {}
        for d in self.DIMENSIONS:
            elo[d] = float(data.get(d, self.DEFAULT_ELO))
        return elo

    def _save_elo(self, elo: Dict[str, float]) -> None:
        with AtomicFileOps.file_lock(self._lock_file):
            AtomicFileOps.write_json(self._elo_file, elo)

    def _append_record(self, record: Dict) -> None:
        payload = record
        if self.security:
            payload = self.security.scrub_dict(record)
        with AtomicFileOps.file_lock(self._lock_file):
            AtomicFileOps.append_jsonl(self._records_file, payload)

    def _append_comparison(self, comp: Dict) -> None:
        payload = comp
        if self.security:
            payload = self.security.scrub_dict(comp)
        with AtomicFileOps.file_lock(self._lock_file):
            AtomicFileOps.append_jsonl(self._comparisons_file, payload)
