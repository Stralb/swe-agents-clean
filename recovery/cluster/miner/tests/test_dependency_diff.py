from src.scanners.dependency_diff import detect_dependency_changes, detect_dependency_regressions


def test_dependency_downgrade_detected():
    files = [{"filename": "requirements.txt", "patch": "-django==4.2.10\n+django==1.2\n"}]
    findings = detect_dependency_regressions(files)
    assert len(findings) == 1
    assert findings[0]["change_type"] == "dependency_downgrade"
    assert findings[0]["package"] == "django"


def test_added_dependency_is_change_but_not_regression_by_itself():
    files = [{"filename": "requirements.txt", "patch": "+django==1.2\n"}]
    changes = detect_dependency_changes(files)
    regressions = detect_dependency_regressions(files)
    assert changes[0]["change_type"] == "added_dependency"
    assert regressions == []


def test_unchanged_dependency_not_flagged():
    files = [{"filename": "requirements.txt", "patch": " django==1.2\n"}]
    assert detect_dependency_changes(files) == []
    assert detect_dependency_regressions(files) == []


def test_constraint_widening_detected():
    files = [{"filename": "requirements.txt", "patch": "-django>=4.2\n+django>=1.2\n"}]
    findings = detect_dependency_regressions(files)
    assert findings[0]["change_type"] == "constraint_widened"


def test_osv_delta_concept_skip_same_before_after(monkeypatch, tmp_path):
    from src.scanners import osv_scanner

    files = [{
        "filename": "requirements.txt",
        "patch": "@@ -1 +1 @@\n-pytest==3.8.0\n+pytest==3.8.1\n",
    }]

    monkeypatch.setattr(osv_scanner.shutil, "which", lambda name: "/usr/bin/osv-scanner")

    def fake_scan_dir(root):
        content = next(root.glob("requirements.txt")).read_text()
        version = "3.8.1" if "3.8.1" in content else "3.8.0"
        return ([{"file": str(root / "requirements.txt"), "package": "pytest", "version": version, "vuln_id": "GHSA-x", "description": "same vuln", "raw": {}}], {"status": "ok", "stdout": "", "stderr": ""})

    monkeypatch.setattr(osv_scanner, "_scan_dir", fake_scan_dir)
    findings, meta = osv_scanner.scan_dependency_patches(files)
    assert findings == []
    assert meta["status"] == "ok"
