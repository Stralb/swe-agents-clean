#!/usr/bin/env python3
"""Build a researcher-only evidence bundle for the PRE-REGISTERED 24-case queue.
Never selects an eligible case, modifies a patch, runs codeql, or emits generation packets.
"""
import csv
import hashlib
import json
import pathlib
import re
from datetime import datetime, timezone

ROOT = pathlib.Path.home() / 'research_artifacts'
PILOT = ROOT / 'prevention_pilot_phase2'
OUT = PILOT / 'case_screen_dossier_v1'
Q = PILOT / 'case_screen_results_v1' / 'RESEARCHER_SCREEN_QUEUE.csv'
A = PILOT / 'case_screen_preaudit_v1'
FROOT = ROOT / 'D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv'
FPROV = ROOT / 'PROV_Phase6_FULL_PROVENANCE_455_FROZEN_v1.0.csv'

def readcsv(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def clean(x):
    return ' '.join(str(x or '').split())

def limited(x, n=180):
    x = clean(x).replace('|', '/').replace('`', "'")
    return x[:n] + ('...' if len(x) > n else '')

def main():
    required = [Q, A/'PREAUDIT_24_RESEARCHER.csv', FROOT, FPROV]
    for f in required:
        if not f.is_file():
            raise SystemExit(f'MISSING_REQUIRED_SOURCE {f}')
    queue = readcsv(Q)
    if len(queue) != 24 or [str(r['queue_rank']) for r in queue] != [str(i) for i in range(1,25)]:
        raise SystemExit('QUEUE_ORDER_OR_SIZE_MISMATCH')
    previous_meta = A / 'AUDIT_METADATA.json'
    if previous_meta.is_file():
        m = json.loads(previous_meta.read_text())
        if m.get('queue_sha256') and m['queue_sha256'] != sha(Q):
            raise SystemExit('QUEUE_HASH_MISMATCH_WITH_PREAUDIT')
    roots = {r['root_id']:r for r in readcsv(FROOT)}
    provenance = readcsv(FPROV)
    bypc = {}
    for p in provenance:
        key = p.get('Study Producing Change ID', '').strip()
        if key:
            bypc[key] = p
    preaudit = {r['root_id']:r for r in readcsv(A/'PREAUDIT_24_RESEARCHER.csv')}
    OUT.mkdir(exist_ok=True)
    entries=[]
    for q in queue:
        idx=int(q['queue_rank']); rid=q['root_id']
        root=roots.get(rid)
        if not root:
            raise SystemExit(f'FROZEN_ROOT_NOT_FOUND {rid}')
        pc_ids=[k.strip() for k in re.split(r'[;|,]',root.get('pc_ids','')) if k.strip()]
        linked=[bypc[p] for p in pc_ids if p in bypc]
        linked=[p for p in linked if p.get('Repository','').lower() == q['repository'].lower()] or linked
        if not linked:
            raise SystemExit(f'FROZEN_PC_JOIN_NOT_FOUND {rid}')
        live_path=A/'LIVE_ISSUE_SNAPSHOTS_RESEARCHER_ONLY'/f'RANK_{idx:02d}.json'
        live=json.loads(live_path.read_text()) if live_path.is_file() else {}
        pa=preaudit.get(rid,{})
        evidence=[]
        for p in linked:
            evidence.append({k:p.get(k,'') for k in (
                'Study Producing Change ID','Case ID','Repository','Issue #','Issue URL',
                'PR #','PR URL','Issue Title','Requested Goal Set','Goal Evidence',
                'Finding-Producing Change','Security-Relevant Mechanism','Mechanism Evidence',
                'Finding Family','Rule ID(s)','Canonical Finding ID(s)',
                'Changed Location(s)','Diff Evidence','Phase3 Mechanism Confidence',
                'Phase4 Precursor Evidence','Safer Local Counterfactual',
                'Counterfactual Evidence','Frozen Broad Attribution')})
        record={
            'queue_rank':idx, 'root_id':rid, 'case_id':q.get('case_id',''),
            'repository':q['repository'], 'frozen_title':q.get('issue_title',''),
            'original_issue_body_dataset_pinned':'NOT_YET_RECOVERED',
            'LIVE_ISSUE_NOT_DATASET_PINNED':{'title':live.get('issue_title',''),
               'body':live.get('issue_body',''),'fetched_at_utc':live.get('fetched_at_utc',''),
               'SHA256':pa.get('issue_body_sha256','')},
            'live_PR_metadata':{'base_sha':pa.get('pr_base_sha_live',''),
               'head_sha':pa.get('pr_head_sha_live',''), 'PR_created':pa.get('pr_created_at',''),
               'issue_created':pa.get('issue_created_at',''),
               'issue_updated':pa.get('issue_updated_at',''),
               'review_reasons':pa.get('review_reasons',''),
               'issue_fetch':pa.get('issue_http',''), 'pr_fetch':pa.get('pr_http','')},
            'frozen_root':root,'frozen_producing_changes':evidence,
            'prior_experiment_exposure':'NOT_YET_VERIFIED',
            'historical_CodeQL_control':'NOT_YET_RUN',
            'prePR_repo_snapshot':'NOT_YET_VERIFIED',
            'functional_oracle':'NOT_YET_DEFINED',
            'decision':'PENDING_HUMAN_ELIGIBILITY_REVIEW'
        }
        entries.append(record)
    (OUT/'RESEARCHER_FULL_24.json').write_text(json.dumps(entries,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    lines=['# Phase 2: Frozen-queue researcher evidence dossier', '',
           'RESEARCHER-ONLY: includes historical warning mechanisms and PR evidence. **NEVER give this to patch generation models.**',
           '',f'Frozen queue SHA256: `{sha(Q)}`','',
           'All 24: PENDING. Live GitHub issues may have been edited after PR creation. Original dataset-pinned bodies are NOT established by this bundle.','',
           '| Rank | Root | Repository | Historical rule | Issue length (live) | Pre-audit flags |',
           '|---:|---|---|---|---:|---|']
    for x in entries:
        pm=x['live_PR_metadata']; body=x['LIVE_ISSUE_NOT_DATASET_PINN']['body'] or ''
        rules=', '.join(sorted({p['Rule ID(s)'] for p in x['frozen_producing_changes']}))
        lines.append(f'| {x["queue_rank"]} | {x["root_id"]} | {x["repository"]} | {rules} | {len(body)} | {limited(pm["review_reasons"],70)} |')
    lines+=['','## Case dossiers (frozen rank order)','']
    for x in entries:
        pa=x['live_PR_metadata']; live=x['LIVE_ISSUE_NOT_DATASET_PINN']
        lines += [f'### #{x["queue_rank"]}: {x["root_id"]} — {x["repository"]}', '',
                  f'**Frozen issue title:** {x["frozen_title"]}',
                  f'**Live PR base/head:** `{pa["base_sha"]}` / `{pa["head_sha"]}`',
                  f'**Live issue/PR fetch:** {pa["issue_fetch"]} / {pa["pr_fetch"]}',
                  f'**Live issue modified after PR?** {"YES" if pa["issue_updated"] and pa["PR_created"] and pa["issue_updated"] > pa["PR_created"] else "NO_OR_UNKNOWN"}',
                  '', '**Live issue text (RESEARCH-ONLY, NOT ORIGINAL FROZEN ISSUE):**', '',
                  '```text', (live['body'] or '[EMPTY OR UNAVAILABLE]')[:9000], '```', '',
                  '**Frozen study evidence:**', '']
        for p in x['frozen_producing_changes']:
            for title,key in [('Requested goal','Requested Goal Set'),('Goal evidence','Goal Evidence'),
                              ('Actual producing change','Finding-Producing Change'),
                              ('Diff evidence','Diff Evidence'), ('Mechanism','Security-Relevant Mechanism'),
                              ('Pre-change evidence','Phase4 Precursor Evidence'),
                              ('Safer counterfactual','Safer Local Counterfactual')]:
                lines.append(f'- **{title}:** {limited(p.get(key,''),1800)}')
        lines += ['', '**Human reviewer:** issue fidelity / implementation difficulty / same security decision / test oracle / prior exposure / pinned base / historical control: **PENDING**', '']
    (OUT/'RESEARCHER_REVIEW_24.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    manifest={
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'codeql_executed':False,'patch_generation_executed':False,
        'approved_cases':0,
        'researcher_only':True,'not_generation_safe':True,
        'queue_frozen_sha256':sha(Q),
        'frozen_roots_sha256':sha(FROOT),'frozen_provenance_sha256':sha(FPROV),
        'WARNING':'Live issue bodies are not dataset-pinned, do not pass to generation.'
    }
    (OUT/'DOSSIER_META.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Narrow inventory: do not descend through massive repo trees or archives.
    patterns = ['*.db','*.sqlite','*.sqlite3']
    bases=[pathlib.Path.home()/'new'/'malicious-issue-miner-rate-smart',ROOT]
    found=[]
    for base in bases:
        if not base.exists():continue
        # bounded walk: don't traverse git, node_modules, or cached repos.
        import os
        for top,dirs,files in os.walk(base):
            depth=len(pathlib.Path(top).relative_to(base).parts)
            dirs[:]=[d for d in dirs if d not in ('node_modules','.git','.venv','repos','tmp','cache','codeql-db')]
            if depth >= 3:dirs[:]=[]
            for fn in files:
                if fn.lower().endswith(('.db','.sqlite','.sqlite3')):
                    path=pathlib.Path(top)/fn
                    try: size=path.stat().st_size
                    except OSError: size=-1
                    found.append({'path':str(path),'bytes':size})
    (OUT/'DB_INVENTORY.json').write_text(json.dumps(found,indent=2)+'\n')
    print('DOSSIER_COMPLETE case_count=24 prior_exposure=PENDING pinned_issues=PENDING approved=0',flush=True)
    print('FILES',OUT/'RESEARCHER_REVIEW_24.md', OUT/'RESEARCHER_FULL_24.json',flush=True)
    print('DB_INVENTORY',len(found),flush=True)

if __name__=='__main__':
    main()
