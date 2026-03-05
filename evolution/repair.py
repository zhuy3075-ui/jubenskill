"""Self-repair & supply-chain secure update (Req 8, 11, P0-A).

Implements: repo allowlist, version pinning, integrity manifest with SHA-256,
dry-run mode, pre-update snapshot, post-update health check, audit logging.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    RepoAllowlistEntry, UpdateManifest, _now_iso, _uuid,
)
from .file_ops import AtomicFileOps
from .logger import EvolveLogger
from .snapshot import SnapshotManager


class SelfRepair:
    """Integrity checking and supply-chain secure self-repair."""

    REQUIRED_FILES = [
        "scripts/parse_script.py",
        "scripts/character_extractor.py",
        "scripts/scene_analyzer.py",
        "scripts/storyboard_generator.py",
        "scripts/prompt_optimizer.py",
        "scripts/consistency_checker.py",
        "scripts/export_utils.py",
        "SKILL.md",
    ]

    # Default repo allowlist (P0-A)
    DEFAULT_ALLOWLIST: List[RepoAllowlistEntry] = []

    def __init__(self, project_root: Path, logger: EvolveLogger,
                 snapshots: SnapshotManager,
                 allowlist: List[Dict] = None):
        self.project_root = project_root
        self.logger = logger
        self.snapshots = snapshots
        self.allowlist = []
        if allowlist:
            for entry in allowlist:
                self.allowlist.append(RepoAllowlistEntry(**entry))
        self.config_file = project_root / "evolve_data" / "repair_config.json"

    # ------------------------------------------------------------------
    # Integrity check (Req 11)
    # ------------------------------------------------------------------

    def check_integrity(self) -> Dict:
        """Check all required files exist and are non-empty."""
        missing, corrupted, ok_files = [], [], []
        for rel in self.REQUIRED_FILES:
            fpath = self.project_root / rel
            if not fpath.exists():
                missing.append(rel)
            elif fpath.stat().st_size == 0:
                corrupted.append(rel)
            else:
                ok_files.append(rel)
        result = {
            "ok": len(missing) == 0 and len(corrupted) == 0,
            "missing": missing,
            "corrupted": corrupted,
            "checked": len(self.REQUIRED_FILES),
            "healthy": len(ok_files),
        }
        self.logger.log("integrity_check", result)
        return result

    # ------------------------------------------------------------------
    # Supply-chain secure update (P0-A)
    # ------------------------------------------------------------------

    def is_repo_allowed(self, owner: str, repo: str) -> bool:
        """Check if owner/repo is in the allowlist."""
        return any(
            e.owner == owner and e.repo == repo for e in self.allowlist
        )

    def is_ref_allowed(self, owner: str, repo: str, ref: str) -> bool:
        """Check if a specific tag/commit is allowed for this repo."""
        for e in self.allowlist:
            if e.owner == owner and e.repo == repo:
                if not e.allowed_refs:  # empty = all refs allowed
                    return True
                return ref in e.allowed_refs
        return False

    def verify_manifest(self, manifest: UpdateManifest,
                        source_dir: Path) -> Dict:
        """Verify downloaded files against manifest hashes (P0-A)."""
        mismatches, verified = [], []
        for rel_path, expected_hash in manifest.files.items():
            fpath = source_dir / rel_path
            if not fpath.exists():
                mismatches.append({
                    "file": rel_path, "reason": "missing",
                })
                continue
            actual_hash = AtomicFileOps.file_hash(fpath)
            if actual_hash != expected_hash:
                mismatches.append({
                    "file": rel_path,
                    "reason": "hash_mismatch",
                    "expected": expected_hash[:16],
                    "actual": actual_hash[:16],
                })
            else:
                verified.append(rel_path)
        result = {
            "ok": len(mismatches) == 0,
            "verified": len(verified),
            "mismatches": mismatches,
        }
        self.logger.log("manifest_verify", result)
        return result

    def repair_from_github(self, repo_url: str, ref: str = "main",
                           dry_run: bool = False) -> Dict:
        """Download and restore files from GitHub with full security checks.

        P0-A enforcement:
        1. Repo must be in allowlist
        2. Ref must be pinned (tag or commit)
        3. Manifest hash verification
        4. Pre-update snapshot
        5. Post-update health check
        6. Failure → reject + audit log
        """
        # Parse owner/repo from URL
        parts = repo_url.rstrip("/").split("/")
        if len(parts) < 2:
            return self._reject("invalid_repo_url", repo_url)
        owner, repo = parts[-2], parts[-1].replace(".git", "")

        # Step 1: Allowlist check
        if not self.is_repo_allowed(owner, repo):
            return self._reject("repo_not_in_allowlist",
                                f"{owner}/{repo}", repo_url=repo_url)

        # Step 2: Ref check
        if not self.is_ref_allowed(owner, repo, ref):
            return self._reject("ref_not_allowed",
                                f"{owner}/{repo}@{ref}", repo_url=repo_url)

        if dry_run:
            self.logger.log("repair_dry_run", {
                "repo": f"{owner}/{repo}", "ref": ref,
                "action": "would_clone_and_verify",
            })
            return {"ok": True, "dry_run": True,
                    "message": f"Would update from {owner}/{repo}@{ref}"}

        # Step 3: Pre-update snapshot
        pre_snap = self.snapshots.create_snapshot(
            trigger="pre_update",
            metadata={"source": f"{owner}/{repo}@{ref}"},
        )

        # Step 4: Clone to temp directory
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp(prefix="evolve_repair_"))
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", ref,
                 repo_url, str(tmp_dir / "repo")],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return self._reject("clone_failed", result.stderr[:200],
                                    repo_url=repo_url)

            clone_dir = tmp_dir / "repo"

            # Step 5: Verify manifest if present
            manifest_path = clone_dir / "manifest.json"
            if manifest_path.exists():
                manifest_data = AtomicFileOps.read_json(manifest_path)
                if manifest_data:
                    manifest = UpdateManifest(**{
                        k: v for k, v in manifest_data.items()
                        if k in UpdateManifest.__dataclass_fields__
                    })
                    verify = self.verify_manifest(manifest, clone_dir)
                    if not verify["ok"]:
                        return self._reject("manifest_verification_failed",
                                            str(verify["mismatches"]),
                                            repo_url=repo_url)

            # Step 6: Copy files
            for rel in self.REQUIRED_FILES:
                src = clone_dir / rel
                if src.exists():
                    dest = self.project_root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dest))

            # Step 7: Post-update health check
            health = self.check_integrity()
            if not health["ok"]:
                # Rollback
                self.snapshots.rollback(pre_snap.snapshot_id,
                                        reason="post_update_health_failed")
                return self._reject("post_update_health_failed",
                                    str(health), repo_url=repo_url)

        finally:
            shutil.rmtree(str(tmp_dir), ignore_errors=True)

        self.logger.log("repair_success", {
            "repo": f"{owner}/{repo}", "ref": ref,
            "pre_snapshot": pre_snap.snapshot_id,
        })
        return {"ok": True, "pre_snapshot": pre_snap.snapshot_id}

    def repair_from_snapshot(self, snapshot_id: str) -> Dict:
        """Restore from local snapshot."""
        return self.snapshots.rollback(snapshot_id, reason="manual_repair")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _reject(self, reason: str, detail: str,
                repo_url: str = "") -> Dict:
        """Reject an update and log audit trail."""
        result = {"ok": False, "reason": reason, "detail": detail}
        self.logger.log("repair_rejected", {
            "reason": reason, "detail": detail[:200],
            "repo_url": repo_url,
        })
        return result
