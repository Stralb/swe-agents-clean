from pathlib import Path


def test_patch_pattern_scanner_removed_from_pipeline():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "src" / "scanners" / "patch_pattern_scanner.py").exists()
    forbidden = ["patch-patterns", "patch_patterns", "SCAN_PATTERNS", "scan_patch_patterns"]
    for rel in ["src", "scripts", "ui", "Makefile", "config.yml"]:
        path = root / rel
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        for file in files:
            if file.suffix in {".pyc", ".db"}:
                continue
            text = file.read_text(encoding="utf-8", errors="ignore")
            for token in forbidden:
                assert token not in text, f"{token} still present in {file}"
