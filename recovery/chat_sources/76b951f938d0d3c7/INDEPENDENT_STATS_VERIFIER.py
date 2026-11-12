#!/usr/bin/env python3
"""Independent read-only arithmetic and structural verifier for Arno issue/PR evidence.

No external network, repository mutation, cluster jobs, model evaluations, or scans.
Outputs observed counts and structural consistency checks; never interprets
scanner warnings as confirmed vulnerabilities or reported findings as causal.

Usage:
 python3 INDEPENDENT_STATS_VERIFIER.py --evidence-zip ARNO_EVIDENCE_20261022_212644.zip \
   --historical-xlsx 'issue_pr_manual_evaluation_master_122(1).xlsx' \
   --output verification.json
 Optional: --c1-csv C1_CASE_SCANNER_OPPORTUNITY_3809.csv \
           --owp-csv owp14_case_arm_counts_20261020.csv
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import statistics
import sys
import zipfile
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for buf in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(buf)
    return digest.hexdigest()


def read_csv_bytes(payload):
    return list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))


def as_number(value):
    if value in ('', None, 'NOT_UPLOADED', 'None', 'null'):
        return None
    return float(value)


def verify_bundle(path):
    with zipfile.ZipFile(path) as z:
        corrupt = z.testzip()
        if corrupt:
            raise ValueError('Corrupt zip member: ' + corrupt)
        pcs = read_csv_bytes(z.read('reference/455_producing_changes.csv'))
        pairs = read_csv_bytes(z.read('reference/190_pairs.csv'))
        manifest = read_csv_bytes(z.read('manifest.csv'))
        roots = [json.loads(line) for line in z.read('reference/342_root_packets.jsonl').decode('utf-8').splitlines() if line.strip()]
        zip_members = set(z.namelist())
    pc_ids = [row['PC ID'] for row in pcs]
    mapped_pcs = [c['pc_id'] for root in roots for c in root['constituent_pcs']]
    case_ids = {row['Case ID'] for row in pcs}
    matched_pos = [row['positive_case_id'] for row in pairs]
    matched_ctrl = [row['control_case_id'] for row in pairs]
    matched_set = set(matched_pos)
    by_unmatched = collections.Counter(row['Case ID'] for row in pcs if row['Case ID'] not in matched_set)
    kinds = collections.Counter(row['kind'] for row in manifest)
    family = collections.Counter(row['Finding Family'] for row in pcs)
    unresolved = [row for row in pcs if row['Introduction Status'].lower() == 'unresolved']
    missing_rules = [row for row in pcs if not row['Rule ID(s)'].strip()]
    uncertain_roots = [row for row in roots if row['boundary_uncertain'] == 'YES']
    target_diff_count = 0
    scanner_summary_count = 0
    full_diffs = 0
    for row in manifest:
        if row['kind'] != 'positive':
            continue
        prefix = 'cases/positive_' + row['case_id'] + '/'
        full_diffs += int(prefix + 'PR_FULL_FROZEN.diff' in zip_members)
        ids = json.loads(row['pc_ids'])
        target_diff_count += int(any(prefix + 'producing_changes/' + pid + '/pr_target_diff.patch' in zip_members for pid in ids))
        scanner_summary_count += int(any(prefix + 'producing_changes/' + pid + '/scanner_evidence.txt' in zip_members for pid in ids))
    integrity = {
        'unique_pc_ids': len(set(pc_ids)) == len(pcs),
        'unique_root_ids': len({r['root_id'] for r in roots}) == len(roots),
        'mapped_pc_multiset_equals_pc_multiset': collections.Counter(mapped_pcs) == collections.Counter(pc_ids),
        'root_declared_sizes_match': all(len(r['constituent_pcs']) == int(r['pc_count']) for r in roots),
        'unique_matched_positive_ids': len(set(matched_pos)) == len(pairs),
        'unique_matched_control_ids': len(set(matched_ctrl)) == len(pairs),
        'case_counts_consistent': sum(kinds.values()) == len(manifest),
    }
    if not all(integrity.values()):
        raise ValueError('Structural integrity check failed: ' + str(integrity))
    no_pc_but_matched = sorted(set(matched_pos) - case_ids, key=int)
    result = {
        'source': {'path': str(path), 'sha256': sha256_file(path), 'zip_members': len(zip_members)},
        'measurement_scope': 'Actual CSV/JSONL records contained in exported cluster ZIP; no scanner reruns',
        'structural_integrity': integrity,
        'counts': {
            'pc_rows': len(pcs),
            'distinct_pc_ids': len(set(pc_ids)),
            'mapped_workflows_with_pcs': len(case_ids),
            'root_packets': len(roots),
            'distinct_root_ids': len({r['root_id'] for r in roots}),
            'root_to_pc_links': len(mapped_pcs),
            'root_size_distribution': dict(sorted(collections.Counter(str(len(r['constituent_pcs'])) for r in roots).items(), key=lambda x:int(x[0]))),
            'root_boundaries_uncertain': len(uncertain_roots),
            'root_boundaries_uncertain_unique_cases': len({str(r['case_id']) for r in uncertain_roots}),
            'matched_pairs': len(pairs),
            'same_repository_pairs': sum(str(r['same_repository']) == '1' for r in pairs),
            'match_tiers': dict(sorted(collections.Counter(r['match_tier'] for r in pairs).items())),
            'matched_positive_cases_with_pcs': len(matched_set & case_ids),
            'matched_positive_cases_without_pcs': no_pc_but_matched,
            'matched_positive_pc_rows': sum(r['Case ID'] in matched_set for r in pcs),
            'unmatched_positive_pc_rows': sum(by_unmatched.values()),
            'unmatched_positive_pc_rows_by_case': dict(sorted(by_unmatched.items(), key=lambda x:int(x[0]))),
            'pc_finding_family': dict(sorted(family.items())),
            'introduction_status': dict(sorted(collections.Counter(r['Introduction Status'] for r in pcs).items())),
            'unresolved_introduction_families': dict(sorted(collections.Counter(r['Finding Family'] for r in unresolved).items())),
            'missing_rule_id_pc_rows': len(missing_rules),
            'missing_rule_id_families': dict(sorted(collections.Counter(r['Finding Family'] for r in missing_rules).items())),
            'review_dossiers_by_kind': dict(sorted(kinds.items())),
            'selected_positive_cases_with_archived_full_pr_diff': full_diffs,
            'selected_positive_cases_with_at_least_one_target_patch': target_diff_count,
            'selected_positive_cases_with_at_least_one_scanner_summary': scanner_summary_count,
        },
        'scope_limits': [
            'The 342 root packets are blinded coder inputs; they do not certify final H/T/M or T1-T5 adjudications.',
            'Root and PC IDs accounting checks do not establish scanner newness, security correctness, or exploitability.',
            'The export does not include complete baseline/head SARIF for all workflows.',
            'Raw paired semantic coding needed to recompute C6/C7 tests is not in this archive.',
            'Study corpus manifest of all 3,809 workflows is not included in this ZIP.',
        ]
    }
    return result


def verify_historical_xlsx(path):
    try:
        from openpyxl import load_workbook
    except ImportError:
        return {'status': 'openpyxl is not installed; cannot inspect historical XLSX'}
    wb = load_workbook(path, read_only=True, data_only=True)
    def sheet_rows(name):
        it = wb[name].values
        head = next(it)
        return [dict(zip(head, values)) for values in it if values and any(v is not None for v in values)]
    cases = sheet_rows('Issue_PR_Master_122')
    canonical = sheet_rows('Step1_Canonical_Findings')
    attributions = sheet_rows('Step3_Attribution')
    risks = sheet_rows('Risk_Assessment')
    context = sheet_rows('Context_Source_122')
    labels = collections.Counter(str(x.get('Final Attribution')) for x in attributions)
    risk_labels = collections.Counter(str(x.get('Final Risk Label')) for x in risks)
    delay = [float(x['Issue to PR Creation Delay (Hours)']) for x in context if x.get('Issue to PR Creation Delay (Hours)') not in (None, '')]
    ages = [float(x['Account Age at Issue (Days)']) for x in context if x.get('Account Age at Issue (Days)') not in (None,'')]
    prior = [float(x['Prior Repo Issues/PRs Before Issue']) for x in context if x.get('Prior Repo Issues/PRs Before Issue') not in (None,'')]
    return {
        'source': {'path': str(path), 'sha256': sha256_file(path)},
        'counts': {
            'included_cases': len(cases), 'unique_cases': len({str(x['Case ID']) for x in cases}),
            'canonical_findings': len(canonical), 'unique_canonical_finding_ids': len({str(x['Canonical Finding ID']) for x in canonical}),
            'producing_changes': len(attributions), 'unique_producing_change_ids': len({str(x['Producing Change ID']) for x in attributions}),
            'attribution_labels': dict(sorted(labels.items())),
            'risk_labels': dict(sorted(risk_labels.items())),
            'risk_human_review_cells_populated': sum(x.get('Human Review / Correction') not in (None, '') for x in risks),
            'issue_pr_negative_delay_count': sum(x < 0 for x in delay),
            'issue_to_pr_delay_median_hours': statistics.median(delay) if delay else None,
            'issue_author_account_age_at_least_365_days': sum(x >= 365 for x in ages),
            'issue_authors_with_zero_prior_repo_activity': sum(x == 0 for x in prior),
            'issue_to_pr_negative_delay_cases': [str(x['Case ID']) for x in context if x.get('Issue to PR Creation Delay (Hours)') not in (None,'') and float(x['Issue to PR Creation Delay (Hours)']) < 0],
        },
        'scope_limit': 'Historical subset only; LLM-assisted risk assessments cannot be represented as independent human validation.'
    }


def verify_c1(path):
    rows = read_csv_bytes(Path(path).read_bytes())
    ids = [row['case_id'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case IDs in C1 source')
    positive = [row for row in rows if row['is_positive'] in ('1', 'true', 'True')]
    return {
        'source': {'path': str(path), 'sha256': sha256_file(path)},
        'counts': {'cases': len(rows), 'scanner_positive_cases': len(positive),
                   'other_cases': len(rows)-len(positive)},
        'scope_limit': 'A C1 scanner-opportunity flag count does not constitute a fresh scan or proof of exploitability.'
    }


def verify_owp(path):
    rows = read_csv_bytes(Path(path).read_bytes())
    paired = [row for row in rows if as_number(row['O_new_claimed']) is not None]
    if len({x['case_id'] for x in rows}) != len(rows):
        raise ValueError('Duplicate OWP case IDs')
    arm_counts = {}
    for arm in 'OWP':
        vals = [as_number(r[arm+'_new_claimed']) for r in rows]
        arm_counts[arm] = {'recorded_scans': sum(x is not None for x in vals),
                           'sum_claimed_new_alerts': int(sum(x for x in vals if x is not None)),
                           'zero_new_alerts_among_paired': sum(as_number(r[arm+'_new_claimed']) == 0 for r in paired)}
    return {
        'source': {'path': str(path), 'sha256': sha256_file(path)},
        'counts': {'case_rows': len(rows), 'fully_paired_OWP': len(paired),
                   'O_absent_case_ids': [r['case_id'] for r in rows if as_number(r['O_new_claimed']) is None],
                   'arms': arm_counts,
                   'W_fewer_claimed_new_alerts_than_O_paired': sum(as_number(r['W_new_claimed']) < as_number(r['O_new_claimed']) for r in paired),
                   'P_fewer_claimed_new_alerts_than_O_paired': sum(as_number(r['P_new_claimed']) < as_number(r['O_new_claimed']) for r in paired),
                   'syntax_failures': [r['case_id']+'-'+a for r in rows for a in 'OWP' if r[a+'_syntax_JSX']=='SYNTAX_FAIL']},
        'scope_limit': 'Recounts archived claims from CSV only. Missing before SARIF means new-alert deltas are not independently reproduced. No full issue-functional acceptance.'
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-zip', type=Path, required=True)
    p.add_argument('--historical-xlsx', type=Path)
    p.add_argument('--c1-csv', type=Path)
    p.add_argument('--owp-csv', type=Path)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    results = {'verifier': 'ARNO_INDEPENDENT_STATS_VERIFIER_v1.0', 'export': verify_bundle(args.evidence_zip)}
    if args.historical_xlsx:
        results['historical_122'] = verify_historical_xlsx(args.historical_xlsx)
    if args.c1_csv:
        results['c1_cohort'] = verify_c1(args.c1_csv)
    if args.owp_csv:
        results['owp_recount'] = verify_owp(args.owp_csv)
    output = json.dumps(results, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(output + '\n',encoding='utf-8')
    print(output)

if __name__ == '__main__':
    main()
