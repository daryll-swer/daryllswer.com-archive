from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "backup-preservation.py"
SPEC = importlib.util.spec_from_file_location("backup_preservation", SCRIPT)
assert SPEC and SPEC.loader
BACKUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BACKUP)
EXPORT_SPEC = importlib.util.spec_from_file_location("preservation_export_for_backup_tests", ROOT / "scripts" / "export-preservation.py")
assert EXPORT_SPEC and EXPORT_SPEC.loader
EXPORT = importlib.util.module_from_spec(EXPORT_SPEC)
EXPORT_SPEC.loader.exec_module(EXPORT)


class BackupPreservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.tooling = self.base / "tooling"
        self.source = self.base / "source"
        self.private = self.base / "private-backup"
        self.tooling.mkdir()
        self.source.mkdir()
        self.private.mkdir()
        for repo in (self.tooling, self.source, self.private):
            self.git(repo, "init", "-q")
            self.git(repo, "config", "user.name", "Backup test")
            self.git(repo, "config", "user.email", "backup@example.invalid")
        (self.tooling / "tool.txt").write_text("trusted tooling\n")
        self.commit(self.tooling)
        (self.source / "README.md").write_text("archive\n")
        (self.source / ".github/workflows/deploy-pages.yml").parent.mkdir(parents=True)
        (self.source / ".github/workflows/deploy-pages.yml").write_text("inert source workflow\n")
        (self.source / ".github/workflows/ci.yml").write_text("inert source workflow\n")
        self.source_sha = self.commit(self.source)
        self.tooling_sha = self.git(self.tooling, "rev-parse", "HEAD")

    @staticmethod
    def git(repo: Path, *args: str) -> str:
        result = subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip()

    def commit(self, repo: Path) -> str:
        self.git(repo, "add", "--all")
        self.git(repo, "commit", "-qm", "fixture")
        return self.git(repo, "rev-parse", "HEAD")

    def commit_private_snapshot(self) -> None:
        self.git(self.private, "add", "snapshot")
        self.git(self.private, "commit", "-qm", "verified snapshot")

    def advance_source(self) -> None:
        (self.source / "README.md").write_text("new archive revision\n")
        self.source_sha = self.commit(self.source)

    def fake_fetch(self, url: str):
        if url.endswith("/git/ref/heads/main"):
            return {"object": {"sha": self.source_sha}}
        if "/actions/workflows/" in url:
            return {"workflow_runs": [{
                "id": 7, "head_sha": self.source_sha, "head_branch": "main",
                "event": "push", "head_repository": {"full_name": "owner/archive"},
                "path": ".github/workflows/deploy-pages.yml", "status": "completed", "conclusion": "success",
            }]}
        if "/actions/runs/7/jobs" in url:
            return {"jobs": [
                {"name": "build", "status": "completed", "conclusion": "success"},
                {"name": "deploy", "status": "completed", "conclusion": "success"},
            ]}
        if "/deployments?" in url:
            return [{"id": 9, "created_at": "2026-11-03T04:17:00Z", "sha": self.source_sha}]
        if "/statuses?" in url:
            return [{"state": "success"}]
        raise AssertionError(f"unexpected evidence endpoint: {url}")

    def make_bag(self, output: Path, *, source: Path | None = None) -> Path:
        with patch.object(EXPORT, "ROOT", self.tooling):
            EXPORT.export(self.source_sha, output, source or self.source)
        return output

    def publish(self, bag: Path, **kwargs):
        with patch.object(BACKUP, "ROOT", self.tooling):
            return BACKUP.publish(
                bag, self.private, "owner/archive", self.tooling_sha,
                exporter=EXPORT, fetch=self.fake_fetch, source_git_dir=self.source, **kwargs,
            )

    def test_exact_main_successful_validated_workflow_and_pages_deployment_required(self) -> None:
        workflow, deployment = BACKUP.verify_public_source("owner/archive", self.source_sha, self.fake_fetch)
        self.assertEqual(workflow["id"], 7)
        self.assertEqual(deployment["sha"], self.source_sha)

        def skipped_deploy(url: str):
            result = self.fake_fetch(url)
            if "/actions/runs/7/jobs" in url:
                result["jobs"][1]["conclusion"] = "skipped"
            return result

        with self.assertRaisesRegex(BACKUP.BackupError, "successful build and deploy"):
            BACKUP.verify_public_source("owner/archive", self.source_sha, skipped_deploy)

    def test_bare_source_fetch_is_exact_and_ignores_inherited_git_credentials(self) -> None:
        remote = self.base / "public-source.git"
        subprocess.run(["git", "clone", "--bare", "--quiet", str(self.source), str(remote)], check=True)
        destination = self.base / "temporary-source.git"
        with patch.dict(os.environ, {
            "GIT_CONFIG_PARAMETERS": "'credential.helper=/tmp/untrusted-helper'",
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_1": "credential.helper",
            "GIT_CONFIG_VALUE_1": "/tmp/untrusted-helper",
            "GIT_ASKPASS": "/tmp/untrusted-askpass",
            "SSH_ASKPASS": "/tmp/untrusted-ssh-askpass",
        }):
            environment = BACKUP.isolated_git_environment()
            self.assertNotIn("GIT_CONFIG_PARAMETERS", environment)
            self.assertNotIn("GIT_CONFIG_KEY_1", environment)
            self.assertNotIn("GIT_ASKPASS", environment)
            self.assertNotIn("SSH_ASKPASS", environment)
            self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
            fetched = BACKUP.fetch_source_commit(
                "owner/archive", self.source_sha, destination, git_url=str(remote),
            )
        self.assertEqual(BACKUP.bare_git(fetched, "rev-parse", "FETCH_HEAD"), self.source_sha)
        bag = self.make_bag(self.base / "bare-source-verification")
        BACKUP.verify_payload_matches_source(bag, self.source_sha, fetched, EXPORT)

    def test_fails_when_latest_pages_deployment_or_main_does_not_match(self) -> None:
        def old_deployment(url: str):
            result = self.fake_fetch(url)
            if "/deployments?" in url:
                result[0]["sha"] = "a" * 40
            return result

        with self.assertRaisesRegex(BACKUP.BackupError, "latest github-pages deployment"):
            BACKUP.verify_public_source("owner/archive", self.source_sha, old_deployment)

        def moved_main(url: str):
            result = self.fake_fetch(url)
            if url.endswith("/git/ref/heads/main"):
                result["object"]["sha"] = "b" * 40
            return result

        with self.assertRaisesRegex(BACKUP.BackupError, "not the current public main"):
            BACKUP.verify_public_source("owner/archive", self.source_sha, moved_main)

    def test_create_and_same_source_noop_verified_record_and_inert_workflows(self) -> None:
        bag = self.make_bag(self.base / "bag")
        self.assertTrue(self.publish(bag))
        self.commit_private_snapshot()
        snapshot = self.private / "snapshot"
        self.assertTrue((snapshot / "data/.github/workflows/deploy-pages.yml").is_file())
        self.assertFalse((snapshot / "data/.git").exists())
        record = json.loads((snapshot / "backup-record.json").read_text())
        self.assertEqual(record["sourceSHA"], self.source_sha)
        self.assertEqual(record["toolingSHA"], self.tooling_sha)
        self.assertEqual(record["manifestSHA256"], BACKUP.hashlib.sha256((snapshot / "manifest-sha256.txt").read_bytes()).hexdigest())
        with self.assertRaisesRegex(EXPORT.ExportError, "exactly cover"):
            EXPORT.verify_bag(snapshot)
        with patch.object(BACKUP, "ROOT", self.tooling):
            self.assertEqual(BACKUP.main(["verify", "--snapshot", str(snapshot)]), 0)
        self.assertFalse(self.publish(bag))
        self.assertEqual(BACKUP.changed_paths(self.private), set())

    def test_backup_verifier_rejects_record_digest_mismatch(self) -> None:
        bag = self.make_bag(self.base / "record-check")
        self.publish(bag)
        snapshot = self.private / "snapshot"
        record_path = snapshot / "backup-record.json"
        record = json.loads(record_path.read_text())
        record["manifestSHA256"] = "0" * 64
        record_path.write_text(json.dumps(record))
        with redirect_stderr(io.StringIO()):
            with patch.object(BACKUP, "ROOT", self.tooling):
                self.assertEqual(BACKUP.main(["verify", "--snapshot", str(snapshot)]), 1)

    def test_corrupt_and_symlink_payloads_are_rejected_before_replacement(self) -> None:
        bag = self.make_bag(self.base / "good-bag")
        self.publish(bag)
        self.commit_private_snapshot()
        original = (self.private / "snapshot/data/README.md").read_bytes()
        bad = self.make_bag(self.base / "bad-bag")
        (bad / "data/README.md").write_text("tampered")
        with self.assertRaises(BACKUP.BackupError):
            self.publish(bad)
        self.assertEqual((self.private / "snapshot/data/README.md").read_bytes(), original)

        linked = self.make_bag(self.base / "linked-bag")
        outside = self.base / "outside"
        outside.write_text("external")
        (linked / "data/escape").symlink_to(outside)
        with self.assertRaisesRegex(BACKUP.BackupError, "symlink"):
            self.publish(linked)
        self.assertEqual((self.private / "snapshot/data/README.md").read_bytes(), original)

    def rehash_tampered_bag(self, bag: Path) -> None:
        payload_manifest = bag / "manifest-sha256.txt"
        rows = payload_manifest.read_text(encoding="utf-8").splitlines()
        payload_manifest.write_text("\n".join(
            f"{EXPORT.hashlib.sha256((bag / name).read_bytes()).hexdigest()} {name}"
            if name == "data/README.md" else row
            for row in rows
            for _, name in [row.split(" ", 1)]
        ) + "\n", encoding="utf-8")
        tag_manifest = bag / "tagmanifest-sha256.txt"
        tag_files = sorted(
            path.relative_to(bag).as_posix()
            for path in bag.iterdir()
            if path.is_file() and path != tag_manifest and path.name != "backup-record.json"
        )
        tag_manifest.write_text("\n".join(
            f"{EXPORT.sha256_file(bag / name)} {name}"
            for name in tag_files
        ) + "\n", encoding="utf-8")

    def test_rehashed_payload_cannot_masquerade_as_source_commit(self) -> None:
        bag = self.make_bag(self.base / "rehash-attack")
        (bag / "data/README.md").write_text("attacker-rewritten source\n")
        self.rehash_tampered_bag(bag)
        with self.assertRaisesRegex(BACKUP.BackupError, "do not match source commit"):
            self.publish(bag)

        valid = self.make_bag(self.base / "valid-for-noop")
        self.publish(valid)
        self.commit_private_snapshot()
        snapshot = self.private / "snapshot"
        (snapshot / "data/README.md").write_text("rewritten existing snapshot\n")
        self.rehash_tampered_bag(snapshot)
        # Restore the record's manifest digest so only source-tree comparison fails.
        record_path = snapshot / "backup-record.json"
        record = json.loads(record_path.read_text())
        record["manifestSHA256"] = EXPORT.sha256_file(snapshot / "manifest-sha256.txt")
        record_path.write_text(json.dumps(record))
        self.git(self.private, "add", "snapshot")
        self.git(self.private, "commit", "-qm", "rewritten snapshot with recomputed checksums")
        with self.assertRaisesRegex(BACKUP.BackupError, "do not match source commit"):
            self.publish(valid)

    def test_verify_staged_detects_ignored_missing_and_tampered_index_entries(self) -> None:
        (self.private / ".gitignore").write_text("snapshot/data/README.md\n")
        self.git(self.private, "add", ".gitignore")
        self.git(self.private, "commit", "-qm", "ignore fixture payload file")
        bag = self.make_bag(self.base / "staged-check")
        self.publish(bag)
        self.git(self.private, "add", "snapshot")
        with self.assertRaisesRegex(BACKUP.BackupError, "file set does not exactly match"):
            BACKUP.verify_staged(self.private, exporter=EXPORT)
        self.git(self.private, "add", "-f", "snapshot")
        BACKUP.verify_staged(self.private, exporter=EXPORT)

        changed_blob = subprocess.run(
            ["git", "-C", str(self.private), "hash-object", "-w", "--stdin"],
            input=b"tampered staged bytes\n", check=True, stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        self.git(self.private, "update-index", "--cacheinfo", f"100644,{changed_blob},snapshot/data/README.md")
        with self.assertRaisesRegex(BACKUP.BackupError, "staged bytes differ"):
            BACKUP.verify_staged(self.private, exporter=EXPORT)
        self.git(self.private, "add", "-f", "snapshot")
        self.git(self.private, "rm", "--cached", "--quiet", "snapshot/data/README.md")
        with self.assertRaisesRegex(BACKUP.BackupError, "file set does not exactly match"):
            BACKUP.verify_staged(self.private, exporter=EXPORT)

    def test_preinstall_copy_or_verification_failure_preserves_previous_snapshot(self) -> None:
        initial = self.make_bag(self.base / "initial")
        self.publish(initial)
        self.commit_private_snapshot()
        preserved = (self.private / "snapshot/data/README.md").read_bytes()
        self.advance_source()
        replacement = self.make_bag(self.base / "replacement")
        with patch.object(BACKUP.shutil, "copytree", side_effect=OSError("injected copy failure")):
            with self.assertRaisesRegex(OSError, "injected copy failure"):
                self.publish(replacement)
        self.assertEqual((self.private / "snapshot/data/README.md").read_bytes(), preserved)

        with patch.object(BACKUP, "validate_snapshot", side_effect=BACKUP.BackupError("injected verification failure")):
            with self.assertRaisesRegex(BACKUP.BackupError, "injected verification failure"):
                self.publish(replacement)
        self.assertEqual((self.private / "snapshot/data/README.md").read_bytes(), preserved)

    def test_postinstall_failure_restores_previous_snapshot(self) -> None:
        initial = self.make_bag(self.base / "initial")
        self.publish(initial)
        self.commit_private_snapshot()
        preserved = (self.private / "snapshot/data/README.md").read_bytes()
        self.advance_source()
        replacement = self.make_bag(self.base / "replacement")
        with patch.object(BACKUP, "changed_paths", side_effect=BACKUP.BackupError("injected post-install failure")):
            with self.assertRaisesRegex(BACKUP.BackupError, "injected post-install failure"):
                self.publish(replacement)
        self.assertEqual((self.private / "snapshot/data/README.md").read_bytes(), preserved)
        self.assertFalse(list(self.base.glob(".private-backup-snapshot-previous-*")))

    def test_parent_and_destination_symlinks_are_rejected(self) -> None:
        bag = self.make_bag(self.base / "safe-bag")
        alias = self.base / "payload-alias"
        alias.symlink_to(bag, target_is_directory=True)
        with self.assertRaisesRegex(BACKUP.BackupError, "cannot be a symlink"):
            self.publish(alias)
        parent_alias = self.base / "parent-alias"
        in_repo_payload = self.private / "fixture-bag"
        shutil.copytree(bag, in_repo_payload)
        self.git(self.private, "add", "fixture-bag")
        self.git(self.private, "commit", "-qm", "fixture payload")
        parent_alias.symlink_to(self.private, target_is_directory=True)
        with self.assertRaisesRegex(BACKUP.BackupError, "outside the backup checkout"):
            self.publish(parent_alias / "fixture-bag")
        (self.private / "snapshot").symlink_to(self.base, target_is_directory=True)
        self.git(self.private, "add", "snapshot")
        self.git(self.private, "commit", "-qm", "hostile snapshot symlink")
        with self.assertRaisesRegex(BACKUP.BackupError, "existing snapshot"):
            self.publish(bag)

    def test_inactive_workflow_template_keeps_transfers_outside_checkout(self) -> None:
        template = (ROOT / "maintenance/backup/backup.yml").read_text(encoding="utf-8")
        readme = (ROOT / "maintenance/backup/README.md").read_text(encoding="utf-8")
        self.assertIn('cron: "17 4 * * 2"', template)
        self.assertIn("BACKUP_ZERO_PAID_OVERAGE_VERIFIED == 'true'", template)
        self.assertIn("BACKUP_TOOLING_SHA != ''", template)
        self.assertGreaterEqual(template.count("github.ref == 'refs/heads/main'"), 2)
        self.assertIn("timeout-minutes: 20", template)
        self.assertIn("timeout-minutes: 10", template)
        self.assertIn("include-hidden-files: true", template)
        self.assertIn("git add -f -- snapshot", template)
        self.assertIn("verify-staged --repository .", template)
        self.assertIn("retention-days: 1", template)
        self.assertIn("RUNNER_TEMP/tooling", template)
        self.assertIn("RUNNER_TEMP/backup-transfer/snapshot", template)
        self.assertIn("contents: write", template)
        self.assertNotIn("pip install", template)
        self.assertIn("next Tuesday retries", readme)
        self.assertIn("FULL_TRUSTED_TOOLING_SHA", readme)
        self.assertFalse((ROOT / ".github/workflows/backup.yml").exists())


if __name__ == "__main__":
    unittest.main()
