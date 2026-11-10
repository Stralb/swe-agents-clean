#!/bin/bash
#SBATCH --job-name=p2_issue_recovery
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:15:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2_issue_recovery_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2_issue_recovery_%j.err

# Read-only study-source recovery. No deletes, overwrites, downloads or installation.
set -euo pipefail
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
python - <<'PY'
import collections
import csv
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

home = Path.home()
research = home / 'research_artifacts'
phase = research / 'prevention_pilot_phase2'
dossier = phase / 'case_screen_dossier_v1/RESEARCHER_FULL_24.json'
assert dossier.is_file(), f'Missing dossier: {dossier}'
cases = json.loads(dossier.read_text(encoding='utf-8'))
assert len(cases) == 24
assert [int(x['queue_rank']) for x in cases] == list(range(1, 25))
assert len({int(x['case_id']) for x in cases}) == 24

sources = [
    home / 'new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.db',
    home / 'new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.full3809-continuation.db',
    home / 'new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db',
]

# Slurm job ID guarantees a fresh directory, and x/open modes forbid overwriting.
job_id = os.environ.get('SLURM_JOB_ID')
assert job_id and job_id.isdecimal(), 'Must execute as a submitted Slurm job.'
out = phase / f'case_screen_issue_recovery_v1_job{job_id}'
out.mkdir(mode=0o750, parents=False, exist_ok=False)
results = []
source_metadata = []
for source_i, source in enumerate(sources):
    meta = {'source_index': source_i, 'database': str(source), 'exists': source.is_file()}
    source_metadata.append(meta)
    if not meta['exists']:
        print('SOURCE_MISSING', source, flush=True)
        continue
    meta['size_bytes'] = source.stat().st_size
    try:
        con = sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True, timeout=20)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA query_only=ON')
        meta['sqlite_quick_header_ok'] = bool(con.execute('PRAGMA schema_version').fetchone())
        for case in cases:
            case_id = int(case['case_id'])
            original = case['frozen_producing_changes'][0]
            expected_issue = int(original['Issue #'])
            expected_pr = int(original['PR #'])
            row = con.execute('''
                SELECT c.id AS db_case_id, c.repo_id AS repo_id,
                       i.id AS db_issue_id, i.number AS issue_number,
                       i.url AS issue_url, i.title AS issue_title, i.body AS issue_body,
                       i.created_at AS issue_created_at, i.updated_at AS issue_updated_at,
                       p.id AS db_pr_id, p.number AS pr_number, p.url AS pr_url,
                       p.created_at AS pr_created_at, p.base_sha AS pr_base_sha,
                       p.head_sha AS pr_head_sha
                FROM cases c
                JOIN issues i ON i.id = c.issue_id
                JOIN pull_requests p ON p.id = c.pr_id
                WHERE c.id = ?
            ''', (case_id,)).fetchone()
            entry = {'source_index': source_i, 'case_id': case_id,
                     'queue_rank': int(case['queue_rank']), 'root_id': case['root_id'],
                     'repository': case['repository'],
                     'expected_issue_number': expected_issue,
                     'expected_pr_number': expected_pr,
                     'case_found': row is not None,
                     'historical_codeql_replay': 'NOT_RUN',
                     'prior_exposure_review': 'NOT_DONE',
                     'pre_pr_issue_body_chronology_supported': False}
            if row is not None:
                data = dict(row)
                body = data['issue_body'] or ''
                live = case.get('LIVE_ISSUE_NOT_DATASET_PINNED') or {}
                entry.update(data)
                entry.update({
                    'issue_body_bytes': len(body.encode('utf-8')),
                    'issue_body_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(),
                    'issue_number_matches_frozen': data['issue_number'] == expected_issue,
                    'pr_number_matches_frozen': data['pr_number'] == expected_pr,
                    'issue_url_matches_frozen': data['issue_url'] == original['Issue URL'],
                    'pr_url_matches_frozen': data['pr_url'] == original['PR URL'],
                    'base_matches_live_pr': data['pr_base_sha'] == case['live_PR_metadata'].get('base_sha'),
                    'body_matches_live_oct16': body == (live.get('body') or ''),
                    'title_matches_frozen': data['issue_title'] == case['frozen_title'],
                })
                try:
                    created = datetime.fromisoformat(str(data['issue_created_at']).replace('Z', '+00:00'))
                    updated = datetime.fromisoformat(str(data['issue_updated_at']).replace('Z', '+00:00'))
                    pr_created = datetime.fromisoformat(str(data['pr_created_at']).replace('Z', '+00:00'))
                    entry['issue_created_before_pr'] = created <= pr_created
                    entry['issue_last_updated_before_pr'] = updated <= pr_created
                except (ValueError, TypeError):
                    entry['issue_created_before_pr'] = None
                    entry['issue_last_updated_before_pr'] = None
                # A corpus issue body is NOT necessarily the exact pre-PR text.
                # A post-PR update makes its temporal fidelity unverified.
                entry['body_temporal_verdict'] = (
                    'NO_BODY' if not body else
                    'ISSUE_CREATED_AFTER_PR' if entry['issue_created_before_pr'] is False else
                    'POST_PR_EDIT_POSSIBLE' if entry['issue_last_updated_before_pr'] is not True else
                    'NO_RECORDED_POST_PR_UPDATE'
                )
                entry['pre_pr_issue_body_chronology_supported'] = bool(
                    body and entry['issue_created_before_pr'] is True
                    and entry['issue_last_updated_before_pr'] is True
                    and entry['issue_number_matches_frozen']
                    and entry['pr_number_matches_frozen']
                )
            results.append(entry)
        con.close()
        meta['status'] = 'OK'
    except (sqlite3.Error, OSError) as exc:
        meta['status'] = 'ERROR'
        meta['error'] = f'{type(exc).__name__}: {str(exc)[:300]}'
    print('SOURCE', source_i, meta.get('status', 'MISSING'), str(source), flush=True)

if not results:
    raise RuntimeError('No source databases could be read; inspect this job log.')

manifest = {
    'purpose': 'Researcher-only source recovery for frozen 24-root queue',
    'warning': 'Never forward this artifact to blinded patch generators.',
    'method': 'Read-only case_id -> issue_id and pr_id foreign-key join; no GitHub refetch',
    'limitation': 'A DB-stored body is NOT automatically a historical pre-PR issue snapshot.',
    'source_dossier_sha256': hashlib.sha256(dossier.read_bytes()).hexdigest(),
    'frozen_queue_ranks': [x['root_id'] for x in cases],
    'databases': source_metadata,
    'records': results,
}
json_path = out / 'RESEARCHER_CORPUS_ISSUES_24.json'
with json_path.open('x', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write('\n')

columns = ['source_index','queue_rank','root_id','repository','case_id','case_found',
           'expected_issue_number','issue_number','issue_number_matches_frozen',
           'expected_pr_number','pr_number','pr_number_matches_frozen',
           'issue_url_matches_frozen','pr_url_matches_frozen','base_matches_live_pr',
           'issue_created_at','issue_updated_at','pr_created_at',
           'issue_created_before_pr','issue_last_updated_before_pr',
           'body_temporal_verdict','pre_pr_issue_body_chronology_supported',
           'issue_body_bytes','issue_body_sha256','body_matches_live_oct16',
           'title_matches_frozen','pr_base_sha','pr_head_sha']
with (out / 'JOIN_SUMMARY_24.csv').open('x', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
    w.writeheader()
    w.writerows(results)

counts = collections.Counter((x['source_index'], x.get('body_temporal_verdict', 'NOT_FOUND')) for x in results)
print('RECOVERY_COMPLETE job=', job_id, 'output=', out, 'rows=', len(results), flush=True)
for idx, meta in enumerate(source_metadata):
    these = [r for r in results if r['source_index'] == idx]
    print('DB_SUMMARY', idx, 'cases=', len(these),
          'found=', sum(r['case_found'] for r in these),
          'matching_issue_pr=', sum(r.get('issue_number_matches_frozen',False) and r.get('pr_number_matches_frozen',False) for r in these),
          'prepr_metadata_supported=', sum(r.get('pre_pr_issue_body_chronology_supported',False) for r in these),
          flush=True)
for rank in [5,16,17,18,19,21,22]:
    for r in results:
        if r['queue_rank']==rank:
            print('PRIORITY', rank,'db=',r['source_index'],'found=',r['case_found'],
                  'ids_match=',r.get('issue_number_matches_frozen',False) and r.get('pr_number_matches_frozen',False),
                  'temporal=',r.get('body_temporal_verdict','NOT_FOUND'),
                  'body_matches_live=',r.get('body_matches_live_oct16'),flush=True)
PY
