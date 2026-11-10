"""Genuine CodeQL 2.27.3 against local generated base/head Python only.

Reuses the SHA-verified archived CodeQL AST runner and fixed git/command
allowlist from archived_codeql_local_process. Only a known public-category
inert command-injection sample is scanned, NEVER executed.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
from unittest import mock

from tests.support import archived_codeql_local_process as base

REPO_URL = base.REPO_URL
FILENAME = base.FILENAME
SUITE = base.SUITE
REAL_BASE = (
    "from flask import request\n"
    "import os\n\n"
    "def safe_entry():\n"
    "    return 'ok'\n"
)
REAL_HEAD = (
    REAL_BASE
    + "\n\ndef introduced_sink():\n"
    + "    os.system(request.args['cmd'])\n"
)
REAL_PATCH = (
    "@@ -1,5 +1,9 @@\n"
    " from flask import request\n"
    " import os\n"
    " \n"
    " def safe_entry():\n"
    "     return 'ok'\n"
    "+\n"
    "+\n"
    "+def introduced_sink():\n"
    "+    os.system(request.args['cmd'])\n"
)


class RealPinnedCodeQLReplay(base.LocalCodeQLReplay):
    """Run exact historic clone/create/analyze commands with one verified CLI."""

    def __enter__(self):
        self._fixture_patch = mock.patch.multiple(
            base,
            BASE_CONTENT=REAL_BASE,
            HEAD_CONTENT=REAL_HEAD,
            PATCH=REAL_PATCH,
        )
        self._fixture_patch.__enter__()
        try:
            super().__enter__()
            cli = Path(os.environ["ARNO_REAL_CODEQL_BINARY"]).resolve()
            if cli.name != "codeql" or not cli.is_file():
                raise ValueError("Missing pinned genuine CodeQL CLI")
            self.bin = cli.parent
            self.binary = cli
            if Path(shutil.which("codeql") or "").resolve() != self.binary:
                raise ValueError("The real CodeQL executable is not first on PATH")
            return self
        except BaseException:
            try:
                super().__exit__(None, None, None)
            finally:
                self._fixture_patch.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self._fixture_patch.__exit__(*args)

    def scan(self, repo_url, sha, *, language, build_mode, query_suite, timeout_seconds):
        if (
            self.temp is None or repo_url != REPO_URL
            or sha not in (self.base_sha, self.head_sha)
            or language != "python" or build_mode != "none" or query_suite != SUITE
            or timeout_seconds < 60 or timeout_seconds > 900
        ):
            raise ValueError("Only preauthorized synthetic CodeQL scans are allowed")
        with mock.patch.dict(os.environ, {
            "PATH": str(self.bin) + os.pathsep + "/usr/local/bin:/usr/bin:/bin",
            "MINER_CODEQL_TMPDIR": str(self.tmp_parent),
            "CODEQL_RAM_MB": "4096", "CODEQL_THREADS": "1",
        }):
            if Path(shutil.which("codeql") or "").resolve() != self.binary:
                raise ValueError("Nonpinned CodeQL detected")
            return self.original_codeql(
                repo_url, sha, language=language, build_mode=build_mode,
                query_suite=query_suite, timeout_seconds=timeout_seconds,
            )
