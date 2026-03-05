"""Quality inspector — self-check + auto-retry (Req 2).

After generation, runs 7-dimension quality scoring.
Keeps backward-compatible headline scores:
- overall_score
- scela_score
- compliance_passed
- consistency_score
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from .models import QualityReport
from .logger import EvolveLogger
from .dimensions import DimensionScorer


def _normalize_weights(weights: Dict[str, float], dims: List[str]) -> Dict[str, float]:
    normalized = {}
    for d in dims:
        normalized[d] = max(0.0, float(weights.get(d, 0.0)))
    s = sum(normalized.values())
    if s <= 0:
        eq = 1.0 / max(len(dims), 1)
        return {d: eq for d in dims}
    vals = {d: normalized[d] / s for d in dims}
    # Keep exact sum=1.0 by compensating the final dimension.
    if dims:
        head = dims[:-1]
        last = dims[-1]
        head_sum = sum(vals[d] for d in head)
        vals[last] = max(0.0, 1.0 - head_sum)
    return vals


class QualityInspector:
    """Post-generation quality gate with auto-retry."""

    MAX_RETRIES = 3
    QUALITY_THRESHOLD = 0.7
    ARCHIVE_THRESHOLD = 0.85

    def __init__(self, logger: EvolveLogger):
        self.logger = logger
        self.dimension_scorer = DimensionScorer()
        self.default_weights = {
            d: 1.0 / len(self.dimension_scorer.DIMENSIONS)
            for d in self.dimension_scorer.DIMENSIONS
        }

    def inspect(self, storyboard: Dict, characters: Dict = None,
                scenes: List[Dict] = None,
                platform: str = None,
                weights: Optional[Dict[str, float]] = None) -> QualityReport:
        """Run full quality inspection on generated output."""
        issues = []
        auto_fixed = []

        dimension_scores = self.dimension_scorer.score_all(
            storyboard=storyboard or {},
            characters=characters or {},
            scenes=scenes or [],
            platform=platform,
        )
        scela_score = float(dimension_scores.get("scela_coverage", 0.0))
        consistency_score = float(dimension_scores.get("consistency", 0.0))
        compliance_score = float(dimension_scores.get("compliance", 1.0))
        compliance_passed = compliance_score >= 0.95
        if not compliance_passed:
            issues.append("合规评分低于阈值")

        active_weights = _normalize_weights(
            weights or self.default_weights,
            self.dimension_scorer.DIMENSIONS,
        )
        overall = 0.0
        for d in self.dimension_scorer.DIMENSIONS:
            overall += float(dimension_scores.get(d, 0.0)) * active_weights.get(d, 0.0)

        report = QualityReport(
            overall_score=round(overall, 3),
            scela_score=round(scela_score, 3),
            compliance_passed=compliance_passed,
            consistency_score=round(consistency_score, 3),
            dimension_scores=dimension_scores,
            active_weights=active_weights,
            attempt_number=1,
            issues=issues,
            auto_fixed=auto_fixed,
        )
        self.logger.log("quality_check", report.to_dict())
        return report

    def auto_retry(self, generate_fn: Callable, *args,
                   max_retries: int = None,
                   **kwargs) -> Tuple[Dict, QualityReport]:
        """Auto-retry generation if quality below threshold.

        generate_fn should return a dict with at least 'storyboard' key.
        """
        retries = max_retries or self.MAX_RETRIES
        best_output = None
        best_report = None

        for attempt in range(1, retries + 1):
            output = generate_fn(*args, **kwargs)
            report = self.inspect(
                output.get("storyboard", {}),
                output.get("characters"),
                output.get("scenes"),
                output.get("platform"),
                output.get("evolved_weights"),
            )
            report.attempt_number = attempt

            if best_report is None or report.overall_score > best_report.overall_score:
                best_output = output
                best_report = report

            self.logger.log("quality_attempt", {
                "attempt": attempt,
                "score": report.overall_score,
                "passed": report.overall_score >= self.QUALITY_THRESHOLD,
            })

            if report.overall_score >= self.QUALITY_THRESHOLD:
                break

        return best_output, best_report
