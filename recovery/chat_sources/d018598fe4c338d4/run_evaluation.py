#!/usr/bin/env python3
import argparse, csv, json, shlex, subprocess
from pathlib import Path

def run_shell(command, cwd):
    if not command:
        return {"command": "", "returncode": None, "stdout": "", "stderr": ""}
    p = subprocess.run(
        command, cwd=cwd, shell=True, text=True, capture_output=True, executable="/bin/bash"
    )
    return {
        "command": command,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--run-meta", required=True, help="JSON with pair_id, cell, attempt, run_id")
    ap.add_argument("--functional-cmd", required=True)
    ap.add_argument("--scanner-cmd", required=True)
    ap.add_argument("--scanner-positive-exit", type=int, default=42)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--append-csv")
    args = ap.parse_args()

    meta = json.loads(Path(args.run_meta).read_text())
    worktree = Path(args.worktree)

    functional = run_shell(args.functional_cmd, worktree)
    scanner = run_shell(args.scanner_cmd, worktree)

    functional_pass = functional["returncode"] == 0
    scanner_valid = scanner["returncode"] in (0, args.scanner_positive_exit)
    scanner_positive = scanner["returncode"] == args.scanner_positive_exit if scanner_valid else None

    row = {
        **meta,
        "materialized": True,
        "functional_pass": functional_pass,
        "scanner_valid": scanner_valid,
        "scanner_positive": scanner_positive,
        "functional_returncode": functional["returncode"],
        "scanner_returncode": scanner["returncode"],
    }

    detail = {
        "summary": row,
        "functional": functional,
        "scanner": scanner,
    }
    Path(args.out_json).write_text(json.dumps(detail, indent=2) + "\n")

    if args.append_csv:
        csvp = Path(args.append_csv)
        exists = csvp.exists()
        with csvp.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not exists:
                w.writeheader()
            w.writerow(row)

    print(json.dumps(row, indent=2))

if __name__ == "__main__":
    main()
