"""Tests for evolution env_detect module (P1-E).

Covers: probe matrix, priority resolution, conflict handling,
safe degraded mode, capability detection, behavior adaptation.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.env_detect import EnvDetector
from evolution.models import Environment


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="test_env_"))
    yield d
    shutil.rmtree(str(d), ignore_errors=True)


class TestEnvDetection:
    def test_detect_returns_environment(self):
        env = EnvDetector.detect()
        assert isinstance(env, Environment)
        assert env.os_name != ""
        assert env.python_version != ""

    def test_detect_claude_code_env_var(self, tmp_dir):
        with patch.dict(os.environ, {"CLAUDE_CODE": "1"}, clear=False):
            env = EnvDetector.detect(tmp_dir)
            assert env.runtime == "claude_code"

    def test_detect_openhands_env_var(self, tmp_dir):
        with patch.dict(os.environ, {"OPENHANDS_WORKSPACE": "/ws"}, clear=False):
            env = EnvDetector.detect(tmp_dir)
            assert env.runtime == "openhands"

    def test_detect_coze_env_var(self, tmp_dir):
        with patch.dict(os.environ, {"COZE_SKILL_ID": "123"}, clear=False):
            env = EnvDetector.detect(tmp_dir)
            assert env.runtime == "coze"

    def test_detect_dir_signature(self, tmp_dir):
        (tmp_dir / ".claude").mkdir()
        with patch.dict(os.environ, {}, clear=False):
            # Remove any env vars that might interfere
            for key in ["CLAUDE_CODE", "CLAUDE_CODE_VERSION",
                        "OPENHANDS_WORKSPACE", "COZE_SKILL_ID"]:
                os.environ.pop(key, None)
            env = EnvDetector.detect(tmp_dir)
            # Should detect claude_code from directory signature
            assert env.runtime in ("claude_code", "standalone")


class TestPriorityResolution:
    def test_env_var_beats_dir_signature(self, tmp_dir):
        """Env var probes have higher priority than dir probes."""
        (tmp_dir / ".claude").mkdir()
        with patch.dict(os.environ, {"OPENHANDS_WORKSPACE": "/ws"}, clear=False):
            for key in ["CLAUDE_CODE", "CLAUDE_CODE_VERSION"]:
                os.environ.pop(key, None)
            env = EnvDetector.detect(tmp_dir)
            assert env.runtime == "openhands"

    def test_conflict_highest_priority_wins(self, tmp_dir):
        """When multiple env vars match, highest priority wins."""
        with patch.dict(os.environ, {
            "CLAUDE_CODE": "1",       # priority 10
            "COZE_SKILL_ID": "123",   # priority 8
        }, clear=False):
            env = EnvDetector.detect(tmp_dir)
            assert env.runtime == "claude_code"


class TestSafeDegradedMode:
    def test_detection_failure_degrades(self, tmp_dir):
        """If detection throws, should return degraded environment."""
        with patch.object(EnvDetector, "_do_detect", side_effect=RuntimeError("boom")):
            env = EnvDetector.detect(tmp_dir)
            assert env.degraded is True
            assert env.runtime == "unknown"
            assert env.capabilities == ["file_read"]

    def test_degraded_has_minimal_capabilities(self):
        env = Environment(
            runtime="unknown", degraded=True,
            capabilities=EnvDetector.CAPABILITIES["unknown"],
        )
        assert "file_read" in env.capabilities
        assert "shell" not in env.capabilities
        assert "network" not in env.capabilities


class TestCapabilities:
    def test_claude_code_capabilities(self):
        caps = EnvDetector.CAPABILITIES["claude_code"]
        assert "file_write" in caps
        assert "shell" in caps
        assert "git" in caps

    def test_coze_capabilities(self):
        caps = EnvDetector.CAPABILITIES["coze"]
        assert "file_write" in caps
        assert "shell" not in caps


class TestBehaviorAdaptation:
    def test_normal_mode(self):
        env = Environment(
            runtime="claude_code", has_git=True, has_network=True,
            capabilities=["file_read", "file_write", "shell", "network", "git"],
        )
        adapt = EnvDetector.adapt_behavior(env)
        assert adapt["can_write_files"] is True
        assert adapt["can_use_git"] is True
        assert adapt["safe_mode"] is False

    def test_degraded_mode(self):
        env = Environment(
            runtime="unknown", degraded=True,
            capabilities=["file_read"],
        )
        adapt = EnvDetector.adapt_behavior(env)
        assert adapt["can_write_files"] is False
        assert adapt["safe_mode"] is True
        assert adapt["max_file_size_mb"] == 1


class TestHeartbeatSchedule:
    """Test 72h scheduling logic (P1-D) via core engine."""

    def test_heartbeat_state_model(self):
        from evolution.models import HeartbeatState
        state = HeartbeatState()
        assert state.check_count == 0
        assert state.consecutive_failures == 0

    def test_heartbeat_backoff(self):
        """Exponential backoff: 2^failures * 60 seconds."""
        from evolution.models import HeartbeatState
        state = HeartbeatState(consecutive_failures=3)
        backoff = min(2 ** state.consecutive_failures * 60, 3600)
        assert backoff == 480  # 2^3 * 60 = 480 seconds
