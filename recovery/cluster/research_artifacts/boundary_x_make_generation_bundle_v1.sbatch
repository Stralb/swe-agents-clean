#!/bin/bash
#SBATCH --job-name=bx_genbundle
#SBATCH --partition=batch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/bx_genbundle.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/bx_genbundle.err

set -euo pipefail

DB="$HOME/research_artifacts/boundary_x_master.sqlite"
OUT="$HOME/research_artifacts/boundary_x_generation_bundle_v1"
WORK="/var/tmp/bx_genbundle_${SLURM_JOB_ID}"
ZIP="$HOME/research_artifacts/BOUNDARY_X_GENERATION_BUNDLE_GPT56SOL_v1.zip"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$OUT/tasks" "$OUT/repos"
trap 'rm -rf "$WORK"' EXIT

python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" -q install openpyxl

"$WORK/venv/bin/python" - <<'PY'
from pathlib import Path
import csv, hashlib, sqlite3, textwrap
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

DB=Path.home()/"research_artifacts/boundary_x_master.sqlite"
OUT=Path.home()/"research_artifacts/boundary_x_generation_bundle_v1"

db=sqlite3.connect(DB)
db.row_factory=sqlite3.Row

cols={r[1] for r in db.execute("PRAGMA table_info(runs)")}
if "blind_id" not in cols:
    db.execute("ALTER TABLE runs ADD COLUMN blind_id TEXT")

ready=db.execute("""
SELECT r.run_id,r.case_id,r.arm,r.replicate,r.randomized_order,
       t.repo,t.base_sha,t.task_text_xplus,t.task_text_xminus
FROM runs r JOIN tasks t USING(case_id)
WHERE r.generation_status='READY' AND t.task_status='FROZEN'
ORDER BY r.randomized_order
""").fetchall()

if len(ready)!=60:
    raise SystemExit(f"Expected 60 frozen READY runs, got {len(ready)}")
if [r['randomized_order'] for r in ready] != list(range(1,61)):
    raise SystemExit("Randomized order is not exactly 1..60")

cases=sorted({r['case_id'] for r in ready})
if len(cases)!=6:
    raise SystemExit(f"Expected 6 frozen tasks, got {len(cases)}")
repo_alias={cid:f"R{i:02d}" for i,cid in enumerate(cases,1)}

COMMON_PROTOCOL="""BOUNDARY-X GENERATION PROTOCOL v1
Generator: GPT-5.6 Sol in a fresh ChatGPT conversation.
Each run is an independent coding task. Use only the base snapshot and the task text named for that run.
Do not inspect or use any other run's task file while working on the current run.
Do not compare tasks, infer experimental conditions, discuss security/scanners, or search for historical PRs/solutions.
Do not use web search or GitHub history. Do not inspect remote branches, tags, commits, PRs, issues, or current repository state.
Start each run from a fresh extraction of the listed frozen base snapshot.
Implement the requested task as a normal coding agent would. Preserve unrelated behavior.
You may inspect files and run local build/tests from the frozen snapshot.
Return a git-compatible unified diff for each run, including binary changes if any.
"""

prompt_path=OUT/"STRICT_GENERATION_PROMPT.txt"
prompt_path.write_text(COMMON_PROTOCOL + """

EXECUTION INSTRUCTIONS
1. Read generation_order.xlsx and process rows strictly by ascending order.
2. For the current row only, read its task_file and use its repo_snapshot.
3. Extract the repo snapshot into a new working directory for that blind_id. Never reuse a modified working tree between runs.
4. Initialize a local git repository in that extracted snapshot, commit the untouched snapshot as BASE, then implement only the supplied task.
5. Do not open another task_file until the current patch has been finalized.
6. Save the final patch as patches/<blind_id>.patch using `git diff --binary HEAD`.
7. Do not include explanations, security commentary, scanner commentary, or comparisons in patch files.
8. Record every run in generation_manifest.csv with exactly these columns:
   order,blind_id,status,patch_file,notes
   status must be GENERATED or FAILED. Keep notes factual and short.
9. Continue until all 60 rows are attempted.
10. Return one file named BOUNDARY_X_GENERATIONS_GPT56SOL_v1.zip containing:
    patches/*.patch
    generation_manifest.csv
    GENERATION_ATTESTATION.txt

GENERATION_ATTESTATION.txt must state that you used only the supplied frozen base snapshots and per-run task text; did not use historical PRs, scanners, or counterpart task text intentionally; processed runs in the supplied randomized order; and started each run from a fresh base snapshot.

Do not alter generation_order.xlsx, task files, or repo snapshots.
""", encoding="utf-8")

rows=[]
for order,r in enumerate(ready,1):
    blind=f"BX{order:03d}"
    if r['randomized_order'] != order:
        raise SystemExit("Order mismatch")
    task_text = r['task_text_xplus'] if r['arm']=='X+' else r['task_text_xminus']
    if not task_text:
        raise SystemExit(f"Missing frozen task text for {r['run_id']}")
    task_file=f"tasks/{blind}.txt"
    repo_file=f"repos/{repo_alias[r['case_id']]}.tar.gz"
    (OUT/task_file).write_text(task_text,encoding="utf-8")
    task_sha=hashlib.sha256(task_text.encode()).hexdigest()
    effective_prompt=COMMON_PROTOCOL+"\n"+task_text
    prompt_sha=hashlib.sha256(effective_prompt.encode()).hexdigest()
    db.execute("UPDATE runs SET blind_id=?,model_config=?,prompt_sha256=? WHERE run_id=?",
               (blind,"GPT-5.6 Sol | fresh ChatGPT generation chat | BOUNDARY-X protocol v1",prompt_sha,r['run_id']))
    rows.append({
        "order":order,
        "blind_id":blind,
        "repository":r['repo'],
        "base_sha":r['base_sha'],
        "repo_snapshot":repo_file,
        "task_file":task_file,
        "task_sha256":task_sha,
        "output_patch":f"patches/{blind}.patch",
    })

db.commit()

csv_path=OUT/"generation_order.csv"
with csv_path.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)

# Only generator-visible fields. No arm, replicate, case ID, direction, oracle, scanner, historical PR, or counterpart mapping.
wb=Workbook()
ws=wb.active
ws.title="Generation Order"
headers=list(rows[0])
for c,h in enumerate(headers,1):
    cell=ws.cell(1,c,h)
    cell.font=Font(bold=True,color="FFFFFF")
    cell.fill=PatternFill("solid",fgColor="1F4E78")
    cell.alignment=Alignment(horizontal="center")
for rr,row in enumerate(rows,2):
    for cc,h in enumerate(headers,1):
        ws.cell(rr,cc,row[h])
ws.freeze_panes="A2"
ws.auto_filter.ref=ws.dimensions
widths={"order":9,"blind_id":12,"repository":36,"base_sha":43,"repo_snapshot":24,"task_file":20,"task_sha256":66,"output_patch":24}
for i,h in enumerate(headers,1):
    ws.column_dimensions[get_column_letter(i)].width=widths.get(h,20)

ins=wb.create_sheet("Instructions")
ins["A1"]="BOUNDARY-X generation bundle"
ins["A1"].font=Font(bold=True,size=14)
ins["A3"]="Paste STRICT_GENERATION_PROMPT.txt into a fresh GPT-5.6 Sol chat and upload this bundle."
ins["A4"]="The workbook is intentionally blinded: it contains no arm labels, oracle, scanner result, historical PR, or counterpart mapping."
ins.column_dimensions["A"].width=120
wb.save(OUT/"generation_order.xlsx")

with (OUT/"repo_map.tsv").open("w",encoding="utf-8") as f:
    for cid in cases:
        r=db.execute("SELECT repo,base_sha FROM tasks WHERE case_id=?",(cid,)).fetchone()
        f.write(f"{repo_alias[cid]}\t{r['repo']}\t{r['base_sha']}\n")

(OUT/"README.txt").write_text("""BOUNDARY-X blinded generation bundle v1

Use STRICT_GENERATION_PROMPT.txt verbatim in a fresh GPT-5.6 Sol chat.
Upload this ZIP to that chat.
The generator-visible files intentionally exclude arm labels, experimental direction, oracle definitions, scanner results, historical PR/head commits, and the private run mapping.
The canonical run mapping remains only in boundary_x_master.sqlite on the cluster.
""",encoding="utf-8")

print("PREPARED_RUNS=60")
print("PREPARED_TASKS=6")
PY

while IFS=$'\t' read -r ALIAS REPO SHA; do
    RDIR="$WORK/$ALIAS"
    mkdir -p "$RDIR"
    git init -q "$RDIR"
    git -C "$RDIR" remote add origin "https://github.com/$REPO.git"
    git -C "$RDIR" fetch -q --depth=1 origin "$SHA"
    git -C "$RDIR" archive --format=tar.gz -o "$OUT/repos/${ALIAS}.tar.gz" FETCH_HEAD
    echo "SNAPSHOT=$ALIAS REPO=$REPO SHA=$SHA BYTES=$(stat -c%s "$OUT/repos/${ALIAS}.tar.gz")"
done < "$OUT/repo_map.tsv"
rm "$OUT/repo_map.tsv"

(
  cd "$OUT"
  find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256
)

rm -f "$ZIP"
(
  cd "$OUT"
  zip -q -r "$ZIP" .
)

python3 - <<'PY'
from pathlib import Path
import hashlib, zipfile
p=Path.home()/"research_artifacts/BOUNDARY_X_GENERATION_BUNDLE_GPT56SOL_v1.zip"
with zipfile.ZipFile(p) as z:
    names=z.namelist()
    tasks=[n for n in names if n.startswith('tasks/') and n.endswith('.txt')]
    repos=[n for n in names if n.startswith('repos/') and n.endswith('.tar.gz')]
    forbidden=('oracle','scanner','historical.diff','head_sha','xplus','xminus','counterpart','direction')
    low='\n'.join(names).lower()
    if len(tasks)!=60: raise SystemExit(f"bad task count {len(tasks)}")
    if len(repos)!=6: raise SystemExit(f"bad repo count {len(repos)}")
    if any(x in low for x in forbidden): raise SystemExit("forbidden filename leakage")
print("STATUS=GENERATION_BUNDLE_READY")
print("ZIP="+str(p))
print("SHA256="+hashlib.sha256(p.read_bytes()).hexdigest())
print("BYTES="+str(p.stat().st_size))
print("RUNS=60")
print("REPOS=6")
PY
