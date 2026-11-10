#!/usr/bin/env python3
"""Create an auditable, leakage-separated prospective case screening queue.

This is candidate selection ONLY: does not claim reproducibility or run CodeQL.
Reads frozen D7 233-root census and Phase6 455-change provenance on cluster.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

JOIN_PATTERN = re.compile(r'(?<![A-Z0-9])(?:[A-Z0-9]+-)?PC-\d+(?!\d)', re.I)
CODE_PATH = re.compile(r'([\w./@-]+\.(?:tsx?|jsx?|mjs|cjs))(?::\d+)?', re.I)
EXCLUDED_CASES = {'3504', '10819', '629', '3592'}  # phase2 pilot and calibration
# Preserve a fixed universe of supported JS/TS code queries for current CodeQL installation.
SECURITY_TERMS = ('security', 'injection', 'traversal', 'crypto', 'random', 'deserial',
                  'xss', 'script', 'command', 'race', 'path', 'redos', 'redirect', 'ssrf',
                  'forgery', 'auth', 'access', 'session', 'secret', 'credential', 'file')
FAMILY_ORDER = ('file_path', 'injection', 'auth_session', 'random_crypto',
                'regex_redos', 'network', 'secrets', 'other_js')
OUTPUT_COLS = [
    'queue_rank','root_id','case_id','repository','issue_number','issue_url','issue_title',
    'pr_number','pr_url','target_rule','family','changed_file','changed_operation',
    'score','score_reasons','pc_ids','join_method','repo_repeated',
    'historical_finding_id','final_chronology_ok','final_evidence_complete',
    'prior_exposure_review','status'
]
CENSUS_COLS = OUTPUT_COLS[1:] + ['eligibility_decision','eligibility_reasons']


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        return list(r), (r.fieldnames or [])


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def cell(row, *names):
    for k in names:
        v = str(row.get(k) or '').strip()
        if v:
            return v
    return ''


def tokens(s):
    return set(x.upper() for x in JOIN_PATTERN.findall(s))


def normalized_case(s):
    s = str(s).strip()
    m = re.search(r'(?:^|[^0-9])0*(\d{1,6})(?:$|[^0-9])', s)
    return str(int(m.group(1))) if m else ''


def flag(s):
    s = str(s).strip().lower()
    if s in {'true', 'yes', '1', 'complete', 'ok'}: return True
    if s in {'false', 'no', '0', 'incomplete', 'failed'}: return False
    return None


def is_test_path(p):
    lo = p.lower().replace('\\', '/')
    return bool(re.search(r'(?:^|/)(?:__tests__|tests?|fixtures|e2e|examples|storybook)(?:/|$)', lo)
                or re.search(r'(?:\.|_)(?:test|spec)\.[a-z]+$', lo))


def family_of(rule):
    r = rule.lower()
    if any(x in r for x in ('path-', 'file-', 'directory', 'temporary-file', 'arbitrary-file', 'symlink')):
        return 'file_path'
    if any(x in r for x in ('injection','xss','cross-site','code-execution','html','eval','query-construction','command')):
        return 'injection'
    if any(x in r for x in ('auth','access-control','cookie','session','csrf','rate-limit','permission')):
        return 'auth_session'
    if any(x in r for x in ('crypto','random','weak-password','key-length')):
        return 'random_crypto'
    if any(x in r for x in ('redos', 'regex', 'regular-expression')):
        return 'regex_redos'
    if any(x in r for x in ('request-forgery','ssrf','url-redirect','http-to','untrusted-url')):
        return 'network'
    if any(x in r for x in ('secret','credential','password','token-leak','private-key','clear-text')):
        return 'secrets'
    return 'other_js'


def short_text(s, max_len=500):
    return re.sub(r'\s+', ' ', str(s)).strip()[:max_len]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--queue-size', type=int, default=24)
    p.add_argument('--wave-size', type=int, default=8)
    args = p.parse_args()
    if args.queue_size <= 0 or args.wave_size <= 0: p.error('Queue/wave sizes must be positive')
    artifacts = args.artifacts.resolve()
    root_path = artifacts / 'D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv'
    prov_path = artifacts / 'PROV_Phase6_FULL_PROVENANCE_455_FROZEN_v1.0.csv'
    for source in (root_path, prov_path):
        if not source.is_file(): p.error('Missing frozen input: ' + str(source))
    roots, rh = read_csv(root_path)
    prov, ph = read_csv(prov_path)
    for expected, fields in [('root_id', rh), ('pc_ids', rh), ('Study Producing Change ID', ph),
                             ('Rule ID(s)', ph), ('Repository', ph), ('Case ID', ph)]:
        if expected not in fields: p.error(f'Expected column {expected!r} missing; actual columns: {fields}')
    if not roots or not prov: p.error('Empty frozen input CSV')
    bypc = defaultdict(list)
    for row in prov:
        for pc in tokens(cell(row, 'Study Producing Change ID', 'Source Producing Change ID')):
            bypc[pc].append(row)

    census = []
    join_counts = Counter()
    for r in roots:
        root_id = cell(r, 'root_id')
        root_pcs = tokens(cell(r, 'pc_ids'))
        matches = []
        for pc in root_pcs:
            matches.extend(bypc.get(pc, []))
        # Deduplicate when both ID types happen to match the same row.
        matched = {cell(x,'Study Producing Change ID'): x for x in matches}
        matches = list(matched.values())
        matched_method = 'exact_pc_id' if matches else 'UNMATCHED'
        join_counts[matched_method] += 1
        chosen = None
        preferred_case = normalized_case(cell(r,'case_id')) or normalized_case(root_id)
        desired_repo = cell(r,'repository').lower()
        if matches:
            matches.sort(key=lambda x:(
                0 if normalized_case(cell(x,'Case ID')) == preferred_case else 1,
                0 if cell(x,'Repository').lower() == desired_repo else 1,
                cell(x,'Study Producing Change ID')))
            chosen = matches[0]
        # Do not guess a focal security rule from another root's same-case findings.
        issue_title = cell(r,'issue_title') or (cell(chosen,'Issue Title') if chosen else '')
        repo = cell(r,'repository') or (cell(chosen,'Repository') if chosen else '')
        path_text = cell(chosen,'Changed Location(s)','Finding-Producing Change') if chosen else ''
        paths = CODE_PATH.findall(path_text)
        if not paths and chosen:
            paths = CODE_PATH.findall(cell(chosen,'Finding-Producing Change','Diff Evidence'))
        primary_path = paths[0] if paths else ''
        rule_list = [x.strip() for x in re.split(r'[;,|]', cell(chosen,'Rule ID(s)')) if x.strip()] if chosen else []
        js_rules = [x for x in rule_list if x.lower().startswith('js/')]
        rule = js_rules[0] if js_rules else (rule_list[0] if rule_list else '')
        fam = family_of(rule)
        case = preferred_case
        reasons = []
        if not matches: reasons.append('no_exact_producing_change_join')
        if not case: reasons.append('unknown_case_id')
        if case in EXCLUDED_CASES: reasons.append('previously_experimented_or_calibration')
        if not repo or not issue_title: reasons.append('missing_repo_or_issue_title')
        if not js_rules: reasons.append('unsupported_or_unknown_js_codeql_rule')
        if not primary_path: reasons.append('changed_source_path_unresolved')
        elif is_test_path(primary_path): reasons.append('test_or_fixture_only_primary_change')
        chronology = flag(cell(r,'final_chronology_ok'))
        complete = flag(cell(r,'final_evidence_complete'))
        if chronology is False: reasons.append('failed_chronology')
        if complete is False: reasons.append('incomplete_root_evidence')

        score = 0
        score_reasons = []
        if matched_method == 'exact_pc_id': score += 5; score_reasons.append('+5_exhaustive_pc_join')
        if chronology is True and complete is True: score += 2; score_reasons.append('+2_chronology_and_evidence')
        if primary_path and not is_test_path(primary_path) and ('src/' in primary_path or 'lib/' in primary_path):
            score += 3; score_reasons.append('+3_production_src')
        if re.search(r'\b(bug|fix|regression|incorrect|error|wrong|crash|fails?|broken)\b',issue_title,re.I):
            score += 3; score_reasons.append('+3_localized_bug_wording')
        elif re.search(r'\b(option|setting|support|allow|add|handle)\b', issue_title, re.I):
            score += 1; score_reasons.append('+1_concrete_request_wording')
        if len(issue_title) <= 130: score += 1; score_reasons.append('+1_short_issue_title')
        if flag(cell(r,'strong_repo_precedent_architecture')) is True:
            score += 2; score_reasons.append('+2_repo_precedent')
        if flag(cell(r,'explicit_prechange_guidance_contract')) is True:
            score += 1; score_reasons.append('+1_prechange_contract')
        if fam in {'file_path','injection','auth_session','random_crypto','regex_redos','network'}:
            score += 2; score_reasons.append('+2_security_mechanism_family')
        if re.search(r'\b(integrat|migrat|rewrite|redesign|refactor|whole|entire|implement\s+full)\b',issue_title,re.I):
            score -= 3; score_reasons.append('-3_large_scope_wording')
        if len(paths) >= 4: score -= 2; score_reasons.append('-2_many_source_paths')
        if fam == 'other_js': score -= 1; score_reasons.append('-1_other_js_rule')
        if chosen and not cell(chosen,'Issue URL'): score_reasons.append('review_missing_issue_url')
        row = {
            'root_id':root_id,'case_id':case,'repository':repo,
            'issue_number':cell(chosen,'Issue #') if chosen else '',
            'issue_url':cell(chosen,'Issue URL') if chosen else '',
            'issue_title':short_text(issue_title,400),
            'pr_number':cell(chosen,'PR #') if chosen else '',
            'pr_url':cell(chosen,'PR URL') if chosen else '',
            'target_rule':rule,'family':fam,'changed_file':primary_path,
            'changed_operation':short_text(cell(chosen,'Finding-Producing Change'),380) if chosen else '',
            'score':score,'score_reasons':';'.join(score_reasons),
            'pc_ids':cell(r,'pc_ids'), 'join_method':matched_method,
            'repo_repeated':'','historical_finding_id':cell(chosen,'Canonical Finding ID(s)') if chosen else '',
            'final_chronology_ok':cell(r,'final_chronology_ok'),
            'final_evidence_complete':cell(r,'final_evidence_complete'),
            'prior_exposure_review':'PENDING: audit other T1/T2 and experimental-generation manifests',
            'status':'METADATA_PROVISIONAL' if not reasons else 'METADATA_EXCLUDED',
            'eligibility_decision':'PROVISIONAL' if not reasons else 'EXCLUDED',
            'eligibility_reasons':';'.join(reasons), 'queue_rank':''
        }
        census.append(row)

    provisional = [r for r in census if r['eligibility_decision'] == 'PROVISIONAL']
    # Sort by explicit score; cryptographic hash deterministically breaks ties without analyst discretion.
    def ordering(row):
        tie=hashlib.sha256(f'case-screen-v1|{row["root_id"]}'.encode()).hexdigest()
        return (-int(row['score']), tie)
    provisional.sort(key=ordering)
    # Stratified round robin, no more than 1 case per repository initially.
    groups = {family: [r for r in provisional if r['family']==family] for family in FAMILY_ORDER}
    picked=[]; selected_repos=set(); selected_cases=set(); family_counts=Counter()
    while len(picked) < args.queue_size:
        progress=False
        for family in FAMILY_ORDER:
            for candidate in groups[family]:
                if candidate in picked or candidate['repository'].lower() in selected_repos or candidate['case_id'] in selected_cases:
                    continue
                candidate['queue_rank']=str(len(picked)+1)
                picked.append(candidate)
                selected_repos.add(candidate['repository'].lower()); selected_cases.add(candidate['case_id'])
                family_counts[family]+=1
                progress=True
                break
            if len(picked) >= args.queue_size: break
        if not progress: break
    # If distinct-repository requirement exhausts population, don't silently relax it.
    for r in picked: r['status']='SCREEN_QUEUE_PREAUDIT'
    reserve = [r for r in provisional if r not in picked]
    reserve.sort(key=ordering)
    for r in reserve:
        r['repo_repeated']='YES' if r['repository'].lower() in selected_repos else 'NO'
    for r in picked: r['repo_repeated']='NO'

    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    def write(name, fields, rows):
        with (out/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
            w.writeheader(); w.writerows(rows)
    write('FULL_ROOT_CENSUS.csv', CENSUS_COLS, census)
    write('RESEARCHER_SCREEN_QUEUE.csv', OUTPUT_COLS, picked)
    write('RESEARCHER_RESERVES.csv', OUTPUT_COLS, reserve)
    # Keep historical rule, vulnerability site, PR metadata and human-coded goal interpretations OUT of this export.
    blinded_cols=['queue_rank','root_id','case_id','repository','issue_number','issue_url','issue_title','prepr_archive','original_issue_body_verified']
    blind=[]
    for r in picked:
        blind.append({**{k:r.get(k,'') for k in blinded_cols},
                      'prepr_archive':'TO_EXTRACT_FROM_DATASET',
                      'original_issue_body_verified':'NO'})
    write('GENERATION_SAFE_QUEUE.csv',blinded_cols,blind)
    screen_fields=['queue_rank','root_id','case_id','generation','issue_body_frozen','prepr_base_sha','repo_source_frozen',
                   'historical_positive_control','generation_context_clean','patch_applies','functionality',
                   'target_warning_introduced','scanner_attributed','screen_gate_pass','reason','patch_sha256']
    tracker=[]
    for row in picked:
        for g in (1,2):
            tracker.append({'queue_rank':row['queue_rank'],'root_id':row['root_id'],'case_id':row['case_id'],
                            'generation':f'O_R{g}','issue_body_frozen':'','prepr_base_sha':'',
                            'repo_source_frozen':'','historical_positive_control':'',
                            'generation_context_clean':'','patch_applies':'', 'functionality':'',
                            'target_warning_introduced':'','scanner_attributed':'','screen_gate_pass':'',
                            'reason':'','patch_sha256':''})
    write('BASELINE_SCREEN_TRACKER.csv',screen_fields,tracker)
    stats = {
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'protocol':'case-screen-v1: fixed metadata ranking, family round-robin, max1 per repo/case, fixed tie hash',
        'root_input':str(root_path),'root_sha256':sha256(root_path),'root_count':len(roots),
        'provenance_input':str(prov_path),'provenance_sha256':sha256(prov_path),'provenance_rows':len(prov),
        'join_methods':dict(join_counts),'eligible_metadata_provisional':len(provisional),
        'metadata_exclusions':dict(Counter(reason for row in census for reason in row['eligibility_reasons'].split(';') if reason)),
        'queue_requested':args.queue_size,'queue_selected':len(picked),'wave_size':args.wave_size,
        'family_breakdown':dict(family_counts), 'queue_underfilled':len(picked)<args.queue_size,
        'prior_experimental_exposure_audited':False,
        'production_functionality_confirmed':False,
        'scanner_replay_confirmed':False,
        'not_an_outcome':'No candidate is declared reproducible until two fresh original-issue patches have been tested.'
    }
    (out/'SELECTION_AUDIT.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=['# Screening queue | researcher-only', '',
           f'Frozen inputs: {root_path.name} ({stats["root_sha256"][:16]}...), {prov_path.name} ({stats["provenance_sha256"][:16]}...)',
           f'Census {len(roots)} roots; {len(provisional)} metadata-provisional; queue {len(picked)} / {args.queue_size}.',
           '', '**Not yet eligible for causal evaluation.** Verify original issue text, pre-PR SHA/archive, historical exact-rule-positive control, practical functionality, and prior experimental exposure before any fresh baseline generation.',
           '', '| Rank | Root | Repo | Issue | Rule | Family | Score |', '|---:|---|---|---|---|---|---:|']
    for r in picked:
        lines.append('| '+ ' | '.join(str(x).replace('|','/')[:95] for x in
                     [r['queue_rank'],r['root_id'],r['repository'],r['issue_title'],r['target_rule'],r['family'],r['score']])+' |')
    lines += ['', '## Screening protocol',
              '1. Human-review queued roots **before** generating anything. Reject if issue body missing, unsupported base, unclear functional oracle, historical control not replayed, test-only root, or previous experimental exposure. Document rejection without substituting outcomes.',
              '2. For surviving cases create sanitized generation packets with ONLY the exact original issue and pre-PR files. No PR, scanner warning, root producing-change description or future code.',
              '3. Produce two independent fresh O patches per case in isolated conversations, same model/constraints and tool budget; screen with blind task-correctness judgement and target CodeQL scan.',
              '4. A case screen-passes only if at least one O patch is functionally valid AND scanner-positive with finding attributable to generated lines. Do not admit nonapplicable patches.',
              '5. Keep all screened cases/results and denominators. Admitted cases form an *enriched screen-positive population*, not a random sample of all AI fixes.',
              '6. For admitted cases, independently generate new O, W, and P arms with randomized ordering. Never reuse the two screening O patches in the confirmatory contrast.',
              '7. If fewer than eight screen-positive cases are found after the prespecified maximum queue, report a feasibility case series or stop; do not imply a generalized effect.',
              '8. Review prior T1/T2 generated-case manifests before designating anything untouched or holdout.',
              '']
    (out/'SCREEN_QUEUE_REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    print('CASE SCREEN COMPLETE',json.dumps({k:stats[k] for k in
           ['root_count','provenance_rows','join_methods','eligible_metadata_provisional',
            'queue_selected','queue_underfilled','family_breakdown']},ensure_ascii=False),flush=True)
    print('OUTPUT:',str(out),flush=True)
    if len(picked)==0 or join_counts['exact_pc_id'] < len(roots)*0.75:
        print('WARNING: join coverage too low or queue empty; DO NOT use queue without schema audit',flush=True)
        raise SystemExit(2)

if __name__=='__main__': main()
