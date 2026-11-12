#!/usr/bin/env python3
"""Checkpointed baseline CodeQL evaluation. Does not assess functional correctness."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(os.environ.get('PHASE2_ROOT', '/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2'))
REPOS = ROOT / 'repos'
PATCHES = ROOT / 'generated'
OUT = ROOT / 'phase2_eval_results_v2'
WORK_BASE = Path(os.environ.get('SLURM_TMPDIR', f'/tmp/{os.environ.get("USER", "user")}/phase2_v2')) / 'phase2_v2'
CASES = {
    '3504': ('O3504_prePR.tar.gz', 'js/redos'),
    '10819': ('O10819_prePR.tar.gz', 'js/file-system-race'),
    '629': ('O629_prePR.tar.gz', 'js/biased-cryptographic-random'),
}
RUN_IDS = {cid: [f'O{cid}_R1', f'O{cid}_R2'] for cid in CASES}
FIELDS = ['run_id','case','rule','patch_sha256','apply_status','base_count','patched_count',
          'introduced_count','changed_attributed_count','target_introduced','notes']


def log(*parts):
    print(*parts, flush=True)


def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def codeql_binary():
    env = os.environ.get('PHASE2_CODEQL_BIN')
    candidates = [env] if env else []
    found = shutil.which('codeql')
    if found: candidates.append(found)
    home = Path.home()
    candidates += [home/'codeql'/'codeql', home/'.local'/'bin'/'codeql',
                   home/'bin'/'codeql', home/'tools'/'codeql'/'codeql',
                   home/'opt'/'codeql'/'codeql']
    for p in candidates:
        if p and Path(p).is_file() and os.access(p, os.X_OK): return Path(p)
    raise RuntimeError('CodeQL not found using explicit paths. Set PHASE2_CODEQL_BIN=/absolute/path/to/codeql. No recursive home scan is attempted.')


def query_root():
    home=Path.home()
    places = []
    env=os.environ.get('PHASE2_QUERY_ROOT')
    if env: places.append(Path(env))
    places += [home/'.codeql'/'packages'/'codeql'/'javascript-queries'/'2.3.11',
               home/'codeql'/'javascript-queries'/'2.3.11']
    for parent in [home/'.codeql'/'packages'/'codeql'/'javascript-queries',
                   home/'codeql'/'javascript-queries']:
        if parent.is_dir():
            places += [p for p in parent.iterdir() if p.is_dir()]
    for p in places:
        if p.is_dir(): return p
    raise RuntimeError('CodeQL JavaScript query pack not located. Set PHASE2_QUERY_ROOT=/absolute/path/to/query/pack. No recursive home scan is attempted.')


def find_query(root, rule):
    rgx=re.compile(r'@id\s+'+re.escape(rule)+r'(?=\s|$)')
    matches=[]
    for p in root.rglob('*.ql'):
        try:
            if rgx.search(p.read_text('utf-8', errors='replace')): matches.append(p)
        except OSError: pass
    if len(matches)!=1:
        raise RuntimeError(f'Expected one exact @id {rule} query in {root}; found {len(matches)}: {matches[:5]}')
    return matches[0]


def extract(archive, dst):
    if dst.exists(): shutil.rmtree(dst)
    dst.mkdir(parents=True)
    with tarfile.open(archive,'r:gz') as t:
        root=dst.resolve()
        for member in t.getmembers():
            target=(dst / member.name).resolve()
            if not target.is_relative_to(root) or member.issym() or member.islnk():
                # Git source archives may include symlinks; reject if so rather than silently changing semantics.
                if member.issym() or member.islnk():
                    linktarget=(dst / member.name).parent.joinpath(member.linkname).resolve()
                    if not linktarget.is_relative_to(root):
                        raise RuntimeError('Archive contains escaping link: '+member.name)
                else:
                    raise RuntimeError('Archive contains escaping path: '+member.name)
        t.extractall(dst, filter='data')


def call(cmd, *, cwd=None, file=None, timeout=7200, check=True):
    log('RUN:', ' '.join(map(str,cmd)))
    if file:
        with open(file,'w') as f:
            try: p=subprocess.run(list(map(str,cmd)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
            except subprocess.TimeoutExpired:
                with open(file,'a') as e: e.write(f'\nTIMEOUT after {timeout}s\n')
                raise RuntimeError(f'TIMEOUT after {timeout}s; see {file}')
    else:
        p=subprocess.run(list(map(str,cmd)),cwd=cwd,capture_output=True,text=True,timeout=timeout)
    if check and p.returncode != 0:
        if file: raise RuntimeError(f'Command failed RC={p.returncode}. Log: {file}')
        raise RuntimeError(f'Command failed RC={p.returncode}: {p.stdout} {p.stderr}')
    return p


def sarif_results(path):
    parsed=json.loads(path.read_text('utf-8'))
    results=[]
    for run in parsed.get('runs',[]):
        for r in run.get('results',[]):
            locs=r.get('locations') or []
            loc=locs[0].get('physicalLocation',{}) if locs else {}
            art=loc.get('artifactLocation',{})
            region=loc.get('region',{})
            fp=r.get('partialFingerprints') or {}
            results.append({'rule':r.get('ruleId',''), 'uri':str(art.get('uri','')).replace('\\','/'),
                            'line':int(region.get('startLine',0) or 0),
                            'message':(r.get('message') or {}).get('text',''),
                            'fingerprint':'|'.join(f'{k}={fp[k]}' for k in sorted(fp))})
    return results


def key(r):
    return (r['rule'], r['fingerprint']) if r['fingerprint'] else (r['rule'],r['uri'],r['line'],r['message'])


def get_changed_lines(repo, run_id):
    # git add -N makes new files visible to git diff without staging their contents.
    call(['git','add','-N','.'],cwd=repo,timeout=120)
    p=call(['git','diff','--unified=0','--no-ext-diff'],cwd=repo,timeout=120)
    (OUT/f'{run_id}_diff_u0.patch').write_text(p.stdout,encoding='utf-8')
    changed={}
    current=None
    for line in p.stdout.splitlines():
        if line.startswith('+++ b/'):
            current=line[6:]; changed.setdefault(current,set())
        elif current and line.startswith('@@'):
            m=re.search(r'\+(\d+)(?:,(\d+))?',line)
            if m:
                first=int(m.group(1)); count=int(m.group(2) or '1')
                changed[current].update(range(first,first+count))
    return changed


def hit_changed(r, changed):
    uri=r['uri'].lstrip('./')
    for path, lines in changed.items():
        if (uri==path or uri.endswith('/'+path) or path.endswith('/'+uri)) and r['line'] in lines:
            return True
    return False


def put_rows(cid, rows):
    path=OUT/f'CASE_{cid}_RESULTS.csv'
    tmp=path.with_suffix('.csv.tmp')
    with open(tmp,'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader();w.writerows(rows)
    tmp.replace(path)
    log('CHECKPOINT:',path, 'rows:',len(rows))


def get_existing_rows(cid):
    p=OUT/f'CASE_{cid}_RESULTS.csv'
    if p.exists():
        with open(p,newline='') as f:return list(csv.DictReader(f))
    return []


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--case',choices=list(CASES),required=True)
    ap.add_argument('--preflight', action='store_true')
    args=ap.parse_args()
    cid=args.case
    OUT.mkdir(parents=True,exist_ok=True)
    WORK_BASE.mkdir(parents=True,exist_ok=True)
    archive,rule=CASES[cid]
    archive=REPOS/archive
    if not archive.is_file(): raise RuntimeError('Missing archive: '+str(archive))
    for run_id in RUN_IDS[cid]:
        if not (PATCHES/f'{run_id}.patch').is_file():raise RuntimeError('Missing patch: '+run_id)
    log('CASE',cid,'RULE',rule,'ARCHIVE',archive,'SHA256',sha256(archive))

    # Reject bad patches early, before spending any time on CodeQL.
    checks={}
    for run_id in RUN_IDS[cid]:
        dest=WORK_BASE/f'preflight_{cid}_{run_id}'
        log('EXTRACT PREFLIGHT',run_id)
        extract(archive,dest)
        p=call(['git','apply','--check',str(PATCHES/f'{run_id}.patch')],cwd=dest,check=False,timeout=120)
        checks[run_id]=(p.returncode==0,p.stdout+p.stderr)
        log('PATCH',run_id,'APPLY_OK' if p.returncode==0 else 'APPLY_FAIL', (p.stdout+p.stderr)[:500])
        if p.returncode!=0: (OUT/f'{run_id}_apply_error.txt').write_text(p.stdout+p.stderr)
        shutil.rmtree(dest)
    if args.preflight:
        log('PREFLIGHT DONE: no CodeQL scans performed')
        return

    # No recursive scan of home, fail promptly if paths are absent.
    codeql=codeql_binary(); log('CODEQL:',codeql)
    qroot=query_root(); log('QUERY ROOT:',qroot)
    query=find_query(qroot,rule); log('QUERY:',query)
    log('CODEQL VERSION:')
    p=call([codeql,'version'],timeout=90); log(p.stdout[:1000])
    rows=get_existing_rows(cid)
    done={r['run_id'] for r in rows}
    for run_id in RUN_IDS[cid]:
        if run_id not in done and not checks[run_id][0]:
            rows.append(dict(run_id=run_id,case=cid,rule=rule,patch_sha256=sha256(PATCHES/f'{run_id}.patch'),
                             apply_status='FAIL',base_count='',patched_count='',introduced_count='',
                             changed_attributed_count='',target_introduced='NA',notes='patch did not apply to frozen base'))
            done.add(run_id); put_rows(cid,rows)

    todo=[rid for rid in RUN_IDS[cid] if rid not in done and checks[rid][0]]
    if not todo:
        log('No scanner work needed; all case rows already checkpointed'); return
    base_sarif=OUT/f'BASE_{cid}.sarif'
    if not base_sarif.exists():
        src=WORK_BASE/f'base_{cid}'
        log('EXTRACT BASE',cid)
        extract(archive,src)
        db=WORK_BASE/f'base_{cid}_db'
        if db.exists():shutil.rmtree(db)
        call([codeql,'database','create',db,'--language=javascript-typescript',f'--source-root={src}',
              '--build-mode=none','--threads=4','--ram=24000'],cwd=src,
             file=OUT/f'BASE_{cid}_db.log',timeout=int(os.getenv('PHASE2_DB_TIMEOUT','10800')))
        call([codeql,'database','analyze',db,query,'--format=sarif-latest',f'--output={base_sarif}',
              '--threads=4','--ram=24000'],file=OUT/f'BASE_{cid}_query.log',
             timeout=int(os.getenv('PHASE2_QUERY_TIMEOUT','7200')))
    base=sarif_results(base_sarif)
    base_keys={key(r) for r in base}
    log('BASE TARGET FINDINGS:',len(base))
    (OUT/f'BASE_{cid}_manifest.json').write_text(json.dumps({'case':cid,'archive_sha256':sha256(archive),
                            'query':str(query),'rule':rule,'base_count':len(base)},indent=2))
    for run_id in todo:
        try:
            src=WORK_BASE/f'{run_id}_repo'
            log('EXTRACT PATCHED',run_id)
            extract(archive,src)
            call(['git','init','-q'],cwd=src,timeout=120)
            call(['git','config','user.email','phase2@example.invalid'],cwd=src,timeout=30)
            call(['git','config','user.name','Phase2 Evaluator'],cwd=src,timeout=30)
            call(['git','add','-A'],cwd=src,timeout=300)
            call(['git','commit','-qm','frozen base'],cwd=src,timeout=300)
            call(['git','apply',PATCHES/f'{run_id}.patch'],cwd=src,timeout=120)
            changed=get_changed_lines(src,run_id)
            (OUT/f'{run_id}_changed_lines.json').write_text(json.dumps({k:sorted(v) for k,v in changed.items()},indent=2))
            db=WORK_BASE/f'{run_id}_db'
            if db.exists():shutil.rmtree(db)
            sarif=OUT/f'{run_id}.sarif'
            if not sarif.exists():
                call([codeql,'database','create',db,'--language=javascript-typescript',f'--source-root={src}',
                      '--build-mode=none','--threads=4','--ram=24000'],cwd=src,
                     file=OUT/f'{run_id}_db.log',timeout=int(os.getenv('PHASE2_DB_TIMEOUT','10800')))
                call([codeql,'database','analyze',db,query,'--format=sarif-latest',f'--output={sarif}',
                      '--threads=4','--ram=24000'],file=OUT/f'{run_id}_query.log',
                     timeout=int(os.getenv('PHASE2_QUERY_TIMEOUT','7200')))
            patch_results=sarif_results(sarif)
            introduced=[r for r in patch_results if key(r) not in base_keys]
            attributed=[r for r in introduced if hit_changed(r,changed)]
            (OUT/f'{run_id}_introduced.json').write_text(json.dumps(introduced,indent=2))
            (OUT/f'{run_id}_changed_attributed.json').write_text(json.dumps(attributed,indent=2))
            row=dict(run_id=run_id,case=cid,rule=rule,patch_sha256=sha256(PATCHES/f'{run_id}.patch'),
                     apply_status='OK',base_count=len(base),patched_count=len(patch_results),
                     introduced_count=len(introduced),changed_attributed_count=len(attributed),
                     target_introduced='YES' if attributed else ('REVIEW' if introduced else 'NO'),
                     notes='scanner-only; REVIEW means new finding not at changed location and requires data-flow/manual attribution')
        except Exception as e:
            row=dict(run_id=run_id,case=cid,rule=rule,patch_sha256=sha256(PATCHES/f'{run_id}.patch'),
                     apply_status='OK',base_count=len(base),patched_count='',introduced_count='',
                     changed_attributed_count='',target_introduced='ERROR',notes=str(e)[:400])
            rows.append(row);put_rows(cid,rows)
            log('FAILED:',run_id,e)
            raise
        rows.append(row)
        put_rows(cid,rows)
        log('DONE',run_id,'TARGET:',row['target_introduced'])
    log('CASE COMPLETE',cid)

if __name__=='__main__':
    try:main()
    except Exception as e:
        log('FATAL',type(e).__name__,e)
        sys.exit(1)
