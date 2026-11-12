#!/bin/bash
#SBATCH --job-name=t1xrecover
#SBATCH --partition=batch
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_EXACT_X_TRANSFER_RECOVERY_v1.out

set -euo pipefail

python3 -u <<'PY'
from pathlib import Path
import csv, hashlib, io, json, os, re, shutil, tarfile, zipfile

ROOT = Path.home() / "research_artifacts"
OUT = ROOT / "T1_EXACT_X_TRANSFER_RECOVERY_v1"
ARCHIVE = ROOT / "T1_EXACT_X_TRANSFER_RECOVERY_v1.tar.gz"

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

# We want the exact frozen apparatus from the completed T1 experiment,
# especially the strongest response root R4. No scanner outcome is used
# to choose X: X is recovered from the already-frozen experiment.
KEYWORDS = (
    "T1_REAL", "t1_real", "condition", "mechanism", "classifier",
    "packet", "schedule", "manifest", "root", "blind", "adjudication",
    "context"
)
TEXT_EXT = {".json",".jsonl",".csv",".tsv",".md",".txt",".yaml",".yml"}

def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def safe_copy(src, tag):
    rel = src.relative_to(ROOT)
    dst = OUT / tag / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst

# 1) Collect small metadata files likely belonging to the real T1 experiment.
manifest = []
for p in ROOT.rglob("*"):
    if not p.is_file():
        continue
    try:
        if p.stat().st_size > 10 * 1024 * 1024:
            continue
    except OSError:
        continue
    low = str(p).lower()
    if "t1" not in low and "real_experiment" not in low and "counterfactual" not in low:
        continue
    if p.suffix.lower() not in TEXT_EXT and not any(k.lower() in p.name.lower() for k in KEYWORDS):
        continue

    # Keep only files with useful experiment identifiers in name/content.
    hit = any(k.lower() in p.name.lower() for k in KEYWORDS)
    content_hit = False
    if p.suffix.lower() in TEXT_EXT:
        try:
            text = p.read_text(errors="ignore")
            content_hit = (
                "R4" in text
                or "Context+" in text
                or "Context-" in text
                or "3167682336938e687fd5a2595de316ce471ac4215b08d61b08bde6bd83ca3022" in text
                or "6517fc7e5c68ad42755de2f5da617d7550664638cb463b18defb7beeed3471b0" in text
            )
        except Exception:
            pass
    if hit or content_hit:
        dst = safe_copy(p, "SMALL_FILES")
        manifest.append({
            "source": str(p),
            "copied": str(dst.relative_to(OUT)),
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
        })

# 2) Inspect nearby archives and extract only small members likely to contain
# frozen condition/root/X packet information.
archive_hits = []
for p in ROOT.rglob("*"):
    if not p.is_file():
        continue
    low = str(p).lower()
    if "t1" not in low and "counterfactual" not in low:
        continue
    if p.stat().st_size > 2 * 1024 * 1024 * 1024:
        continue

    try:
        members = []
        opener = None
        if p.name.endswith((".tar.gz",".tgz",".tar")):
            tf = tarfile.open(p, "r:*")
            opener = ("tar", tf)
            for m in tf.getmembers():
                if not m.isfile() or m.size > 5*1024*1024:
                    continue
                name = m.name.lower()
                if any(k.lower() in name for k in KEYWORDS) or "r4" in name:
                    members.append(m)
        elif p.suffix.lower() == ".zip":
            zf = zipfile.ZipFile(p)
            opener = ("zip", zf)
            for info in zf.infolist():
                if info.is_dir() or info.file_size > 5*1024*1024:
                    continue
                name = info.filename.lower()
                if any(k.lower() in name for k in KEYWORDS) or "r4" in name:
                    members.append(info)
        else:
            continue

        if not members:
            if opener:
                opener[1].close()
            continue

        bundle_dir = OUT / "ARCHIVE_MEMBERS" / re.sub(r"[^A-Za-z0-9._-]+","_",p.name)
        bundle_dir.mkdir(parents=True, exist_ok=True)

        extracted = 0
        kind, obj = opener
        for m in members[:300]:
            try:
                name = m.name if kind == "tar" else m.filename
                data = obj.extractfile(m).read() if kind == "tar" else obj.read(m)
                dst = bundle_dir / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
                extracted += 1
            except Exception:
                pass
        obj.close()

        archive_hits.append({
            "archive": str(p),
            "archive_sha256": sha256(p),
            "members_extracted": extracted,
        })
    except Exception:
        continue

# 3) Include frozen matched-control mapping and current v9/v10 metadata so the
# recovered positive root can be cross-walked to its historical negative.
for name in (
    "DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz",
    "T1_V9_BLIND_ADJUDICATION_FROZEN_v1.tar.gz",
    "T1_V9_FULL_BLIND_REVIEW.tar.gz",
    "T1_RESERVE3_V10_BLIND_REVIEW.tar.gz",
):
    p = ROOT / name
    if p.exists() and p.is_file():
        # Do not copy large packet archives wholesale except Step6/frozen maps.
        if p.stat().st_size <= 50*1024*1024:
            dst = safe_copy(p, "CROSSWALK")
            manifest.append({
                "source": str(p),
                "copied": str(dst.relative_to(OUT)),
                "bytes": p.stat().st_size,
                "sha256": sha256(p),
            })

# 4) Search copied textual content for R4 / exact condition-map evidence.
hits = []
for p in OUT.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in TEXT_EXT:
        continue
    try:
        text = p.read_text(errors="ignore")
    except Exception:
        continue
    score = 0
    reasons = []
    for needle in (
        "R4", "Context+", "Context-", "root_id", "croot", "precedent",
        "3167682336938e687fd5a2595de316ce471ac4215b08d61b08bde6bd83ca3022",
        "6517fc7e5c68ad42755de2f5da617d7550664638cb463b18defb7beeed3471b0",
    ):
        if needle.lower() in text.lower():
            score += 1
            reasons.append(needle)
    if score:
        hits.append({
            "file": str(p.relative_to(OUT)),
            "score": score,
            "reasons": reasons,
        })
hits.sort(key=lambda x: (-x["score"], x["file"]))

(OUT / "RECOVERY_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
(OUT / "ARCHIVE_HITS.json").write_text(json.dumps(archive_hits, indent=2) + "\n")
(OUT / "R4_SEARCH_HITS.json").write_text(json.dumps(hits[:200], indent=2) + "\n")

summary = {
    "status": "DONE",
    "small_files_copied": len(manifest),
    "archives_with_relevant_members": len(archive_hits),
    "ranked_text_hits": len(hits),
    "purpose": "Recover exact frozen X/root mapping from completed T1 experiment and crosswalk it to matched historical negative without redefining X.",
}
(OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")

if ARCHIVE.exists():
    ARCHIVE.unlink()
with tarfile.open(ARCHIVE, "w:gz") as tf:
    tf.add(OUT, arcname=OUT.name)

print("STATUS=DONE")
print("SMALL_FILES_COPIED=", len(manifest))
print("ARCHIVES_WITH_RELEVANT_MEMBERS=", len(archive_hits))
print("RANKED_TEXT_HITS=", len(hits))
print("OUTPUT=", ARCHIVE)
print("SHA256=", sha256(ARCHIVE))
PY
