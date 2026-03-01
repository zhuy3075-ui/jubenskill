"""Rule engine — reference internalization + push-back (Req 7, P1-F).

Parses references/*.md to extract actionable rules. Implements three-level
push-back: hard_deny, soft_warn, suggest_alternative.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from .models import RuleVerdict, RULE_HARD_DENY, RULE_SOFT_WARN, RULE_SUGGEST_ALT
from .logger import EvolveLogger


class RuleEngine:
    """Internalizes rules from reference docs and enforces them."""

    # Built-in hard-deny rules (always enforced)
    HARD_DENY_RULES = [
        {
            "id": "HD-001", "pattern": r"(?:真实人名|real\s+name)",
            "reason": "禁止使用真实人名（合规要求）",
            "alternative": "使用虚构角色名或通用描述",
        },
        {
            "id": "HD-002",
            "pattern": r"(?:版权|copyright|©|Marvel|Disney|漫威|迪士尼)",
            "reason": "禁止使用版权IP内容",
            "alternative": "使用原创角色和场景描述",
        },
        {
            "id": "HD-003",
            "pattern": r"(?:暴力|血腥|gore|violence|dismember)",
            "reason": "禁止生成暴力血腥内容",
            "alternative": "使用隐喻或暗示性表达",
        },
        {
            "id": "HD-004",
            "pattern": r"(?:裸体|nude|naked|色情|porn)",
            "reason": "禁止生成色情内容",
            "alternative": "使用得体的角色描述",
        },
    ]

    # Soft-warn rules (warn but continue)
    SOFT_WARN_RULES = [
        {
            "id": "SW-001",
            "pattern": r"(?:品牌|brand|logo|商标)",
            "reason": "包含品牌/商标引用，可能有合规风险",
            "alternative": "使用通用产品描述替代品牌名",
        },
        {
            "id": "SW-002",
            "pattern": r"(?:超过|exceed)\s*(?:15|20|30)\s*(?:秒|seconds)",
            "reason": "视频时长可能超出平台限制",
            "alternative": "建议控制在5-15秒范围内",
        },
    ]

    def __init__(self, references_dir: Path, logger: EvolveLogger):
        self.references_dir = references_dir
        self.logger = logger
        self.custom_rules: List[Dict] = []
        self._loaded = False

    def load_rules(self) -> int:
        """Parse references/*.md and extract additional rules. Returns count."""
        if not self.references_dir.exists():
            self._loaded = True
            return 0
        count = 0
        for md_file in self.references_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                # Extract rules from "禁止/不得/必须" patterns
                for line in content.split("\n"):
                    line = line.strip()
                    if re.search(r"(禁止|不得|严禁|must\s+not|forbidden)", line, re.I):
                        self.custom_rules.append({
                            "id": f"REF-{count:03d}",
                            "level": RULE_HARD_DENY,
                            "text": line[:200],
                            "source": md_file.name,
                        })
                        count += 1
                    elif re.search(r"(建议|推荐|should|recommend)", line, re.I):
                        self.custom_rules.append({
                            "id": f"REF-{count:03d}",
                            "level": RULE_SUGGEST_ALT,
                            "text": line[:200],
                            "source": md_file.name,
                        })
                        count += 1
            except Exception:
                continue
        self._loaded = True
        self.logger.log("rules_loaded", {
            "custom_rules": count,
            "builtin_hard": len(self.HARD_DENY_RULES),
            "builtin_soft": len(self.SOFT_WARN_RULES),
        })
        return count

    # ------------------------------------------------------------------
    # Check request against all rules (P1-F: three-level push-back)
    # ------------------------------------------------------------------

    def check_request(self, user_request: str) -> List[RuleVerdict]:
        """Check user request against all rules. Returns list of verdicts."""
        if not self._loaded:
            self.load_rules()
        verdicts = []
        # Hard deny rules
        for rule in self.HARD_DENY_RULES:
            if re.search(rule["pattern"], user_request, re.I):
                verdicts.append(RuleVerdict(
                    rule_id=rule["id"],
                    level=RULE_HARD_DENY,
                    reason=rule["reason"],
                    alternative=rule["alternative"],
                ))
        # Soft warn rules
        for rule in self.SOFT_WARN_RULES:
            if re.search(rule["pattern"], user_request, re.I):
                verdicts.append(RuleVerdict(
                    rule_id=rule["id"],
                    level=RULE_SOFT_WARN,
                    reason=rule["reason"],
                    alternative=rule["alternative"],
                ))
        # Custom rules from references
        for rule in self.custom_rules:
            # Simple keyword match from rule text
            keywords = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", rule["text"])
            keywords = [k.lower() for k in keywords[:5] if len(k) > 1]
            req_lower = user_request.lower()
            if any(kw in req_lower for kw in keywords):
                verdicts.append(RuleVerdict(
                    rule_id=rule["id"],
                    level=rule["level"],
                    reason=rule["text"][:100],
                    source_file=rule.get("source", ""),
                ))
        if verdicts:
            self.logger.log("rule_check", {
                "request_preview": user_request[:100],
                "verdicts": [v.to_dict() for v in verdicts],
            })
        return verdicts

    def generate_pushback(self, verdicts: List[RuleVerdict]) -> str:
        """Generate human-readable push-back message."""
        if not verdicts:
            return ""
        lines = []
        hard = [v for v in verdicts if v.level == RULE_HARD_DENY]
        soft = [v for v in verdicts if v.level == RULE_SOFT_WARN]
        suggest = [v for v in verdicts if v.level == RULE_SUGGEST_ALT]

        if hard:
            lines.append("⛔ 以下内容被规则禁止，无法继续：")
            for v in hard:
                lines.append(f"  [{v.rule_id}] {v.reason}")
                if v.alternative:
                    lines.append(f"    → 建议: {v.alternative}")
        if soft:
            lines.append("⚠️ 以下内容存在风险，请注意：")
            for v in soft:
                lines.append(f"  [{v.rule_id}] {v.reason}")
                if v.alternative:
                    lines.append(f"    → 建议: {v.alternative}")
        if suggest:
            lines.append("💡 建议优化：")
            for v in suggest:
                lines.append(f"  [{v.rule_id}] {v.reason}")
                if v.alternative:
                    lines.append(f"    → {v.alternative}")
        return "\n".join(lines)

    def has_hard_deny(self, verdicts: List[RuleVerdict]) -> bool:
        """Check if any verdict is a hard deny."""
        return any(v.level == RULE_HARD_DENY for v in verdicts)
