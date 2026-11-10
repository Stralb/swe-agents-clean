from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

COLLECTOR = Path.home() / "research_artifacts" / "export_real122_attack_audit_evidence_cluster.py"

spec = importlib.util.spec_from_file_location("collector", COLLECTOR)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

# Cases 1-26 from the sequential run completed successfully.
# Case 6183 was only STARTED when we stopped it, so rerun from there.
REMAINING = [
    6183,
    7680,
    7682,
    7791,
    7930,
    8135,
    8173,
    9942,
    9992,
    9998,
    10145,
    10146,
    10155,
    10326,
    10339,
    10361,
    10375,
    10773,
    10791,
    11275,
    11276,
    11286,
    11539,
    12313,
    12328,
    12334,
    12344,
    12358,
    12888,
    12898,
    13918,
    13919,
    13922,
    14194,
    15684,
    15686,
    16178,
    16213,
    16262,
    16311,
    16332,
    16341,
]

TASK = int(os.environ["SLURM_ARRAY_TASK_ID"])
TASKS = 6
MY_CASES = REMAINING[TASK::TASKS]

ROOT = Path.home() / "research_artifacts"
JOB = os.environ.get("SLURM_ARRAY_JOB_ID", "manual")

OUT = ROOT / f"f1f5_qc_remaining_{JOB}_task_{TASK}"
CACHE = ROOT / f"f1f5_qc_cache_{JOB}_task_{TASK}"

OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

print(f"Array job: {JOB}")
print(f"Task: {TASK}/{TASKS - 1}")
print(f"Cases: {MY_CASES}")
print(f"Output: {OUT}", flush=True)

con = sqlite3.connect(collector.DEFAULT_DB, timeout=60)
con.row_factory = sqlite3.Row

results = []
errors = []
start = time.time()

for i, case_id in enumerate(MY_CASES, 1):
    print(
        f"[task {TASK}] [{i}/{len(MY_CASES)}] START case {case_id}",
        flush=True,
    )

    before = time.time()

    try:
        result = collector.collect_case(
            con,
            case_id,
            OUT,
            CACHE,
            errors,
        )
    except Exception as exc:
        result = {
            "case_id": case_id,
            "status": "unhandled_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        errors.append(
            f"case {case_id}: {type(exc).__name__}: {exc}"
        )

    results.append(result)

    print(
        f"[task {TASK}] DONE case {case_id} "
        f"status={result.get('status')} "
        f"seconds={round(time.time() - before, 1)}",
        flush=True,
    )

con.close()

collector.write_json(
    OUT / "collection_results.json",
    results,
)

collector.write_json(
    OUT / "summary.json",
    {
        "array_job_id": JOB,
        "array_task_id": TASK,
        "cases": MY_CASES,
        "case_count": len(MY_CASES),
        "elapsed_seconds": round(time.time() - start, 1),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "statuses": {
            str(status): sum(
                1 for r in results if r.get("status") == status
            )
            for status in sorted(
                set(r.get("status") for r in results)
            )
        },
    },
)

(OUT / "collection_errors.log").write_text(
    "\n".join(errors) + ("\n" if errors else ""),
    encoding="utf-8",
)

ZIP = ROOT / f"f1f5_qc_remaining_{JOB}_task_{TASK}.zip"

print(f"Creating {ZIP}", flush=True)
collector.zip_dir(OUT, ZIP)

print(
    f"TASK {TASK} COMPLETE: {ZIP}",
    flush=True,
)
