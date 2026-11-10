#!/usr/bin/env python3
import csv, hashlib, json, os, re, shutil, subprocess, sys, tarfile, tempfile, urllib.parse, zipfile
from pathlib import Path

CAL=Path(os.environ.get("CAL", Path.home()/"research_artifacts/counterfactual_replay_r1/calibration_medium")).expanduser()
OUT=Path(os.environ.get("EVAL_OUT", CAL/"corrected_target_eval_v1")).expanduser()
MANIFEST=OUT/"RUN_MANIFEST.csv"
PAIR=sys.argv[1]
CODEQL=Path(os.environ.get("CODEQL", Path.home()/"tools/codeql/codeql")).expanduser()
PACK=Path.home()/".codeql/packages/codeql/javascript-queries/2.3.11"
DBSRC=Path(os.environ.get("SOURCE_DB", "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db"))
POS_CASE={"S5PAIR-001":334,"S5PAIR-016":17320,"S5PAIR-025":3581,"S5PAIR-044":21682}

OUT.mkdir(parents=True, exist_ok=True)
(OUT/"run_results").mkdir(exist_ok=True)
(OUT/"sarif").mkdir(exist_ok=True)
(OUT/"cache").mkdir(exist_ok=True)


def run(cmd, cwd=None, timeout=1800, stdout=None):
    p=subprocess.run(cmd,cwd=cwd,text=True,stdout=stdout if stdout is not None else subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if p.returncode!=0:
        raise RuntimeError(f"command failed rc={p.returncode}: {' '.join(map(str,cmd))}\nSTDERR:\n{p.stderr[-5000:]}")
    return p

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def materialize_base(kind, ref, dest):
    dest.mkdir(parents=True,exist_ok=True)
    tar_path=None
    cleanup=[]
    if kind=="repo_tar":
        tar_path=Path(ref)
    elif kind=="input_zip":
        zpath=Path(ref)
        with zipfile.ZipFile(zpath) as z:
            members=[n for n in z.namelist() if Path(n).name=="repo.tar.gz"]
            if len(members)!=1: raise RuntimeError(f"{zpath}: expected one repo.tar.gz, found {len(members)}")
            tar_path=dest.parent/"repo.tar.gz"
            with z.open(members[0]) as src, open(tar_path,'wb') as dst: shutil.copyfileobj(src,dst)
            cleanup.append(tar_path)
    elif kind=="nested_input_zip":
        outer,member=ref.split("::",1)
        nested=dest.parent/"input.zip"; tar_path=dest.parent/"repo.tar.gz"
        with zipfile.ZipFile(outer) as z, z.open(member) as src, open(nested,'wb') as dst: shutil.copyfileobj(src,dst)
        with zipfile.ZipFile(nested) as z:
            members=[n for n in z.namelist() if Path(n).name=="repo.tar.gz"]
            if len(members)!=1: raise RuntimeError("nested input zip lacks unique repo.tar.gz")
            with z.open(members[0]) as src, open(tar_path,'wb') as dst: shutil.copyfileobj(src,dst)
        cleanup.extend([nested,tar_path])
    elif kind=="giant_repo_member":
        outer,member=ref.split("::",1); tar_path=dest.parent/"repo.tar.gz"
        with zipfile.ZipFile(outer) as z, z.open(member) as src, open(tar_path,'wb') as dst: shutil.copyfileobj(src,dst)
        cleanup.append(tar_path)
    else:
        raise RuntimeError(f"unknown base kind {kind}")
    with tarfile.open(tar_path,"r:gz") as tf: tf.extractall(dest)
    for p in cleanup:
        try: p.unlink()
        except Exception: pass
    entries=[p for p in dest.iterdir() if p.name not in {"__MACOSX"}]
    if len(entries)==1 and entries[0].is_dir(): return entries[0], sha256_file(tar_path) if kind=="repo_tar" else None
    return dest, sha256_file(tar_path) if kind=="repo_tar" else None

def extract_patch(kind, ref, outp):
    if kind=="patch": shutil.copy2(ref,outp); return
    if kind=="output_zip":
        with zipfile.ZipFile(ref) as z:
            members=[n for n in z.namelist() if Path(n).name=="submission.patch"]
            if len(members)!=1: raise RuntimeError(f"{ref}: expected one submission.patch, found {len(members)}")
            with z.open(members[0]) as src, open(outp,'wb') as dst: shutil.copyfileobj(src,dst)
        return
    raise RuntimeError(f"unknown patch kind {kind}")

def resolve_query(rule):
    hits=[]
    for q in PACK.rglob("*.ql"):
        try:
            t=q.read_text(encoding='utf-8',errors='ignore')[:12000]
        except Exception: continue
        if re.search(r'@id\s+'+re.escape(rule)+r'\b',t): hits.append(q)
    if len(hits)!=1:
        raise RuntimeError(f"query resolution for {rule}: {len(hits)} hits: {hits[:10]}")
    return hits[0]

def init_git(repo):
    run(["git","init","-q"],cwd=repo)
    run(["git","config","user.email","counterfactual@local"],cwd=repo)
    run(["git","config","user.name","Counterfactual Eval"],cwd=repo)
    run(["git","add","-A"],cwd=repo)
    run(["git","commit","-qm","base"],cwd=repo)

def apply_patch(repo, patch):
    if patch.stat().st_size == 0:
        return "empty_patch_no_change"
    attempts=[
        ["git","apply","--whitespace=nowarn",str(patch)],
        ["git","apply","-p1","--whitespace=nowarn",str(patch)],
        ["git","apply","-p2","--whitespace=nowarn",str(patch)],
    ]
    errs=[]
    for cmd in attempts:
        p=subprocess.run(cmd,cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if p.returncode==0: return " ".join(cmd[1:])
        errs.append(p.stderr[-2000:])
        subprocess.run(["git","reset","--hard","HEAD"],cwd=repo,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(["git","clean","-fd"],cwd=repo,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    raise RuntimeError("patch apply failed\n"+"\n---\n".join(errs))

def changed_ranges(repo, diff_path):
    p=run(["git","diff","--unified=0","HEAD","--"],cwd=repo)
    diff_path.write_text(p.stdout,encoding='utf-8')
    ranges={}; cur=None
    for line in p.stdout.splitlines():
        if line.startswith("+++ b/"):
            cur=line[6:]
            ranges.setdefault(cur,[])
        elif line.startswith("@@") and cur:
            m=re.search(r'\+(\d+)(?:,(\d+))?',line)
            if m:
                start=int(m.group(1)); n=int(m.group(2) or "1")
                if n>0: ranges[cur].append((start,start+n-1))
    return ranges

def codeql_scan(repo, ql, dbdir, sarif):
    if dbdir.exists(): shutil.rmtree(dbdir)
    run([str(CODEQL),"database","create",str(dbdir),"--language=javascript-typescript","--build-mode=none",f"--source-root={repo}","--overwrite","--threads=2","--ram=12000"],timeout=1800)
    run([str(CODEQL),"database","analyze",str(dbdir),str(ql),"--format=sarif-latest",f"--output={sarif}","--threads=2","--ram=12000","--rerun"],timeout=1800)

def uri_path(uri):
    uri=urllib.parse.unquote(uri or "")
    if uri.startswith("file://"):
        uri=urllib.parse.urlparse(uri).path
    return uri.replace('\\','/').lstrip('./')

def loc_from_physical(ploc):
    art=ploc.get("artifactLocation",{}); reg=ploc.get("region",{})
    return {"file":uri_path(art.get("uri","")),"line":int(reg.get("startLine",0) or 0),"end_line":int(reg.get("endLine",reg.get("startLine",0)) or 0)}

def parse_results(sarif, target):
    data=json.loads(Path(sarif).read_text(encoding='utf-8'))
    out=[]
    for rr in data.get("runs",[]):
        for r in rr.get("results",[]):
            if r.get("ruleId")!=target: continue
            locs=[]
            for l in r.get("locations",[]):
                if l.get("physicalLocation"): locs.append(loc_from_physical(l["physicalLocation"]))
            for l in r.get("relatedLocations",[]):
                if l.get("physicalLocation"): locs.append(loc_from_physical(l["physicalLocation"]))
            for cf in r.get("codeFlows",[]):
                for tf in cf.get("threadFlows",[]):
                    for tfl in tf.get("locations",[]):
                        l=tfl.get("location",{})
                        if l.get("physicalLocation"): locs.append(loc_from_physical(l["physicalLocation"]))
            msg=r.get("message",{}).get("text","")
            fps=r.get("partialFingerprints",{}) or {}
            fp=json.dumps(fps,sort_keys=True) if fps else None
            primary=locs[0] if locs else {"file":"","line":0,"end_line":0}
            fallback=(target,primary['file'],primary['line'],msg)
            out.append({"rule":target,"message":msg,"fingerprint":fp,"fallback":fallback,"primary":primary,"locations":locs})
    return out

def overlaps(loc, ranges):
    f=loc['file']
    candidates=[f]
    # SARIF may include absolute source root; suffix matching is used only for changed-file attribution.
    for cf in ranges:
        if f.endswith('/'+cf) or f==cf: candidates.append(cf)
    for c in candidates:
        if c not in ranges: continue
        a=loc.get('line',0); b=loc.get('end_line',a)
        for x,y in ranges[c]:
            if max(a,x) <= min(b,y): return True
    return False

def result_key(r): return ("fp",r['fingerprint']) if r['fingerprint'] else ("fb",)+tuple(r['fallback'])

def hist_anchor(pair,target):
    if not DBSRC.exists(): return (None,None)
    import sqlite3
    con=sqlite3.connect(DBSRC)
    row=con.execute("SELECT file_path,line FROM scanner_findings WHERE case_id=? AND scanner='codeql' AND rule_id=? AND introduced=1 ORDER BY id LIMIT 1",(POS_CASE[pair],target)).fetchone()
    con.close()
    return row if row else (None,None)

rows=[]
with MANIFEST.open(newline='',encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r['pair_id']==PAIR:
            rows.append(r)

run_only=os.environ.get("RUN_ONLY")
if run_only:
    rows=[r for r in rows if r["run_id"]==run_only]
    if len(rows)!=1:
        raise SystemExit(f"{PAIR}: RUN_ONLY={run_only} matched {len(rows)} runs")
else:
    if len(rows)!=4:
        raise SystemExit(f"{PAIR}: expected 4 runs, got {len(rows)}")

for r in rows:
    rid=r['run_id']; target=r['target_rule']; result_path=OUT/"run_results"/f"{rid}.json"
    work=Path(tempfile.mkdtemp(prefix=f"cf_{rid}_",dir=os.environ.get("TMPDIR",None)))
    rec={"run_id":rid,"pair_id":PAIR,"condition":r['condition'],"target_rule":target,"status":"ERROR"}
    try:
        srcdir=work/"src"
        repo,_=materialize_base(r['base_kind'],r['base_ref'],srcdir)
        patch=work/"submission.patch"; extract_patch(r['patch_kind'],r['patch_ref'],patch)
        init_git(repo)
        ql=resolve_query(target); rec['query_file']=str(ql)
        # Base cache key includes the exact committed source tree hash and target rule.
        tree=run(["git","rev-parse","HEAD^{tree}"],cwd=repo).stdout.strip()
        cachekey=hashlib.sha256((tree+"|"+target).encode()).hexdigest()[:20]
        rec['base_tree']=tree; rec['base_cache_key']=cachekey
        base_sarif=OUT/"cache"/f"{cachekey}.base.sarif"
        if not base_sarif.exists():
            codeql_scan(repo,ql,work/"db_base",base_sarif)
        base=parse_results(base_sarif,target)
        rec['base_target_count']=len(base)
        rec['patch_apply_method']=apply_patch(repo,patch)
        ranges=changed_ranges(repo,work/"generated.diff")
        rec['changed_files']=sorted(ranges)
        rec['changed_ranges']={k:v for k,v in ranges.items()}
        patched_sarif=OUT/"sarif"/f"{rid}.patched.sarif"
        codeql_scan(repo,ql,work/"db_patched",patched_sarif)
        patched=parse_results(patched_sarif,target)
        rec['patched_target_count']=len(patched)
        base_keys={result_key(x) for x in base}
        new=[x for x in patched if result_key(x) not in base_keys]
        for x in new:
            x['primary_changed']=overlaps(x['primary'],ranges)
            x['any_changed']=any(overlaps(l,ranges) for l in x['locations'])
        rec['new_target_count']=len(new)
        rec['new_primary_changed_count']=sum(1 for x in new if x['primary_changed'])
        rec['new_any_changed_count']=sum(1 for x in new if x['any_changed'])
        rec['target_introduced_primary']=rec['new_primary_changed_count']>0
        rec['target_introduced_diff_linked']=rec['new_any_changed_count']>0
        hf,hl=hist_anchor(PAIR,target); rec['historical_file']=hf; rec['historical_line']=hl
        rec['same_historical_file']=bool(hf and any((x['primary']['file']==hf or x['primary']['file'].endswith('/'+hf)) for x in new if x['any_changed']))
        rec['new_results']=[{"primary":x['primary'],"message":x['message'],"primary_changed":x['primary_changed'],"any_changed":x['any_changed'],"fingerprint":x['fingerprint']} for x in new]
        rec['status']="OK"
    except Exception as e:
        rec['error']=str(e)
    finally:
        result_path.write_text(json.dumps(rec,indent=2,ensure_ascii=False),encoding='utf-8')
        shutil.rmtree(work,ignore_errors=True)
        print(rid, rec['status'], "base",rec.get('base_target_count'),"patched",rec.get('patched_target_count'),"introduced",rec.get('target_introduced_diff_linked'), flush=True)
