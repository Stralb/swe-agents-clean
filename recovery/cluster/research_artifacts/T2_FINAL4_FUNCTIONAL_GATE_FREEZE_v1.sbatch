#!/bin/bash
#SBATCH --job-name=t2fgate
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T2_FINAL4_FUNC_GATE_FREEZE_v1_%j.out

set -euo pipefail

python3 -u <<'PY'
import hashlib
import json
import re
import tarfile
from pathlib import Path

ROOT = Path.home() / "research_artifacts"

sealed = []

for s in range(8):
    tar_path = ROOT / f"T2_FINAL4_FUNC_DISCOVERY_SEALED_v1_S{s}.tar.gz"

    with tarfile.open(tar_path, "r:gz") as tf:
        member = next(
            m for m in tf.getmembers()
            if m.isfile() and m.name.endswith(".json")
        )
        obj = json.loads(tf.extractfile(member).read().decode())
        sealed.append(obj)

def covers(root, path):
    root = root.strip("./")
    path = path.replace("\\", "/")

    if not root:
        return True

    return path == root or path.startswith(root + "/")

def test_script(scripts):
    if "test" in scripts:
        return "test"

    priority = ["test:unit", "test:ci", "test:integration"]

    for p in priority:
        if p in scripts:
            return p

    xs = sorted(
        k for k in scripts
        if k.startswith("test:")
    )

    return xs[0] if xs else None

def is_test_config(path):
    name = Path(path).name.lower()

    return bool(
        re.match(r"(vitest|jest|playwright)\.config\.", name)
        or name in {
            "jest.config.js",
            "jest.config.ts",
            "vitest.config.js",
            "vitest.config.ts",
            "playwright.config.js",
            "playwright.config.ts",
        }
    )

frozen = []

for obj in sorted(sealed, key=lambda x: x["shard"]):
    candidates = []

    for pkg in obj["packages"]:
        script = test_script(pkg.get("scripts") or {})

        if script:
            candidates.append({
                "package_root": pkg["package_root"],
                "package_manager": pkg["package_manager"],
                "script": script,
            })

    if not candidates:
        raise RuntimeError(
            f"no deterministic test gate for shard {obj['shard']}"
        )

    target_paths = list(obj.get("test_files") or [])

    if not target_paths:
        target_paths = [
            x["path"]
            for x in obj.get("changed_files") or []
        ]

    selected = {}

    for path in target_paths:
        matches = [
            c for c in candidates
            if covers(c["package_root"], path)
        ]

        if not matches:
            continue

        chosen = sorted(
            matches,
            key=lambda c: (
                -len(c["package_root"]),
                c["package_root"],
                c["script"]
            )
        )[0]

        selected[
            (chosen["package_root"], chosen["script"])
        ] = chosen

    if not selected:
        chosen = sorted(
            candidates,
            key=lambda c: (
                c["package_root"],
                c["script"]
            )
        )[0]

        selected[
            (chosen["package_root"], chosen["script"])
        ] = chosen

    config_files = [
        x["path"]
        for x in obj.get("changed_files") or []
        if is_test_config(x["path"])
    ]

    oracle_files = sorted(set(
        list(obj.get("test_files") or [])
        + list(obj.get("fixture_files") or [])
        + config_files
    ))

    entry = {
        "shard": obj["shard"],
        "run_ids": sorted(obj["run_ids"]),
        "repository": obj["repository"],
        "base_sha": obj["base_sha"],
        "head_sha": obj["head_sha"],
        "gates": sorted(
            selected.values(),
            key=lambda x: (
                x["package_root"],
                x["script"]
            )
        ),
        "oracle_files": oracle_files,
        "historical_test_count": len(
            obj.get("test_files") or []
        ),
        "oracle_file_count": len(oracle_files),
    }

    frozen.append(entry)

sealed_path = (
    ROOT /
    "T2_FINAL4_FUNCTIONAL_GATE_FREEZE_SEALED_v1.json"
)

sealed_path.write_text(
    json.dumps(frozen, indent=2) + "\n"
)

sealed_sha = hashlib.sha256(
    sealed_path.read_bytes()
).hexdigest()

public = {
    "version": "T2_FINAL4_FUNCTIONAL_GATE_FREEZE_v1",
    "task_states": len(frozen),
    "condition_mapping_used": False,
    "scanner_outcomes_used": False,
    "tasks": [
        {
            "shard": x["shard"],
            "run_count": len(x["run_ids"]),
            "gate_family": "test",
            "gate_count": len(x["gates"]),
            "historical_test_count": x[
                "historical_test_count"
            ],
            "oracle_file_count": x[
                "oracle_file_count"
            ],
        }
        for x in frozen
    ],
    "sealed_sha256": sealed_sha,
}

public_path = (
    ROOT /
    "T2_FINAL4_FUNCTIONAL_GATE_FREEZE_PUBLIC_v1.json"
)

public_path.write_text(
    json.dumps(public, indent=2) + "\n"
)

print("STATUS=DONE")
print("TASK_STATES=", len(frozen))
print("SEALED_SHA256=", sealed_sha)
print("SEALED=", sealed_path)
print("PUBLIC=", public_path)

for x in frozen:
    print(
        "SHARD",
        x["shard"],
        "RUNS",
        len(x["run_ids"]),
        "GATES",
        len(x["gates"]),
        "HIST_TESTS",
        x["historical_test_count"],
        "ORACLE_FILES",
        x["oracle_file_count"],
    )
PY
