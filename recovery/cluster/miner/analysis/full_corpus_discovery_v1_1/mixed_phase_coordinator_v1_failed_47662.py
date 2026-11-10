from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


analysis_dir = Path(os.environ["ANALYSIS_DIR"]).resolve()
runroot = Path(os.environ["RUNROOT"]).resolve()
repo = Path(os.environ["REPO"]).resolve()
db = Path(os.environ["DB"]).resolve()
python_bin = os.environ["PYTHON_BIN"]
phase = int(os.environ["PHASE"])

worker = analysis_dir / "worker.slurm"
coord = analysis_dir / "mixed_phase_coordinator.slurm"
logdir = runroot / "logs"
manifest_dir = runroot / "00_manifest"

logdir.mkdir(parents=True, exist_ok=True)
manifest_dir.mkdir(parents=True, exist_ok=True)

base_export = (
    f"ALL,"
    f"ANALYSIS_DIR={analysis_dir},"
    f"RUNROOT={runroot},"
    f"REPO={repo},"
    f"DB={db},"
    f"PYTHON_BIN={python_bin}"
)


def submit(cmd):
    print("SBATCH_COMMAND=" + " ".join(cmd), flush=True)
    out = subprocess.check_output(
        cmd,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()

    jobid = out.split(";")[0].strip()
    print("SBATCH_RESULT=" + out, flush=True)
    return jobid


def submit_worker(
    stage,
    partition,
    cpus,
    mem,
    walltime,
    dependency=None,
):
    exports = base_export + f",STAGES={stage}"

    cmd = [
        "sbatch",
        "--parsable",
        "--job-name",
        f"fcdisc-{stage}",
        "--partition",
        partition,
        "--nodes",
        "1",
        "--ntasks",
        "1",
        "--cpus-per-task",
        str(cpus),
        "--mem",
        mem,
        "--time",
        walltime,
        "--output",
        str(logdir / f"fcdisc-{stage}-%j.out"),
        "--error",
        str(logdir / f"fcdisc-{stage}-%j.err"),
        "--export",
        exports,
    ]

    if dependency:
        cmd += [
            "--dependency",
            "afterok:" + ":".join(dependency),
        ]

    cmd.append(str(worker))
    return submit(cmd)


def submit_next_coordinator(next_phase, dependencies):
    exports = (
        base_export
        + f",PHASE={next_phase}"
    )

    cmd = [
        "sbatch",
        "--parsable",
        "--job-name",
        f"fcdisc-mix-p{next_phase}coord",
        "--partition",
        "batch",
        "--nodes",
        "1",
        "--ntasks",
        "1",
        "--cpus-per-task",
        "1",
        "--mem",
        "2G",
        "--time",
        "00:15:00",
        "--dependency",
        "afterok:" + ":".join(dependencies),
        "--output",
        str(logdir / f"mixed-coordinator-p{next_phase}-%j.out"),
        "--error",
        str(logdir / f"mixed-coordinator-p{next_phase}-%j.err"),
        "--export",
        exports,
        str(coord),
    ]

    return submit(cmd)


def load_manifest():
    path = manifest_dir / "MIXED_DAG_JOBS.json"

    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "runroot": str(runroot),
        "scheduler_strategy": (
            "one_biggpu_one_bigbatch_two_stampede"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phases": {},
    }


def save_manifest(data):
    path = manifest_dir / "MIXED_DAG_JOBS.json"
    tmp = manifest_dir / "MIXED_DAG_JOBS.json.tmp"

    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(path)


manifest = load_manifest()
phase_key = f"phase_{phase}"

if phase_key in manifest["phases"]:
    print(
        f"PHASE_ALREADY_SUBMITTED={phase} "
        f"{manifest['phases'][phase_key]}"
    )
    raise SystemExit(0)


if phase == 1:
    jobs = {}

    jobs["landscape"] = submit_worker(
        "landscape",
        "biggpu",
        16,
        "32G",
        "18:00:00",
    )

    jobs["signatures"] = submit_worker(
        "signatures",
        "bigbatch",
        16,
        "32G",
        "18:00:00",
    )

    jobs["patterns"] = submit_worker(
        "patterns",
        "stampede",
        16,
        "48G",
        "24:00:00",
    )

    jobs["topology"] = submit_worker(
        "topology",
        "stampede",
        12,
        "32G",
        "18:00:00",
    )

    next_job = submit_next_coordinator(
        2,
        list(jobs.values()),
    )

    manifest["phases"][phase_key] = {
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs,
        "next_coordinator": next_job,
    }

    save_manifest(manifest)

    print("MIXED_PHASE_1_SUBMITTED=YES")
    print("NEXT_COORDINATOR=" + next_job)


elif phase == 2:
    jobs = {}

    jobs["relationships"] = submit_worker(
        "relationships",
        "biggpu",
        20,
        "48G",
        "1-00:00:00",
    )

    jobs["repository"] = submit_worker(
        "repository",
        "bigbatch",
        16,
        "32G",
        "18:00:00",
    )

    jobs["temporal"] = submit_worker(
        "temporal",
        "stampede",
        12,
        "32G",
        "18:00:00",
    )

    jobs["anomalies"] = submit_worker(
        "anomalies",
        "stampede",
        20,
        "48G",
        "1-00:00:00",
    )

    next_job = submit_next_coordinator(
        3,
        list(jobs.values()),
    )

    manifest["phases"][phase_key] = {
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs,
        "next_coordinator": next_job,
    }

    save_manifest(manifest)

    print("MIXED_PHASE_2_SUBMITTED=YES")
    print("NEXT_COORDINATOR=" + next_job)


elif phase == 3:
    jobs = {}

    jobs["archetypes"] = submit_worker(
        "archetypes",
        "biggpu",
        32,
        "64G",
        "2-12:00:00",
    )

    jobs["text"] = submit_worker(
        "text",
        "bigbatch",
        20,
        "48G",
        "1-00:00:00",
    )

    next_job = submit_next_coordinator(
        4,
        list(jobs.values()),
    )

    manifest["phases"][phase_key] = {
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs,
        "next_coordinator": next_job,
    }

    save_manifest(manifest)

    print("MIXED_PHASE_3_SUBMITTED=YES")
    print("NEXT_COORDINATOR=" + next_job)


elif phase == 4:
    report_job = submit_worker(
        "report",
        "batch",
        8,
        "32G",
        "04:00:00",
    )

    manifest["phases"][phase_key] = {
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "jobs": {
            "report": report_job,
        },
        "next_coordinator": None,
    }

    manifest["final_report_job"] = report_job
    save_manifest(manifest)

    print("MIXED_PHASE_4_SUBMITTED=YES")
    print("FINAL_REPORT_JOB=" + report_job)


else:
    raise RuntimeError(f"Unknown phase: {phase}")
