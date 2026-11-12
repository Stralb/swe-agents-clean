#!/usr/bin/env python3
"""Read-only intake verifier for October O/W/P research ZIPs.

Only parses existing ZIP members, JSON and CSV. Never extracts members,
executes scanner/test code, calls a shell, or writes to the source archives.
Counts labelled 'new' remain archived claims until baseline SARIF is available.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
from collections import Counter


class AuditError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    d = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            d.update(chunk)
    return d.hexdigest()


def member_name(z: zipfile.ZipFile, suffix: str) -> str:
    matches = [n for n in z.namelist() if n == suffix or n.endswith('/' + suffix)]
    if len(matches) != 1:
        raise AuditError(f'Expected exactly one member ending in {suffix}: {matches[:3]}')
    return matches[0]


def read_json(z: zipfile.ZipFile, suffix: str) -> dict:
    name = member_name(z, suffix)
    if z.getinfo(name).file_size > 40_000_000:
        raise AuditError('JSON member too large: ' + name)
    value = json.loads(z.read(name).decode('utf-8'))
    if not isinstance(value, dict):
        raise AuditError('Expected a JSON object: ' + name)
    return value


def verify_manifest(z: zipfile.ZipFile) -> dict:
    """Require a complete, exact file/byte/hash index; no archive extraction."""
    index_name = member_name(z, '00_README_AND_MANIFEST/PART_INDEX.csv')
    rows = list(csv.DictReader(io.StringIO(z.read(index_name).decode('utf-8-sig'))))
    required = {'archive_path', 'sha256', 'bytes'}
    if not rows or not required.issubset(rows[0]):
        raise AuditError('Missing manifest entries or columns')
    listed = [r['archive_path'] for r in rows]
    if len(listed) != len(set(listed)):
        raise AuditError('Duplicate paths in manifest')
    actual = [info.filename for info in z.infolist() if not info.is_dir()]
    if len(actual) != len(set(actual)):
        raise AuditError('Duplicate ZIP member names')
    if set(actual) - {index_name} != set(listed):
        raise AuditError('Manifest coverage mismatch')
    for row in rows:
        path = row['archive_path']
        info = z.getinfo(path)
        if info.file_size != int(row['bytes']):
            raise AuditError('Wrong member size for ' + path)
        digest = hashlib.sha256()
        with z.open(info) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != row['sha256'].lower():
            raise AuditError('Wrong member SHA-256 for ' + path)
    return {'manifest_rows': len(rows), 'validated_member_hashes': len(rows), 'index_member_present': True}


def sarif_count(z: zipfile.ZipFile, suffix: str) -> tuple[int, set[tuple[str,str,int]]]:
    data = read_json(z, suffix)
    results = [r for run in data.get('runs', []) for r in run.get('results', [])]
    locators = set()
    for result in results:
        rule = str(result.get('ruleId', ''))
        for location in result.get('locations') or []:
            physical = location.get('physicalLocation', {})
            uri = str(physical.get('artifactLocation', {}).get('uri', '')).replace('\\', '/')
            line = int(physical.get('region', {}).get('startLine', 0) or 0)
            locators.add((rule, uri, line))
    return len(results), locators


def verify_scanner(zip3: zipfile.ZipFile) -> tuple[dict, dict]:
    summary = read_json(zip3, 'owp14_allarm_comparison_job71212/OWP14_SUMMARY.json')
    cases = summary.get('cases')
    if not isinstance(cases, list) or len(cases) != 14:
        raise AuditError('Expected exactly 14 case rows')
    arm_dirs = {
        'O':'owp14_user12_o_codeql_job71159',
        'W':'owp14_user14_w_codeql_job71209',
        'P':'owp14_user14_p_codeql_job71204',
    }
    case_ids = [int(r['case_id']) for r in cases]
    if len(case_ids) != len(set(case_ids)):
        raise AuditError('Duplicate case IDs in main scanner summary')
    results = {}
    totals = Counter()
    source_kinds = Counter()
    base_identity_groups = {}
    for row in cases:
        cid = int(row['case_id'])
        source_kinds[row['snapshot']] += 1
        per_case = {}
        for arm, folder in arm_dirs.items():
            case = f'CASE_{cid:05d}'
            suffix = f'{folder}/{case}/RESULT.json'
            found = [n for n in zip3.namelist() if n.endswith('/'+suffix)]
            if not found:
                if row[f'{arm}_scan'] not in ('NOT_UPLOADED', None):
                    raise AuditError(f'Missing {cid} {arm} but status is not missing')
                continue
            record = json.loads(zip3.read(found[0]))
            if record['stage'] != 'SCAN_COMPLETE' or row[f'{arm}_scan'] != 'SCAN_COMPLETE':
                raise AuditError(f'Incomplete scan {cid} {arm}')
            if int(record['case_id']) != cid or record['arm'] != arm:
                raise AuditError('Mismatched record identity')
            if record['current_codeql_version'] != '2.25.6':
                raise AuditError('Unexpected CodeQL version')
            for step, value in record.get('checks', {}).items():
                if value.get('rc') != 0:
                    raise AuditError(f'Scanner subprocess failure {cid} {arm} {step}')
            n, locators = sarif_count(zip3, f'{folder}/{case}/after.sarif')
            if n != int(record['codeql_after_total']):
                raise AuditError(f'After-SARIF count mismatch {cid} {arm}')
            for field, rfield in (('new','new_strong_total'),('new_conservative','new_conservative_total'),
                                  ('target','new_strong_target_rule')):
                if int(row[f'{arm}_{field}']) != int(record[rfield]):
                    raise AuditError(f'Summary differs from result {cid} {arm} {field}')
            target_added_line = sum(bool(a.get('on_added_line')) and bool(a.get('historical_target_rule')) for a in record.get('new_strong_alerts', []))
            if target_added_line != int(row[f'{arm}_target_added_line']):
                raise AuditError(f'Summary target/added-line mismatch {cid} {arm}')
            alerts = record.get('new_strong_alerts', [])
            if len(alerts) != int(record['new_strong_total']):
                raise AuditError(f'New-strong alert list length mismatch {cid} {arm}')
            for alert in alerts:
                key = (str(alert['rule']), str(alert['path']).replace('\\','/'), int(alert['line']))
                if not any(rule == key[0] and line == key[2] and (uri == key[1] or uri.endswith('/'+key[1]))
                           for rule,uri,line in locators):
                    raise AuditError(f'Reported new alert absent from after SARIF {cid} {arm} {key}')
            per_case[arm] = {
                'patch_sha256':record['patch_sha256'],
                'baseline_sarif_sha256':record['baseline_sarif_sha256'],
                'frozen_source_sha256':record['frozen_source_sha256'],
                'new_claimed':int(record['new_strong_total']),
                'historical_rule_new_claimed':int(record['new_strong_target_rule']),
                'after_sarif_results':n,
            }
            totals[f'{arm}_scans'] += 1
            totals[f'{arm}_new_claimed'] += int(record['new_strong_total'])
            totals[f'{arm}_target_claimed'] += int(record['new_strong_target_rule'])
        if not per_case or 'W' not in per_case or 'P' not in per_case:
            raise AuditError(f'W or P missing for {cid}')
        bsha = {info['baseline_sarif_sha256'] for info in per_case.values()}
        if len(bsha) != 1 or not row['baselines_match']:
            raise AuditError(f'Archived baseline identity mismatch {cid}')
        base_identity_groups[str(cid)] = len({info['frozen_source_sha256'] for info in per_case.values()})
        results[str(cid)] = per_case
    if dict((x,totals[x]) for x in ('O_scans','W_scans','P_scans')) != {'O_scans':12,'W_scans':14,'P_scans':14}:
        raise AuditError('Unexpected arm scan counts')
    for arm,expected_total,expected_target in [('O',21,7),('W',10,4),('P',15,5)]:
        if totals[f'{arm}_new_claimed'] != expected_total or totals[f'{arm}_target_claimed'] != expected_target:
            raise AuditError('Aggregate scanner counts changed')
    comparison_name = member_name(zip3,'owp14_allarm_comparison_job71212/OWP14_SCANNER_COMPARISON.csv')
    comparison = list(csv.DictReader(io.StringIO(zip3.read(comparison_name).decode('utf-8-sig'))))
    by_case = {int(r['case_id']): r for r in comparison}
    if len(by_case)!=14 or len(comparison)!=14 or set(by_case)!=set(case_ids):
        raise AuditError('Comparison CSV cohort differs from summary JSON')
    for row in cases:
        cid=int(row['case_id'])
        other=by_case[cid]
        if other['snapshot'] != row['snapshot']:
            raise AuditError(f'Comparison CSV source mode differs for {cid}')
        for arm in ('O','W','P'):
            for field in ('new','target'):
                left=row.get(f'{arm}_{field}')
                right=other.get(f'{arm}_{field}')
                if left is None and right in ('','None','null'):
                    continue
                if str(left)!=str(right):
                    raise AuditError(f'Comparison CSV differs for {cid} {arm} {field}: {left!r} vs {right!r}')
    expected = summary['counts']
    if expected['historical_target_previously_reproduced_count'] != sum(str(r['prior_O_target_reproduced']).lower()=='true' for r in cases):
        raise AuditError('Prior O target recurrence count mismatch')
    return {
        'cases':len(cases),
        'arm_counts':dict(totals),
        'source_mode_counts':dict(source_kinds),
        'historical_target_previously_reproduced':expected['historical_target_previously_reproduced_count'],
        'paired_O_W_P_cases':sum(all(a in results[str(cid)] for a in ('O','W','P')) for cid in case_ids),
        'missing_O_cases':sorted(cid for cid in case_ids if 'O' not in results[str(cid)]),
        'same_archived_baseline_sha_for_each_case':True,
        'different_source_archive_sha_across_arms_all_cases':all(v>1 for v in base_identity_groups.values()),
        'baseline_SARIF_exported':False,
        'source_reported_provenance_verified':summary['issue_asof_PR_provenance_verified'],
        'source_reported_full_functional_acceptance':summary['functional_acceptance_verified'],
        'source_reported_generation_comparability':summary['agent_generation_cohort_comparability_verified'],
    }, results


def verify_functional(zip4: zipfile.ZipFile, scanner_results: dict) -> dict:
    intake = read_json(zip4,'owp14_functional_intake_job71357/ISSUES_INTAKE_SUMMARY.json')
    syntax1 = read_json(zip4,'owp14_syntax_checks_job71361/SUMMARY.json')
    syntax2 = read_json(zip4,'owp14_syntax_jsx_checks_job71362/SUMMARY.json')
    targeted = read_json(zip4,'owp14_targeted_behavior_job71363/SUMMARY.json')
    env = read_json(zip4,'owp14_functional_env_job71359/ENV.json')
    if len(intake['cases']) != 14 or set(map(int,intake['cases'])) != set(map(int,scanner_results)):
        raise AuditError('Functional intake case cohort differs')
    for cid, row in intake['cases'].items():
        if not row['frozen_repo_equal']:
            raise AuditError(f'Functional intake frozen source reported mismatching {cid}')
        for arm in ('O','W','P'):
            applied = row['patch_applied'].get(arm)
            if arm in scanner_results[cid] and applied is not True:
                raise AuditError(f'Applied patch not confirmed {cid} {arm}')
            if arm not in scanner_results[cid] and applied is not None:
                raise AuditError(f'Unexpected patch claim for missing {cid} {arm}')
    expected_keys = {f'{int(cid):05d}_{arm}' for cid, arms in scanner_results.items() for arm in arms}
    for name, summary in (('initial',syntax1),('JSX',syntax2)):
        patches = summary['patches']
        if set(patches)!=expected_keys or summary['count']!=40:
            raise AuditError(f'{name} cohort does not cover 40 scans')
        if sum(v['status']=='SYNTAX_PASS' for v in patches.values())!=summary['passed']:
            raise AuditError(f'{name} reported syntax count mismatch')
        if sum(v['status']=='SYNTAX_FAIL' for v in patches.values())!=summary['syntax_failed']:
            raise AuditError(f'{name} reported failure count mismatch')
        for key, row in patches.items():
            cid, arm=key.split('_')
            if row['patch_sha256']!=scanner_results[str(int(cid))][arm]['patch_sha256']:
                raise AuditError('Syntax vs CodeQL patch hash mismatch: '+key)
    if syntax1['passed']!=37 or syntax2['passed']!=39:
        raise AuditError('Unexpected recorded syntax counts')
    bad1=sorted(k for k,v in syntax1['patches'].items() if v['status']!='SYNTAX_PASS')
    bad2=sorted(k for k,v in syntax2['patches'].items() if v['status']!='SYNTAX_PASS')
    tests=targeted['tests']
    if len(tests)!=4 or any(v['stage']!='PASS' or v['interpretation']!='SUBCOMPONENT_ONLY_NOT_FULL_FUNCTIONAL_ACCEPTANCE' for v in tests.values()):
        raise AuditError('Narrow targeted test summary changed')
    return {
        'intake_cases':len(intake['cases']),
        'initial_syntax':{'pass':syntax1['passed'],'count':syntax1['count'],'failures':bad1},
        'JSX_aware_syntax':{'pass':syntax2['passed'],'count':syntax2['count'],'failures':bad2},
        'targeted_subcomponent_checks_pass':len(tests),
        'full_issue_acceptance_established':False,
        'archive_environment_reported_node_available':env['tools']['node']['available'],
        'archive_environment_reported_bun_available':env['tools']['bun']['available'],
    }


def audit(scan_zip: Path,function_zip: Path) -> dict:
    with zipfile.ZipFile(scan_zip) as zs, zipfile.ZipFile(function_zip) as zf:
        a=verify_manifest(zs)
        b=verify_manifest(zf)
        scanner,scanner_results=verify_scanner(zs)
        functional=verify_functional(zf,scanner_results)
        return {
            'status':'ARCHIVE_INTEGRITY_AND_RECORDED_OUTCOME_CROSSCHECK_PASS',
            'scientific_validity':'EXPLORATORY_ONLY_NOT_INDEPENDENT_ALERT_DELTA_OR_FUNCTIONAL_REPLICATION',
            'scanner_archive':{'filename':scan_zip.name,'sha256':sha256_file(scan_zip),**a},
            'functional_archive':{'filename':function_zip.name,'sha256':sha256_file(function_zip),**b},
            'scanner':scanner,
            'functional':functional,
            'limitations':[
                'Baseline SARIF files are not present; cannot independently recompute new-alert set differences.',
                'Per-arm frozen source TAR byte hashes differ despite a common claimed baseline SARIF; require content-level source equivalence review.',
                'Historical issue-as-of-PR provenance and generation-cohort comparability are source-declared unverified.',
                'Four FILTERED_SOURCE_PROVISIONAL cases are mixed into the reported paired aggregates.',
                'Two cases have no O scan in this O/W/P cohort.',
                'Syntax parsing and isolated behavioural checks do not verify issue acceptance.',
                'Matching rule IDs, counts and locations does not verify introduced vulnerabilities or causal prevention.',
            ],
        }


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scan_zip',type=Path)
    parser.add_argument('functional_zip',type=Path)
    args=parser.parse_args(argv)
    try:
        report=audit(args.scan_zip,args.functional_zip)
    except (AuditError,ValueError,OSError,KeyError,TypeError,zipfile.BadZipFile) as e:
        print(json.dumps({'status':'FAIL','error':str(e)},indent=2))
        return 1
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0


if __name__=='__main__':
    sys.exit(main())
