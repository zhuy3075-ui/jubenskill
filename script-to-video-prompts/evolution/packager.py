"""One-click packaging for distribution (Req 9).

Creates zip/tar archives with pre-distribution sensitive content scanning.
Blocks packaging if sensitive content is detected (P0-C).
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Dict, List

from .models import _now_iso
from .file_ops import AtomicFileOps
from .logger import EvolveLogger
from .security import SecurityGuard


class Packager:
    """Package the skill for distribution."""

    EXCLUDE_PATTERNS = {
        "__pycache__", "*.pyc", ".git", ".claude",
        "evolve_data/snapshots", "*.tmp", "*.lock",
    }

    def __init__(self, project_root: Path, logger: EvolveLogger,
                 security: SecurityGuard):
        self.project_root = project_root
        self.logger = logger
        self.security = security

    def package(self, output_path: str = None, fmt: str = "zip",
                include_memory: bool = False) -> Dict:
        """Create distribution package.

        P0-C: Runs sensitive content scan before packaging.
        Blocks if sensitive content is found.
        """
        # Step 1: Pre-scan for sensitive content
        scan_results = self.security.scan_directory(self.project_root)
        blocked = [r for r in scan_results if r.get("blocked")]
        if blocked:
            self.logger.log("package_blocked", {
                "reason": "sensitive_content_detected",
                "findings": blocked[:10],
            })
            return {
                "ok": False,
                "reason": "sensitive_content_detected",
                "findings": blocked,
            }

        # Step 2: Collect files
        files = self._collect_files(include_memory)

        # Step 3: Create archive
        if not output_path:
            output_path = str(
                self.project_root.parent /
                f"script-to-video-prompts-{_now_iso()[:10]}.{fmt}"
            )

        tmp_dir = Path(tempfile.mkdtemp(prefix="evolve_pkg_"))
        try:
            # Copy files to staging
            for f in files:
                rel = f.relative_to(self.project_root)
                dest = tmp_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(f), str(dest))

            # Create archive
            if fmt == "zip":
                archive = shutil.make_archive(
                    output_path.replace(".zip", ""), "zip", str(tmp_dir))
            else:
                archive = shutil.make_archive(
                    output_path.replace(".tar.gz", ""), "gztar", str(tmp_dir))
        finally:
            shutil.rmtree(str(tmp_dir), ignore_errors=True)

        self.logger.log("package_created", {
            "path": archive, "files": len(files), "format": fmt,
        })
        return {"ok": True, "path": archive, "files": len(files)}

    def _collect_files(self, include_memory: bool) -> List[Path]:
        files = []
        for f in self.project_root.rglob("*"):
            if not f.is_file():
                continue
            rel = str(f.relative_to(self.project_root))
            # Check exclusions
            skip = False
            for pattern in self.EXCLUDE_PATTERNS:
                if pattern.startswith("*"):
                    if f.suffix == pattern[1:]:
                        skip = True
                        break
                elif pattern in rel:
                    skip = True
                    break
            if skip:
                continue
            if not include_memory and "evolve_data" in rel:
                continue
            files.append(f)
        return files
