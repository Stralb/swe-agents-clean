#!/usr/bin/env python3
import argparse, hashlib, json, shutil
from pathlib import Path

def sha256_file(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def copy_tree(src, dst):
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(src)
    shutil.copytree(src, dst)

def list_files(root):
    out = []
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out.append({
                "path": p.relative_to(root).as_posix(),
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
            })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    required = ["pair_id","P","N"]
    for k in required:
        if k not in spec:
            raise SystemExit(f"missing spec key: {k}")

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    pair = spec["pair_id"]
    rows = []
    for role in ("P","N"):
        role_spec = spec[role]
        for k in ("base_sha","issue_file","common_context_dir","x_context_dir"):
            if k not in role_spec:
                raise SystemExit(f"missing {role}.{k}")

        issue_src = Path(role_spec["issue_file"])
        common_src = Path(role_spec["common_context_dir"])
        x_src = Path(role_spec["x_context_dir"])

        for sign, include_x in (("-", False), ("+", True)):
            cell = f"{role}{sign}"
            cell_dir = out / pair / cell
            (cell_dir / "context").mkdir(parents=True)

            shutil.copy2(issue_src, cell_dir / "ISSUE.txt")
            copy_tree(common_src, cell_dir / "context" / "COMMON")
            if include_x:
                copy_tree(x_src, cell_dir / "context" / "X")

            meta = {
                "pair_id": pair,
                "cell": cell,
                "historical_role": role,
                "base_sha": role_spec["base_sha"],
                "x_visible": include_x,
                "issue_sha256": sha256_file(issue_src),
                "common_files": list_files(common_src),
                "x_files": list_files(x_src) if include_x else [],
            }
            (cell_dir / "PACKET_METADATA.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            rows.append(meta)

    # Invariant checks: same issue/common within +/- for each role.
    by = {r["cell"]: r for r in rows}
    for role in ("P","N"):
        minus, plus = by[f"{role}-"], by[f"{role}+"]
        assert minus["base_sha"] == plus["base_sha"]
        assert minus["issue_sha256"] == plus["issue_sha256"]
        assert minus["common_files"] == plus["common_files"]
        assert minus["x_files"] == []
        assert len(plus["x_files"]) >= 1

    print(f"BUILT {pair}: P-/P+/N-/N+")
    print("INVARIANTS=PASS")

if __name__ == "__main__":
    main()
