"""Original SHA-pinned Trivy snapshot/worktree runner with genuine offline DB.

Only fabricated two-commit local Git input and a manifest of public fixed
requests versions. This is a test-only command allowlist. Git clone is
redirected solely to the generated file:// repository. No Wits/original DBs.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest import mock

from tests.support.archived_trivy_local_process import _load_original_trivy
from tests.test_miner_real_dependency_engines import _original_shell, _allowlisted_binary

REPO_URL = "https://example.invalid/fixture/real-frozen-trivy-snapshots"
FILENAME = "fixture/requirements.txt"
BASE = "requests==2.32.5\n"
HEAD = "requests==2.19.1\n"
PATCH = "@@ -1 +1 @@\n-" + BASE.rstrip("\n") + "\n+" + HEAD.rstrip("\n") + "\n"
DB_PATH = Path("/tmp/trivy-cache/db")


class RealFrozenTrivySnapshot:
    def __init__(self):
        self.context = None
        self.checkout_dir = None
        self.calls = []

    @staticmethod
    def _git(*args, cwd):
        res = subprocess.run(
            ["git", *args], cwd=cwd,
            capture_output=True, text=True, timeout=30, check=True,
        )
        return res.stdout.strip()

    def __enter__(self):
        self.context = tempfile.TemporaryDirectory(prefix="arno_real_trivy_snapshot_")
        self.root = Path(self.context.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self._git("init", "--quiet", cwd=self.source)
        manifest = self.source / FILENAME
        manifest.parent.mkdir(parents=True)
        manifest.write_text(BASE, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Fabricated Test",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "synthetic base",
            cwd=self.source,
        )
        self.base_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        manifest.write_text(HEAD, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Fabricated Test",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "synthetic head",
            cwd=self.source,
        )
        self.head_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        self.binary = _allowlisted_binary(
            "trivy", "ARNO_TRIVY_BINARY", None,
        )
        if not (DB_PATH / "trivy.db").is_file():
            raise RuntimeError("Pinned Trivy-DB volume unavailable")
        self.original_shell = _original_shell()
        self.archived_driver = _load_original_trivy(self._restricted_cmd)
        return self

    def __exit__(self, *_exc):
        if self.context is not None:
            self.context.cleanup()
            self.context = None

    @staticmethod
    def files():
        return [{
            "filename": FILENAME,
            "status": "modified",
            "category": "dependency",
            "patch": PATCH,
            "additions": 1,
            "deletions": 1,
        }]

    def _restricted_cmd(self, cmd, cwd=None, timeout=None, env=None):
        if (
            not isinstance(cmd, list) or not cmd
            or any(not isinstance(a, str) for a in cmd)
            or env is not None
        ):
            raise ValueError("Original Trivy subprocess call rejected")
        working = Path(cwd).resolve() if cwd is not None else None
        if cmd == ["trivy", "--version"] and cwd is None:
            _allowlisted_binary("trivy", "ARNO_TRIVY_BINARY", None)
            allowed = cmd
        elif (
            len(cmd) == 8
            and cmd[:7] == [
                "git", "clone", "--depth", "1",
                "--filter=blob:none", "--no-checkout", REPO_URL
            ]
            and cwd is None
        ):
            self.checkout_dir = Path(cmd[7]).resolve()
            if (
                self.checkout_dir.name != "repo"
                or not str(self.checkout_dir.parent).startswith(
                    str(Path(tempfile.gettempdir()).resolve()) + os.sep
                )
                or self.checkout_dir.parent == self.root
                or self.checkout_dir.parent == self.source
            ):
                raise ValueError("Original checkout is not in disposable temp")
            allowed = cmd[:6] + ["file://" + str(self.source), cmd[7]]
        elif (
            len(cmd) == 6 and cmd[:5] == [
                "git", "fetch", "--depth", "1", "origin",
            ]
            and cmd[5] in (self.base_sha, self.head_sha)
            and working == self.checkout_dir
        ):
            allowed = cmd
        elif (
            len(cmd) == 7
            and cmd[:5] == [
                "git", "worktree", "add", "--detach", "--force",
            ]
            and cmd[6] in (self.base_sha, self.head_sha)
            and working == self.checkout_dir
        ):
            requested = Path(cmd[5]).resolve()
            intended = (
                self.checkout_dir.parent /
                ("base" if cmd[6] == self.base_sha else "head")
            )
            if requested != intended:
                raise ValueError("Trivy worktree escaped synthetic temp")
            allowed = cmd
        elif (
            len(cmd) == 14
            and cmd[:13] == [
                "trivy", "filesystem", "--scanners", "vuln",
                "--pkg-types", "library", "--include-dev-deps",
                "--offline-scan", "--format", "json",
                "--no-progress", "--exit-code", "0",
            ]
            and cwd is None
        ):
            scan_root = Path(cmd[13]).resolve()
            if self.checkout_dir is None or scan_root not in (
                self.checkout_dir.parent / "base",
                self.checkout_dir.parent / "head",
            ):
                raise ValueError("Trivy was given non-synthetic scan root")
            contents = BASE if scan_root.name == "base" else HEAD
            if (scan_root / FILENAME).read_text(encoding="utf-8") != contents:
                raise ValueError("Trivy synthetic manifest differs")
            if not (DB_PATH / "trivy.db").is_file():
                raise ValueError("Pinned offline DB is absent")
            _allowlisted_binary("trivy", "ARNO_TRIVY_BINARY", None)
            allowed = cmd
        else:
            raise ValueError("Unexpected original Trivy command " + cmd[0])
        self.calls.append(cmd[0])
        return self.original_shell(allowed, cwd=cwd, timeout=min(timeout or 120, 120))

    def run(self, repo_url, base_sha, head_sha, files, *, timeout_seconds=120):
        if (
            self.context is None or repo_url != REPO_URL
            or base_sha != self.base_sha or head_sha != self.head_sha
            or files != self.files()
        ):
            raise ValueError("Refuse non-synthetic repo, SHA or PR diff")
        with mock.patch.dict(os.environ, {
            "TRIVY_CACHE_DIR": "/tmp/trivy-cache",
            "TRIVY_SKIP_DB_UPDATE": "true",
            "TRIVY_SKIP_JAVA_DB_UPDATE": "true",
            "TRIVY_SKIP_VERSION_CHECK": "true",
        }):
            return self.archived_driver(
                repo_url, base_sha, head_sha, files,
                timeout_seconds=timeout_seconds,
            )
