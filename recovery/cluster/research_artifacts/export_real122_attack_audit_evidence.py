#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

VERSION = "real122-attack-audit-evidence-v1.0"
DEFAULT_DB = "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db"
OUT_ROOT = Path.home() / "research_artifacts"
CACHE_ROOT = OUT_ROOT / "real122_repo_cache"
MAX_BLOB_BYTES = 3 * 1024 * 1024
MAX_GREP_HITS = 120
MAX_IDENTIFIERS = 18
MAX_LITERALS = 18
MAX_REMOVED_FRAGMENTS = 24

ACTIVE_122 = [
    7930,7791,6104,154,3340,16262,461,4379,5264,5267,10145,10146,10155,169,
    4299,4309,13918,13919,13922,280,4621,3267,5355,15151,668,629,299,415,
    15684,3697,3699,648,13501,12358,13422,10326,10330,10339,10361,16332,
    16341,16343,10773,10779,3581,3582,3592,15686,3448,4207,4216,649,15694,
    15703,3382,9992,9994,9998,10005,7682,12354,704,3882,11286,11539,12925,
    10819,9942,12334,290,291,313,334,8461,3429,16311,15739,15748,15749,3490,
    8135,14194,16298,3622,6145,6150,6183,12344,4408,12361,16301,4811,653,
    3504,10375,708,10791,4134,4135,7680,12328,8147,8149,8152,10270,10277,
    181,3684,16209,16213,8173,12888,11276,664,11275,16203,6017,166,16178,
    12313,12898,608,
]

# All current Present/Not-verifiable footprint cases from the frozen blind audit.
AUDIT_NEEDS_EVIDENCE = [
    166,280,290,291,299,313,334,415,608,653,3382,3622,3684,3697,4299,4309,
    4408,4621,5264,5267,5355,6183,7680,7682,7791,7930,8135,8173,9942,9992,
    9998,10145,10146,10339,10361,10375,10773,10791,11275,11286,11539,12328,
    12334,12344,12888,12898,13918,13919,13922,14194,15686,16178,16213,16262,
    16311,16341,
]

# Fixed reproducible QC sample from cases that were Absent on all five first-pass footprints.
QC_NEGATIVE_SAMPLE = [169,10326,10155,16332,12358,12313,3267,704,15684,6104,4811,11276]

STOPWORDS = {
    "this","that","with","from","have","when","where","what","which","would","should","could",
    "there","their","about","after","before","into","while","does","doesnt","using","used","need",
    "issue","problem","error","fix","change","code","current","expected","actual","please","also",
    "then","than","only","some","more","make","work","works","working","support","version","test",
    "tests","file","files","function","method","class","return","value","values","true","false",
}

SECURITY_RE = r"(security|secure|CVE-[0-9]{4}-[0-9]+|GHSA-[0-9A-Za-z-]+|vulnerab|exploit|XSS|CSRF|SSRF|injection|sanitize|sanitis|auth|permission|credential|secret|token|path traversal|hardening|validation|bypass)"
URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_b64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, sqlite3.Row):
        return {k: json_safe(value[k]) for k in value.keys()}
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(data), indent=2, ensure_ascii=False), encoding="utf-8")


def run(cmd: list[str], timeout: int = 300, text: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=text,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        out = e.stdout if e.stdout is not None else ("" if text else b"")
        err = e.stderr if e.stderr is not None else ("" if text else b"")
        return subprocess.CompletedProcess(cmd, 124, out, err)


def git(git_dir: Path, args: list[str], timeout: int = 300, text: bool = True) -> subprocess.CompletedProcess:
    return run(["git", f"--git-dir={git_dir}", *args], timeout=timeout, text=text)


def table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def columns(con: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(con, table):
        return set()
    return {str(r[1]) for r in con.execute(f"PRAGMA table_info({table})")}


def one(con: sqlite3.Connection, table: str, pk: Any) -> dict[str, Any] | None:
    if not table_exists(con, table):
        return None
    row = con.execute(f"SELECT * FROM {table} WHERE id=?", (pk,)).fetchone()
    return dict(row) if row else None


def rows_where(con: sqlite3.Connection, table: str, col: str, val: Any) -> list[dict[str, Any]]:
    if not table_exists(con, table) or col not in columns(con, table):
        return []
    return [dict(r) for r in con.execute(f"SELECT * FROM {table} WHERE {col}=?", (val,)).fetchall()]


def first(d: dict[str, Any] | None, *names: str) -> Any:
    if not d:
        return None
    for n in names:
        if n in d and d[n] not in (None, ""):
            return d[n]
    return None


def parse_number(row: dict[str, Any] | None) -> int | None:
    v = first(row, "number", "issue_number", "pr_number")
    if v is not None:
        try:
            return int(v)
        except Exception:
            pass
    u = str(first(row, "html_url", "url") or "")
    m = re.search(r"/(?:issues|pulls?|pull)/(\d+)(?:$|[/?#])", u)
    if m:
        return int(m.group(1))
    m = re.search(r"/(\d+)(?:$|[/?#])", u)
    return int(m.group(1)) if m else None


def safe_repo_name(full_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", full_name)


def ensure_repo(full_name: str, git_dir: Path, log: list[str]) -> bool:
    remote = f"https://github.com/{full_name}.git"
    if not git_dir.exists():
        git_dir.parent.mkdir(parents=True, exist_ok=True)
        cp = run(["git", "clone", "--bare", "--filter=blob:none", "--no-tags", remote, str(git_dir)], timeout=1200)
        if cp.returncode != 0:
            log.append(f"clone failed for {full_name}: {cp.stderr[-1200:]}")
            return False
    else:
        git(git_dir, ["remote", "set-url", "origin", remote], timeout=60)
    return True


def have_commit(git_dir: Path, sha: str) -> bool:
    if not sha:
        return False
    cp = git(git_dir, ["cat-file", "-e", f"{sha}^{{commit}}"], timeout=60)
    return cp.returncode == 0


def fetch_commit(git_dir: Path, sha: str, pr_number: int | None, is_head: bool, log: list[str]) -> bool:
    if have_commit(git_dir, sha):
        return True
    cp = git(git_dir, ["fetch", "--no-tags", "--force", "origin", sha], timeout=600)
    if cp.returncode == 0 and have_commit(git_dir, sha):
        return True
    if is_head and pr_number:
        cp2 = git(git_dir, ["fetch", "--no-tags", "--force", "origin", f"refs/pull/{pr_number}/head"], timeout=600)
        if cp2.returncode == 0 and have_commit(git_dir, sha):
            return True
    cp3 = git(git_dir, ["fetch", "--no-tags", "--force", "origin", "+refs/heads/*:refs/heads/*"], timeout=900)
    if cp3.returncode == 0 and have_commit(git_dir, sha):
        return True
    log.append(f"could not fetch commit {sha}: {(cp.stderr or '')[-800:]}")
    return False


def extract_identifiers(text: str) -> list[str]:
    scored: dict[str, int] = {}
    for m in re.finditer(r"`([^`\n]{3,100})`", text or ""):
        token = m.group(1).strip()
        if re.fullmatch(r"[A-Za-z0-9_./:@-]+", token):
            scored[token] = scored.get(token, 0) + 8
    patterns = [
        r"\b[A-Za-z_][A-Za-z0-9_]{2,}\([^\n)]{0,80}\)",
        r"\b[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+\b",
        r"\b[A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)+\b",
        r"\b[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+\b",
        r"\b[A-Za-z_][A-Za-z0-9_.:-]{3,}\b",
    ]
    for p in patterns:
        for m in re.finditer(p, text or ""):
            token = m.group(0).strip()
            token = re.sub(r"\([^)]*\)$", "", token)
            low = token.lower()
            if low in STOPWORDS or len(token) < 4 or token.isdigit():
                continue
            score = 2
            if "_" in token or "/" in token or "." in token or any(c.isupper() for c in token[1:]):
                score += 3
            scored[token] = scored.get(token, 0) + score
    return [k for k, _ in sorted(scored.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[:MAX_IDENTIFIERS]]


def grep_commit(git_dir: Path, commit: str, token: str) -> dict[str, Any]:
    cp = git(git_dir, ["grep", "-n", "-I", "-F", "-e", token, commit, "--"], timeout=90)
    lines = (cp.stdout or "").splitlines()
    return {
        "query": token,
        "returncode": cp.returncode,
        "hit_count_capped": min(len(lines), MAX_GREP_HITS),
        "truncated": len(lines) > MAX_GREP_HITS,
        "hits": lines[:MAX_GREP_HITS],
        "stderr": (cp.stderr or "")[-500:] if cp.returncode not in (0, 1) else "",
    }


def extract_added_literals(diff_text: str) -> list[str]:
    found: dict[str, int] = {}
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        s = line[1:]
        for m in re.finditer(r"(?P<q>['\"`])(?P<v>[^'\"`\n]{4,180})(?P=q)", s):
            v = m.group("v").strip()
            if len(v) < 4 or v.lower() in STOPWORDS:
                continue
            if re.fullmatch(r"[A-Za-z0-9_./:@?&=%+#-]{4,180}", v) or "http" in v.lower() or "/" in v:
                found[v] = found.get(v, 0) + 1
    return [k for k, _ in sorted(found.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[:MAX_LITERALS]]


def changed_paths_from_name_status(text: str) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        vals = parts[1:]
        if status.startswith("R") or status.startswith("C"):
            vals = vals[-2:]
        for p in vals:
            p = p.strip()
            if p and p not in paths:
                paths.append(p)
    return paths


def safe_git_path(path: str) -> str | None:
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts:
        return None
    return str(p)


def save_blob(git_dir: Path, commit: str, repo_path: str, out_root: Path) -> dict[str, Any]:
    safe = safe_git_path(repo_path)
    if not safe:
        return {"path": repo_path, "status": "unsafe_path_skipped"}
    obj = git(git_dir, ["rev-parse", f"{commit}:{repo_path}"], timeout=60)
    if obj.returncode != 0:
        return {"path": repo_path, "status": "not_present"}
    size_cp = git(git_dir, ["cat-file", "-s", obj.stdout.strip()], timeout=60)
    try:
        size = int((size_cp.stdout or "0").strip())
    except Exception:
        size = -1
    meta = {"path": repo_path, "status": "present", "git_object": obj.stdout.strip(), "size": size}
    if size > MAX_BLOB_BYTES:
        meta["content_saved"] = False
        meta["reason"] = f"blob exceeds {MAX_BLOB_BYTES} bytes"
        return meta
    cp = git(git_dir, ["show", f"{commit}:{repo_path}"], timeout=120, text=False)
    if cp.returncode != 0:
        meta["content_saved"] = False
        meta["reason"] = (cp.stderr or b"").decode("utf-8", "replace")[-500:]
        return meta
    dest = out_root / safe
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(cp.stdout or b"")
    meta["content_saved"] = True
    meta["sha256"] = hashlib.sha256(cp.stdout or b"").hexdigest()
    return meta


def removed_fragments(diff0: str) -> list[dict[str, str]]:
    current = None
    out: list[dict[str, str]] = []
    for line in diff0.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*?) b/(.*)$", line)
            current = m.group(2) if m else None
            continue
        if line.startswith("-") and not line.startswith("---") and current:
            frag = line[1:].strip()
            if len(frag) >= 20 and not frag.startswith(("//", "#", "*")):
                frag = frag[:160]
                out.append({"path": current, "fragment": frag})
                if len(out) >= MAX_REMOVED_FRAGMENTS:
                    break
    return out


def all_urls(obj: Any) -> list[str]:
    text = json.dumps(json_safe(obj), ensure_ascii=False)
    urls = []
    for u in URL_RE.findall(text):
        u = u.rstrip(".,;:!?)\"]}'")
        if u not in urls:
            urls.append(u)
    return urls


def zip_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(src.parent))


def collect_case(con: sqlite3.Connection, case_id: int, out_dir: Path, cache_root: Path, global_log: list[str]) -> dict[str, Any]:
    case_log: list[str] = []
    case = one(con, "cases", case_id)
    if not case:
        return {"case_id": case_id, "status": "missing_case"}
    repo = one(con, "repos", case.get("repo_id"))
    issue = one(con, "issues", case.get("issue_id"))
    pr = one(con, "pull_requests", case.get("pr_id"))
    full_name = str(first(repo, "full_name") or "")
    issue_no = parse_number(issue)
    pr_no = parse_number(pr)
    base_sha = str(first(pr, "base_sha") or "")
    head_sha = str(first(pr, "head_sha") or "")

    cdir = out_dir / "cases" / str(case_id)
    cdir.mkdir(parents=True, exist_ok=True)

    db_snapshot = {
        "case": case,
        "repo": repo,
        "issue": issue,
        "pull_request": pr,
        "pr_files": rows_where(con, "pr_files", "pr_id", case.get("pr_id")),
        "ai_markers": rows_where(con, "ai_markers", "case_id", case_id),
        "upstream_features": rows_where(con, "upstream_features", "case_id", case_id),
        "artifact_regions": rows_where(con, "artifact_regions", "case_id", case_id),
        "pr_region_profiles": rows_where(con, "pr_region_profiles", "case_id", case_id),
        "case_retrievals": rows_where(con, "case_retrievals", "case_id", case_id),
    }
    write_json(cdir / "db_snapshot.json", db_snapshot)

    issue_text = "\n".join(str(x or "") for x in [first(issue, "title"), first(issue, "body", "description")])
    pr_text = "\n".join(str(x or "") for x in [first(pr, "title"), first(pr, "body", "description")])
    (cdir / "issue_text_from_db.txt").write_text(issue_text, encoding="utf-8", errors="replace")
    (cdir / "pr_text_from_db.txt").write_text(pr_text, encoding="utf-8", errors="replace")

    meta: dict[str, Any] = {
        "case_id": case_id,
        "repo_full_name": full_name,
        "issue_number": issue_no,
        "pr_number": pr_no,
        "stored_base_sha": base_sha,
        "stored_head_sha": head_sha,
        "started_at": utc_now(),
    }

    if not full_name or not base_sha or not head_sha:
        meta["status"] = "missing_repo_or_sha"
        write_json(cdir / "case_metadata.json", meta)
        return meta

    git_dir = cache_root / f"{safe_repo_name(full_name)}.git"
    if not ensure_repo(full_name, git_dir, case_log):
        meta["status"] = "repo_clone_failed"
        write_json(cdir / "case_metadata.json", meta)
        (cdir / "errors.txt").write_text("\n".join(case_log), encoding="utf-8")
        global_log.extend(f"case {case_id}: {x}" for x in case_log)
        return meta

    ok_base = fetch_commit(git_dir, base_sha, pr_no, False, case_log)
    ok_head = fetch_commit(git_dir, head_sha, pr_no, True, case_log)
    if not (ok_base and ok_head):
        meta["status"] = "commit_fetch_failed"
        write_json(cdir / "case_metadata.json", meta)
        (cdir / "errors.txt").write_text("\n".join(case_log), encoding="utf-8")
        global_log.extend(f"case {case_id}: {x}" for x in case_log)
        return meta

    mb = git(git_dir, ["merge-base", base_sha, head_sha], timeout=120)
    merge_base = (mb.stdout or "").strip() if mb.returncode == 0 else ""
    meta["true_merge_base"] = merge_base
    meta["merge_base_equals_stored_base"] = bool(merge_base and merge_base == base_sha)
    if not merge_base:
        meta["status"] = "merge_base_failed"
        case_log.append((mb.stderr or "")[-1000:])
        write_json(cdir / "case_metadata.json", meta)
        (cdir / "errors.txt").write_text("\n".join(case_log), encoding="utf-8")
        global_log.extend(f"case {case_id}: {x}" for x in case_log)
        return meta

    gdir = cdir / "git_evidence"
    gdir.mkdir(parents=True, exist_ok=True)

    ns = git(git_dir, ["diff", "--name-status", "-M", merge_base, head_sha], timeout=180)
    name_status = ns.stdout or ""
    (gdir / "changed_paths_name_status.txt").write_text(name_status, encoding="utf-8")
    paths = changed_paths_from_name_status(name_status)

    stat = git(git_dir, ["diff", "--stat", merge_base, head_sha], timeout=180)
    (gdir / "diff_stat.txt").write_text(stat.stdout or "", encoding="utf-8")

    patch_path = gdir / "full_patch_u40.diff"
    with patch_path.open("wb") as fh:
        cp = subprocess.run(
            ["git", f"--git-dir={git_dir}", "diff", "--no-ext-diff", "--unified=40", merge_base, head_sha],
            stdout=fh, stderr=subprocess.PIPE, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, check=False,
        )
    if cp.returncode != 0:
        case_log.append(f"full diff failed: {(cp.stderr or b'').decode('utf-8','replace')[-1000:]}")

    diff0 = git(git_dir, ["diff", "--no-ext-diff", "--unified=0", merge_base, head_sha], timeout=300)
    diff0_text = diff0.stdout or ""
    (gdir / "patch_u0.diff").write_text(diff0_text, encoding="utf-8", errors="replace")

    tree = git(git_dir, ["ls-tree", "-r", "--name-only", merge_base], timeout=300)
    (gdir / "pre_pr_tree_paths.txt").write_text(tree.stdout or "", encoding="utf-8", errors="replace")

    blob_meta: dict[str, Any] = {"base": [], "head": []}
    for path in paths:
        blob_meta["base"].append(save_blob(git_dir, merge_base, path, gdir / "base_files"))
        blob_meta["head"].append(save_blob(git_dir, head_sha, path, gdir / "head_files"))
    write_json(gdir / "changed_file_blob_manifest.json", blob_meta)

    ids = extract_identifiers(issue_text)
    write_json(gdir / "issue_identifier_candidates.json", ids)
    write_json(gdir / "identifier_search_pre_pr.json", [grep_commit(git_dir, merge_base, t) for t in ids])
    write_json(gdir / "identifier_search_head.json", [grep_commit(git_dir, head_sha, t) for t in ids])

    literals = extract_added_literals(diff0_text)
    write_json(gdir / "added_literal_candidates.json", literals)
    write_json(gdir / "added_literal_search_pre_pr.json", [grep_commit(git_dir, merge_base, t) for t in literals])

    if paths:
        hist_cmd = [
            "log", merge_base, "-n", "120", "--date=iso-strict",
            "--format=%H%x09%ad%x09%an%x09%s", "--extended-regexp", "--regexp-ignore-case",
            f"--grep={SECURITY_RE}", "--", *paths,
        ]
        sh = git(git_dir, hist_cmd, timeout=300)
        (gdir / "pre_pr_security_commit_history_changed_paths.txt").write_text(sh.stdout or "", encoding="utf-8", errors="replace")
        if sh.returncode not in (0, 1):
            case_log.append(f"security history failed: {(sh.stderr or '')[-700:]}")

    origins = []
    for item in removed_fragments(diff0_text):
        path = item["path"]
        frag = item["fragment"]
        cp2 = git(
            git_dir,
            ["log", merge_base, "-S", frag, "-n", "6", "--date=iso-strict", "--format=%H%x09%ad%x09%an%x09%s", "--", path],
            timeout=180,
        )
        origins.append({
            "path": path,
            "removed_fragment": frag,
            "history_hits": (cp2.stdout or "").splitlines(),
            "stderr": (cp2.stderr or "")[-500:] if cp2.returncode not in (0, 1) else "",
        })
    write_json(gdir / "removed_line_origin_search.json", origins)

    urls = all_urls(db_snapshot)
    (cdir / "external_urls_referenced.txt").write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")

    meta.update({
        "status": "ok",
        "changed_path_count": len(paths),
        "issue_identifier_count": len(ids),
        "added_literal_count": len(literals),
        "external_url_count": len(urls),
        "patch_sha256": sha256_file(patch_path) if patch_path.exists() else None,
        "finished_at": utc_now(),
    })
    write_json(cdir / "case_metadata.json", meta)
    if case_log:
        (cdir / "errors.txt").write_text("\n".join(case_log), encoding="utf-8")
        global_log.extend(f"case {case_id}: {x}" for x in case_log)
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect frozen-protocol evidence for the 122-case F1-F5 audit.")
    parser.add_argument("--db", default=os.environ.get("ARNO_DB", DEFAULT_DB))
    parser.add_argument("--mode", choices=["qc", "all"], default="qc")
    parser.add_argument("--out-root", default=str(OUT_ROOT))
    args = parser.parse_args()

    db_path = Path(args.db)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    cache_root = out_root / "real122_repo_cache"

    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}", file=sys.stderr)
        return 2
    if shutil.which("git") is None:
        print("ERROR: git is not available on PATH", file=sys.stderr)
        return 2

    if len(ACTIVE_122) != 122 or len(set(ACTIVE_122)) != 122:
        print("ERROR: embedded active-case list is not exactly 122 unique IDs", file=sys.stderr)
        return 2

    if args.mode == "qc":
        case_ids = sorted(set(AUDIT_NEEDS_EVIDENCE + QC_NEGATIVE_SAMPLE))
        selection_note = "All frozen first-pass Present/Not-verifiable cases plus a fixed reproducible 12-case all-Absent QC sample."
    else:
        case_ids = list(ACTIVE_122)
        selection_note = "All 122 active cases."

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_name = f"real122_attack_audit_evidence_{args.mode}_{VERSION}_{stamp}"
    bundle_dir = out_root / bundle_name
    bundle_dir.mkdir(parents=True, exist_ok=False)

    con = sqlite3.connect(str(db_path), timeout=60)
    con.row_factory = sqlite3.Row
    quick = con.execute("PRAGMA quick_check").fetchone()[0]

    manifest = {
        "version": VERSION,
        "created_utc": utc_now(),
        "mode": args.mode,
        "selection_note": selection_note,
        "case_ids": case_ids,
        "case_count": len(case_ids),
        "active_122_count": len(ACTIVE_122),
        "database": str(db_path),
        "database_sha256": sha256_file(db_path),
        "database_quick_check": quick,
        "git_version": (run(["git", "--version"], timeout=30).stdout or "").strip(),
        "python_version": sys.version,
        "safety": "Read-only against the SQLite snapshot and GitHub repositories. No builds/tests/scanners are run. Existing risk labels are not read.",
        "external_resource_policy": "URLs are inventoried only. External linked resources are not automatically downloaded; recover exact public versions later only if F5 requires them.",
    }
    write_json(bundle_dir / "manifest.json", manifest)

    readme = f"""{VERSION}\n\nPurpose\n-------\nCollect exact public repository/history evidence needed to QC the frozen F1-F5 real-case audit without changing the footprint definitions.\n\nMode: {args.mode}\nCases: {len(case_ids)}\nSelection: {selection_note}\n\nEvidence collected per case\n---------------------------\n- Raw case/repo/issue/PR rows from the authoritative SQLite snapshot.\n- Stored PR base/head SHA and git-computed true merge-base.\n- Exact pre-PR repository tree path listing.\n- Full PR diff plus changed-file base/head contents up to {MAX_BLOB_BYTES} bytes per file.\n- Repo-wide exact searches at pre-PR state for high-value identifiers extracted from the issue.\n- Same identifier searches at PR head to help inspect F2 reachability/integration.\n- Exact searches for critical-looking string literals added by the patch, to support F5 trusted-grounding checks.\n- Pre-PR security-related commit history restricted to the changed paths.\n- History searches for substantive removed lines, useful for finding the commit that introduced a protection later weakened by the PR.\n- Referenced URLs are inventoried but not fetched automatically.\n\nImportant\n---------\nThis bundle does not assign or change F1-F5 labels. It gathers the Y/H/Z evidence required by the already-frozen protocol.\n"""
    (bundle_dir / "README.txt").write_text(readme, encoding="utf-8")

    global_log: list[str] = []
    results = []
    start = time.time()
    for idx, cid in enumerate(case_ids, 1):
        print(f"[{idx}/{len(case_ids)}] case {cid}", flush=True)
        try:
            results.append(collect_case(con, cid, bundle_dir, cache_root, global_log))
        except Exception as e:
            msg = f"case {cid}: unhandled error: {type(e).__name__}: {e}"
            print(msg, file=sys.stderr, flush=True)
            global_log.append(msg)
            results.append({"case_id": cid, "status": "unhandled_error", "error": str(e)})

    con.close()
    write_json(bundle_dir / "collection_results.json", results)
    (bundle_dir / "collection_errors.log").write_text("\n".join(global_log) + ("\n" if global_log else ""), encoding="utf-8")

    counts: dict[str, int] = {}
    for r in results:
        counts[r.get("status", "unknown")] = counts.get(r.get("status", "unknown"), 0) + 1
    summary = {
        "finished_utc": utc_now(),
        "elapsed_seconds": round(time.time() - start, 2),
        "status_counts": counts,
        "error_line_count": len(global_log),
    }
    write_json(bundle_dir / "summary.json", summary)

    zip_path = out_root / f"{bundle_name}.zip"
    print(f"Creating archive: {zip_path}", flush=True)
    zip_dir(bundle_dir, zip_path)
    sha_path = Path(str(zip_path) + ".sha256")
    sha_path.write_text(f"{sha256_file(zip_path)}  {zip_path.name}\n", encoding="ascii")

    latest_zip = out_root / f"real122_attack_audit_evidence_{args.mode}_LATEST.zip"
    latest_sha = out_root / f"real122_attack_audit_evidence_{args.mode}_LATEST.zip.sha256"
    for link in (latest_zip, latest_sha):
        try:
            if link.exists() or link.is_symlink():
                link.unlink()
        except OSError:
            pass
    latest_zip.symlink_to(zip_path.name)
    latest_sha.symlink_to(sha_path.name)

    print("\nDONE")
    print(f"Bundle directory: {bundle_dir}")
    print(f"ZIP: {zip_path}")
    print(f"SHA256: {sha_path}")
    print(f"Status counts: {counts}")
    if global_log:
        print(f"Warnings/errors recorded: {len(global_log)} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
