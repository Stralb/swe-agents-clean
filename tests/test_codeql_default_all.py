
from miner.scanners import scanner_runner


def test_codeql_default_trigger_is_all(monkeypatch):
    calls = []
    class DB:
        def one(self, q, params=()):
            if "scanner_findings" in q:
                return {"n": 0}
            return None
        def execute(self, *a, **k):
            pass
        def query(self, *a, **k):
            if "pr_files" in a[0]:
                return [{"filename":"src/app.ts", "patch":"+const x = 1"}]
            return []
    def fake_insert_run(db, case_id, pr_id, scanner, status, stdout, stderr):
        calls.append((scanner, status, stderr))
    monkeypatch.setattr(scanner_runner, "_scanner_already_ran", lambda *a, **k: False)
    monkeypatch.setattr(scanner_runner, "_insert_run", fake_insert_run)
    monkeypatch.setattr(scanner_runner, "scan_snapshot_with_codeql", lambda *a, **k: ([], {"status":"ok","stdout":"","stderr":""}))
    monkeypatch.setattr(scanner_runner, "diff_findings", lambda base, head: [])
    monkeypatch.setattr(scanner_runner, "filter_findings_to_pr_delta", lambda fs, files: [])
    case={"case_id":1,"pr_id":1,"repo_url":"https://github.com/o/r","base_sha":"a","head_sha":"b"}
    scanner_runner.scan_case(DB(), case, {"scanners":{"codeql":True,"semgrep":False,"osv":False,"gitleaks":False}})
    assert ("codeql-base", "ok", "") in calls
    assert ("codeql-head", "ok", "") in calls
    assert any(c[0] == "codeql" and c[1] == "ok" for c in calls)
    assert not any("Semgrep" in c[2] for c in calls)
