#!/bin/bash
#SBATCH --job-name=bx_genbundle2
#SBATCH --partition=batch
#SBATCH --time=00:40:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/bx_genbundle2.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/bx_genbundle2.err

set -euo pipefail

DB="$HOME/research_artifacts/boundary_x_master.sqlite"
OUT="$HOME/research_artifacts/boundary_x_generation_bundle_v2_slim"
WORK="/var/tmp/bx_genbundle2_${SLURM_JOB_ID}"
ZIP="$HOME/research_artifacts/BOUNDARY_X_GENERATION_BUNDLE_GPT56SOL_v2_SLIM.zip"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$OUT/tasks" "$OUT/repos"
trap 'rm -rf "$WORK"' EXIT

python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" -q install openpyxl

"$WORK/venv/bin/python" - <<'PY'
from pathlib import Path
import csv, hashlib, sqlite3
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

DB=Path.home()/"research_artifacts/boundary_x_master.sqlite"
OUT=Path.home()/"research_artifacts/boundary_x_generation_bundle_v2_slim"

db=sqlite3.connect(DB)
db.row_factory=sqlite3.Row

ready=db.execute("""
SELECT r.run_id,r.case_id,r.arm,r.replicate,r.randomized_order,r.blind_id,
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

COMMON_PROTOCOL="""BOUNDARY-X GENERATION PROTOCOL v2
Generator: GPT-5.6 Sol in one fresh generation conversation.
Treat every row as a separate coding attempt starting from an untouched frozen base snapshot.
Use only the source snapshot and task text named for the current row.
Do not search the web or GitHub history and do not use historical PRs, scanner findings, evaluator/oracle information, counterpart task text, or experimental labels.
Do not compare rows or infer what experimental condition a row belongs to.
Do not intentionally copy an implementation from an earlier attempt. Solve the current task from its own supplied text and frozen source context.
Preserve unrelated behavior.
The source archives are deterministic text/source snapshots. Large binaries, generated build outputs, dependency caches, and other non-source artifacts are intentionally omitted.
"""

strict = COMMON_PROTOCOL + """

EXECUTION INSTRUCTIONS
1. Read generation_order.xlsx and process rows strictly by ascending order.
2. Work on ONE row at a time. Do not open another task file until the current row is finished.
3. For the current row, extract its repo_snapshot into a NEW working directory and read only its task_file.
4. Initialize a local git repository in the extracted source snapshot and commit the untouched contents as BASE.
5. Implement the requested task as a normal coding agent would using the supplied source context. If a necessary source file is genuinely absent from the slim snapshot, mark that run FAILED_MISSING_CONTEXT rather than inventing unseen code.
6. Save the final unified diff as patches/<blind_id>.patch using `git diff --binary HEAD`.
7. Patch files contain only the diff. No explanations, scanner/security commentary, experimental commentary, or comparisons.
8. Maintain generation_manifest.csv with exactly:
   order,blind_id,status,patch_file,notes
   status must be GENERATED, FAILED_MISSING_CONTEXT, or FAILED_OTHER. Notes must be factual and short.
9. Continue until all 60 rows have been attempted.
10. Return one ZIP named BOUNDARY_X_GENERATIONS_GPT56SOL_v1.zip containing:
    patches/*.patch
    generation_manifest.csv
    GENERATION_ATTESTATION.txt

GENERATION_ATTESTATION.txt must state that only the supplied frozen source snapshots and per-run task text were used; historical PRs, scanners, evaluator/oracle data, counterpart task text, and web/GitHub history were not intentionally used; runs were processed in supplied order; and each attempt started from a fresh snapshot.

Do not modify generation_order.xlsx, task files, repo archives, or MANIFEST.sha256.
"""
(OUT/"STRICT_GENERATION_PROMPT.txt").write_text(strict,encoding="utf-8")

rows=[]
for order,r in enumerate(ready,1):
    blind=r['blind_id'] or f"BX{order:03d}"
    if r['randomized_order'] != order:
        raise SystemExit("Order mismatch")
    task_text=r['task_text_xplus'] if r['arm']=='X+' else r['task_text_xminus']
    if not task_text:
        raise SystemExit(f"Missing task text for {r['run_id']}")
    task_file=f"tasks/{blind}.txt"
    repo_file=f"repos/{repo_alias[r['case_id']]}.tar.gz"
    (OUT/task_file).write_text(task_text,encoding="utf-8")
    rows.append({
        "order":order,
        "blind_id":blind,
        "repository":r['repo'],
        "base_sha":r['base_sha'],
        "repo_snapshot":repo_file,
        "task_file":task_file,
        "task_sha256":hashlib.sha256(task_text.encode()).hexdigest(),
        "output_patch":f"patches/{blind}.patch",
    })

with (OUT/"generation_order.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)

wb=Workbook()
ws=wb.active
ws.title="Generation Order"
headers=list(rows[0])
for c,h in enumerate(headers,1):
    x=ws.cell(1,c,h)
    x.font=Font(bold=True,color="FFFFFF")
    x.fill=PatternFill("solid",fgColor="1F4E78")
    x.alignment=Alignment(horizontal="center")
for rr,row in enumerate(rows,2):
    for cc,h in enumerate(headers,1):
        ws.cell(rr,cc,row[h])
ws.freeze_panes="A2"
ws.auto_filter.ref=ws.dimensions
widths={"order":9,"blind_id":12,"repository":36,"base_sha":43,"repo_snapshot":24,"task_file":20,"task_sha256":66,"output_patch":24}
for i,h in enumerate(headers,1):
    ws.column_dimensions[get_column_letter(i)].width=widths.get(h,20)

ins=wb.create_sheet("Instructions")
ins["A1"]="BOUNDARY-X blinded generation bundle v2 (slim source snapshots)"
ins["A1"].font=Font(bold=True,size=14)
ins["A3"]="Upload this ZIP to one fresh GPT-5.6 Sol generation chat and paste STRICT_GENERATION_PROMPT.txt verbatim."
ins["A4"]="Generator-visible data contain no arm labels, replicate labels, oracle, scanner result, historical PR/head, direction, or counterpart mapping."
ins["A5"]="Large binaries/generated outputs are omitted deterministically; tracked source/config/test files remain."
ins.column_dimensions["A"].width=125
wb.save(OUT/"generation_order.xlsx")

with (OUT/"repo_map.tsv").open("w",encoding="utf-8") as f:
    for cid in cases:
        r=db.execute("SELECT repo,base_sha FROM tasks WHERE case_id=?",(cid,)).fetchone()
        f.write(f"{repo_alias[cid]}\t{r['repo']}\t{r['base_sha']}\n")

(OUT/"README.txt").write_text("""BOUNDARY-X blinded generation bundle v2

Use STRICT_GENERATION_PROMPT.txt verbatim in one fresh GPT-5.6 Sol generation chat.
The six repository archives are deterministic slim source snapshots made from the frozen base commits.
The bundle intentionally excludes experimental arm/direction labels, replicate identities, behavioral oracle definitions, scanner outputs, historical PR/head commits, and the private run mapping.
The canonical private mapping remains only in boundary_x_master.sqlite on the cluster.
""",encoding="utf-8")

print("PREPARED_RUNS=60")
print("PREPARED_TASKS=6")
PY

# Neutral deterministic source/context filter. It does NOT inspect task wording or historical patches.
while IFS=$'\t' read -r ALIAS REPO SHA; do
    RDIR="$WORK/$ALIAS"
    EXPORT="$WORK/export_$ALIAS"
    mkdir -p "$RDIR" "$EXPORT"
    git init -q "$RDIR"
    git -C "$RDIR" remote add origin "https://github.com/$REPO.git"
    git -C "$RDIR" fetch -q --depth=1 origin "$SHA"

    git -C "$RDIR" ls-tree -r -l --full-tree FETCH_HEAD > "$WORK/${ALIAS}_tree.txt"

    python3 - "$RDIR" "$EXPORT" "$WORK/${ALIAS}_tree.txt" <<'PY'
from pathlib import Path
import os, subprocess, sys

repo=Path(sys.argv[1]); out=Path(sys.argv[2]); tree=Path(sys.argv[3])

EXCLUDE_PARTS={
    '.git','node_modules','dist','build','coverage','.next','out','target',
    'vendor','vendors','third_party','third-party','.cache','.turbo',
    'artifacts','generated','__generated__','storybook-static'
}
TEXT_EXT={
    '.ts','.tsx','.js','.jsx','.mjs','.cjs','.mts','.cts',
    '.py','.pyi','.rs','.go','.java','.kt','.kts','.scala',
    '.c','.cc','.cpp','.cxx','.h','.hh','.hpp','.cs','.fs','.fsx',
    '.rb','.php','.swift','.sh','.bash','.zsh','.fish','.ps1',
    '.sql','.graphql','.gql','.proto','.vue','.svelte','.astro',
    '.json','.jsonc','.yaml','.yml','.toml','.ini','.cfg','.conf',
    '.xml','.html','.htm','.css','.scss','.sass','.less',
    '.md','.mdx','.rst','.txt','.properties','.gradle'
}
SPECIAL={
    'package.json','tsconfig.json','jsconfig.json','cargo.toml','go.mod','go.sum',
    'pyproject.toml','setup.py','setup.cfg','requirements.txt','pipfile',
    'dockerfile','makefile','cmakelists.txt','justfile','gemfile','rakefile',
    '.npmrc','.yarnrc','.yarnrc.yml','.pnpmfile.cjs','.gitignore','.gitattributes',
    'eslint.config.js','eslint.config.mjs','vitest.config.ts','vitest.config.js',
    'jest.config.js','jest.config.ts','vite.config.ts','vite.config.js'
}
MAX_FILE=1_500_000
LOCK_MAX=500_000

included=[]; omitted=[]
for line in tree.read_text(errors='replace').splitlines():
    try:
        left,path=line.split('\t',1)
        parts=left.split()
        size=int(parts[3]) if parts[3].isdigit() else 0
    except Exception:
        continue
    pp=Path(path)
    low_parts={p.lower() for p in pp.parts[:-1]}
    name=pp.name.lower(); ext=pp.suffix.lower()
    if low_parts & EXCLUDE_PARTS:
        omitted.append((path,size,'excluded_dir')); continue
    is_lock=name.endswith('.lock') or name in {'package-lock.json','pnpm-lock.yaml','yarn.lock','bun.lock','bun.lockb'}
    allowed=(ext in TEXT_EXT or name in SPECIAL or name.startswith('readme') or name.startswith('license') or name.startswith('contributing'))
    limit=LOCK_MAX if is_lock else MAX_FILE
    if not allowed:
        omitted.append((path,size,'non_source')); continue
    if size>limit:
        omitted.append((path,size,'too_large')); continue
    try:
        data=subprocess.check_output(['git','-C',str(repo),'show',f'FETCH_HEAD:{path}'],stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        omitted.append((path,size,'read_error')); continue
    # Reject files with NUL bytes even if extension looked textual.
    if b'\x00' in data[:8192]:
        omitted.append((path,size,'binary')); continue
    dest=out/path
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(data)
    included.append((path,len(data)))

(out/'REPO_FILE_INDEX.txt').write_text(
    'INCLUDED TRACKED SOURCE/CONFIG/TEST FILES\n' +
    '\n'.join(f'{s}\t{p}' for p,s in included) +
    '\n\nOMITTED TRACKED FILES\n' +
    '\n'.join(f'{reason}\t{s}\t{p}' for p,s,reason in omitted) + '\n',
    encoding='utf-8'
)
(out/'SNAPSHOT_INFO.txt').write_text(
    f'Frozen commit: {subprocess.check_output(["git","-C",str(repo),"rev-parse","FETCH_HEAD"],text=True).strip()}\n'
    f'Included files: {len(included)}\nOmitted files: {len(omitted)}\n',encoding='utf-8')
print(f'INCLUDED={len(included)} OMITTED={len(omitted)}')
PY

    tar -C "$EXPORT" -czf "$OUT/repos/${ALIAS}.tar.gz" .
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
p=Path.home()/"research_artifacts/BOUNDARY_X_GENERATION_BUNDLE_GPT56SOL_v2_SLIM.zip"
with zipfile.ZipFile(p) as z:
    names=z.namelist()
    tasks=[n for n in names if n.startswith('tasks/') and n.endswith('.txt')]
    repos=[n for n in names if n.startswith('repos/') and n.endswith('.tar.gz')]
    forbidden=('oracle','scanner','historical.diff','head_sha','xplus','xminus','counterpart','direction')
    low='\n'.join(names).lower()
    if len(tasks)!=60: raise SystemExit(f"bad task count {len(tasks)}")
    if len(repos)!=6: raise SystemExit(f"bad repo count {len(repos)}")
    if any(x in low for x in forbidden): raise SystemExit("forbidden filename leakage")
print("STATUS=GENERATION_BUNDLE_V2_READY")
print("ZIP="+str(p))
print("SHA256="+hashlib.sha256(p.read_bytes()).hexdigest())
print("BYTES="+str(p.stat().st_size))
print("RUNS=60")
print("REPOS=6")
PY
