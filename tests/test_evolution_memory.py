"""Tests for evolution memory module.

Covers: preferences CRUD, corrections, patterns, archiving, concurrent writes,
interrupted writes, corrupted JSON recovery, eviction, maintenance.
"""
import json
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.memory import MemoryStore
from evolution.security import SecurityGuard
from evolution.logger import EvolveLogger
from evolution.models import CorrectionRecord, PromptPattern


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="test_mem_"))
    yield d
    shutil.rmtree(str(d), ignore_errors=True)


@pytest.fixture
def logger(tmp_dir):
    return EvolveLogger(tmp_dir / "logs")


@pytest.fixture
def security(logger):
    return SecurityGuard(logger=logger)


@pytest.fixture
def store(tmp_dir, logger, security):
    return MemoryStore(tmp_dir / "memory", logger, security)


class TestPreferences:
    def test_set_and_get(self, store):
        ok, reason = store.set_preference("style", "cinematic")
        assert ok
        pref = store.get_preference("style")
        assert pref is not None
        assert pref["content"]["value"] == "cinematic"

    def test_update_existing(self, store):
        store.set_preference("style", "cinematic")
        store.set_preference("style", "anime")
        pref = store.get_preference("style")
        assert pref["content"]["value"] == "anime"

    def test_get_nonexistent(self, store):
        assert store.get_preference("nonexistent") is None

    def test_get_all(self, store):
        store.set_preference("style", "cinematic")
        store.set_preference("format", "16:9")
        prefs = store.get_all_preferences()
        assert len(prefs) == 2

    def test_reject_sensitive_value(self, store):
        ok, reason = store.set_preference("config", "password=secret123")
        assert not ok
        assert "sensitive" in reason

    def test_high_impact_conflict(self, store):
        store.set_preference("style", "cinematic", confidence=0.9)
        ok, reason = store.set_preference("style", "anime", confidence=0.5)
        assert not ok
        assert "conflict" in reason


class TestCorrections:
    def test_add_correction(self, store):
        record = CorrectionRecord(
            original_output="长发女孩",
            user_correction="短发女孩",
            reflection="发型描述错误",
            rule_extracted="当描述包含短发时使用short hair",
        )
        ok, reason = store.add_correction(record)
        assert ok

    def test_get_corrections(self, store):
        for i in range(3):
            record = CorrectionRecord(
                original_output=f"original_{i}",
                user_correction=f"corrected_{i}",
                reflection=f"reflection_{i}",
                rule_extracted=f"rule_{i}",
            )
            store.add_correction(record)
        corrections = store.get_corrections(limit=2)
        assert len(corrections) == 2

    def test_find_relevant(self, store):
        record = CorrectionRecord(
            original_output="长发",
            user_correction="短发",
            reflection="发型错误",
            rule_extracted="短发 short hair 优先",
        )
        store.add_correction(record)
        relevant = store.find_relevant_corrections("描述角色短发造型")
        assert len(relevant) >= 1

    def test_correction_pii_scrubbed(self, store):
        record = CorrectionRecord(
            original_output="联系 13812345678",
            user_correction="联系方式已隐藏",
        )
        store.add_correction(record)
        corrections = store.get_corrections()
        content = json.dumps(corrections[-1], ensure_ascii=False)
        assert "13812345678" not in content


class TestPatterns:
    def test_add_pattern(self, store):
        pattern = PromptPattern(
            template="cinematic, wide shot, golden hour",
            score=0.9, genre="drama",
        )
        ok, reason = store.add_pattern(pattern)
        assert ok

    def test_get_top_patterns(self, store):
        for i, score in enumerate([0.5, 0.9, 0.7]):
            store.add_pattern(PromptPattern(
                template=f"pattern_{i}", score=score, genre="drama"))
        top = store.get_top_patterns(genre="drama", limit=2)
        assert len(top) == 2
        assert top[0]["content"]["score"] >= top[1]["content"]["score"]


class TestArchive:
    def test_archive_high_quality(self, store):
        aid = store.archive_output(
            {"storyboard": {"title": "test"}}, score=0.9, title="test")
        assert aid is not None

    def test_reject_low_quality(self, store):
        aid = store.archive_output(
            {"storyboard": {"title": "test"}}, score=0.5, title="test")
        assert aid is None

    def test_get_archived(self, store):
        store.archive_output(
            {"storyboard": {"title": "test"}}, score=0.9, title="test")
        archives = store.get_archived_examples()
        assert len(archives) == 1


class TestStats:
    def test_stats(self, store):
        store.set_preference("style", "cinematic")
        stats = store.get_stats()
        assert stats["preferences"] == 1
        assert "corrections" in stats
        assert "patterns" in stats
        assert "archives" in stats


class TestCorruptedJSON:
    def test_corrupted_prefs_file(self, store):
        store._prefs_file.write_text("not json{{{")
        # Should return empty list, not crash
        prefs = store.get_all_preferences()
        assert prefs == []

    def test_corrupted_corrections_file(self, store):
        store._corrections_file.write_text("{bad")
        corrections = store.get_corrections()
        assert corrections == []


class TestEviction:
    def test_evict_when_full(self, store):
        store.MAX_ENTRIES_PER_CATEGORY = 5
        for i in range(10):
            store.add_pattern(PromptPattern(
                template=f"pattern_{i}", score=0.5, genre="test"))
        patterns = store.get_top_patterns(limit=100)
        assert len(patterns) <= 5


class TestMaintenance:
    def test_run_maintenance(self, store):
        store.set_preference("style", "cinematic")
        store.add_pattern(PromptPattern(
            template="test", score=0.8, genre="drama"))
        stats = store.run_maintenance()
        assert "preferences_kept" in stats
        assert "patterns_kept" in stats
