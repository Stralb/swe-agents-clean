"""Real OSV v2.6 offline full original snapshot and worker replay.

Only synthetic two-commit local git histories and a fabricated OSV advisory ZIP.
Archived scanner functions are SHA verified and AST-selected; original Git and
shell paths execute under an allowlisted redirection and no-network container.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest import mock
from zipfile import ZipFile, ZIP_STORED

from tests.support.archived_osv_local_process import _load_original_osv
from tests.test_miner_real_dependency_engines import (
    _original_shell, _allowlisted_binary, OSV_SHA256,
    SYNTHETIC_ADVISORY, PACKAGE, ADVISORY,
)

REPO_URL = "https://example.invalid/fixture/real-offline-osv-snapshots"
FILE = "fixture/requirements.txt"
BASE = PACKAGE + "==2.0.0\n"
HEAD = PACKAGE + "==1.0.0\n"
PATCH = "@@ -1 +1 @@\n-" + BASE.rstrip("\n") + "\n+" + HEAD.rstrip("\n") + "\n"


class RealOfflineOSVSnapshot:
    def __init__(self):
        self.context = None
        self.commands = []
        self.repo_dir = None

    @staticmethod
    def _git(*args, cwd):
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True,
            text=True, check=True, timeout=25,
        )
        return result.stdout.strip()

    def __enter__(self):
        self.context = tempfile.TemporaryDirectory(prefix="arno_real_osv_replay_")
        self.root = Path(self.context.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self._git("init", "--quiet", cwd=self.source)
        manifest = self.source / FILE
        manifest.parent.mkdir(parents=True)
        manifest.write_text(BASE, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "fabricated base package",
            cwd=self.source,
        )
        self.base_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        manifest.write_text(HEAD, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "fabricated head package",
            cwd=self.source,
        )
        self.head_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        self.db_dir = self.root / "synthetic-advisory-db"
        self.zips = [
            self.db_dir / prefix / "PyPI" / "all.zip"
            for prefix in ("osv-scalibr", "osv-scanner")
        ]
        data = json.dumps(
            SYNTHETIC_ADVISORY, sort_keys=True, separators=(",", ":")
        )
        for target in self.zips:
            target.parent.mkdir(parents=True)
            with ZipFile(target, "w", compression=ZIP_STORED) as archive:
                archive.writestr(ADVISORY + ".json", data)
        self.binary = _allowlisted_binary(
            "osv-scanner", "ARNO_OSV_BINARY", OSV_SHA256,
        )
        self.original_shell = _original_shell()
        self.archived_driver = _load_original_osv(self._restricted_cmd)
        return self

    def __exit__(self, *_exc):
        if self.context is not None:
            self.context.cleanup()
            self.context = None

    @staticmethod
    def files():
        return [{
            "filename": FILE,
            "status": "modified",
            "category": "dependency",
            "patch": PATCH,
            "additions": 1,
            "deletions": 1,
        }]

    def _restricted_cmd(self, cmd, cwd=None, timeout=None, env=None):
        if (
            not isinstance(cmd, list)
            or any(not isinstance(item, str) for item in cmd)
            or not cmd or env is not None
        ):
            raise ValueError("Rejected unexpected original OSV scanner command")
        working = Path(cwd).resolve() if cwd is not None else None
        git_clone = (
            len(cmd) == 7 and cmd[:6] == [
                "git", "clone", "--depth", "1", "--no-checkout", REPO_URL
            ]
        )
        if git_clone:
            self.repo_dir = Path(cmd[6]).resolve()
            if (
                working is None
                or self.repo_dir != working / "repo"
                or self.repo_dir.parent == self.root
                or not str(working).startswith(
                    str(Path(tempfile.gettempdir()).resolve()) + os.sep
                )
            ):
                raise ValueError("Unexpected clone destination")
            actual = cmd[:5] + ["file://" + str(self.source), cmd[6]]
        elif (
            len(cmd) == 6
            and cmd[:5] == ["git", "fetch", "--depth", "1", "origin"]
            and cmd[5] in (self.base_sha, self.head_sha)
            and working == self.repo_dir
        ):
            actual = cmd
        elif (
            len(cmd) == 5
            and cmd[:4] == ["git", "ls-tree", "-r", "--name-only"]
            and cmd[4] in (self.base_sha, self.head_sha)
            and working == self.repo_dir
        ):
            actual = cmd
        elif (
            len(cmd) == 3 and cmd[:2] == ["git", "show"]
            and cmd[2] in (self.base_sha + ":" + FILE, self.head_sha + ":" + FILE)
            and working == self.repo_dir
        ):
            actual = cmd
        elif (
            len(cmd) == 9 and cmd[:8] == [
                "osv-scanner", "scan", "source", "--recursive", "--no-ignore",
                "--allow-no-lockfiles", "--format", "json"
            ] and cwd is None
        ):
            scan_root = Path(cmd[8]).resolve()
            if (
                self.repo_dir is None or scan_root not in (
                    self.repo_dir.parent / "base", self.repo_dir.parent / "head"
                )
            ):
                raise ValueError("OSV scan escaped its synthetic snapshot")
            expected = BASE if scan_root.name == "base" else HEAD
            if (scan_root / FILE).read_text(encoding="utf-8") != expected:
                raise ValueError("OSV was given nonfixture source data")
            if not all(path.is_file() for path in self.zips):
                raise ValueError("Synthetic advisory data missing")
            _allowlisted_binary("osv-scanner", "ARNO_OSV_BINARY", OSV_SHA256)
            # Safety-only offline args, not part of historical CLI.
            actual = cmd[:-1] + [
                "--offline", "--local-db-path", str(self.db_dir),
                "--no-resolve", str(scan_root)
            ]
        else:
            raise ValueError("Disallowed original OSV command: " + cmd[0])
        self.commands.append(cmd[0])
        return self.original_shell(actual, cwd=cwd, timeout=min(timeout or 90, 90))

    def run(self, repo_url, base_sha, head_sha, files, *, timeout_seconds=90):
        if (
            self.context is None or repo_url != REPO_URL
            or base_sha != self.base_sha or head_sha != self.head_sha
            or files != self.files()
        ):
            raise ValueError("Only the explicit synthetic repo and PR are allowed")
        with mock.patch.dict(os.environ, {
            "OSV_SCALIBR_LOCAL_DB_CACHE_DIRECTORY": str(self.db_dir),
            "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY": str(self.db_dir),
        }):
            return self.archived_driver(
                repo_url, base_sha, head_sha, files,
                timeout_seconds=timeout_seconds,
            )
