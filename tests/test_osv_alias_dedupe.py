from src.scanners.osv_scanner import _finding_key


def test_osv_aliases_share_finding_key():
    pysec = {
        "package": "idna",
        "vuln_id": "PYSEC-2026-215",
        "raw": {"id": "PYSEC-2026-215", "aliases": ["CVE-2026-45409", "GHSA-65pc-fj4g-8rjx"]},
    }
    ghsa = {
        "package": "idna",
        "vuln_id": "GHSA-65pc-fj4g-8rjx",
        "raw": {"id": "GHSA-65pc-fj4g-8rjx", "aliases": ["CVE-2026-45409", "PYSEC-2026-215"]},
    }
    assert _finding_key(pysec) == _finding_key(ghsa)
