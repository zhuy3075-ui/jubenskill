"""Tests for preference formation and weight derivation."""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.preference_former import PreferenceFormer


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def test_preference_requires_min_comparisons():
    pf = PreferenceFormer()
    rows = []
    for _ in range(9):
        rows.append(
            {
                "dimension": "visual_precision",
                "winner": "new",
                "timestamp": _iso_now(),
            }
        )
    prefs = pf.build_preferences(rows)
    assert "visual_precision" not in prefs


def test_preference_direction_and_confidence():
    pf = PreferenceFormer()
    rows = []
    # 12 comparisons, 10 wins -> prefer_high
    for i in range(12):
        rows.append(
            {
                "dimension": "shot_diversity",
                "winner": "new" if i < 10 else "opponent",
                "timestamp": _iso_now(),
            }
        )
    prefs = pf.build_preferences(rows)
    assert "shot_diversity" in prefs
    p = prefs["shot_diversity"]
    assert p["direction"] == "prefer_high"
    assert p["confidence"] >= 0.3


def test_derive_weights_normalized_and_clamped():
    pf = PreferenceFormer()
    base = {d: 1.0 / len(pf.DIMENSIONS) for d in pf.DIMENSIONS}
    prefs = {
        "visual_precision": {
            "weight_adjustment": 0.1,
            "confidence": 1.0,
        },
        "compliance": {
            "weight_adjustment": -0.1,
            "confidence": 1.0,
        },
    }
    w = pf.derive_weights(base, prefs)
    assert abs(sum(w.values()) - 1.0) < 1e-6
    assert w["visual_precision"] > w["compliance"]
    for v in w.values():
        assert 0.0 <= v <= 1.0

