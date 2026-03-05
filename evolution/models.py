"""Shared data models for the evolution system.

All dataclasses used across evolution modules. Follows the existing project
pattern of @dataclass with to_dict() methods.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Memory models
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    id: str = field(default_factory=_uuid)
    category: str = ""            # preference | correction | pattern | rule
    content: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    last_accessed: str = field(default_factory=_now_iso)
    access_count: int = 0
    decay_score: float = 1.0      # 1.0=fresh, 0.0=expired
    source: str = "auto"          # user | auto | reflection

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class UserPreference:
    key: str = ""
    value: Any = None
    confidence: float = 1.0       # increases with repeated confirmation
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CorrectionRecord:
    id: str = field(default_factory=_uuid)
    original_output: str = ""
    user_correction: str = ""
    reflection: str = ""          # WHY it was wrong (system-generated)
    rule_extracted: str = ""      # preventive rule
    applied_count: int = 0
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PromptPattern:
    pattern_id: str = field(default_factory=_uuid)
    template: str = ""
    score: float = 0.0
    genre: str = ""
    usage_count: int = 0
    success_rate: float = 0.0
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Snapshot models
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    snapshot_id: str = field(default_factory=_uuid)
    timestamp: str = field(default_factory=_now_iso)
    trigger: str = "manual"       # pre_evolution | manual | pre_update | pre_rollback
    files: Dict[str, str] = field(default_factory=dict)  # rel_path -> sha256
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Log models
# ---------------------------------------------------------------------------

@dataclass
class EvolveLogEntry:
    timestamp: str = field(default_factory=_now_iso)
    event_type: str = ""          # learn | correct | archive | rollback | decay | check | security | error
    details: Dict = field(default_factory=dict)
    before_state: Optional[Dict] = None
    after_state: Optional[Dict] = None
    operator: str = "system"      # system | user

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Quality models
# ---------------------------------------------------------------------------

@dataclass
class QualityReport:
    overall_score: float = 0.0
    scela_score: float = 0.0
    compliance_passed: bool = True
    consistency_score: float = 0.0
    attempt_number: int = 1
    issues: List[str] = field(default_factory=list)
    auto_fixed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Rules models (P1-F: push-back levels)
# ---------------------------------------------------------------------------

RULE_HARD_DENY = "hard_deny"
RULE_SOFT_WARN = "soft_warn"
RULE_SUGGEST_ALT = "suggest_alternative"


@dataclass
class RuleVerdict:
    rule_id: str = ""
    level: str = RULE_SOFT_WARN   # hard_deny | soft_warn | suggest_alternative
    reason: str = ""
    alternative: str = ""
    source_file: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Environment models (P1-E)
# ---------------------------------------------------------------------------

@dataclass
class Environment:
    runtime: str = "unknown"      # claude_code | openhands | coze | standalone | unknown
    os_name: str = ""
    python_version: str = ""
    has_git: bool = False
    has_network: bool = False
    project_root: str = ""
    capabilities: List[str] = field(default_factory=list)
    degraded: bool = False        # True if detection failed → safe mode

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Supply-chain models (P0-A)
# ---------------------------------------------------------------------------

@dataclass
class RepoAllowlistEntry:
    owner: str = ""
    repo: str = ""
    allowed_refs: List[str] = field(default_factory=list)  # tags or commit SHAs

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class UpdateManifest:
    version: str = ""
    files: Dict[str, str] = field(default_factory=dict)  # rel_path -> sha256
    source_repo: str = ""
    source_ref: str = ""          # tag or commit SHA
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Heartbeat model (P1-D)
# ---------------------------------------------------------------------------

@dataclass
class HeartbeatState:
    last_checked_at: str = field(default_factory=_now_iso)
    check_count: int = 0
    consecutive_failures: int = 0
    next_backoff_seconds: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)
