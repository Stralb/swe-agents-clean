#!/bin/bash
#SBATCH --job-name=p2prepraudit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:12:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2prepraudit_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2prepraudit_%j.err

# Researcher-only case chronology audit v2. Compute is confined to a batch worker.
# v2: hash mismatches are recorded rather than terminating the six-case audit.
# Existing research artifacts are read-only. New files are unique to SLURM_JOB_ID.
set -euo pipefail
umask 077

python3 - <<'PY'
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
from datetime import datetime, timezone
from urllib.request import Request, urlopen

JOB = os.environ.get('SLURM_JOB_ID', '')
assert re.fullmatch(r'[0-9]+', JOB), 'This code must be launched through sbatch.'
ROOT = Path.home() / 'research_artifacts' / 'prevention_pilot_phase2'
SOURCE = ROOT / 'case_screen_issue_recovery_v1_job69671' / 'RESEARCHER_CORPUS_ISSUES_24.json'
assert SOURCE.is_file(), 'Missing frozen issue recovery source: ' + str(SOURCE)
OUT = ROOT / ('case_prepr_audit_job' + JOB)
OUT.mkdir(mode=0o700, exist_ok=False)

RANKS = (16, 17, 18, 19, 21, 22)
EXPECT = {
    16: ('CROOT-00313-01', 'gsd-build/gsd-2', 2660),
    17: ('CROOT-10339-01', 'binaricat/Netcatty', 2337),
    18: ('CROOT-03582-01', 'breaking-brake/cc-wf-studio', 626),
    19: ('CROOT-07680-02', 'slkiser/opencode-quota', 13),
    21: ('CROOT-17062-01', 'pbakaus/impeccable', 486),
    22: ('CROOT-21682-01', 'remotion-dev/remotion', 10147),
}
raw = json.loads(SOURCE.read_text(encoding='utf-8'))
all_rows = raw['records']
results = []
audit_detail = []
TOKEN = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or ''


def digest(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def iso(s):
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except (AttributeError, ValueError, TypeError):
        return None


def gh_json(url, data=None):
    headers = {
        'User-Agent': 'Wits-Research-Readonly-Issue-PrePR-Audit',
        'Accept': 'application/vnd.github+json',
    }
    if TOKEN:
        headers['Authorization'] = 'Bearer ' + TOKEN
    if data is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(data).encode('utf-8')
    req = Request(url, data=data, headers=headers)
    try:
        with urlopen(req, timeout=9) as resp:
            return json.loads(resp.read(1_500_000).decode('utf-8')), None
    except Exception as e:
        # Never print or store authentication headers/token.
        return None, type(e).__name__ + ': ' + str(e)[:150]


def github_evidence(repo, issue, pr_created):
    owner, name = repo.split('/', 1)
    evidence = {'source': 'unavailable', 'errors': []}
    rest, error = gh_json('https://api.github.com/repos/' + repo + '/issues/' + str(issue))
    if error:
        evidence['errors'].append('GET issue: ' + error)
    elif isinstance(rest, dict):
        evidence.update(source='github_rest', live_issue={
            'created_at': rest.get('created_at'),
            'updated_at': rest.get('updated_at'),
            'body_sha256': digest(rest.get('body') or ''),
            'title_sha256': digest(rest.get('title') or ''),
            'body_length': len(rest.get('body') or ''),
        })
    else:
        evidence['errors'].append('GET issue: unexpected response')

    if not TOKEN:
        # Unauthenticated REST timeline cannot prove original issue-body content.
        timeline, error = gh_json('https://api.github.com/repos/' + repo + '/issues/' + str(issue) + '/timeline?per_page=100&page=1')
        if error:
            evidence['errors'].append('GET timeline: ' + error)
        elif isinstance(timeline, list):
            evidence['timeline_sample_size'] = len(timeline)
            evidence['timeline_truncated_possible'] = len(timeline) == 100
            evidence['edit_events'] = [
                {'created_at': x.get('created_at'), 'event': x.get('event'),
                 'body_change_metadata_present': bool((x.get('changes') or {}).get('body'))}
                for x in timeline if x.get('event') == 'edited'
            ]
        evidence['edit_history_status'] = 'NO_GRAPHQL_TOKEN__REST_METADATA_ONLY'
        return evidence

    query = '''query($owner:String!, $name:String!, $number:Int!, $cursor:String) {
      repository(owner:$owner,name:$name) {
        issue(number:$number) {
          createdAt updatedAt title body
          userContentEdits(first:100, after:$cursor) {
            nodes { editedAt diff }
            pageInfo { hasNextPage endCursor }
          }
        }
      }
    }'''
    edits = []
    cursor = None
    issue_data = None
    completed = False
    for _ in range(6):
        response, error = gh_json('https://api.github.com/graphql', {
            'query': query,
            'variables': {'owner': owner, 'name': name, 'number': issue, 'cursor': cursor},
        })
        if error:
            evidence['errors'].append('GraphQL request: ' + error)
            break
        if response.get('errors'):
            evidence['errors'].append('GraphQL errors: ' + json.dumps(response['errors'])[:500])
            break
        issue_data = ((response.get('data') or {}).get('repository') or {}).get('issue')
        if not issue_data:
            evidence['errors'].append('GraphQL issue missing')
            break
        connection = issue_data.get('userContentEdits')
        if not connection:
            evidence['errors'].append('GraphQL userContentEdits unavailable')
            break
        edits.extend(connection.get('nodes') or [])
        page = connection.get('pageInfo') or {}
        if not page.get('hasNextPage'):
            completed = True
            break
        cursor = page.get('endCursor')
        if not cursor:
            evidence['errors'].append('GraphQL edit pagination cursor missing')
            break

    if issue_data:
        evidence['source'] = 'github_graphql'
        evidence['graphql_body_sha256'] = digest(issue_data.get('body') or '')
        evidence['graphql_title_sha256'] = digest(issue_data.get('title') or '')
        evidence['graphql_created_at'] = issue_data.get('createdAt')
        evidence['graphql_updated_at'] = issue_data.get('updatedAt')
        evidence['graphql_edits'] = edits  # researcher-only; NEVER give to patch generator
        evidence['graphql_edits_complete'] = completed
        pr_dt = iso(pr_created)
        evidence['post_pr_user_content_edit_count'] = sum(
            iso(e.get('editedAt')) is not None and pr_dt is not None
            and iso(e.get('editedAt')) >= pr_dt for e in edits
        )
        evidence['edit_history_status'] = ('COMPLETE' if completed else 'INCOMPLETE')
    else:
        evidence['edit_history_status'] = 'GRAPHQL_UNAVAILABLE'
    return evidence


for rank in RANKS:
    matched = [r for r in all_rows if r.get('queue_rank') == rank and r.get('source_index') in (0, 1, 2)]
    assert matched, 'No records for frozen rank ' + str(rank)
    reference = next((r for r in matched if r.get('source_index') == 2 and r.get('case_found')), None)
    assert reference, 'No pinned final snapshot for rank ' + str(rank)
    expected_id, expected_repo, expected_issue = EXPECT[rank]
    assert (reference.get('root_id'), reference.get('repository'), reference.get('issue_number')) == (
        expected_id, expected_repo, expected_issue), 'Frozen identity mismatch at rank ' + str(rank)
    assert reference.get('base_matches_live_pr') is True, 'Base mismatch rank ' + str(rank)
    assert reference.get('issue_number_matches_frozen') is True, 'Issue number mismatch rank ' + str(rank)
    assert reference.get('pr_number_matches_frozen') is True, 'PR number mismatch rank ' + str(rank)
    srcs = []
    for r in sorted(matched, key=lambda r: r['source_index']):
        body = r.get('issue_body') or ''
        srcs.append({
            'source_index': r['source_index'], 'case_found': r.get('case_found'),
            'issue_updated_at': r.get('issue_updated_at'),
            'issue_created_at': r.get('issue_created_at'),
            'issue_body_sha256': digest(body), 'body_bytes': len(body.encode('utf-8')),
            'db_recorded_body_sha256': r.get('issue_body_sha256'),
            'issue_title_sha256': digest(r.get('issue_title') or ''),
            'pre_pr_body_chronology_supported': r.get('pre_pr_issue_body_chronology_supported'),
            'base_sha': r.get('pr_base_sha'), 'head_sha': r.get('pr_head_sha'),
        })
        srcs[-1]['stored_body_sha_matches_recomputed'] = (
            srcs[-1]['issue_body_sha256'] == srcs[-1]['db_recorded_body_sha256'])
        if not srcs[-1]['stored_body_sha_matches_recomputed']:
            print('BODY_HASH_MISMATCH', rank, 'source', r['source_index'],
                  'recorded', srcs[-1]['db_recorded_body_sha256'],
                  'recomputed', srcs[-1]['issue_body_sha256'], flush=True)

    consistency = len({s['issue_body_sha256'] for s in srcs if s['case_found']}) == 1
    historic = github_evidence(reference['repository'], reference['issue_number'], reference['pr_created_at'])
    live_sha = ((historic.get('live_issue') or {}).get('body_sha256') or historic.get('graphql_body_sha256'))
    post_pr = historic.get('post_pr_user_content_edit_count')
    edits_complete = historic.get('graphql_edits_complete') is True
    current_matches = bool(live_sha and live_sha == digest(reference.get('issue_body') or ''))
    if reference.get('pre_pr_issue_body_chronology_supported'):
        verdict = 'PREPR_DB_TIMESTAMP_SUPPORTS_BODY'
    elif edits_complete and post_pr == 0 and current_matches:
        verdict = 'GRAPHQL_NO_POSTPR_EDIT_AND_DB_MATCH__STRONGER_SUPPORT'
    elif edits_complete and post_pr is not None and post_pr > 0:
        verdict = 'GRAPHQL_POSTPR_CONTENT_EDIT__PREPR_BODY_UNVERIFIED'
    else:
        verdict = 'POSTPR_UPDATED__PREPR_BODY_UNVERIFIED'

    row = {
        'rank': rank, 'root_id': expected_id, 'repo': expected_repo,
        'issue': expected_issue, 'pr': reference.get('pr_number'),
        'base_sha': reference.get('pr_base_sha'), 'head_sha': reference.get('pr_head_sha'),
        'pr_created_at': reference.get('pr_created_at'),
        'issue_updated_at': reference.get('issue_updated_at'),
        'sources_present': ','.join(str(s['source_index']) for s in srcs),
        'db_bodies_consistent': consistency,
        'stored_sha_all_consistent': all(s['stored_body_sha_matches_recomputed'] for s in srcs),
        'db_body_sha256': digest(reference.get('issue_body') or ''),
        'live_body_matches_db': current_matches if live_sha else 'UNKNOWN',
        'github_evidence': historic.get('edit_history_status'),
        'post_pr_user_content_edits': post_pr if post_pr is not None else 'UNKNOWN',
        'verdict': verdict,
    }
    results.append(row)
    audit_detail.append({'summary': row, 'snapshot_comparison': srcs,
                         'github': historic, 'researcher_only_db_issue_body': reference.get('issue_body') or ''})
    print('CASE', rank, expected_id, 'snapshot_consistent=', consistency,
          'github=', historic.get('edit_history_status'), 'verdict=', verdict, flush=True)

manifest = {
    'purpose': 'Researcher-only evidence audit for frozen priority ranks 16,17,18,19,21,22',
    'generated_at_utc': datetime.now(timezone.utc).isoformat(),
    'slurm_job_id': JOB,
    'input_path': str(SOURCE),
    'input_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'github_authenticated_graphql_attempted': bool(TOKEN),
    'warning': ('NEVER expose researcher-only material to patch-generation model. '
                'Post-PR issue updated_at by itself does not establish a changed body; '
                'a repeated present-day body in 3 databases does not prove its pre-PR content. '
                'GraphQL userContentEdits can supply edit metadata/diffs but is not by itself a full version snapshot.'),
    'cases': audit_detail,
}
with (OUT / 'RESEARCHER_ISSUE_AUDIT.json').open('x', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.write('\n')
with (OUT / 'CASE_SUMMARY.csv').open('x', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    writer.writeheader()
    writer.writerows(results)
with (OUT / 'STATUS.txt').open('x', encoding='utf-8') as f:
    for row in results:
        f.write('{rank} {root_id} {verdict} {github_evidence}\n'.format(**row))
archive = ROOT / ('case_prepr_audit_job' + JOB + '.tar.gz')
with tarfile.open(archive, 'x:gz') as tf:
    for f in sorted(OUT.iterdir()):
        tf.add(f, arcname=OUT.name + '/' + f.name)
print('AUDIT_COMPLETE', JOB, flush=True)
print('ARCHIVE', archive, flush=True)
print('SHA256', hashlib.sha256(archive.read_bytes()).hexdigest(), flush=True)
PY
