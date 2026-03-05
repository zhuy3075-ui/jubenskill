"""Tests for evolution security module.

Covers: PII scrubbing, sensitive content detection, learning boundaries,
memory decay, compression traceability, conflict resolution, package scan.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.security import SecurityGuard
from evolution.logger import EvolveLogger


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="test_sec_"))
    yield d
    import shutil
    shutil.rmtree(str(d), ignore_errors=True)


@pytest.fixture
def logger(tmp_dir):
    return EvolveLogger(tmp_dir / "logs")


@pytest.fixture
def guard(logger):
    return SecurityGuard(logger=logger)


class TestPIIScrubbing:
    def test_phone_number(self, guard):
        assert "[PHONE]" in guard.scrub_pii("联系电话 13812345678")

    def test_email(self, guard):
        assert "[EMAIL]" in guard.scrub_pii("邮箱 test@example.com")

    def test_id_number(self, guard):
        assert "[ID_NUMBER]" in guard.scrub_pii("身份证 110101199001011234")

    def test_bank_card(self, guard):
        assert "[CARD]" in guard.scrub_pii("卡号 6222 0200 1234 5678")

    def test_secret_key(self, guard):
        assert "[SECRET_KEY]" in guard.scrub_pii("sk_live_abcdefghijklmnop1234")

    def test_absolute_path_windows(self, guard):
        assert "[PATH]" in guard.scrub_pii(r"路径 C:\Users\admin\secret.txt")

    def test_absolute_path_unix(self, guard):
        assert "[PATH]" in guard.scrub_pii("路径 /home/user/credentials")

    def test_scrub_dict_recursive(self, guard):
        data = {"name": "test", "phone": "13812345678",
                "nested": {"email": "a@b.com"}}
        result = guard.scrub_dict(data)
        assert "[PHONE]" in result["phone"]
        assert "[EMAIL]" in result["nested"]["email"]


class TestSensitiveContentDetection:
    def test_api_key_pattern(self, guard):
        hits = guard.contains_sensitive("api_key: sk_live_abc123def456ghi789jkl")
        assert len(hits) > 0

    def test_bearer_token(self, guard):
        hits = guard.contains_sensitive("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert len(hits) > 0

    def test_private_key(self, guard):
        hits = guard.contains_sensitive("-----BEGIN RSA PRIVATE KEY-----")
        assert any("SENSITIVE" in h for h in hits)

    def test_password_in_config(self, guard):
        hits = guard.contains_sensitive("password=mysecretpass123")
        assert len(hits) > 0

    def test_clean_text_no_hits(self, guard):
        hits = guard.contains_sensitive("一个女孩在咖啡厅喝咖啡")
        assert len(hits) == 0


class TestSensitiveFileDetection:
    @pytest.mark.parametrize("filename,expected", [
        (".env", True),
        (".env.local", True),
        ("credentials.json", True),
        ("secret_config.yaml", True),
        ("id_rsa", True),
        ("server.key", True),
        ("normal_script.py", False),
        ("SKILL.md", False),
    ])
    def test_sensitive_files(self, guard, filename, expected):
        assert guard.is_sensitive_file(filename) == expected


class TestLearningBoundary:
    def test_whitelist_filter(self, guard):
        data = {
            "style": "cinematic", "format": "16:9",
            "password": "secret", "api_key": "sk_123",
            "score": 0.9,
        }
        filtered = guard.filter_learnable_fields(data)
        assert "style" in filtered
        assert "score" in filtered
        assert "password" not in filtered
        assert "api_key" not in filtered

    def test_validate_entry_too_large(self, guard):
        entry = {"category": "preference", "content": "x" * 60000}
        ok, reason = guard.validate_memory_entry(entry)
        assert not ok
        assert "too_large" in reason

    def test_validate_entry_with_sensitive(self, guard):
        entry = {"category": "preference",
                 "content": {"key": "test", "value": "password=secret123"}}
        ok, reason = guard.validate_memory_entry(entry)
        assert not ok
        assert "sensitive" in reason

    def test_validate_entry_invalid_category(self, guard):
        entry = {"category": "hacked", "content": {}}
        ok, reason = guard.validate_memory_entry(entry)
        assert not ok
        assert "invalid_category" in reason

    def test_validate_entry_ok(self, guard):
        entry = {"category": "preference",
                 "content": {"key": "style", "value": "cinematic"}}
        ok, reason = guard.validate_memory_entry(entry)
        assert ok


class TestMemoryDecay:
    def test_fresh_entries_survive(self, guard):
        from evolution.models import _now_iso
        entries = [
            {"id": "1", "last_accessed": _now_iso(), "decay_score": 1.0},
            {"id": "2", "last_accessed": _now_iso(), "decay_score": 1.0},
        ]
        kept, stats = guard.apply_decay(entries)
        assert stats["kept"] == 2
        assert stats["removed"] == 0

    def test_old_entries_decay(self, guard):
        entries = [
            {"id": "1", "last_accessed": "2020-01-01T00:00:00+00:00",
             "decay_score": 0.05},
        ]
        kept, stats = guard.apply_decay(entries)
        assert stats["removed"] >= 1


class TestMemoryCompression:
    def test_compress_duplicates(self, guard):
        entries = [
            {"id": "1", "category": "preference",
             "content": {"key": "style"}, "decay_score": 1.0, "access_count": 5},
            {"id": "2", "category": "preference",
             "content": {"key": "style"}, "decay_score": 0.5, "access_count": 1},
        ]
        compressed, summaries = guard.compress_memories(entries)
        assert len(compressed) == 1
        assert len(summaries) == 1
        # Traceability: summary must contain merged IDs
        assert "merged_ids" in summaries[0]
        assert "2" in summaries[0]["merged_ids"]

    def test_compress_preserves_unique(self, guard):
        entries = [
            {"id": "1", "category": "preference",
             "content": {"key": "style"}, "decay_score": 1.0, "access_count": 1},
            {"id": "2", "category": "preference",
             "content": {"key": "format"}, "decay_score": 1.0, "access_count": 1},
        ]
        compressed, summaries = guard.compress_memories(entries)
        assert len(compressed) == 2
        assert len(summaries) == 0


class TestConflictResolution:
    def test_detect_conflicts(self, guard):
        entries = [
            {"id": "1", "category": "preference",
             "content": {"key": "style", "value": "cinematic", "confidence": 0.5}},
            {"id": "2", "category": "preference",
             "content": {"key": "style", "value": "anime", "confidence": 0.5}},
        ]
        conflicts = guard.detect_conflicts(entries)
        assert len(conflicts) == 1
        assert conflicts[0]["key"] == "style"

    def test_auto_resolve_low_impact(self, guard):
        entries = [
            {"id": "1", "category": "preference",
             "content": {"key": "style", "value": "cinematic", "confidence": 0.5},
             "access_count": 10},
            {"id": "2", "category": "preference",
             "content": {"key": "style", "value": "anime", "confidence": 0.3},
             "access_count": 1},
        ]
        resolved, user_req = guard.resolve_conflicts_auto(entries)
        assert len(resolved) == 1
        assert len(user_req) == 0

    def test_high_impact_requires_user(self, guard):
        entries = [
            {"id": "1", "category": "preference",
             "content": {"key": "style", "value": "cinematic", "confidence": 0.9},
             "access_count": 10},
            {"id": "2", "category": "preference",
             "content": {"key": "style", "value": "anime", "confidence": 0.9},
             "access_count": 5},
        ]
        resolved, user_req = guard.resolve_conflicts_auto(entries)
        assert len(user_req) == 1
        assert user_req[0]["high_impact"] is True


class TestPackageScan:
    def test_scan_finds_env_file(self, guard, tmp_dir):
        (tmp_dir / ".env").write_text("SECRET=abc")
        findings = guard.scan_directory(tmp_dir)
        assert any(f["reason"] == "sensitive_filename" for f in findings)

    def test_scan_finds_api_key_in_content(self, guard, tmp_dir):
        (tmp_dir / "config.py").write_text("api_key=sk_live_abcdefghijklmnop1234")
        findings = guard.scan_directory(tmp_dir)
        assert any("sensitive_content" in f["reason"] for f in findings)

    def test_scan_clean_directory(self, guard, tmp_dir):
        (tmp_dir / "clean.py").write_text("print('hello')")
        findings = guard.scan_directory(tmp_dir)
        assert len(findings) == 0
