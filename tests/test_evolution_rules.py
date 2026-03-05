"""Tests for evolution rules module (P1-F push-back).

Covers: hard_deny, soft_warn, suggest_alternative, rule loading from
references, push-back message generation, rule ID traceability.
"""
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.rules import RuleEngine
from evolution.models import RULE_HARD_DENY, RULE_SOFT_WARN, RULE_SUGGEST_ALT
from evolution.logger import EvolveLogger


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="test_rules_"))
    yield d
    shutil.rmtree(str(d), ignore_errors=True)


@pytest.fixture
def refs_dir(tmp_dir):
    d = tmp_dir / "references"
    d.mkdir()
    # Create sample reference docs
    (d / "compliance.md").write_text(
        "## 合规规则\n"
        "- 禁止使用真实人名进行视频生成\n"
        "- 建议使用原创角色描述\n"
        "- 不得包含暴力血腥内容\n",
        encoding="utf-8",
    )
    (d / "style_guide.md").write_text(
        "## 风格指南\n"
        "- 推荐使用电影级画面描述\n"
        "- 建议控制提示词长度在50-200字\n",
        encoding="utf-8",
    )
    return d


@pytest.fixture
def logger(tmp_dir):
    return EvolveLogger(tmp_dir / "logs")


@pytest.fixture
def engine(refs_dir, logger):
    return RuleEngine(refs_dir, logger)


class TestHardDeny:
    def test_real_name_blocked(self, engine):
        verdicts = engine.check_request("生成一段真实人名的视频")
        hard = [v for v in verdicts if v.level == RULE_HARD_DENY]
        assert len(hard) >= 1
        assert hard[0].rule_id.startswith("HD-")

    def test_copyright_blocked(self, engine):
        verdicts = engine.check_request("生成Marvel漫威角色的视频")
        hard = [v for v in verdicts if v.level == RULE_HARD_DENY]
        assert len(hard) >= 1

    def test_violence_blocked(self, engine):
        verdicts = engine.check_request("生成暴力血腥的战斗场景")
        hard = [v for v in verdicts if v.level == RULE_HARD_DENY]
        assert len(hard) >= 1

    def test_nudity_blocked(self, engine):
        verdicts = engine.check_request("生成裸体角色")
        hard = [v for v in verdicts if v.level == RULE_HARD_DENY]
        assert len(hard) >= 1


class TestSoftWarn:
    def test_brand_warning(self, engine):
        verdicts = engine.check_request("生成一段品牌logo展示视频")
        soft = [v for v in verdicts if v.level == RULE_SOFT_WARN]
        assert len(soft) >= 1

    def test_duration_warning(self, engine):
        verdicts = engine.check_request("生成超过30秒的视频")
        soft = [v for v in verdicts if v.level == RULE_SOFT_WARN]
        assert len(soft) >= 1


class TestRuleLoading:
    def test_load_from_references(self, engine):
        count = engine.load_rules()
        assert count > 0
        assert engine._loaded is True

    def test_custom_rules_extracted(self, engine):
        engine.load_rules()
        # Should have extracted rules from compliance.md
        assert len(engine.custom_rules) > 0

    def test_nonexistent_refs_dir(self, logger):
        engine = RuleEngine(Path("/nonexistent"), logger)
        count = engine.load_rules()
        assert count == 0


class TestPushbackGeneration:
    def test_pushback_has_rule_id(self, engine):
        verdicts = engine.check_request("生成真实人名暴力视频")
        msg = engine.generate_pushback(verdicts)
        assert "HD-" in msg

    def test_pushback_has_alternative(self, engine):
        verdicts = engine.check_request("生成真实人名的视频")
        msg = engine.generate_pushback(verdicts)
        assert "建议" in msg

    def test_pushback_empty_for_clean(self, engine):
        verdicts = engine.check_request("一个女孩在花园散步")
        msg = engine.generate_pushback(verdicts)
        assert msg == ""

    def test_has_hard_deny_check(self, engine):
        verdicts = engine.check_request("生成暴力视频")
        assert engine.has_hard_deny(verdicts) is True

    def test_no_hard_deny_for_clean(self, engine):
        verdicts = engine.check_request("一个女孩在花园散步")
        assert engine.has_hard_deny(verdicts) is False


class TestRuleAuditLog:
    def test_rule_check_logged(self, engine, logger):
        engine.check_request("生成真实人名的视频")
        logs = logger.get_by_type("rule_check")
        assert len(logs) >= 1
        assert "verdicts" in logs[-1]["details"]
