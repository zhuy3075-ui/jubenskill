"""Dimension-level quality scorers for evolution quality checks.

Provides 7 scoring dimensions in [0, 1]:
- scela_coverage
- consistency
- compliance
- shot_diversity
- mood_rhythm
- visual_precision
- platform_fit
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class DimensionScorer:
    """Compute deterministic quality dimension scores from generation outputs."""

    DIMENSIONS = [
        "scela_coverage",
        "consistency",
        "compliance",
        "shot_diversity",
        "mood_rhythm",
        "visual_precision",
        "platform_fit",
    ]

    def __init__(self):
        self._optimizer_cls = None

    def score_all(
        self,
        storyboard: Dict,
        characters: Dict | None = None,
        scenes: List[Dict] | None = None,
        platform: str | None = None,
    ) -> Dict[str, float]:
        shots = storyboard.get("shots", []) if storyboard else []
        platform_l = (platform or "").lower()
        prompts = [
            (s.get("optimized_prompt") or s.get("visual_prompt") or "").strip()
            for s in shots
        ]
        prompts = [p for p in prompts if p]

        scela = self.score_scela_coverage(prompts)
        consistency = self.score_consistency(storyboard, characters or {}, scenes or [])
        compliance = self.score_compliance(prompts, platform_l)
        shot_diversity = self.score_shot_diversity(shots)
        mood_rhythm = self.score_mood_rhythm(shots)
        visual_precision = self.score_visual_precision(shots, prompts)
        platform_fit = self.score_platform_fit(shots, prompts, platform_l, scela)

        return {
            "scela_coverage": round(scela, 3),
            "consistency": round(consistency, 3),
            "compliance": round(compliance, 3),
            "shot_diversity": round(shot_diversity, 3),
            "mood_rhythm": round(mood_rhythm, 3),
            "visual_precision": round(visual_precision, 3),
            "platform_fit": round(platform_fit, 3),
        }

    def _get_optimizer(self):
        if self._optimizer_cls is not None:
            return self._optimizer_cls()
        try:
            scripts_dir = Path(__file__).parent.parent / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from prompt_optimizer import PromptOptimizer  # type: ignore

            self._optimizer_cls = PromptOptimizer
            return self._optimizer_cls()
        except Exception:
            return None

    def score_scela_coverage(self, prompts: List[str]) -> float:
        if not prompts:
            return 0.0
        optimizer = self._get_optimizer()
        if optimizer is None:
            # Conservative fallback when scorer dependency is unavailable.
            return 0.5
        scores = []
        for prompt in prompts:
            try:
                result = optimizer.check_scela(prompt)
                scores.append(float(result.get("score", 0.0)))
            except Exception:
                scores.append(0.0)
        return _clamp(sum(scores) / max(len(scores), 1))

    def score_consistency(
        self,
        storyboard: Dict,
        characters: Dict,
        scenes: List[Dict],
    ) -> float:
        shots = storyboard.get("shots", []) if storyboard else []
        if not shots:
            return 0.5

        # Character reference consistency: do shots mention known characters?
        known_chars = [str(c) for c in characters.keys()]
        if known_chars:
            hit = 0
            for s in shots:
                text = f"{s.get('subject', '')} {s.get('visual_prompt', '')}"
                if any(n in text for n in known_chars):
                    hit += 1
            char_cons = hit / len(shots)
        else:
            char_cons = 0.6

        # Scene continuity: adjacent scene numbers should not jump too wildly.
        nums = [int(s.get("scene_number", 0) or 0) for s in shots]
        if len(nums) <= 1:
            scene_cont = 1.0
        else:
            jumps = sum(1 for i in range(1, len(nums)) if abs(nums[i] - nums[i - 1]) > 1)
            scene_cont = 1.0 - (jumps / (len(nums) - 1))

        # Optional scene reference availability.
        scene_ref = 0.7 if not scenes else 1.0
        return _clamp(char_cons * 0.5 + scene_cont * 0.35 + scene_ref * 0.15)

    def score_compliance(self, prompts: List[str], platform_l: str) -> float:
        if not prompts:
            return 1.0
        if platform_l not in ("seedance", "即梦"):
            return 1.0
        optimizer = self._get_optimizer()
        if optimizer is None:
            return 1.0
        violations = 0
        for prompt in prompts:
            try:
                issues = optimizer._check_seedance_compliance(prompt)
                if issues:
                    violations += len(issues)
            except Exception:
                continue
        penalty = min(0.8, violations * 0.08)
        return _clamp(1.0 - penalty)

    def score_shot_diversity(self, shots: List[Dict]) -> float:
        if not shots:
            return 0.0
        shot_sizes = {
            str(s.get("shot_size", "")).strip().lower() for s in shots if s.get("shot_size")
        }
        moves = {
            str(s.get("camera_movement", "")).strip().lower()
            for s in shots
            if s.get("camera_movement")
        }
        size_score = min(1.0, len(shot_sizes) / 6.0)
        move_score = min(1.0, len(moves) / 6.0)
        return _clamp(size_score * 0.5 + move_score * 0.5)

    def score_mood_rhythm(self, shots: List[Dict]) -> float:
        if not shots:
            return 0.0
        moods = [str(s.get("mood", "")).strip().lower() for s in shots if s.get("mood")]
        if not moods:
            return 0.5
        unique_ratio = len(set(moods)) / len(moods)
        if len(moods) == 1:
            transition_ratio = 0.0
        else:
            transitions = sum(1 for i in range(1, len(moods)) if moods[i] != moods[i - 1])
            transition_ratio = transitions / (len(moods) - 1)
        # Favor moderate transitions; too static or too jumpy both get lower.
        rhythm = 1.0 - abs(transition_ratio - 0.45)
        return _clamp(unique_ratio * 0.35 + rhythm * 0.65)

    def score_visual_precision(self, shots: List[Dict], prompts: List[str]) -> float:
        if not shots or not prompts:
            return 0.0
        # Prompt detail density.
        words = [len(p.split()) for p in prompts]
        avg_words = sum(words) / len(words)
        length_score = _clamp(avg_words / 30.0)

        # Structured shot info completeness.
        complete = 0
        for s in shots:
            if s.get("subject") and s.get("action") and (
                s.get("visual_prompt") or s.get("optimized_prompt")
            ):
                complete += 1
        completeness = complete / len(shots)
        return _clamp(length_score * 0.4 + completeness * 0.6)

    def score_platform_fit(
        self,
        shots: List[Dict],
        prompts: List[str],
        platform_l: str,
        scela_score: float,
    ) -> float:
        if not prompts:
            return 0.0
        if platform_l in ("seedance", "即梦"):
            # Fit to Seedance: SCELA + timeline-style structure hints.
            timeline_hits = sum(
                1
                for p in prompts
                if any(k in p for k in ("0-", "秒", "@图片", "@视频", "镜头", "运镜"))
            )
            timeline_score = timeline_hits / len(prompts)
            return _clamp(scela_score * 0.7 + timeline_score * 0.3)

        cinematic_hits = sum(
            1
            for p in prompts
            if any(k in p.lower() for k in ("cinematic", "high quality", "8k", "电影级"))
        )
        return _clamp(0.6 + 0.4 * (cinematic_hits / len(prompts)))
