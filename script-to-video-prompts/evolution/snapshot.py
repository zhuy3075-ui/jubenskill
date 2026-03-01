"""Transactional snapshot & rollback system (Req 12, P0-B).

Supports: global file lock, prepare/commit two-phase recovery,
failure auto-rollback, post-rollback consistency verification.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .models import Snapshot, _now_iso, _uuid
from .file_ops import AtomicFileOps
from .logger import EvolveLogger


class SnapshotManager:
    """Version snapshots with transactional semantics."""

    MAX_SNAPSHOTS = 20
    # Directories to snapshot (relative to project root)
    SNAPSHOT_DIRS = ["scripts", "evolution", "references", "assets"]
    SNAPSHOT_FILES = ["SKILL.md", "requirements.txt"]
    # Never snapshot these
    EXCLUDE_DIRS = {"evolve_data", "__pycache__", ".git", "node_modules"}

    def __init__(self, snapshot_dir: Path, project_root: Path,
                 logger: EvolveLogger):
        self.snapshot_dir = snapshot_dir
        self.project_root = project_root
        self.logger = logger
        self.lock_file = snapshot_dir / ".snapshot.lock"
        AtomicFileOps.ensure_dir(snapshot_dir)

    # ------------------------------------------------------------------
    # Create snapshot
    # ------------------------------------------------------------------

    def create_snapshot(self, trigger: str = "manual",
                        metadata: Optional[Dict] = None) -> Snapshot:
        """Create a full snapshot of project files (excluding evolve_data/)."""
        sid = _uuid()
        snap_path = self.snapshot_dir / sid

        with AtomicFileOps.file_lock(self.lock_file):
            # Phase 1: PREPARE — copy files to staging area
            staging = self.snapshot_dir / f".staging_{sid}"
            staging.mkdir(parents=True, exist_ok=True)
            files_dir = staging / "files"
            files_dir.mkdir()

            file_hashes = {}
            try:
                for item in self._collect_project_files():
                    rel = item.relative_to(self.project_root)
                    dest = files_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(item), str(dest))
                    file_hashes[str(rel)] = AtomicFileOps.file_hash(item)
            except Exception as e:
                # PREPARE failed — clean up staging
                shutil.rmtree(str(staging), ignore_errors=True)
                self.logger.log("snapshot_error", {
                    "phase": "prepare", "error": str(e), "snapshot_id": sid,
                })
                raise

            # Write manifest
            snap = Snapshot(
                snapshot_id=sid,
                timestamp=_now_iso(),
                trigger=trigger,
                files=file_hashes,
                metadata=metadata or {},
            )
            AtomicFileOps.write_json(staging / "manifest.json", snap.to_dict())

            # Phase 2: COMMIT — atomic rename staging → final
            try:
                staging.rename(snap_path)
            except Exception as e:
                shutil.rmtree(str(staging), ignore_errors=True)
                self.logger.log("snapshot_error", {
                    "phase": "commit", "error": str(e), "snapshot_id": sid,
                })
                raise

        self._cleanup_old_snapshots()
        self.logger.log("snapshot_create", {
            "snapshot_id": sid, "trigger": trigger,
            "file_count": len(file_hashes),
        })
        return snap

    # ------------------------------------------------------------------
    # List / get snapshots
    # ------------------------------------------------------------------

    def list_snapshots(self) -> List[Snapshot]:
        """List all snapshots, newest first."""
        snaps = []
        for d in self.snapshot_dir.iterdir():
            if not d.is_dir() or d.name.startswith("."):
                continue
            manifest = d / "manifest.json"
            data = AtomicFileOps.read_json(manifest)
            if data:
                snaps.append(Snapshot(**{
                    k: v for k, v in data.items()
                    if k in Snapshot.__dataclass_fields__
                }))
        snaps.sort(key=lambda s: s.timestamp, reverse=True)
        return snaps

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        manifest = self.snapshot_dir / snapshot_id / "manifest.json"
        data = AtomicFileOps.read_json(manifest)
        if not data:
            return None
        return Snapshot(**{
            k: v for k, v in data.items()
            if k in Snapshot.__dataclass_fields__
        })

    # ------------------------------------------------------------------
    # Rollback (P0-B: two-phase with consistency check)
    # ------------------------------------------------------------------

    def rollback(self, snapshot_id: str, operator: str = "user",
                 reason: str = "") -> Dict:
        """Rollback to a specific snapshot.

        1. Creates a pre-rollback snapshot
        2. Restores files from target snapshot
        3. Verifies consistency (hash check)
        4. If verification fails, auto-rollback to pre-rollback snapshot
        """
        target = self.get_snapshot(snapshot_id)
        if not target:
            return {"ok": False, "error": f"snapshot {snapshot_id} not found"}

        target_dir = self.snapshot_dir / snapshot_id / "files"
        if not target_dir.exists():
            return {"ok": False, "error": "snapshot files directory missing"}

        # Capture before-state hashes
        before_hashes = {}
        for item in self._collect_project_files():
            rel = str(item.relative_to(self.project_root))
            before_hashes[rel] = AtomicFileOps.file_hash(item)

        # Step 1: Create pre-rollback snapshot
        pre_snap = self.create_snapshot(
            trigger="pre_rollback",
            metadata={"rollback_target": snapshot_id},
        )

        with AtomicFileOps.file_lock(self.lock_file):
            try:
                # Step 2: Restore files
                for rel_path, expected_hash in target.files.items():
                    src = target_dir / rel_path
                    dest = self.project_root / rel_path
                    if src.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(src), str(dest))

                # Step 3: Verify consistency
                verification = self._verify_consistency(target)
                if not verification["ok"]:
                    # Step 4: Auto-rollback to pre-rollback state
                    self._restore_from(pre_snap.snapshot_id)
                    self.logger.log("rollback_failed", {
                        "target": snapshot_id,
                        "reason": "consistency_check_failed",
                        "mismatches": verification.get("mismatches", []),
                        "auto_restored_to": pre_snap.snapshot_id,
                    }, operator=operator)
                    return {
                        "ok": False,
                        "error": "consistency check failed, auto-restored",
                        "restored_to": pre_snap.snapshot_id,
                    }
            except Exception as e:
                # Restore from pre-rollback snapshot on any error
                try:
                    self._restore_from(pre_snap.snapshot_id)
                except Exception:
                    pass
                self.logger.log("rollback_error", {
                    "target": snapshot_id, "error": str(e),
                }, operator=operator)
                return {"ok": False, "error": str(e)}

        # Capture after-state hashes
        after_hashes = {}
        for item in self._collect_project_files():
            rel = str(item.relative_to(self.project_root))
            after_hashes[rel] = AtomicFileOps.file_hash(item)

        # Audit log with full before/after
        self.logger.log("rollback", {
            "snapshot_id": snapshot_id,
            "operator": operator,
            "reason": reason,
            "before_hash": AtomicFileOps.data_hash(before_hashes),
            "after_hash": AtomicFileOps.data_hash(after_hashes),
            "pre_rollback_snapshot": pre_snap.snapshot_id,
        }, before={"file_hashes": before_hashes},
           after={"file_hashes": after_hashes},
           operator=operator)

        return {"ok": True, "snapshot_id": snapshot_id,
                "pre_rollback": pre_snap.snapshot_id}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_project_files(self) -> List[Path]:
        """Collect all project files eligible for snapshot."""
        files = []
        for d in self.SNAPSHOT_DIRS:
            dp = self.project_root / d
            if dp.exists():
                for f in dp.rglob("*"):
                    if f.is_file() and not any(
                        ex in f.parts for ex in self.EXCLUDE_DIRS
                    ):
                        files.append(f)
        for fname in self.SNAPSHOT_FILES:
            fp = self.project_root / fname
            if fp.exists():
                files.append(fp)
        return files

    def _verify_consistency(self, snap: Snapshot) -> Dict:
        """Verify current files match snapshot hashes."""
        mismatches = []
        for rel_path, expected in snap.files.items():
            actual_path = self.project_root / rel_path
            if not actual_path.exists():
                mismatches.append({"file": rel_path, "reason": "missing"})
                continue
            actual_hash = AtomicFileOps.file_hash(actual_path)
            if actual_hash != expected:
                mismatches.append({
                    "file": rel_path,
                    "reason": "hash_mismatch",
                    "expected": expected[:12],
                    "actual": actual_hash[:12],
                })
        return {"ok": len(mismatches) == 0, "mismatches": mismatches}

    def _restore_from(self, snapshot_id: str) -> None:
        """Low-level restore without creating another snapshot."""
        files_dir = self.snapshot_dir / snapshot_id / "files"
        if not files_dir.exists():
            raise FileNotFoundError(f"snapshot {snapshot_id} files missing")
        for f in files_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(files_dir)
                dest = self.project_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(f), str(dest))

    def _cleanup_old_snapshots(self) -> None:
        """Remove oldest snapshots beyond MAX_SNAPSHOTS."""
        snaps = self.list_snapshots()
        if len(snaps) <= self.MAX_SNAPSHOTS:
            return
        for old in snaps[self.MAX_SNAPSHOTS:]:
            old_dir = self.snapshot_dir / old.snapshot_id
            if old_dir.exists():
                shutil.rmtree(str(old_dir), ignore_errors=True)
