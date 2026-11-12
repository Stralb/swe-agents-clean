#!/usr/bin/env python3
"""Historical PR candidate replay; writes ONLY historical_controls_v1/.

Uses frozen source and original v2 CodeQL baseline/query setup. Does not modify
experimental patches/results. An online PR .patch is not necessarily the exact
historical dataset snapshot; this evaluator records it as a candidate.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import phase2_eval_v2 as ev

ROOT = Path(os.getenv('PHASE2_ROOT', '/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2'))
OUT = ROOT / 'historical_controls_v1'
PATCH_DIR = OUT / 'patches'
WORK = Path(os.getenv('SLURM_TMPDIR', f'/tmp/{os.getenv("USER", "user")}/phase2_historical_v1')) / 'phase2_historical_v1'
CASE = {
    '3504': {'archive': 'O3504_prePR.tar.gz', 'repo': 'pingdotgg/t3code', 'pr': 4167,
             'rule': 'js/redos', 'file': 'packages/shared/src/composerInlineTokens.ts',
             'anchor': 'SCOPED_PACKAGE_REFERENCE_REGEX'},
    '10819': {'archive': 'O10819_prePR.tar.gz', 'repo': 'evilz/vscode-reveal', 'pr': 1477,
              'rule': 'js/file-system-race', 'file': 'src/RevealServer.ts',
              'anchor': 'fs.readFileSync(htmlFragmentPath'},
    '629': {'archive': 'O629_prePR.tar.gz', 'repo': 'ZHANGTIANYAO1/teamspeak-music-bot', 'pr': 118,
            'rule': 'js/biased-cryptographic-random', 'file': 'src/music/spotify/spotify-oauth.ts',
            'anchor': 'bytes[i] % PKCE_CHARS.length'},
}
FIELDS = ['case','repository','pr_number','rule','base_archive_sha256','pr_patch_sha256',
          'candidate_patch_applies','expected_code_present','scanner_status','base_count',
          'patched_count','introduced_count','changed_attributed_count','notes']


def log(*xs): print(*xs, flush=True)


def write_row(cid, row):
    out=OUT / f'HIST_{cid}_RESULTS.csv'
    tmp=out.with_suffix('.csv.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader(); writer.writerow(row)
    tmp.replace(out)
    log('CHECKPOINT',out)


def main(cid):
    cfg=CASE[cid]
    OUT.mkdir(parents=True,exist_ok=True)
    WORK.mkdir(parents=True,exist_ok=True)
    ev.OUT=OUT # Historical outputs ONLY (do not overwrite experimental results)
    pfile=PATCH_DIR / f'H{cid}_PR{cfg["pr"]}.patch'
    archive=ROOT/'repos'/cfg['archive']
    row=dict(case=cid,repository=cfg['repo'],pr_number=cfg['pr'],rule=cfg['rule'],
             base_archive_sha256='',pr_patch_sha256='',candidate_patch_applies='UNTESTED',
             expected_code_present='UNKNOWN',scanner_status='UNTESTED',base_count='',
             patched_count='',introduced_count='',changed_attributed_count='',notes='')
    if not archive.is_file() or not pfile.is_file():
        row['notes']='Missing archived source or historical PR candidate patch'
        write_row(cid,row)
        raise RuntimeError(row['notes']+': '+str(archive)+' / '+str(pfile))
    row['base_archive_sha256']=ev.sha256(archive)
    row['pr_patch_sha256']=ev.sha256(pfile)
    patch_text=pfile.read_text('utf-8',errors='replace')
    if 'diff --git ' not in patch_text:
        row['notes']='Downloaded PR patch has no git diff hunks (download failure?)'
        write_row(cid,row)
        raise RuntimeError(row['notes'])
    log('CASE',cid,'HISTORICAL PR',cfg['repo'],cfg['pr'])
    log('PR PATCH SHA256',row['pr_patch_sha256'])
    log('ARCHIVE SHA256',row['base_archive_sha256'])

    # Verify the old v2 base scanner is exactly for this source and target rule.
    base_manifest=ROOT/'phase2_eval_results_v2'/f'BASE_{cid}_manifest.json'
    base_sarif=ROOT/'phase2_eval_results_v2'/f'BASE_{cid}.sarif'
    if not base_manifest.is_file() or not base_sarif.is_file():
        row['notes']='Missing original baseline manifest or SARIF; stop, do not infer scanner outcome'
        write_row(cid,row)
        raise RuntimeError(row['notes'])
    manifest=json.loads(base_manifest.read_text('utf-8'))
    if (manifest.get('archive_sha256') != row['base_archive_sha256'] or
        manifest.get('rule') != cfg['rule']):
        row['notes']='Original baseline manifest does not match frozen source archive/rule'
        write_row(cid,row)
        raise RuntimeError(row['notes'])

    # Recover the PR candidate ONLY on the exact frozen pre-PR tree.
    src=WORK/f'historical_{cid}_repo'
    ev.extract(archive,src)
    try:
        ck=ev.call(['git','apply','--check',pfile],cwd=src,check=False,timeout=180)
        if ck.returncode:
            row['candidate_patch_applies']='FAIL'
            row['scanner_status']='NOT_RUN'
            row['notes']='Historical PR candidate does not apply to frozen pre-PR source. Recover dataset-pinned PR diff or SHA; do not use --3way, --reject, or fuzzy fixes.'
            (OUT/f'H{cid}_apply_error.txt').write_text((ck.stdout or '')+(ck.stderr or ''))
            log('APPLY_FAIL',cid,(ck.stdout or '')+(ck.stderr or ''))
            write_row(cid,row)
            return
        row['candidate_patch_applies']='OK'
        log('APPLY_OK',cid)
        ev.call(['git','init','-q'],cwd=src,timeout=120)
        ev.call(['git','config','user.email','historical@example.invalid'],cwd=src,timeout=20)
        ev.call(['git','config','user.name','Historical Control'],cwd=src,timeout=20)
        ev.call(['git','add','-A'],cwd=src,timeout=300)
        ev.call(['git','commit','-qm','frozen base'],cwd=src,timeout=300)
        ev.call(['git','apply',pfile],cwd=src,timeout=180)
        historical_file=src/cfg['file']
        anchor_present=historical_file.is_file() and cfg['anchor'] in historical_file.read_text('utf-8',errors='replace')
        row['expected_code_present']='YES' if anchor_present else 'NO'
        log('EXPECTED CODE PRESENT',row['expected_code_present'],'file',cfg['file'])
        changed=ev.get_changed_lines(src, f'H{cid}_PR{cfg["pr"]}')
        (OUT/f'H{cid}_changed_lines.json').write_text(json.dumps({k:sorted(v) for k,v in changed.items()},indent=2))

        codeql=ev.codeql_binary()
        query=ev.find_query(ev.query_root(),cfg['rule'])
        if str(query)!=manifest.get('query'):
            row['scanner_status']='CONFIG_MISMATCH'
            row['notes']='CodeQL query path changed from baseline; do not compare results'
            write_row(cid,row)
            return
        baseres=ev.sarif_results(base_sarif)
        if len(baseres)!=manifest.get('base_count'):
            row['scanner_status']='BASE_MISMATCH'
            row['notes']='Baseline SARIF and manifest have inconsistent finding counts'
            write_row(cid,row)
            return
        basekeys={ev.key(r) for r in baseres}
        row['base_count']=len(baseres)
        db=WORK/f'historical_{cid}_db'
        if db.exists(): shutil.rmtree(db)
        sarif=OUT/f'H{cid}_PR{cfg["pr"]}.sarif'
        if sarif.exists(): sarif.unlink()
        ev.call([codeql,'database','create',db,'--language=javascript-typescript',f'--source-root={src}',
                 '--build-mode=none','--threads=4','--ram=24000'],cwd=src,
                file=OUT/f'H{cid}_db.log',timeout=10800)
        ev.call([codeql,'database','analyze',db,query,'--format=sarif-latest',f'--output={sarif}',
                 '--threads=4','--ram=24000'],file=OUT/f'H{cid}_query.log',timeout=7200)
        results=[r for r in ev.sarif_results(sarif) if r['rule']==cfg['rule']]
        new=[r for r in results if ev.key(r) not in basekeys]
        attributed=[r for r in new if ev.hit_changed(r,changed)]
        (OUT/f'H{cid}_introduced.json').write_text(json.dumps(new,indent=2,ensure_ascii=False))
        (OUT/f'H{cid}_attributed.json').write_text(json.dumps(attributed,indent=2,ensure_ascii=False))
        row.update(patched_count=len(results),introduced_count=len(new),
                   changed_attributed_count=len(attributed))
        if attributed and anchor_present:
            row['scanner_status']='POSITIVE_REPRODUCED'
        elif new:
            row['scanner_status']='REVIEW_ATTRIBUTION'
        else:
            row['scanner_status']='SCANNER_NEGATIVE'
        row['notes']='GitHub PR .patch candidate; verify pinned historical commit/diff before claiming exact reconstruction. Separate functionality assessment still required.'
        write_row(cid,row)
        log('RESULT',cid,row['scanner_status'],'base',row['base_count'],
            'patched',row['patched_count'],'introduced',row['introduced_count'],
            'changed_attributed',row['changed_attributed_count'])
    except Exception as e:
        row['scanner_status']='ERROR'
        row['notes']=type(e).__name__+': '+str(e)[:600]
        write_row(cid,row)
        log('ERROR',cid,row['notes'])
        raise
    finally:
        if os.getenv('HIST_KEEP_SRC')!='1':
            shutil.rmtree(src,ignore_errors=True)


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in CASE:
        raise SystemExit('Usage: python3 -u phase2_historical_control_v1.py {3504|10819|629}')
    main(sys.argv[1])
