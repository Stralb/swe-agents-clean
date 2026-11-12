#!/bin/bash
#SBATCH --job-name=t1func22
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_PRIMARY_PILOT_FUNC22_%j.out

set -euo pipefail

ROOT="$HOME/research_artifacts"
GENROOT="$ROOT/T1_PRIMARY_PILOT_GENERATIONS_v1_EXTRACTED/T1_PRIMARY_PILOT_GENERATIONS_v1"
AUDIT="$ROOT/T1_PRIMARY_PILOT_PACKET_AUDIT_v1.tar.gz"
OUT="$ROOT/T1_PRIMARY_PILOT_FUNC22_v1"
NODE_HOME="$HOME/tools/node22"
GROUP="${GROUP:?submit with --export=ALL,GROUP=0 or GROUP=1}"

mkdir -p "$OUT/public" "$OUT/sealed"

# Two internal workers per bigbatch node.
# GROUP=0 -> RUN_001..RUN_004
# GROUP=1 -> RUN_005..RUN_008
if [ "$GROUP" = "0" ]; then
  WORKER_A="1 3"
  WORKER_B="2 4"
elif [ "$GROUP" = "1" ]; then
  WORKER_A="5 7"
  WORKER_B="6 8"
else
  echo "invalid GROUP=$GROUP"
  exit 2
fi

ensure_node22() {
  if [ -x "$NODE_HOME/bin/node" ] && "$NODE_HOME/bin/node" -v | grep -q '^v22\.'; then
    return 0
  fi

  mkdir -p "$HOME/tools"
  lock="$HOME/tools/.node22_install.lock"

  # Serialize install if both jobs start at once.
  exec 9>"$lock"
  flock 9

  if [ -x "$NODE_HOME/bin/node" ] && "$NODE_HOME/bin/node" -v | grep -q '^v22\.'; then
    return 0
  fi

  tmp="${SLURM_TMPDIR:-/tmp}/node22-install"
  rm -rf "$tmp"
  mkdir -p "$tmp"

  url="https://nodejs.org/dist/v22.22.1/node-v22.22.1-linux-x64.tar.xz"
  archive="$tmp/node22.tar.xz"

  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --retry-delay 2 "$url" -o "$archive"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$archive" "$url"
  else
    echo "curl/wget unavailable"
    exit 3
  fi

  rm -rf "$NODE_HOME"
  mkdir -p "$NODE_HOME"
  tar -xJf "$archive" --strip-components=1 -C "$NODE_HOME"

  "$NODE_HOME/bin/node" -v
  "$NODE_HOME/bin/npm" -v
}

ensure_node22

export PATH="$NODE_HOME/bin:$HOME/tools/codeql:$HOME/tools/go/bin:$PATH"

echo "NODE=$(node -v)"
echo "NPM=$(npm -v)"

run_worker() {
  local wid="$1"
  shift
  local runs=("$@")
  local wtmp="${SLURM_TMPDIR:-/tmp}/t1func22_${SLURM_JOB_ID}_${wid}"
  mkdir -p "$wtmp"

  export WID="$wid"
  export RUN_LIST="${runs[*]}"
  export WTMP="$wtmp"
  export ROOT GENROOT AUDIT OUT NODE_HOME

  python3 -u <<'PY'
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(os.environ["ROOT"])
GENROOT = Path(os.environ["GENROOT"])
AUDIT = Path(os.environ["AUDIT"])
OUT = Path(os.environ["OUT"])
WTMP = Path(os.environ["WTMP"])
RUNS = [int(x) for x in os.environ["RUN_LIST"].split()]
WID = os.environ["WID"]

def run(cmd, cwd=None, timeout=1800):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)

def must(cmd, cwd=None, timeout=1800):
    p = run(cmd, cwd=cwd, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"command failed rc={p.returncode}: {cmd}\n{p.stderr[-3000:]}")
    return p

def safe_rel(raw):
    p = Path(raw)
    if not raw or p.is_absolute() or ".." in p.parts:
        raise ValueError("unsafe path")
    return p

with tarfile.open(AUDIT, "r:gz") as tf:
    member = next(m for m in tf.getmembers() if m.isfile() and m.name.endswith("/SEALED_PROVENANCE.json"))
    prov = json.loads(tf.extractfile(member).read().decode())["PAIR_PRIMARY"]

repo_url = f"https://github.com/{prov['repository']}.git"
base_sha = prov["true_base_sha"]

repo = WTMP / "repo"
must(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", repo_url, str(repo)], timeout=900)
must(["git", "fetch", "-q", "origin", base_sha], cwd=repo, timeout=900)

def add_worktree(run_id):
    wt = WTMP / run_id
    must(["git", "worktree", "add", "-q", "--detach", str(wt), base_sha], cwd=repo, timeout=300)
    return wt

def materialize(wt, gen_path):
    data = json.loads(gen_path.read_text())
    for item in data["files"]:
        rel = safe_rel(item["path"])
        dst = wt / rel
        resolved = dst.resolve(strict=False)
        root = wt.resolve()
        if resolved != root and root not in resolved.parents:
            raise RuntimeError("path escape")
        if dst.exists() and dst.is_symlink():
            raise RuntimeError("symlink overwrite refused")
        op = item.get("op", "write")
        if op == "write":
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(item["content"], encoding="utf-8")
        elif op == "delete":
            if dst.exists():
                if dst.is_dir():
                    raise RuntimeError("directory delete refused")
                dst.unlink()
        else:
            raise RuntimeError("unsupported op")
    must(["git", "add", "-A", "--"], cwd=wt)
    dc = run(["git", "diff", "--cached", "--check"], cwd=wt)
    return dc.returncode == 0

def get_scripts(wt):
    pj = wt / "package.json"
    if not pj.exists():
        return None, {}, "NO_PACKAGE_JSON"
    pkg = json.loads(pj.read_text())
    scripts = pkg.get("scripts") or {}
    pm = str(pkg.get("packageManager") or "")
    if (wt/"pnpm-lock.yaml").exists() or pm.startswith("pnpm"):
        return "pnpm", scripts, None
    if (wt/"package-lock.json").exists():
        return "npm", scripts, None
    if (wt/"yarn.lock").exists():
        return "yarn", scripts, None
    return None, scripts, "NO_LOCKFILE"

def cmd_result(cmd, wt, timeout):
    p = run(cmd, cwd=wt, timeout=timeout)
    return {
        "rc": p.returncode,
        "stdout_tail": p.stdout[-8000:],
        "stderr_tail": p.stderr[-8000:],
    }

for n in RUNS:
    run_id = f"RUN_{n:03d}"
    public_path = OUT/"public"/f"{run_id}_functional22.json"
    sealed_dir = OUT/"sealed"/run_id
    sealed_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_id": run_id,
        "materialized": False,
        "diff_check_pass": False,
        "node_major_22": True,
        "install": "NOT_RUN",
        "typecheck": "NOT_AVAILABLE",
        "test": "NOT_AVAILABLE",
        "functional_gate": "INDETERMINATE",
    }
    logs = {}

    try:
        wt = add_worktree(run_id)
        gen = GENROOT/f"{run_id}_generation.json"
        summary["diff_check_pass"] = materialize(wt, gen)
        summary["materialized"] = True

        pm, scripts, problem = get_scripts(wt)
        summary["package_manager"] = pm
        if problem:
            summary["install"] = problem
        else:
            if pm == "npm":
                install_cmd = ["npm","ci"]
                type_cmd = ["npm","run","typecheck"] if "typecheck" in scripts else None
                test_cmd = ["npm","test"] if "test" in scripts else None
            elif pm == "pnpm":
                install_cmd = ["corepack","pnpm","install","--frozen-lockfile"]
                type_cmd = ["corepack","pnpm","run","typecheck"] if "typecheck" in scripts else None
                test_cmd = ["corepack","pnpm","run","test"] if "test" in scripts else None
            else:
                install_cmd = ["corepack","yarn","install","--immutable"]
                type_cmd = ["corepack","yarn","typecheck"] if "typecheck" in scripts else None
                test_cmd = ["corepack","yarn","test"] if "test" in scripts else None

            logs["install"] = cmd_result(install_cmd, wt, 1800)
            summary["install"] = "PASS" if logs["install"]["rc"] == 0 else "FAIL"

            if summary["install"] == "PASS":
                if type_cmd:
                    logs["typecheck"] = cmd_result(type_cmd, wt, 1800)
                    summary["typecheck"] = "PASS" if logs["typecheck"]["rc"] == 0 else "FAIL"
                if test_cmd:
                    logs["test"] = cmd_result(test_cmd, wt, 1800)
                    summary["test"] = "PASS" if logs["test"]["rc"] == 0 else "FAIL"

        if summary["install"] == "PASS":
            available = [x for x in (summary["typecheck"], summary["test"]) if x != "NOT_AVAILABLE"]
            if available and all(x == "PASS" for x in available):
                summary["functional_gate"] = "PASS"
            elif any(x == "FAIL" for x in available):
                summary["functional_gate"] = "FAIL"
            else:
                summary["functional_gate"] = "NEEDS_TASK_REVIEW"
        elif summary["install"] == "FAIL":
            summary["functional_gate"] = "ENV_OR_DEP_FAILURE"

    except Exception as e:
        logs["exception"] = str(e)
        summary["functional_gate"] = "EVALUATION_ERROR"

    public_path.write_text(json.dumps(summary, indent=2) + "\n")
    (sealed_dir/"functional22_logs.json").write_text(json.dumps(logs, indent=2) + "\n")

    print(
        run_id,
        f"materialized={int(summary['materialized'])}",
        f"install={summary['install']}",
        f"typecheck={summary['typecheck']}",
        f"test={summary['test']}",
        f"gate={summary['functional_gate']}",
        flush=True,
    )

print(f"INTERNAL_WORKER_{WID}=DONE", flush=True)
PY
}

run_worker A $WORKER_A > "$OUT/worker_${SLURM_JOB_ID}_A.out" 2>&1 &
P1=$!
run_worker B $WORKER_B > "$OUT/worker_${SLURM_JOB_ID}_B.out" 2>&1 &
P2=$!

wait "$P1"
wait "$P2"

echo "STATUS=GROUP_${GROUP}_DONE"
