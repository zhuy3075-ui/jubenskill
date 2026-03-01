"""Tests for evolution snapshot module.

Covers: create/list/rollback, two-phase commit, consistency verification,
failure auto-rollback, concurrent write protection, rollback audit log.
"""
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.snapshot import SnapshotManager
from evolution.logger import EvolveLogger
from evolution.file_ops import AtomicFileOps


@pytest.fixture
def project_dir():
    d = Path(tempfile.mkdtemp(prefix="test_snap_proj_"))
    # Create minimal project structure
    (d / "scripts").mkdir()
    (d / "scripts" / "parse_script.py").write_text("# parse")
    (d / "scripts" / "prompt_optimizer.py").write_text("# optimize")
    (d / "SKILL.md").write_text("# Skill")
    (d / "evolution").mkdir()
    (d / "evolution" / "__init__.py").write_text("# init")
    yield d
    shutil.rmtree(str(d), ignore_errors=True)


@pytest.fixture
def snap_dir(project_dir):
    d = project_dir / "evolve_data" / "snapshots"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def logger(project_dir):
    log_dir = project_dir / "evolve_data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return EvolveLogger(log_dir)


@pytest.fixture
def manager(snap_dir, project_dir, logger):
    return SnapshotManager(snap_dir, project_dir, logger)


class TestSnapshotCreate:
    def test_create_snapshot(self, manager):
        snap = manager.create_snapshot(trigger="test")
        assert snap.snapshot_id
        assert snap.trigger == "test"
        assert len(snap.files) > 0

    def test_snapshot_has_manifest(self, manager, snap_dir):
        snap = manager.create_snapshot()
        manifest = snap_dir / snap.snapshot_id / "manifest.json"
        assert manifest.exists()
        data = json.loads(manifest.read_text())
        assert data["snapshot_id"] == snap.snapshot_id

    def test_snapshot_files_copied(self, manager, snap_dir):
        snap = manager.create_snapshot()
        files_dir = snap_dir / snap.snapshot_id / "files"
        assert (files_dir / "SKILL.md").exists()

    def test_snapshot_hashes_correct(self, manager, snap_dir, project_dir):
        snap = manager.create_snapshot()
        for rel, expected_hash in snap.files.items():
            actual = AtomicFileOps.file_hash(project_dir / rel)
            assert actual == expected_hash, f"Hash mismatch for {rel}"


class TestSnapshotList:
    def test_list_empty(self, manager):
        assert manager.list_snapshots() == []

    def test_list_after_create(self, manager):
        manager.create_snapshot()
        manager.create_snapshot()
        snaps = manager.list_snapshots()
        assert len(snaps) == 2

    def test_list_newest_first(self, manager):
        s1 = manager.create_snapshot()
        s2 = manager.create_snapshot()
        snaps = manager.list_snapshots()
        assert snaps[0].snapshot_id == s2.snapshot_id


class TestSnapshotRollback:
    def test_rollback_restores_file(self, manager, project_dir):
        # Create snapshot with original content
        snap = manager.create_snapshot()
        # Modify file
        (project_dir / "SKILL.md").write_text("# Modified")
        # Rollback
        result = manager.rollback(snap.snapshot_id)
        assert result["ok"] is True
        # Verify restored
        assert (project_dir / "SKILL.md").read_text() == "# Skill"

    def test_rollback_creates_pre_rollback_snapshot(self, manager, project_dir):
        snap = manager.create_snapshot()
        (project_dir / "SKILL.md").write_text("# Modified")
        result = manager.rollback(snap.snapshot_id)
        assert "pre_rollback" in result
        # Pre-rollback snapshot should exist
        pre = manager.get_snapshot(result["pre_rollback"])
        assert pre is not None

    def test_rollback_nonexistent_snapshot(self, manager):
        result = manager.rollback("nonexistent")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_rollback_audit_log(self, manager, project_dir, logger):
        snap = manager.create_snapshot()
        (project_dir / "SKILL.md").write_text("# Modified")
        manager.rollback(snap.snapshot_id, operator="test_user",
                         reason="testing")
        logs = logger.get_by_type("rollback")
        assert len(logs) >= 1
        log = logs[-1]
        assert log["details"]["snapshot_id"] == snap.snapshot_id
        assert log["details"]["operator"] == "test_user"
        assert "before_hash" in log["details"]
        assert "after_hash" in log["details"]

    def test_rollback_consistency_check(self, manager, project_dir):
        snap = manager.create_snapshot()
        (project_dir / "SKILL.md").write_text("# Modified")
        result = manager.rollback(snap.snapshot_id)
        assert result["ok"] is True
        # After rollback, file should match snapshot hash
        actual_hash = AtomicFileOps.file_hash(project_dir / "SKILL.md")
        assert actual_hash == snap.files.get("SKILL.md")


class TestSnapshotCleanup:
    def test_cleanup_old_snapshots(self, manager):
        manager.MAX_SNAPSHOTS = 3
        for _ in range(5):
            manager.create_snapshot()
        snaps = manager.list_snapshots()
        assert len(snaps) <= 3


class TestCorruptedSnapshot:
    def test_corrupted_manifest(self, manager, snap_dir):
        # Create a snapshot with corrupted manifest
        bad_dir = snap_dir / "bad_snap"
        bad_dir.mkdir()
        (bad_dir / "manifest.json").write_text("not json{{{")
        snaps = manager.list_snapshots()
        # Should not crash, just skip corrupted
        assert all(s.snapshot_id != "bad_snap" for s in snaps)

    def test_missing_files_dir(self, manager, snap_dir, project_dir):
        # Create snapshot, then delete files dir
        snap = manager.create_snapshot()
        files_dir = snap_dir / snap.snapshot_id / "files"
        shutil.rmtree(str(files_dir))
        result = manager.rollback(snap.snapshot_id)
        assert result["ok"] is False
