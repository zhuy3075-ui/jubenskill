"""Tests for scorer-related /evolve command routing."""
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.core import EvolveEngine


def _make_project() -> Path:
    d = Path(tempfile.mkdtemp(prefix="test_sc_cmd_"))
    # minimal project files used by subsystems
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    for f in [
        "parse_script.py",
        "character_extractor.py",
        "scene_analyzer.py",
        "storyboard_generator.py",
        "prompt_optimizer.py",
        "consistency_checker.py",
        "export_utils.py",
    ]:
        (d / "scripts" / f).write_text("# stub", encoding="utf-8")
    (d / "references").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("# skill", encoding="utf-8")
    return d


def test_scores_and_preferences_commands():
    proj = _make_project()
    try:
        engine = EvolveEngine(project_root=proj)
        out = engine.handle_command("/evolve scores")
        assert "ELO" in out
        out2 = engine.handle_command("/evolve preferences")
        assert "偏好" in out2 or "暂无" in out2
    finally:
        shutil.rmtree(str(proj), ignore_errors=True)


def test_scorer_subcommands():
    proj = _make_project()
    try:
        engine = EvolveEngine(project_root=proj)
        out = engine.handle_command("/evolve scorer reset")
        assert "评分历史已重置" in out
        out2 = engine.handle_command("/evolve scorer calibrate")
        assert "评分校准完成" in out2
    finally:
        shutil.rmtree(str(proj), ignore_errors=True)

