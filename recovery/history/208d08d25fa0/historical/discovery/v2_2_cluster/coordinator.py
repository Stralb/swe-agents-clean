from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


ANALYSIS_DIR = Path(os.environ["ANALYSIS_DIR"]).resolve()
OUTROOT = Path(os.environ["OUTROOT"]).resolve()
SOURCE_RUNROOT = Path(os.environ["SOURCE_RUNROOT"]).resolve()
PYTHON_BIN = os.environ["PYTHON_BIN"]
WORKER = ANALYSIS_DIR / "worker.slurm"

# v2.2 is deliberately much smaller than v2/v2.1. It reuses frozen outcome-blind raw artifacts.
PLAN = {
    "audit":          dict(partition="batch",    cpus=4, mem="8G",  time="1-00:00:00", deps=[]),
    "blocks":         dict(partition="bigbatch", cpus=8, mem="64G", time="2-00:00:00", deps=["audit"]),
    "transformations":dict(partition="bigbatch", cpus=8, mem="64G", time="2-00:00:00", deps=["blocks"]),
    "flows":          dict(partition="stampede", cpus=8, mem="24G", time="2-00:00:00", deps=["blocks"]),
    "cochange":       dict(partition="bigbatch", cpus=8, mem="64G", time="2-00:00:00", deps=["blocks"]),
    "templates":      dict(partition="stampede", cpus=8, mem="24G", time="2-00:00:00", deps=["blocks"]),
    "validate":       dict(partition="bigbatch", cpus=8, mem="64G", time="3-00:00:00", deps=["transformations", "cochange"]),
    "catalog":        dict(partition="batch",    cpus=4, mem="8G",  time="1-00:00:00", deps=["validate", "templates"]),
    "report":         dict(partition="batch",    cpus=4, mem="8G",  time="1-00:00:00", deps=["catalog", "flows"]),
}

# Only use fallbacks that can satisfy the same resource request on this cluster.
FALLBACKS = {
    "bigbatch": ["biggpu"],
    "stampede": ["bigbatch"],
    "batch": [],
}

manifest = {
    "version": "v2.2-change-operation-miner-1",
    "submitted_at": now(),
    "outroot": str(OUTROOT),
    "source_runroot": str(SOURCE_RUNROOT),
    "jobs": {},
    "scheduler_status": "SUBMITTING",
}
manifest_path = OUTROOT / "00_audit" / "SUBMITTED_JOBS_V22.json"
write_json(manifest_path, manifest)


def submit(stage: str, spec: dict, dep_ids: list[str]):
    partitions = [spec["partition"]] + FALLBACKS.get(spec["partition"], [])
    attempts = []
    for part in partitions:
        cmd = [
            "sbatch", "--parsable",
            "--job-name", f"fcv22-{stage}",
            "--partition", part,
            "--nodes", "1",
            "--ntasks", "1",
            "--cpus-per-task", str(spec["cpus"]),
            "--mem", spec["mem"],
            "--time", spec["time"],
            "--output", str(OUTROOT / "logs" / f"fcv22-{stage}-%j.out"),
            "--error", str(OUTROOT / "logs" / f"fcv22-{stage}-%j.err"),
            "--export", ",".join([
                "ALL",
                f"ANALYSIS_DIR={ANALYSIS_DIR}",
                f"OUTROOT={OUTROOT}",
                f"SOURCE_RUNROOT={SOURCE_RUNROOT}",
                f"PYTHON_BIN={PYTHON_BIN}",
                f"STAGE={stage}",
            ]),
        ]
        if dep_ids:
            cmd += ["--dependency", "afterok:" + ":".join(dep_ids)]
        cmd.append(str(WORKER))
        print("SBATCH_COMMAND=" + " ".join(cmd), flush=True)
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        msg = (p.stdout or "").strip()
        print(f"SBATCH_EXIT={p.returncode} OUTPUT={msg}", flush=True)
        attempts.append({"partition": part, "returncode": p.returncode, "output": msg})
        if p.returncode == 0:
            jid = msg.split(";", 1)[0].strip()
            return jid, part, attempts
        time.sleep(1)
    return None, None, attempts

job_ids = {}
for stage, spec in PLAN.items():
    missing = [d for d in spec["deps"] if d not in job_ids]
    if missing:
        manifest["jobs"][stage] = {
            "status": "NOT_SUBMITTED_MISSING_DEPENDENCY",
            "missing_dependencies": missing,
            "dependencies": spec["deps"],
        }
        write_json(manifest_path, manifest)
        print(f"STAGE_NOT_SUBMITTED={stage}:missing={','.join(missing)}", flush=True)
        continue

    dep_ids = [job_ids[d] for d in spec["deps"]]
    jid, part, attempts = submit(stage, spec, dep_ids)
    if jid:
        job_ids[stage] = jid
        manifest["jobs"][stage] = {
            "job_id": jid,
            "partition": part,
            "dependencies": dep_ids,
            "cpus": spec["cpus"],
            "mem": spec["mem"],
            "time": spec["time"],
            "attempts": attempts,
            "status": "SUBMITTED",
        }
        print(f"STAGE_SUBMITTED={stage}:{jid}:{part}", flush=True)
    else:
        manifest["jobs"][stage] = {
            "status": "SUBMISSION_FAILED",
            "dependencies": dep_ids,
            "attempts": attempts,
        }
        print(f"STAGE_SUBMISSION_FAILED={stage}", flush=True)
    write_json(manifest_path, manifest)

if len(job_ids) == len(PLAN):
    manifest["scheduler_status"] = "FULL_V22_DAG_SUBMITTED"
    manifest["final_report_job"] = job_ids.get("report")
else:
    manifest["scheduler_status"] = "PARTIAL_V22_DAG_SUBMITTED"
    manifest["submitted_count"] = len(job_ids)
    manifest["expected_count"] = len(PLAN)
write_json(manifest_path, manifest)
print("COORDINATOR_STATUS=" + manifest["scheduler_status"], flush=True)
if manifest.get("final_report_job"):
    print("FINAL_REPORT_JOB=" + str(manifest["final_report_job"]), flush=True)
