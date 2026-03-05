"""Tests for 7-dimension quality scoring compatibility."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.quality import QualityInspector
from evolution.logger import EvolveLogger


@pytest.fixture
def logger(tmp_path):
    return EvolveLogger(tmp_path / "logs")


@pytest.fixture
def inspector(logger):
    return QualityInspector(logger)


def _sample_storyboard():
    return {
        "title": "demo",
        "shots": [
            {
                "shot_id": "1-1",
                "scene_number": 1,
                "shot_size": "medium shot",
                "camera_movement": "tracking",
                "subject": "角色A",
                "action": "走向窗边",
                "mood": "紧张",
                "visual_prompt": "cinematic medium shot, character walking to window, warm light",
            },
            {
                "shot_id": "1-2",
                "scene_number": 1,
                "shot_size": "close-up",
                "camera_movement": "push in",
                "subject": "角色A",
                "action": "回头",
                "mood": "震惊",
                "visual_prompt": "close-up, push in, dramatic expression, cinematic lighting",
            },
        ],
    }


def test_quality_report_contains_7d_and_legacy(inspector):
    report = inspector.inspect(
        storyboard=_sample_storyboard(),
        characters={"角色A": {}},
        scenes=[{"scene_number": 1}],
        platform="seedance",
    )
    # Legacy fields
    assert 0.0 <= report.overall_score <= 1.0
    assert 0.0 <= report.scela_score <= 1.0
    assert 0.0 <= report.consistency_score <= 1.0
    assert isinstance(report.compliance_passed, bool)

    # New fields
    assert isinstance(report.dimension_scores, dict)
    assert len(report.dimension_scores) == 7
    for v in report.dimension_scores.values():
        assert 0.0 <= float(v) <= 1.0
    assert abs(sum(report.active_weights.values()) - 1.0) < 1e-6


def test_custom_weights_are_normalized(inspector):
    report = inspector.inspect(
        storyboard=_sample_storyboard(),
        platform="seedance",
        weights={
            "scela_coverage": 3.0,
            "consistency": 1.0,
            "compliance": 1.0,
            "shot_diversity": 1.0,
            "mood_rhythm": 1.0,
            "visual_precision": 1.0,
            "platform_fit": 1.0,
        },
    )
    assert abs(sum(report.active_weights.values()) - 1.0) < 1e-6
    assert report.active_weights["scela_coverage"] > report.active_weights["consistency"]

