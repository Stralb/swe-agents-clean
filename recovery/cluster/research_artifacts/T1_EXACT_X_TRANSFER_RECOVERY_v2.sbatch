#!/bin/bash
#SBATCH --job-name=t1xrec2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_EXACT_X_TRANSFER_RECOVERY_v2_%j.out

set -euo pipefail

GROUP="${GROUP:?submit with --export=ALL,GROUP=0 or GROUP=1}"

python3 -u <<'PY'
from pathlib import Path
import hashlib, json, os, re, shutil, tarfile, zipfile

ROOT = Path.home() / "research_artifacts"
GROUP = int(os.environ["GROUP"])
OUT = ROOT / f"T1_EXACT_X_TRANSFER_RECOVERY_v2_G{GROUP}"
ARCHIVE = ROOT / f"T1_EXACT_X_TRANSFER_RECOVERY_v2_G{GROUP}.tar.gz"

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

TEXT_EXT = {".json",".jsonl",".csv",".tsv",".md",".txt",".yaml",".yml"}
KEYWORDS = (
    "T1_REAL", "t1_real", "condition", "mechanism", "classifier",
    "packet", "schedule", "manifest", "root", "blind", "adjudication",
    "context", "precedent", "counterfactual"
)
HASH_NEEDLES = (
    "3167682336938e687fd5a2595de316ce471ac4215b08d61b08bde6bd83ca3022",
    "6517fc7e5c68ad42755de2f5da617d7550664638cb463b18defb7beeed3471b0",
)

def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def excluded(p):
    s = str(p)
    return (
        "T1_EXACT_X_TRANSFER_RECOVERY_v1" in s
        or "T1_EXACT_X_TRANSFER_RECOVERY_v2" in s
        or OUT in p.parents
    )

def safe_dst(tag, src, idx):
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", src.name)
    return OUT / tag / f"{idx:05d}_{name}"

records = []
hits = []

if GROUP == 0:
    # Search only small textual experiment metadata, never our own output tree.
    idx = 0
    for p in ROOT.rglob("*"):
        if not p.is_file() or excluded(p):
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > 10*1024*1024 or p.suffix.lower() not in TEXT_EXT:
            continue

        low = str(p).lower()
        if "t1" not in low and "counterfactual" not in low and "real_experiment" not in low:
            continue

        try:
            text = p.read_text(errors="ignore")
        except Exception:
            continue

        score = 0
        reasons = []
        for needle in ("R4","Context+","Context-","precedent","root_id","croot",*HASH_NEEDLES):
            if needle.lower() in text.lower():
                score += 1
                reasons.append(needle)

        if score == 0:
            continue

        idx += 1
        dst = safe_dst("TEXT_HITS", p, idx)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)

        rec = {
            "source": str(p),
            "copied": str(dst.relative_to(OUT)),
            "bytes": size,
            "sha256": sha256(p),
            "score": score,
            "reasons": reasons,
        }
        records.append(rec)
        hits.append(rec)

else:
    # Inspect archive member names and extract only small likely-relevant members.
    idx = 0
    for p in ROOT.rglob("*"):
        if not p.is_file() or excluded(p):
            continue
        low = str(p).lower()
        if "t1" not in low and "counterfactual" not in low:
            continue
        try:
            if p.stat().st_size > 2*1024*1024*1024:
                continue
        except OSError:
            continue

        try:
            if p.name.endswith((".tar.gz",".tgz",".tar")):
                with tarfile.open(p, "r:*") as tf:
                    members = [
                        m for m in tf.getmembers()
                        if m.isfile()
                        and m.size <= 5*1024*1024
                        and (
                            "r4" in m.name.lower()
                            or any(k.lower() in m.name.lower() for k in KEYWORDS)
                        )
                    ]
                    if not members:
                        continue
                    for m in members[:300]:
                        try:
                            data = tf.extractfile(m).read()
                        except Exception:
                            continue
                        idx += 1
                        dst = OUT/"ARCHIVE_MEMBERS"/f"{idx:05d}_{re.sub(r'[^A-Za-z0-9._-]+','_',Path(m.name).name)}"
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(data)
                        records.append({
                            "archive": str(p),
                            "member": m.name,
                            "bytes": len(data),
                            "archive_sha256": sha256(p),
                            "copied": str(dst.relative_to(OUT)),
                        })

            elif p.suffix.lower() == ".zip":
                with zipfile.ZipFile(p) as zf:
                    members = [
                        m for m in zf.infolist()
                        if not m.is_dir()
                        and m.file_size <= 5*1024*1024
                        and (
                            "r4" in m.filename.lower()
                            or any(k.lower() in m.filename.lower() for k in KEYWORDS)
                        )
                    ]
                    if not members:
                        continue
                    for m in members[:300]:
                        try:
                            data = zf.read(m)
                        except Exception:
                            continue
                        idx += 1
                        dst = OUT/"ARCHIVE_MEMBERS"/f"{idx:05d}_{re.sub(r'[^A-Za-z0-9._-]+','_',Path(m.filename).name)}"
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(data)
                        records.append({
                            "archive": str(p),
                            "member": m.filename,
                            "bytes": len(data),
                            "archive_sha256": sha256(p),
                            "copied": str(dst.relative_to(OUT)),
                        })
        except Exception as e:
            records.append({"archive_error": str(p), "error": str(e)[:500]})

    # Rank extracted textual members by exact earlier-experiment evidence.
    for q in (OUT/"ARCHIVE_MEMBERS").glob("*") if (OUT/"ARCHIVE_MEMBERS").exists() else []:
        try:
            text = q.read_text(errors="ignore")
        except Exception:
            continue
        score = 0
        reasons = []
        for needle in ("R4","Context+","Context-","precedent","root_id","croot",*HASH_NEEDLES):
            if needle.lower() in text.lower():
                score += 1
                reasons.append(needle)
        if score:
            hits.append({
                "file": str(q.relative_to(OUT)),
                "score": score,
                "reasons": reasons,
            })

hits.sort(key=lambda x: (-x.get("score",0), json.dumps(x, sort_keys=True)))
(OUT/"RECORDS.json").write_text(json.dumps(records, indent=2)+"\n")
(OUT/"RANKED_HITS.json").write_text(json.dumps(hits[:300], indent=2)+"\n")
(OUT/"SUMMARY.json").write_text(json.dumps({
    "status":"DONE",
    "group":GROUP,
    "records":len(records),
    "ranked_hits":len(hits),
    "purpose":"Recover exact frozen X/root mapping from completed T1 experiment without redefining X."
}, indent=2)+"\n")

if ARCHIVE.exists():
    ARCHIVE.unlink()
with tarfile.open(ARCHIVE, "w:gz") as tf:
    tf.add(OUT, arcname=OUT.name)

print("STATUS=DONE")
print("GROUP=", GROUP)
print("RECORDS=", len(records))
print("RANKED_HITS=", len(hits))
print("OUTPUT=", ARCHIVE)
print("SHA256=", sha256(ARCHIVE))
PY
