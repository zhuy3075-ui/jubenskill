"""Pattern learner — prompt analysis, reflection, archiving (Req 4, 5, 6).

Analyzes generation results to extract successful patterns, reflects on
corrections to prevent repeat mistakes, and archives high-quality outputs.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .models import (
    CorrectionRecord, PromptPattern, QualityReport, _uuid, _now_iso,
)
from .logger import EvolveLogger
from .memory import MemoryStore


class PatternLearner:
    """Active learning from generation results and user corrections."""

    # Common prompt structure patterns to extract
    PATTERN_MARKERS = [
        re.compile(r"([\w\s]+),\s*([\w\s]+shot),\s*([\w\s]+)"),  # subject, shot, style
        re.compile(r"(cinematic|dramatic|soft|warm|cold)\s+\w+"),
        re.compile(r"(slow\s+motion|time\s*lapse|tracking\s+shot)"),
    ]

    def __init__(self, memory: MemoryStore, logger: EvolveLogger):
        self.memory = memory
        self.logger = logger

    # ------------------------------------------------------------------
    # Prompt pattern analysis (Req 4)
    # ------------------------------------------------------------------

    def analyze_generation(self, storyboard: Dict,
                           quality_report: QualityReport) -> List[PromptPattern]:
        """After generation, extract successful patterns from high-scoring prompts."""
        extracted = []
        shots = storyboard.get("shots", [])
        for shot in shots:
            prompt = shot.get("optimized_prompt") or shot.get("visual_prompt", "")
            if not prompt:
                continue
            score = quality_report.scela_score
            if score < 0.6:
                continue
            # Extract structural patterns
            for marker in self.PATTERN_MARKERS:
                match = marker.search(prompt)
                if match:
                    template = match.group(0)
                    pattern = PromptPattern(
                        pattern_id=_uuid(),
                        template=template,
                        score=score,
                        genre=storyboard.get("metadata", {}).get("genre", ""),
                        usage_count=1,
                        success_rate=score,
                    )
                    self.memory.add_pattern(pattern)
                    extracted.append(pattern)
        if extracted:
            self.logger.log("patterns_extracted", {
                "count": len(extracted),
                "avg_score": round(
                    sum(p.score for p in extracted) / len(extracted), 3),
            })
        return extracted

    # ------------------------------------------------------------------
    # Reflection & correction (Req 5)
    # ------------------------------------------------------------------

    def reflect_on_correction(self, original: str, corrected: str,
                               context: Dict = None) -> CorrectionRecord:
        """Analyze WHY the original was wrong, generate a preventive rule."""
        # Diff analysis
        orig_words = set(original.lower().split())
        corr_words = set(corrected.lower().split())
        added = corr_words - orig_words
        removed = orig_words - corr_words

        reflection_parts = []
        if removed:
            reflection_parts.append(f"错误包含: {', '.join(list(removed)[:5])}")
        if added:
            reflection_parts.append(f"应补充: {', '.join(list(added)[:5])}")
        reflection = "; ".join(reflection_parts) or "用户修正了输出内容"

        # Generate preventive rule
        rule_parts = []
        if removed:
            rule_parts.append(f"避免使用: {', '.join(list(removed)[:3])}")
        if added:
            rule_parts.append(f"优先使用: {', '.join(list(added)[:3])}")
        rule = "; ".join(rule_parts) or "遵循用户修正偏好"

        record = CorrectionRecord(
            id=_uuid(),
            original_output=original[:500],
            user_correction=corrected[:500],
            reflection=reflection,
            rule_extracted=rule,
        )
        self.memory.add_correction(record)
        self.logger.log("reflection", {
            "correction_id": record.id,
            "reflection": reflection[:200],
            "rule": rule[:200],
        })
        return record

    def apply_learned_corrections(self, prompt: str) -> str:
        """Apply stored correction rules to a new prompt before generation."""
        corrections = self.memory.find_relevant_corrections(prompt)
        result = prompt
        for c in corrections:
            rule = c.get("content", {}).get("rule_extracted", "")
            # Simple keyword avoidance
            avoid_match = re.search(r"避免使用:\s*(.+?)(?:;|$)", rule)
            if avoid_match:
                for word in avoid_match.group(1).split(","):
                    word = word.strip()
                    if word and word in result:
                        result = result.replace(word, "")
        return result.strip()

    # ------------------------------------------------------------------
    # Archiving (Req 6)
    # ------------------------------------------------------------------

    def maybe_archive(self, output: Dict,
                      quality_report: QualityReport) -> Optional[str]:
        """Archive output if score > ARCHIVE_THRESHOLD."""
        if quality_report.overall_score < 0.85:
            return None
        title = output.get("storyboard", {}).get("title", "untitled")
        return self.memory.archive_output(
            output, quality_report.overall_score, title)
