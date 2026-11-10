#!/usr/bin/env python3
import hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if p.returncode != 0:
        print("CMD FAILED:", cmd)
        print(p.stdout)
        print(p.stderr)
        raise SystemExit(p.returncode)
    return p

def write(p, s):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

with tempfile.TemporaryDirectory() as td:
    td = Path(td)

    # Freeze test
    pairs = td / "pairs.json"
    pairs.write_text(json.dumps(["PAIR-A","PAIR-B"]))
    out1, out2 = td/"freeze1", td/"freeze2"
    run([sys.executable, str(ROOT/"freeze_pilot.py"), "--pairs", str(pairs), "--reps", "2", "--seed", "7", "--out", str(out1)])
    run([sys.executable, str(ROOT/"freeze_pilot.py"), "--pairs", str(pairs), "--reps", "2", "--seed", "7", "--out", str(out2)])
    assert (out1/"RUN_SCHEDULE.csv").read_bytes() == (out2/"RUN_SCHEDULE.csv").read_bytes()
    assert len((out1/"RUN_SCHEDULE.csv").read_text().splitlines()) == 1 + 16

    # Packet invariants test
    for role in ("P","N"):
        write(td/f"{role}_issue.txt", f"{role} issue\n")
        write(td/f"{role}_common"/"target.txt", f"{role} common\n")
        write(td/f"{role}_x"/"precedent.txt", f"{role} X\n")
    spec = {
        "pair_id": "PAIR-A",
        "P": {"base_sha":"PBASE","issue_file":str(td/"P_issue.txt"),"common_context_dir":str(td/"P_common"),"x_context_dir":str(td/"P_x")},
        "N": {"base_sha":"NBASE","issue_file":str(td/"N_issue.txt"),"common_context_dir":str(td/"N_common"),"x_context_dir":str(td/"N_x")},
    }
    specp = td/"spec.json"; specp.write_text(json.dumps(spec))
    packets = td/"packets"
    p = run([sys.executable, str(ROOT/"build_packets.py"), "--spec", str(specp), "--out", str(packets)])
    assert "INVARIANTS=PASS" in p.stdout
    assert not (packets/"PAIR-A"/"P-"/"context"/"X").exists()
    assert (packets/"PAIR-A"/"P+"/"context"/"X"/"precedent.txt").exists()
    assert not (packets/"PAIR-A"/"N-"/"context"/"X").exists()
    assert (packets/"PAIR-A"/"N+"/"context"/"X"/"precedent.txt").exists()

    # Materialization test
    repo = td/"repo"; repo.mkdir()
    run(["git","init"], repo)
    run(["git","config","user.email","test@example.com"], repo)
    run(["git","config","user.name","Test"], repo)
    write(repo/"a.txt","old\n")
    run(["git","add","a.txt"], repo)
    run(["git","commit","-m","base"], repo)
    base = run(["git","rev-parse","HEAD"], repo).stdout.strip()

    gen = td/"gen.json"
    gen.write_text(json.dumps({"files":[{"path":"a.txt","op":"write","content":"new\n"},{"path":"b.txt","op":"write","content":"created\n"}]}))
    wt = td/"wt"; diff = td/"out.diff"
    p = run([sys.executable, str(ROOT/"materialize_generation.py"),
             "--repo",str(repo),"--base-sha",base,"--generation-json",str(gen),
             "--worktree",str(wt),"--out-diff",str(diff)])
    assert (wt/"a.txt").read_text() == "new\n"
    assert (wt/"b.txt").read_text() == "created\n"
    assert "a.txt" in diff.read_text()
    assert "b.txt" in diff.read_text()

    # Path traversal must fail.
    bad = td/"bad.json"
    bad.write_text(json.dumps({"files":[{"path":"../escape.txt","content":"x"}]}))
    badwt = td/"badwt"
    q = subprocess.run([sys.executable, str(ROOT/"materialize_generation.py"),
             "--repo",str(repo),"--base-sha",base,"--generation-json",str(bad),
             "--worktree",str(badwt),"--out-diff",str(td/"bad.diff")],
             text=True,capture_output=True)
    assert q.returncode != 0
    assert not (td/"escape.txt").exists()

    # Evaluation test: functional pass + scanner negative
    meta = td/"meta.json"; meta.write_text(json.dumps({"pair_id":"PAIR-A","cell":"N-","attempt":1,"run_id":"x"}))
    ev = td/"eval.json"; csvp = td/"results.csv"
    p = run([sys.executable, str(ROOT/"run_evaluation.py"),
             "--worktree",str(wt),"--run-meta",str(meta),
             "--functional-cmd","test -f a.txt",
             "--scanner-cmd","exit 0",
             "--out-json",str(ev),"--append-csv",str(csvp)])
    data = json.loads(ev.read_text())
    assert data["summary"]["functional_pass"] is True
    assert data["summary"]["scanner_positive"] is False

    # Evaluation test: scanner positive convention
    ev2 = td/"eval2.json"
    p = run([sys.executable, str(ROOT/"run_evaluation.py"),
             "--worktree",str(wt),"--run-meta",str(meta),
             "--functional-cmd","test -f a.txt",
             "--scanner-cmd","exit 42",
             "--out-json",str(ev2)])
    data2 = json.loads(ev2.read_text())
    assert data2["summary"]["scanner_positive"] is True

    print("ALL_TESTS_PASS")
