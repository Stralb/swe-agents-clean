#!/usr/bin/env python3
import argparse, csv, hashlib, json, random
from pathlib import Path

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def stable_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True, help="JSON list of selected anonymized pair IDs")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pairs = json.loads(Path(args.pairs).read_text())
    if not isinstance(pairs, list) or not pairs or len(set(pairs)) != len(pairs):
        raise SystemExit("pairs JSON must be a non-empty list of unique IDs")

    runs = []
    cells = ["P-", "P+", "N-", "N+"]
    for pair_id in pairs:
        for cell in cells:
            for attempt in range(1, args.reps + 1):
                runs.append({
                    "pair_id": pair_id,
                    "cell": cell,
                    "attempt": attempt,
                })

    rng = random.Random(args.seed)
    rng.shuffle(runs)
    for i, run in enumerate(runs, 1):
        run["run_order"] = i
        run["run_id"] = f"{run['pair_id']}__{run['cell'].replace('+','plus').replace('-','minus')}__r{run['attempt']}"

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with (out / "RUN_SCHEDULE.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["run_order","run_id","pair_id","cell","attempt"])
        w.writeheader()
        w.writerows(runs)

    protocol = {
        "pairs": pairs,
        "cells": cells,
        "reps_per_cell": args.reps,
        "seed": args.seed,
        "n_runs": len(runs),
        "invariants": [
            "same historical base within P-/P+",
            "same historical base within N-/N+",
            "same issue text within each historical case",
            "repository base is never edited to create context conditions",
            "only visibility of optional context X differs within +/- cells",
            "one isolated LLM session per run",
            "generated output is materialized without manual repair",
            "functional failure is not counted as scanner-negative evidence",
        ],
    }
    protocol_bytes = stable_json(protocol)
    (out / "FROZEN_PROTOCOL.json").write_bytes(protocol_bytes + b"\n")

    manifest = {
        "schedule_sha256": sha256_bytes((out / "RUN_SCHEDULE.csv").read_bytes()),
        "protocol_sha256": sha256_bytes(protocol_bytes),
    }
    manifest["commitment_sha256"] = sha256_bytes(stable_json(manifest))
    (out / "FREEZE_SHA256.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
