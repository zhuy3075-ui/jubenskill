"""Tests for evolution repair module (supply-chain security P0-A).

Covers: integrity check, repo allowlist, ref pinning, manifest verification,
hash mismatch attack simulation, dry-run mode, audit logging.
"""
import json
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evolution.repair import SelfRepair
from evolution.snapshot import SnapshotManager
from evolution.logger import EvolveLogger
from evolution.file_ops import AtomicFileOps
from evolution.models import UpdateManifest


@pytest.fixture
def project_dir():
    d = Path(tempfile.mkdtemp(prefix="test_repair_"))
    (d / "scripts").mkdir()
    for f in SelfRepair.REQUIRED_FILES:
        fp = d / f
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(f"# {f}")
    (d / "evolve_data" / "snapshots").mkdir(parents=True)
    (d / "evolve_data" / "logs").mkdir(parents=True)
    (d / "evolution").mkdir(exist_ok=True)
    (d / "evolution" / "__init__.py").write_text("")
    yield d
    shutil.rmtree(str(d), ignore_errors=True)


@pytest.fixture
def logger(project_dir):
    return EvolveLogger(project_dir / "evolve_data" / "logs")


@pytest.fixture
def snapshots(project_dir, logger):
    return SnapshotManager(
        project_dir / "evolve_data" / "snapshots", project_dir, logger)


@pytest.fixture
def repair(project_dir, logger, snapshots):
    allowlist = [
        {"owner": "trusted-org", "repo": "skill-repo",
         "allowed_refs": ["v1.0.0", "v2.0.0"]},
    ]
    return SelfRepair(project_dir, logger, snapshots, allowlist=allowlist)


class TestIntegrityCheck:
    def test_all_files_present(self, repair):
        result = repair.check_integrity()
        assert result["ok"] is True
        assert result["healthy"] == len(SelfRepair.REQUIRED_FILES)

    def test_missing_file(self, repair, project_dir):
        (project_dir / "scripts" / "parse_script.py").unlink()
        result = repair.check_integrity()
        assert result["ok"] is False
        assert "scripts/parse_script.py" in result["missing"]

    def test_empty_file_corrupted(self, repair, project_dir):
        (project_dir / "SKILL.md").write_text("")
        result = repair.check_integrity()
        assert result["ok"] is False
        assert "SKILL.md" in result["corrupted"]


class TestRepoAllowlist:
    def test_allowed_repo(self, repair):
        assert repair.is_repo_allowed("trusted-org", "skill-repo") is True

    def test_disallowed_repo(self, repair):
        assert repair.is_repo_allowed("evil-org", "malware") is False

    def test_allowed_ref(self, repair):
        assert repair.is_ref_allowed("trusted-org", "skill-repo", "v1.0.0") is True

    def test_disallowed_ref(self, repair):
        assert repair.is_ref_allowed("trusted-org", "skill-repo", "v999") is False

    def test_unknown_repo_ref(self, repair):
        assert repair.is_ref_allowed("unknown", "repo", "main") is False


class TestManifestVerification:
    def test_valid_manifest(self, repair, project_dir):
        # Create manifest matching actual files
        files = {}
        for f in SelfRepair.REQUIRED_FILES:
            fp = project_dir / f
            if fp.exists():
                files[f] = AtomicFileOps.file_hash(fp)
        manifest = UpdateManifest(version="1.0", files=files)
        result = repair.verify_manifest(manifest, project_dir)
        assert result["ok"] is True

    def test_hash_mismatch_attack(self, repair, project_dir):
        """Simulate supply-chain attack: file hash doesn't match manifest."""
        files = {"SKILL.md": "0000000000000000000000000000000000000000000000000000000000000000"}
        manifest = UpdateManifest(version="1.0", files=files)
        result = repair.verify_manifest(manifest, project_dir)
        assert result["ok"] is False
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["reason"] == "hash_mismatch"

    def test_missing_file_in_manifest(self, repair, project_dir):
        files = {"nonexistent.py": "abc123"}
        manifest = UpdateManifest(version="1.0", files=files)
        result = repair.verify_manifest(manifest, project_dir)
        assert result["ok"] is False
        assert result["mismatches"][0]["reason"] == "missing"


class TestSupplyChainSecurity:
    def test_reject_unknown_repo(self, repair):
        result = repair.repair_from_github(
            "https://github.com/evil-org/malware", ref="main")
        assert result["ok"] is False
        assert "allowlist" in result["reason"]

    def test_reject_unknown_ref(self, repair):
        result = repair.repair_from_github(
            "https://github.com/trusted-org/skill-repo", ref="v999")
        assert result["ok"] is False
        assert "ref_not_allowed" in result["reason"]

    def test_dry_run_mode(self, repair):
        result = repair.repair_from_github(
            "https://github.com/trusted-org/skill-repo",
            ref="v1.0.0", dry_run=True)
        assert result["ok"] is True
        assert result["dry_run"] is True

    def test_rejection_audit_log(self, repair, logger):
        repair.repair_from_github(
            "https://github.com/evil-org/malware", ref="main")
        logs = logger.get_by_type("repair_rejected")
        assert len(logs) >= 1
        assert "allowlist" in logs[-1]["details"]["reason"]
