from __future__ import annotations

import importlib.util
import http.client
import http.server
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export-preservation.py"
SPEC = importlib.util.spec_from_file_location("preservation_export", SCRIPT)
assert SPEC and SPEC.loader
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


class PreservationExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Preservation test")
        self.write("README.md", b"archive instructions\n")
        self.write("IMPLEMENTATION_STATUS.md", b"durable delivery ledger\n")
        self.write(".gitattributes", b"*.png binary\n")
        self.write(".github/workflows/ci.yml", b"name: CI\n")
        self.write(".github/dependabot.yml", b"version: 2\n")
        self.write("tests/test_validation_guard.py", b"def test_guard(): pass\n")
        self.write("docs/.nojekyll", b"")
        self.write("archive-manifest.json", b"{}\n")
        self.write("archive-status.json", b"{}\n")
        self.write("requirements.txt", b"-r requirements.in\n")
        self.write("requirements.in", b"example==1.0\n")
        self.write("requirements-lock.txt", b"example==1.0 --hash=sha256:abcd\n")
        self.write("content/posts/example/index.md", b"article\n")
        self.write("docs/posts/example/index.html", b"reader route\n")
        self.write("docs/assets/fonts/example.woff2", b"font-bytes")
        self.write("assets/example.png", b"media-bytes")
        self.write("content/rights-registry.json", b"{}\n")
        self.write("data/sheets/as141253-ipv6-architecture-example/visual.html", b"ipv6 visual\n")
        self.write("data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.json", b"{}\n")
        self.write("scripts/rebuild.py", b"print('offline')\n")
        self.write("content/private/notes.txt", b"not for package")
        self.write("assets/credentials/token.txt", b"not for package")
        self.write("content/posts/example/.env.production", b"not for package")
        self.write("assets/private-key.pem", b"not for package")
        self.write("data/sheets/as141253-ipv6-architecture-example/legacy-visual-models/old.html", b"preserved historical model")
        self.write(".git/config-secret", b"excluded")
        self.git("add", "--all")
        self.git("commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout

    def write(self, relative: str, content: bytes) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def export(self, *, dirty_ok: bool = False) -> Path:
        destination = self.base / "preservation"
        with patch.object(EXPORT, "ROOT", self.repo):
            commit = EXPORT.validate_commit(self.commit, dirty_ok)
            EXPORT.export(commit, destination)
        return destination

    def test_exports_committed_reader_assets_metadata_rights_and_ipv6(self) -> None:
        bag = self.export()
        payload = bag / "data"
        required = [
            "README.md", "content/posts/example/index.md", "content/rights-registry.json",
            "docs/posts/example/index.html", "docs/assets/fonts/example.woff2",
            "assets/example.png", "data/sheets/as141253-ipv6-architecture-example/visual.html",
            "data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.json",
            "scripts/rebuild.py",
        ]
        for relative in required:
            self.assertTrue((payload / relative).is_file(), relative)
        self.assertEqual(
            (payload / "data/sheets/as141253-ipv6-architecture-example/legacy-visual-models/old.html").read_bytes(),
            b"preserved historical model",
        )
        for excluded in [
            "content/private/notes.txt", "assets/credentials/token.txt",
            "content/posts/example/.env.production", "assets/private-key.pem",
        ]:
            self.assertFalse((payload / excluded).exists(), excluded)
        for required_root in [
            "archive-manifest.json", "archive-status.json", "requirements.in", "requirements-lock.txt",
            ".gitattributes", ".github/workflows/ci.yml", ".github/dependabot.yml",
            "tests/test_validation_guard.py", "docs/.nojekyll",
            "IMPLEMENTATION_STATUS.md",
        ]:
            self.assertTrue((payload / required_root).is_file(), required_root)
        with patch.object(EXPORT, "ROOT", self.repo):
            expected_snapshot = {name for name, _ in EXPORT.committed_files(self.commit)}
        actual_snapshot = {path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()}
        self.assertEqual(actual_snapshot, expected_snapshot)
        info = (bag / "bag-info.txt").read_text(encoding="utf-8")
        self.assertIn(f"Source-Commit: {self.commit}", info)
        self.assertIn("Exporter-Python:", info)
        self.assertIn("Exporter-Git:", info)
        self.assertIn("https://github.com/daryll-swer/daryllswer.com-archive", info)
        instructions = (bag / "README-PRESERVATION.md").read_text()
        for command in [
            "data/scripts/export-preservation.py --verify .",
            "--directory data/docs", "make -C data PYTHON=\"$(pwd)/.venv/bin/python\" render-site",
            "data/scripts/validate-mirror.py --offline --no-report", "data/tests/",
            "Git-history-dependent", "--require-hashes",
            "External hyperlinks, embedded media",
        ]:
            self.assertIn(command, instructions)
        EXPORT.verify_bag(bag)

    def test_restore_copy_verifies_without_network_calls(self) -> None:
        bag = self.export()
        restored = self.base / "restored"
        archive = self.base / "preservation.tar"
        with tarfile.open(archive, "w") as stream:
            stream.add(bag, arcname="preservation")
        with tarfile.open(archive, "r") as stream:
            stream.extractall(self.base / "extracted", filter="data")
        restored.mkdir()
        shutil.copytree(self.base / "extracted" / "preservation", restored, dirs_exist_ok=True)
        with patch("urllib.request.urlopen", side_effect=AssertionError("network access attempted")):
            EXPORT.verify_bag(restored)
        self.assertEqual((restored / "data/assets/example.png").read_bytes(), b"media-bytes")

    def test_full_project_restore_runs_offline_validator_without_git_or_network(self) -> None:
        source = self.base / "full-source"
        ignored = {".git", ".cache", ".tmp", ".preview", "__pycache__", "node_modules"}

        def ignore_working_state(_directory: str, names: list[str]) -> set[str]:
            return {
                name for name in names
                if name in ignored or name.startswith((".venv", "venv"))
            }

        shutil.copytree(ROOT, source, ignore=ignore_working_state)

        def run_git(*args: str) -> str:
            result = subprocess.run(
                ["git", *args], cwd=source, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            return result.stdout.strip()

        run_git("init", "-q")
        run_git("config", "user.email", "preservation-test@example.invalid")
        run_git("config", "user.name", "Preservation integration test")
        run_git("add", "--all")
        run_git("commit", "-qm", "isolated full-project restore fixture")
        commit = run_git("rev-parse", "HEAD")
        package = self.base / "full-preservation"
        with patch.object(EXPORT, "ROOT", source):
            approved_commit = EXPORT.validate_commit(commit, allow_dirty=False)
            EXPORT.export(approved_commit, package)

        restored_root = package / "data"
        self.assertFalse((restored_root / ".git").exists())
        self.assertTrue((restored_root / "IMPLEMENTATION_STATUS.md").is_file())
        self.assertFalse((restored_root / "PLANS.md").exists())
        self.assertTrue((restored_root / "docs/.nojekyll").is_file())
        validator = restored_root / "scripts" / "validate-mirror.py"
        bootstrap = (
            "import os, runpy, socket, sys, urllib.request; "
            "script = sys.argv[1]; "
            "sys.path.insert(0, os.path.dirname(script)); "
            "deny = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('network access attempted')); "
            "socket.create_connection = deny; socket.getaddrinfo = deny; "
            "socket.socket.connect = deny; socket.socket.connect_ex = deny; "
            "urllib.request.urlopen = deny; "
            "sys.argv = [script, '--offline', '--no-report']; "
            "runpy.run_path(script, run_name='__main__')"
        )
        result = subprocess.run(
            [sys.executable, "-c", bootstrap, str(validator)],
            cwd=restored_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validation errors=0 warnings=0", result.stdout)

    def test_fresh_restore_serves_routes_and_assets_with_external_network_blocked(self) -> None:
        self.write("docs/posts/example/index.html", b"reader route\n")
        self.write("docs/assets/fonts/example.woff2", b"font-bytes")
        self.write("docs/sheets/as141253-ipv6-architecture-example/visual.html", b"IPv6 visual\n")
        self.git("add", "docs")
        self.git("commit", "-qm", "reader assets")
        commit = self.git("rev-parse", "HEAD").strip()
        bag = self.base / "preservation"
        with patch.object(EXPORT, "ROOT", self.repo):
            EXPORT.export(commit, bag)
        restored = self.base / "fresh-restore"
        shutil.copytree(bag, restored)
        document_root = restored / "data" / "docs"
        expected = {
            "/posts/example/index.html": b"reader route\n",
            "/assets/fonts/example.woff2": b"font-bytes",
            "/sheets/as141253-ipv6-architecture-example/visual.html": b"IPv6 visual\n",
        }

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(document_root), **kwargs)

            def log_message(self, format: str, *args: object) -> None:
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        original_connect = socket.socket.connect
        original_getaddrinfo = socket.getaddrinfo

        def loopback_resolution(host: object, *args: object, **kwargs: object):
            if host not in {"127.0.0.1", "::1", "localhost"}:
                raise AssertionError(f"outbound network blocked: {host}")
            return original_getaddrinfo(host, *args, **kwargs)

        def loopback_only(sock: socket.socket, address: object) -> None:
            host = address[0] if isinstance(address, tuple) else ""
            if host not in {"127.0.0.1", "::1"}:
                raise AssertionError(f"outbound network blocked: {host}")
            original_connect(sock, address)

        try:
            with patch.object(socket, "getaddrinfo", loopback_resolution), patch.object(socket.socket, "connect", loopback_only):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                for route, body in expected.items():
                    connection.request("GET", route)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, route)
                    self.assertEqual(response.read(), body, route)
                connection.close()
                external = http.client.HTTPConnection("example.invalid", 80, timeout=1)
                with self.assertRaisesRegex(AssertionError, "outbound network blocked"):
                    external.connect()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)

    def test_dirty_tree_rejected_by_default_but_explicit_commit_export_is_available(self) -> None:
        self.write("README.md", b"uncommitted edit\n")
        with patch.object(EXPORT, "ROOT", self.repo):
            with self.assertRaisesRegex(EXPORT.ExportError, "working tree is dirty"):
                EXPORT.validate_commit(self.commit, False)
            self.assertEqual(EXPORT.validate_commit(self.commit, True), self.commit)

    def test_commit_argument_must_be_full_hash(self) -> None:
        with patch.object(EXPORT, "ROOT", self.repo):
            with self.assertRaisesRegex(EXPORT.ExportError, "full commit hash"):
                EXPORT.validate_commit("HEAD", False)

    def test_existing_or_in_repository_destination_is_rejected(self) -> None:
        inside = self.repo / "package"
        with patch.object(EXPORT, "ROOT", self.repo):
            with self.assertRaisesRegex(EXPORT.ExportError, "outside the repository"):
                EXPORT.ensure_external_output(inside)
            existing = self.base / "already-there"
            existing.mkdir()
            with self.assertRaisesRegex(EXPORT.ExportError, "already exists"):
                EXPORT.ensure_external_output(existing)

    def test_manifest_detects_payload_tampering_and_unlisted_files(self) -> None:
        bag = self.export()
        (bag / "data/assets/example.png").write_bytes(b"altered")
        with self.assertRaisesRegex(EXPORT.ExportError, "checksum mismatch"):
            EXPORT.verify_bag(bag)
        (bag / "data/assets/example.png").write_bytes(b"media-bytes")
        (bag / "data/unlisted.txt").write_text("extra")
        with self.assertRaisesRegex(EXPORT.ExportError, "exactly cover"):
            EXPORT.verify_bag(bag)

    def test_verifier_rejects_a_symlink_bag_path(self) -> None:
        bag = self.export()
        alias = self.base / "bag-alias"
        alias.symlink_to(bag, target_is_directory=True)
        with self.assertRaisesRegex(EXPORT.ExportError, "real directory"):
            EXPORT.verify_bag(alias)

    def test_symlink_is_rejected_even_when_path_would_be_excluded(self) -> None:
        outside = self.base / "outside.txt"
        outside.write_text("outside")
        (self.repo / "private").mkdir()
        (self.repo / "private" / "escape").symlink_to(outside)
        self.git("add", "private/escape")
        self.git("commit", "-qm", "symlink")
        commit = self.git("rev-parse", "HEAD").strip()
        with patch.object(EXPORT, "ROOT", self.repo):
            with self.assertRaisesRegex(EXPORT.ExportError, "unsupported committed file type"):
                EXPORT.committed_files(commit)


if __name__ == "__main__":
    unittest.main()
