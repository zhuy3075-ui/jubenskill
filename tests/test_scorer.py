"""Tests for micro scorer."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.scorer import MicroScorer
from evolution.logger import EvolveLogger
from evolution.security import SecurityGuard
from evolution.models import QualityReport


@pytest.fixture
def scorer(tmp_path):
    logger = EvolveLogger(tmp_path / "logs")
    guard = SecurityGuard(logger=logger)
    return MicroScorer(tmp_path / "scores", logger=logger, security=guard)


def _report(base: float = 0.75) -> QualityReport:
    dims = {
        "scela_coverage": base,
        "consistency": base,
        "compliance": 1.0,
        "shot_diversity": base - 0.05,
        "mood_rhythm": base,
        "visual_precision": base - 0.08,
        "platform_fit": base - 0.03,
    }
    return QualityReport(
        overall_score=base,
        scela_score=dims["scela_coverage"],
        consistency_score=dims["consistency"],
        compliance_passed=True,
        dimension_scores=dims,
    )


def _storyboard():
    return {
        "title": "demo",
        "metadata": {"estimated_duration": 10},
        "shots": [{"shot_id": "1-1"}],
    }


def test_phase_progression(scorer):
    for i in range(1, 12):
        summary = scorer.process_generation(
            storyboard=_storyboard(),
            quality_report=_report(0.72 + i * 0.001),
            genre="drama",
            platform="seedance",
            duration_seconds=10,
        )
    assert summary["generation_count"] == 11
    assert summary["phase"] == "observe"
    assert summary["compared"] is True


def test_margin_and_tie_rule(scorer):
    new = {
        "record_id": "a",
        "dimension_scores": {d: 0.70 for d in scorer.DIMENSIONS},
        "phase": "observe",
    }
    opp = {
        "record_id": "b",
        "dimension_scores": {d: 0.69 for d in scorer.DIMENSIONS},
        "phase": "observe",
    }
    comparisons = scorer._compare_records(new, opp)
    assert len(comparisons) == len(scorer.DIMENSIONS)
    # delta=0.01 < 0.02 -> tie
    assert all(c["winner"] == "tie" for c in comparisons)


def test_elo_updates_direction(scorer):
    elo = {d: 1500.0 for d in scorer.DIMENSIONS}
    comps = [
        {
            "dimension": "shot_diversity",
            "winner": "new",
            "source": "auto",
            "margin": 0.03,
        },
        {
            "dimension": "visual_precision",
            "winner": "opponent",
            "source": "auto",
            "margin": -0.04,
        },
    ]
    after = scorer._update_elo(elo, comps)
    assert after["shot_diversity"] > 1500.0
    assert after["visual_precision"] < 1500.0


def test_reset_and_calibrate(scorer):
    # create some data
    for i in range(1, 6):
        scorer.process_generation(
            storyboard=_storyboard(),
            quality_report=_report(0.70 + i * 0.01),
            genre="ad",
            platform="seedance",
            duration_seconds=10,
        )
    cal = scorer.calibrate()
    assert cal["ok"] is True
    assert "comparisons" in cal

    rst = scorer.reset()
    assert rst["ok"] is True
    state = scorer.get_state()
    assert state["generation_count"] == 0
    assert state["phase"] == "shadow"

