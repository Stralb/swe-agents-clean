from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ANALYSIS_DIR = Path(os.environ["ANALYSIS_DIR"]).resolve()
RUNROOT = Path(os.environ["RUNROOT"]).resolve()
REPO = Path(os.environ["REPO"]).resolve()
DB = Path(os.environ["DB"]).resolve()
PYTHON_BIN = os.environ["PYTHON_BIN"]
PHASE = int(os.environ["PHASE"])

WORKER = ANALYSIS_DIR / "worker.slurm"
COORD = ANALYSIS_DIR / "mixed_phase_coordinator_v2.slurm"

LOGDIR = RUNROOT / "logs"
CHECKPOINT_DIR = RUNROOT / "checkpoints"
MANIFEST_DIR = RUNROOT / "00_manifest"
MANIFEST_PATH = MANIFEST_DIR / "MIXED_DAG_JOBS_V2.json"

LOGDIR.mkdir(parents=True, exist_ok=True)
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

BASE_EXPORT = (
    "ALL,"
    f"ANALYSIS_DIR={ANALYSIS_DIR},"
    f"RUNROOT={RUNROOT},"
    f"REPO={REPO},"
    f"DB={DB},"
    f"PYTHON_BIN={PYTHON_BIN}"
)


def now():
    return datetime.now(timezone.utc).isoformat()


def load_manifest():
    if MANIFEST_PATH.exists():
        try:
            return json.loads(
                MANIFEST_PATH.read_text(encoding="utf-8")
            )
        except Exception as exc:
            print(
                "MANIFEST_READ_WARNING="
                + repr(exc),
                flush=True,
            )

    return {
        "version": "scheduler-v2",
        "runroot": str(RUNROOT),
        "created_at": now(),
        "strategy": (
            "1 biggpu + up to 2 stampede + batch; "
            "bigbatch only as fallback"
        ),
        "resource_basis": {
            "bigbatch": "14 CPU/node, ~124 GB/node",
            "stampede": "16 CPU/node, ~30 GB/node",
            "biggpu": "minimum observed 12 CPU/node, ~122 GB/node",
        },
        "phases": {},
    }


def save_manifest(data):
    tmp = MANIFEST_PATH.with_suffix(".json.tmp")

    tmp.write_text(
        json.dumps(
            data,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    tmp.replace(MANIFEST_PATH)


def stage_passed(stage):
    path = CHECKPOINT_DIR / f"{stage}.json"

    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("status") == "PASS"
    except Exception:
        return False


def run_sbatch(cmd):
    print(
        "SBATCH_COMMAND=" + " ".join(cmd),
        flush=True,
    )

    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    output = (proc.stdout or "").strip()

    print(
        "SBATCH_EXIT_CODE=" + str(proc.returncode),
        flush=True,
    )

    print(
        "SBATCH_OUTPUT=" + output,
        flush=True,
    )

    if proc.returncode != 0:
        return None, output

    jobid = output.split(";")[0].strip()

    if not jobid:
        return None, output

    return jobid, output


def worker_command(
    stage,
    partition,
    cpus,
    mem,
    walltime,
):
    exports = BASE_EXPORT + f",STAGES={stage}"

    return [
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
        str(LOGDIR / f"fcdisc-{stage}-%j.out"),
        "--error",
        str(LOGDIR / f"fcdisc-{stage}-%j.err"),
        "--export",
        exports,
        str(WORKER),
    ]


# Each list is ordered primary -> fallback.
#
# All requests fit the physical nodes observed on 2026-08-29.
STAGE_ALLOCATIONS = {
    "signatures": [
        ("biggpu", 8, "16G", "12:00:00"),
        ("batch", 4, "8G", "12:00:00"),
        ("bigbatch", 8, "16G", "12:00:00"),
    ],

    "patterns": [
        ("stampede", 8, "16G", "1-00:00:00"),
        ("bigbatch", 8, "24G", "1-00:00:00"),
    ],

    "topology": [
        ("stampede", 8, "16G", "12:00:00"),
        ("batch", 4, "8G", "12:00:00"),
        ("bigbatch", 8, "16G", "12:00:00"),
    ],

    "relationships": [
        ("biggpu", 8, "64G", "1-12:00:00"),
        ("bigbatch", 8, "48G", "1-12:00:00"),
    ],

    "repository": [
        ("batch", 4, "8G", "12:00:00"),
        ("bigbatch", 8, "16G", "12:00:00"),
    ],

    "temporal": [
        ("stampede", 8, "16G", "12:00:00"),
        ("batch", 4, "8G", "12:00:00"),
        ("bigbatch", 8, "16G", "12:00:00"),
    ],

    "anomalies": [
        ("stampede", 8, "24G", "1-00:00:00"),
        ("bigbatch", 8, "32G", "1-00:00:00"),
    ],

    "archetypes": [
        ("biggpu", 8, "96G", "2-12:00:00"),
        ("bigbatch", 8, "96G", "2-12:00:00"),
    ],

    "text": [
        ("stampede", 8, "24G", "1-00:00:00"),
        ("bigbatch", 8, "32G", "1-00:00:00"),
    ],

    "report": [
        ("batch", 4, "8G", "04:00:00"),
        ("bigbatch", 8, "16G", "04:00:00"),
    ],
}


PHASE_STAGES = {
    1: [
        "landscape",
        "signatures",
        "patterns",
        "topology",
    ],

    2: [
        "relationships",
        "repository",
        "temporal",
        "anomalies",
    ],

    3: [
        "archetypes",
        "text",
    ],

    4: [
        "report",
    ],
}


manifest = load_manifest()

phase_key = f"phase_{PHASE}"

phase_record = manifest["phases"].setdefault(
    phase_key,
    {
        "started_at": now(),
        "jobs": {},
        "skipped_passed": [],
        "submission_failures": {},
        "next_coordinator": None,
    },
)

save_manifest(manifest)


def submit_stage(stage):
    existing = phase_record["jobs"].get(stage)

    if existing and existing.get("job_id"):
        print(
            f"STAGE_ALREADY_RECORDED={stage}:"
            f"{existing['job_id']}",
            flush=True,
        )
        return existing["job_id"]

    if stage_passed(stage):
        print(
            f"STAGE_ALREADY_PASS={stage}",
            flush=True,
        )

        if stage not in phase_record["skipped_passed"]:
            phase_record["skipped_passed"].append(stage)

        save_manifest(manifest)
        return None

    failures = []

    for partition, cpus, mem, walltime in STAGE_ALLOCATIONS[stage]:
        cmd = worker_command(
            stage,
            partition,
            cpus,
            mem,
            walltime,
        )

        jobid, output = run_sbatch(cmd)

        if jobid:
            phase_record["jobs"][stage] = {
                "job_id": jobid,
                "partition": partition,
                "cpus_per_task_requested": cpus,
                "memory_requested": mem,
                "time_requested": walltime,
                "submitted_at": now(),
            }

            save_manifest(manifest)

            print(
                f"STAGE_SUBMITTED={stage}:"
                f"{jobid}:{partition}",
                flush=True,
            )

            return jobid

        failures.append({
            "partition": partition,
            "cpus": cpus,
            "memory": mem,
            "time": walltime,
            "error": output,
        })

        print(
            f"STAGE_SUBMIT_FAILED={stage}:"
            f"{partition}",
            flush=True,
        )

    phase_record["submission_failures"][stage] = failures
    save_manifest(manifest)

    raise RuntimeError(
        f"All scheduler allocations failed for stage {stage}"
    )


def submit_next(next_phase, dependencies):
    existing = phase_record.get("next_coordinator")

    if existing:
        print(
            "NEXT_COORDINATOR_ALREADY_RECORDED="
            + str(existing),
            flush=True,
        )
        return existing

    exports = BASE_EXPORT + f",PHASE={next_phase}"

    cmd = [
        "sbatch",
        "--parsable",
        "--job-name",
        f"fcdisc-v2-p{next_phase}coord",
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
    ]

    if dependencies:
        cmd += [
            "--dependency",
            "afterok:" + ":".join(dependencies),
        ]

    cmd += [
        "--output",
        str(LOGDIR / f"v2-coordinator-p{next_phase}-%j.out"),
        "--error",
        str(LOGDIR / f"v2-coordinator-p{next_phase}-%j.err"),
        "--export",
        exports,
        str(COORD),
    ]

    jobid, output = run_sbatch(cmd)

    if not jobid:
        phase_record["next_coordinator_failure"] = {
            "next_phase": next_phase,
            "error": output,
            "timestamp": now(),
        }

        save_manifest(manifest)

        raise RuntimeError(
            f"Could not submit coordinator for phase {next_phase}"
        )

    phase_record["next_coordinator"] = jobid
    phase_record["next_coordinator_submitted_at"] = now()

    save_manifest(manifest)

    print(
        f"NEXT_COORDINATOR={jobid}",
        flush=True,
    )

    return jobid


if PHASE not in PHASE_STAGES:
    raise RuntimeError(f"Unknown phase: {PHASE}")


dependencies = []

for stage in PHASE_STAGES[PHASE]:
    jobid = submit_stage(stage)

    if jobid:
        dependencies.append(jobid)


phase_record["submission_complete_at"] = now()
phase_record["dependency_jobs"] = dependencies
save_manifest(manifest)


if PHASE < 4:
    submit_next(
        PHASE + 1,
        dependencies,
    )

else:
    phase_record["pipeline_submission_complete_at"] = now()
    manifest["final_report_job"] = (
        phase_record["jobs"].get("report", {}).get("job_id")
    )
    save_manifest(manifest)

    print(
        "FINAL_PHASE_SUBMITTED=YES",
        flush=True,
    )


print(
    f"PHASE_{PHASE}_COORDINATION=PASS",
    flush=True,
)
