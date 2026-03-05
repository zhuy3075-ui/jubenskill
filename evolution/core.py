"""EvolveEngine — central orchestrator for the self-evolution system.

Initializes all subsystems, provides pre/post processing middleware,
handles /evolve commands, and manages the 72h heartbeat schedule (P1-D).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from .models import HeartbeatState, QualityReport, _now_iso
from .file_ops import AtomicFileOps
from .logger import EvolveLogger
from .security import SecurityGuard
from .memory import MemoryStore
from .quality import QualityInspector
from .learner import PatternLearner
from .rules import RuleEngine
from .snapshot import SnapshotManager
from .env_detect import EnvDetector
from .packager import Packager
from .repair import SelfRepair
from .triggers import TriggerRouter
from .scorer import MicroScorer
from .preference_former import PreferenceFormer


class EvolveEngine:
    """Central orchestrator for the self-evolution system."""

    VERSION = "2.0.0"
    HEARTBEAT_INTERVAL_HOURS = 72
    MAX_BACKOFF_SECONDS = 3600  # 1 hour max backoff

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.data_dir = self.project_root / "evolve_data"
        AtomicFileOps.ensure_dir(self.data_dir)

        # Initialize subsystems
        self.logger = EvolveLogger(self.data_dir / "logs")
        self.security = SecurityGuard(logger=self.logger)
        self.memory = MemoryStore(
            self.data_dir / "memory", self.logger, self.security)
        self.quality = QualityInspector(self.logger)
        self.learner = PatternLearner(self.memory, self.logger)
        self.rules = RuleEngine(
            self.project_root / "references", self.logger)
        self.snapshots = SnapshotManager(
            self.data_dir / "snapshots", self.project_root, self.logger)
        self.env = EnvDetector.detect(self.project_root)
        self.packager = Packager(
            self.project_root, self.logger, self.security)
        self.repair = SelfRepair(
            self.project_root, self.logger, self.snapshots)
        self.scorer = MicroScorer(
            self.data_dir / "scores", self.logger, self.security)
        self.pref_former = PreferenceFormer(self.logger)
        self.triggers = TriggerRouter(self)

        # Heartbeat state (P1-D)
        self._heartbeat_file = self.data_dir / "heartbeat.json"

        # Log engine startup
        self.logger.log("engine_start", {
            "version": self.VERSION,
            "runtime": self.env.runtime,
            "degraded": self.env.degraded,
        })

    # ------------------------------------------------------------------
    # Pipeline middleware
    # ------------------------------------------------------------------

    def pre_process(self, user_input: Dict) -> Dict:
        """Before generation: load preferences, apply patterns, check rules."""
        enriched = dict(user_input)

        # Check heartbeat (P1-D)
        self._check_heartbeat()

        # Load user preferences
        prefs = self.memory.get_all_preferences()
        if prefs:
            pref_dict = {}
            for p in prefs:
                content = p.get("content", {})
                pref_dict[content.get("key", "")] = content.get("value")
            enriched["user_preferences"] = pref_dict

            # Inject evolved weights for quality scoring (active phase only).
            evolved_weights = {}
            for k, v in pref_dict.items():
                if not isinstance(k, str):
                    continue
                if not k.startswith("evolved.weight."):
                    continue
                dim = k.replace("evolved.weight.", "", 1)
                try:
                    evolved_weights[dim] = float(v)
                except (TypeError, ValueError):
                    continue
            if evolved_weights:
                enriched["evolved_weights"] = evolved_weights

        # Get relevant patterns
        genre = user_input.get("genre", "")
        patterns = self.memory.get_top_patterns(genre=genre, limit=5)
        if patterns:
            enriched["suggested_patterns"] = [
                p.get("content", {}).get("template", "") for p in patterns
            ]

        # Apply learned corrections
        if "prompt" in enriched:
            enriched["prompt"] = self.learner.apply_learned_corrections(
                enriched["prompt"])

        # Rule check
        request_text = user_input.get("prompt", "") or user_input.get("text", "")
        if request_text:
            verdicts = self.rules.check_request(request_text)
            if verdicts:
                enriched["rule_verdicts"] = [v.to_dict() for v in verdicts]
                if self.rules.has_hard_deny(verdicts):
                    enriched["blocked"] = True
                    enriched["block_reason"] = self.rules.generate_pushback(verdicts)

        self.logger.log("pre_process", {
            "has_preferences": bool(prefs),
            "has_patterns": bool(patterns),
            "blocked": enriched.get("blocked", False),
        })
        return enriched

    def post_process(self, output: Dict,
                     quality_report: QualityReport) -> Dict:
        """After generation: learn, archive, scrub, log."""
        # Learn patterns
        storyboard = output.get("storyboard", {})
        if storyboard:
            self.learner.analyze_generation(storyboard, quality_report)

        # Archive if high quality
        archive_id = self.learner.maybe_archive(output, quality_report)

        # Micro scorer: compare with peers and update ELO.
        scoreboard = self.scorer.process_generation(
            storyboard=storyboard,
            quality_report=quality_report,
            genre=output.get("genre", ""),
            platform=output.get("platform", ""),
            duration_seconds=float(
                storyboard.get("metadata", {}).get("estimated_duration", 0.0)
            ),
            archive_id=archive_id or "",
        )
        quality_report.comparison_summary = scoreboard
        quality_report.elo_ratings = self.scorer.get_elo_ratings()

        # Build evolved preferences from comparisons and persist as preferences.
        comps = self.scorer.get_recent_comparisons(limit=500)
        prefs = self.pref_former.build_preferences(comps)
        phase = self.scorer.get_state().get("phase", "shadow")
        if phase == "active" and prefs:
            base = {
                d: 1.0 / len(self.pref_former.DIMENSIONS)
                for d in self.pref_former.DIMENSIONS
            }
            active_w = self.pref_former.derive_weights(base, prefs)
            quality_report.active_weights = active_w
            for dim, w in active_w.items():
                self.memory.set_preference(
                    key=f"evolved.weight.{dim}",
                    value=round(float(w), 6),
                    confidence=0.6,
                )
            for dim, item in prefs.items():
                self.memory.set_preference(
                    key=f"evolved.pref.{dim}",
                    value={
                        "direction": item.get("direction", "neutral"),
                        "strength": item.get("strength", 0.0),
                        "confidence": item.get("confidence", 0.0),
                        "comparison_count": item.get("comparison_count", 0),
                    },
                    confidence=float(item.get("confidence", 0.0)),
                )

        # Run maintenance (decay, compression, conflict resolution)
        self.memory.run_maintenance()

        # Log
        self.logger.log("post_process", {
            "quality_score": quality_report.overall_score,
            "archived": quality_report.overall_score >= 0.85,
            "scoring_phase": scoreboard.get("phase", "shadow"),
            "scoring_compared": scoreboard.get("compared", False),
        })
        return output

    # ------------------------------------------------------------------
    # /evolve command handlers
    # ------------------------------------------------------------------

    def handle_command(self, command: str) -> str:
        """Entry point for /evolve commands."""
        action, params = self.triggers.parse(command)
        return self.triggers.dispatch(action, params)

    def status(self) -> str:
        mem_stats = self.memory.get_stats()
        snaps = self.snapshots.list_snapshots()
        recent = self.logger.get_recent(5)
        lines = [
            f"📊 进化系统 v{self.VERSION}",
            f"运行环境: {self.env.runtime} ({'降级模式' if self.env.degraded else '正常'})",
            f"记忆条目: {sum(mem_stats.values())} "
            f"(偏好:{mem_stats['preferences']}, "
            f"纠错:{mem_stats['corrections']}, "
            f"模式:{mem_stats['patterns']})",
            f"归档作品: {mem_stats['archives']}",
            f"快照数: {len(snaps)}",
            "",
            "最近事件:",
        ]
        for e in recent:
            lines.append(f"  [{e.get('timestamp', '?')[:19]}] {e.get('event_type', '?')}")
        return "\n".join(lines)

    def force_learn(self) -> str:
        archives = self.memory.get_archived_examples(limit=3)
        if not archives:
            return "暂无可学习的归档内容"
        count = 0
        for a in archives:
            storyboard = a.get("output", {}).get("storyboard", {})
            if storyboard:
                report = QualityReport(
                    overall_score=a.get("score", 0.8),
                    scela_score=a.get("score", 0.8),
                )
                patterns = self.learner.analyze_generation(storyboard, report)
                count += len(patterns)
        return f"从 {len(archives)} 个归档中提取了 {count} 个模式"

    def rollback(self, snapshot_id: str = None) -> str:
        if not snapshot_id:
            snaps = self.snapshots.list_snapshots()
            if not snaps:
                return "暂无可用快照"
            lines = ["可用快照："]
            for s in snaps[:10]:
                lines.append(
                    f"  {s.snapshot_id} | {s.timestamp[:19]} | {s.trigger}")
            lines.append("\n使用: /evolve rollback <snapshot_id>")
            return "\n".join(lines)
        result = self.snapshots.rollback(snapshot_id)
        if result.get("ok"):
            return f"已回滚到快照 {snapshot_id}"
        return f"回滚失败: {result.get('error', 'unknown')}"

    def show_memory(self) -> str:
        stats = self.memory.get_stats()
        prefs = self.memory.get_all_preferences()
        lines = [f"📝 记忆系统状态: {json.dumps(stats, ensure_ascii=False)}"]
        if prefs:
            lines.append("\n偏好设置:")
            for p in prefs[:10]:
                c = p.get("content", {})
                lines.append(f"  {c.get('key')}: {c.get('value')} "
                             f"(置信度: {c.get('confidence', 0)})")
        return "\n".join(lines)

    def show_scores(self) -> str:
        state = self.scorer.get_state()
        elo = self.scorer.get_elo_ratings()
        lines = [
            "🏁 微分差评分状态",
            f"phase: {state.get('phase', 'shadow')}",
            f"generation_count: {state.get('generation_count', 0)}",
            f"comparisons_count: {state.get('comparisons_count', 0)}",
            "",
            "ELO:",
        ]
        for k in sorted(elo.keys()):
            lines.append(f"  {k}: {elo[k]}")
        return "\n".join(lines)

    def show_evolved_preferences(self) -> str:
        prefs = self.memory.get_all_preferences()
        evolved = []
        for p in prefs:
            c = p.get("content", {})
            key = c.get("key", "")
            if isinstance(key, str) and key.startswith("evolved."):
                evolved.append((key, c.get("value"), c.get("confidence", 0)))
        if not evolved:
            return "暂无已形成的进化偏好"
        lines = ["🧠 进化偏好："]
        for key, value, conf in sorted(evolved):
            lines.append(f"  {key}: {value} (置信度: {conf})")
        return "\n".join(lines)

    def compare_with_archive(self, archive_id: str) -> str:
        result = self.scorer.compare_with_archive_id(archive_id)
        if not result.get("ok"):
            return f"比较失败: {result.get('reason', 'unknown')}"
        return (
            "手动比较完成: "
            f"challenger={result.get('challenger')} "
            f"opponent={result.get('opponent')} "
            f"wins={result.get('wins')} losses={result.get('losses')} ties={result.get('ties')}"
        )

    def scorer_reset(self) -> str:
        self.scorer.reset()
        return "✅ 评分历史已重置（保留普通记忆）"

    def scorer_calibrate(self) -> str:
        result = self.scorer.calibrate()
        return f"✅ 评分校准完成，重放比较记录: {result.get('comparisons', 0)}"

    def health_check(self) -> str:
        integrity = self.repair.check_integrity()
        if integrity["ok"]:
            return f"✅ 系统健康 ({integrity['healthy']}/{integrity['checked']} 文件正常)"
        lines = [f"⚠️ 发现问题 ({integrity['healthy']}/{integrity['checked']} 文件正常)"]
        if integrity["missing"]:
            lines.append(f"  缺失: {', '.join(integrity['missing'])}")
        if integrity["corrupted"]:
            lines.append(f"  损坏: {', '.join(integrity['corrupted'])}")
        return "\n".join(lines)

    def export_package(self, **kwargs) -> str:
        result = self.packager.package(**{
            k: v for k, v in kwargs.items()
            if k in ("output_path", "fmt", "include_memory")
        })
        if result.get("ok"):
            return f"📦 打包完成: {result['path']} ({result['files']} 文件)"
        return f"打包失败: {result.get('reason', 'unknown')}"

    def show_log(self, n: int = 10) -> str:
        entries = self.logger.get_recent(n)
        if not entries:
            return "暂无日志"
        return self.logger.format_human_readable(entries)

    def reset(self, confirm: bool = False) -> str:
        if not confirm:
            return "⚠️ 此操作将清除所有进化数据。使用 /evolve reset --confirm 确认。"
        # Create final snapshot before reset
        self.snapshots.create_snapshot(trigger="pre_reset")
        import shutil
        for sub in ["memory", "archive", "logs"]:
            d = self.data_dir / sub
            if d.exists():
                shutil.rmtree(str(d), ignore_errors=True)
                d.mkdir(parents=True, exist_ok=True)
        scores = self.data_dir / "scores"
        if scores.exists():
            shutil.rmtree(str(scores), ignore_errors=True)
        scores.mkdir(parents=True, exist_ok=True)
        self.logger.log("reset", {"operator": "user"})
        return "✅ 进化数据已重置。快照已保留用于恢复。"

    # ------------------------------------------------------------------
    # Heartbeat (P1-D: 72h passive check)
    # ------------------------------------------------------------------

    def _check_heartbeat(self) -> None:
        """Passive heartbeat: check if 72h have passed since last check."""
        state = self._load_heartbeat()
        now = datetime.now(timezone.utc)
        try:
            last = datetime.fromisoformat(state.last_checked_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            last = now

        hours_since = (now - last).total_seconds() / 3600
        if hours_since < self.HEARTBEAT_INTERVAL_HOURS:
            return

        # Check with exponential backoff on failure
        if state.consecutive_failures > 0:
            backoff = min(
                2 ** state.consecutive_failures * 60,
                self.MAX_BACKOFF_SECONDS,
            )
            if (now - last).total_seconds() < backoff:
                return

        # Run health check
        integrity = self.repair.check_integrity()
        state.check_count += 1
        state.last_checked_at = _now_iso()

        if integrity["ok"]:
            state.consecutive_failures = 0
            state.next_backoff_seconds = 0
        else:
            state.consecutive_failures += 1
            state.next_backoff_seconds = min(
                2 ** state.consecutive_failures * 60,
                self.MAX_BACKOFF_SECONDS,
            )
            self.logger.log("heartbeat_failure", {
                "integrity": integrity,
                "consecutive_failures": state.consecutive_failures,
                "next_backoff": state.next_backoff_seconds,
            })

        self._save_heartbeat(state)

    def _load_heartbeat(self) -> HeartbeatState:
        data = AtomicFileOps.read_json(self._heartbeat_file)
        if not data:
            return HeartbeatState()
        return HeartbeatState(**{
            k: v for k, v in data.items()
            if k in HeartbeatState.__dataclass_fields__
        })

    def _save_heartbeat(self, state: HeartbeatState) -> None:
        AtomicFileOps.write_json(self._heartbeat_file, state.to_dict())
