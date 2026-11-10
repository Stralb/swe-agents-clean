from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
TMP_DIR = DATA_DIR / "tmp"
RAW_DIR = DATA_DIR / "raw"
EXPORT_DIR = DATA_DIR / "exports"

for p in (DATA_DIR, TMP_DIR, RAW_DIR, EXPORT_DIR):
    p.mkdir(parents=True, exist_ok=True)
