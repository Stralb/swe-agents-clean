#!/bin/bash
#SBATCH --job-name=bx_extract
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/boundary_x_extract_v2.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/boundary_x_extract_v2.err

set -euo pipefail

python3 - <<'PY'
from pathlib import Path
import sqlite3, json, zipfile, hashlib

HOME = Path.home()
ART = HOME / "research_artifacts"
D = ART / "D_COMPLETE_ROOT_PROVENANCE_v1_0"
PACKETS = D / "02_PACKETS" / "by_root_A"
DB = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db")
OUT = ART / "boundary_x_census_v2"
OUT.mkdir(parents=True, exist_ok=True)

CONTROL_IDS = [147, 157, 216, 8169, 3280, 282, 285, 200, 332, 314, 489, 424, 5811, 10184, 6064, 3870, 12942, 8134, 9950, 13885, 12343, 3264, 3342, 3373, 18470, 3425, 117, 3489, 3506, 3587, 3584, 18107, 8188, 3679, 3690, 3692, 3885, 4132, 28969, 449, 4215, 4214, 4298, 16272, 4359, 4406, 4622, 4810, 4804, 16296, 549, 5356, 155, 4054, 6105, 31203, 3736, 6192, 6174, 7681, 17908, 7792, 7929, 213, 8150, 8151, 8153, 8171, 8469, 4665, 9988, 10004, 9997, 9995, 471, 10147, 10144, 4208, 35472, 10346, 10314, 10349, 10332, 16252, 10777, 10776, 10789, 10808, 10821, 15711, 3583, 3224, 11538, 16387, 34277, 5, 12335, 12347, 12897, 12357, 4901, 16456, 16638, 14195, 212, 13500, 13921, 150, 14193, 16581, 3362, 15685, 15700, 195, 20097, 20084, 15750, 16179, 16012, 16212, 16210, 17201, 10653, 8474, 11897, 10319, 10357, 8161, 16370, 16188, 16996, 16397, 16437, 102, 156, 368, 4187, 16492, 4153, 7780, 3460, 16591, 16626, 16650, 8148, 12315, 16775, 4606, 16870, 17052, 4410, 17057, 4648, 17078, 17074, 17079, 17321, 17409, 17430, 17476, 3726, 17703, 18468, 18464, 18471, 17044, 3773, 3663, 15735, 15747, 3250, 21657, 3724, 21678, 17411, 16363, 21943, 9979, 3744, 3604, 16433, 3786, 27306, 3768, 31208, 3765, 151, 32758, 4021, 34280]

# Precheck
root_files = sorted(PACKETS.glob("CROOT-*.json"))
if len(root_files) != 342:
    raise SystemExit(f"PRECHECK_FAIL_ROOT_PACKETS={len(root_files)} expected=342")
if not DB.is_file():
    raise SystemExit(f"PRECHECK_FAIL_DB_MISSING={DB}")

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

required = {"cases","repos","issues","pull_requests","pr_files"}
present = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
missing = required - present
if missing:
    raise SystemExit("PRECHECK_FAIL_TABLES=" + ",".join(sorted(missing)))

# Positive-origin population: preserve all 342 frozen root packets as a conservative
# superset. Later eligibility rule 5 removes H/T/non-discretionary roots; this avoids
# recreating Stage-D routing on the cluster.
pos_out = OUT / "POSITIVE_ROOT_PACKETS_342.jsonl"
with pos_out.open("w", encoding="utf-8") as w:
    for p in root_files:
        obj = json.loads(p.read_text(encoding="utf-8"))
        w.write(json.dumps(obj, ensure_ascii=False) + "\n")

def case_context(cid):
    row = con.execute("""
        SELECT
            c.id AS case_id,
            r.full_name AS repository,
            i.number AS issue_number,
            i.url AS issue_url,
            i.title AS issue_title,
            i.body AS issue_body,
            p.number AS pr_number,
            p.url AS pr_url,
            p.title AS pr_title,
            p.body AS pr_body,
            p.base_sha,
            p.head_sha,
            p.additions,
            p.deletions,
            p.changed_files_count
        FROM cases c
        JOIN repos r ON r.id = c.repo_id
        JOIN issues i ON i.id = c.issue_id
        JOIN pull_requests p ON p.id = c.pr_id
        WHERE c.id = ?
    """, (cid,)).fetchone()
    if not row:
        return None
    d = dict(row)

    files = [dict(x) for x in con.execute("""
        SELECT filename, status, additions, deletions, patch
        FROM pr_files
        WHERE pr_id = (SELECT pr_id FROM cases WHERE id = ?)
        ORDER BY filename
    """, (cid,))]

    # Bounded patch export for first-pass eligibility census.
    cap = 120000
    used = 0
    kept = []
    truncated = False
    for f in files:
        block_len = len(f.get("patch") or "")
        if used + block_len > cap:
            remain = max(0, cap - used)
            f = dict(f)
            if remain:
                f["patch"] = (f.get("patch") or "")[:remain]
                kept.append(f)
            truncated = True
            break
        kept.append(f)
        used += block_len

    d["pr_files"] = kept
    d["patch_context_truncated"] = truncated
    d["total_pr_files"] = len(files)
    return d

neg_out = OUT / "NEGATIVE_CONTROLS_190.jsonl"
missing_controls = []
with neg_out.open("w", encoding="utf-8") as w:
    for cid in CONTROL_IDS:
        ctx = case_context(cid)
        if ctx is None:
            missing_controls.append(cid)
            continue
        w.write(json.dumps(ctx, ensure_ascii=False) + "\n")

if missing_controls:
    raise SystemExit("PRECHECK_FAIL_MISSING_CONTROL_CASES=" + ",".join(map(str, missing_controls)))

neg_n = sum(1 for line in neg_out.open(encoding="utf-8") if line.strip())
if neg_n != 190:
    raise SystemExit(f"PRECHECK_FAIL_NEG_ROWS={neg_n} expected=190")

summary = OUT / "SUMMARY.txt"
summary.write_text(
    "BOUNDARY-X CENSUS INPUT\n"
    "POSITIVE_ROOT_PACKETS=342\n"
    "NEGATIVE_CONTROL_WORKFLOWS=190\n"
    "CONTROL_IDS_UNIQUE=190\n"
    "NO_MODEL_GENERATION=YES\n"
    "DB_MODE=READ_ONLY\n",
    encoding="utf-8",
)

zip_path = ART / "BOUNDARY_X_CENSUS_INPUT_v2.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(pos_out, pos_out.name)
    z.write(neg_out, neg_out.name)
    z.write(summary, summary.name)

sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
print(summary.read_text(), end="")
print("ZIP=", zip_path)
print("SHA256=", sha)
print("ZIP_BYTES=", zip_path.stat().st_size)

con.close()
PY
