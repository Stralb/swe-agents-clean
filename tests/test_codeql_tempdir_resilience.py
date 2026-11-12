from __future__ import annotations

from pathlib import Path

from miner.scanners import codeql_scanner


def test_codeql_tempdir_uses_configured_linux_local_parent(tmp_path, monkeypatch):
    parent = tmp_path / "codeql-tmp"
    monkeypatch.setenv("MINER_CODEQL_TMPDIR", str(parent))

    with codeql_scanner._codeql_tempdir() as root:
        assert root.parent == parent
        assert root.name.startswith("miner-codeql-")
        (root / "still_here.txt").write_text("ok")

    assert parent.exists()


def test_codeql_tempdir_cleanup_failure_is_not_scan_failure(tmp_path, monkeypatch):
    parent = tmp_path / "codeql-tmp"
    monkeypatch.setenv("MINER_CODEQL_TMPDIR", str(parent))

    class BadTemporaryDirectory:
        def __init__(self, *args, **kwargs):
            self.name = str(parent / "miner-codeql-bad")
            Path(self.name).mkdir(parents=True, exist_ok=True)
            self.kwargs = kwargs

        def cleanup(self):
            raise OSError("simulated WSL cleanup race")

    monkeypatch.setattr(codeql_scanner.tempfile, "TemporaryDirectory", BadTemporaryDirectory)

    with codeql_scanner._codeql_tempdir() as root:
        assert root.exists()


def test_javascript_codeql_preflight_requires_node_when_codeql_exists(monkeypatch):
    def fake_which(name: str):
        if name == "codeql":
            return "/usr/bin/codeql"
        if name == "node":
            return None
        return None

    monkeypatch.setattr(codeql_scanner.shutil, "which", fake_which)
    ok, msg = codeql_scanner._codeql_preflight("javascript-typescript")
    assert ok is False
    assert "node" in msg.lower()


def test_python_codeql_preflight_does_not_require_node(monkeypatch):
    def fake_which(name: str):
        if name == "codeql":
            return "/usr/bin/codeql"
        if name == "node":
            return None
        return None

    monkeypatch.setattr(codeql_scanner.shutil, "which", fake_which)
    ok, msg = codeql_scanner._codeql_preflight("python")
    assert ok is True
    assert msg == ""
