#!/usr/bin/env python3
import argparse, json, os, shutil, subprocess
from pathlib import Path

def safe_rel_path(raw):
    p = Path(raw)
    if p.is_absolute() or ".." in p.parts or raw.strip() == "":
        raise ValueError(f"unsafe path: {raw!r}")
    return p

def ensure_inside(root, target):
    root = root.resolve()
    target = target.resolve(strict=False)
    if root != target and root not in target.parents:
        raise ValueError(f"path escapes worktree: {target}")

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--generation-json", required=True)
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--out-diff", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    worktree = Path(args.worktree).resolve()
    if worktree.exists():
        shutil.rmtree(worktree)

    check = run(["git","cat-file","-e",f"{args.base_sha}^{{commit}}"], repo)
    if check.returncode != 0:
        raise SystemExit(f"base sha not found: {args.base_sha}")

    add = run(["git","worktree","add","--detach",str(worktree),args.base_sha], repo)
    if add.returncode != 0:
        raise SystemExit(add.stderr)

    data = json.loads(Path(args.generation_json).read_text())
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise SystemExit("generation JSON must contain a 'files' list")

    seen = set()
    for item in data["files"]:
        if not isinstance(item, dict) or "path" not in item:
            raise SystemExit("each file entry requires 'path'")
        rel = safe_rel_path(item["path"])
        if rel.as_posix() in seen:
            raise SystemExit(f"duplicate path: {rel}")
        seen.add(rel.as_posix())

        dst = worktree / rel
        ensure_inside(worktree, dst)

        # Refuse to follow an existing symlink.
        if dst.exists() and dst.is_symlink():
            raise SystemExit(f"refusing symlink target: {rel}")

        op = item.get("op", "write")
        if op == "write":
            if "content" not in item or not isinstance(item["content"], str):
                raise SystemExit(f"write requires string content: {rel}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(item["content"], encoding="utf-8")
        elif op == "delete":
            if dst.exists():
                if dst.is_dir():
                    raise SystemExit(f"refusing directory delete: {rel}")
                dst.unlink()
        else:
            raise SystemExit(f"unsupported op {op!r} for {rel}")

    stage = run(["git","add","-A","--"], worktree)
    if stage.returncode != 0:
        raise SystemExit(stage.stderr)

    diff = run(["git","diff","--cached","--binary","--no-ext-diff","--"], worktree)
    Path(args.out_diff).write_text(diff.stdout, encoding="utf-8")

    status = run(["git","status","--porcelain"], worktree)
    result = {
        "worktree": str(worktree),
        "changed_paths": [line[3:] for line in status.stdout.splitlines() if len(line) >= 4],
        "materialized": True,
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
