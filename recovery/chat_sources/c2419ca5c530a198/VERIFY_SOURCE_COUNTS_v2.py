#!/usr/bin/env python3
"""Independent, read-only auditing of provided research evidence.

Audits counts and provenance from actual local source bytes. Does not claim
external scanner correctness, model authorship, human validation, or causality.
"""
from __future__ import annotations
import csv,io,json,zipfile,hashlib,statistics,collections,pathlib
import openpyxl
B=pathlib.Path('/mnt/data')
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
Z=B/'ARNO_EVIDENCE_20261022_212644.zip'
W=B/'issue_pr_manual_evaluation_master_122(1).xlsx'
O=B/'ARNO_DRAFT_STARTER_20261022/OWP14_REPO_CASE_ARM_COUNTS_20261020.csv'
P=B/'ARNO_RESEARCH_INTELLECTUAL_HISTORY_v1_0.zip'
with zipfile.ZipFile(Z) as z:
 assert z.testzip() is None
 rdr=lambda p:list(csv.DictReader(io.StringIO(z.read(p).decode('utf-8-sig'))))
 pcs=rdr('reference/455_producing_changes.csv')
 pairs=rdr('reference/190_pairs.csv')
 roots=[json.loads(s) for s in z.read('reference/342_root_packets.jsonl').decode('utf8').splitlines() if s.strip()]
 manifest=rdr('manifest.csv')
 info={x.filename for x in z.infolist()}
 assert len(pcs)==455 and len({x['PC ID'] for x in pcs})==455
 assert len(roots)==342 and len({x['root_id'] for x in roots})==342
 pc_to_root=[t['pc_id'] for r in roots for t in r['constituent_pcs']]
 assert collections.Counter(pc_to_root)==collections.Counter(x['PC ID'] for x in pcs)
 assert all(int(r['pc_count'])==len(r['constituent_pcs']) for r in roots)
 assert len(pairs)==190 and len({x['positive_case_id'] for x in pairs})==190
 assert len({x['control_case_id'] for x in pairs})==190
 assert len(manifest)==89
 cases={x['Case ID'] for x in pcs}
 matched={x['positive_case_id'] for x in pairs}
 unmatched=collections.Counter(x['Case ID'] for x in pcs if x['Case ID'] not in matched)
 unresolved=[x for x in pcs if x['Introduction Status']=='unresolved']
 parts=collections.Counter(x['Partition'] for x in pcs)
 families=collections.Counter(x['Finding Family'] for x in pcs)
 matching=collections.Counter(x['match_tier'] for x in pairs)
 dossiers=collections.Counter(x['kind'] for x in manifest)
 full_diffs=[];target_patches=[];scanners=[]
 for x in manifest:
  if x['kind']!='positive':continue
  prefix='cases/positive_'+x['case_id']+'/'
  if prefix+'PR_FULL_FROZEN.diff' in info:full_diffs.append(x['case_id'])
  pids=json.loads(x['pc_ids'])
  if any(prefix+'producing_changes/'+p+'/pr_target_diff.patch' in info for p in pids):target_patches.append(x['case_id'])
  if any(prefix+'producing_changes/'+p+'/scanner_evidence.txt' in info for p in pids):scanners.append(x['case_id'])
 result={
  'zip_integrity':'PASS','source_sha256':H(Z),'zip_members':len(info),
  'producing_changes':len(pcs),'unique_pcs':len(set(x['PC ID'] for x in pcs)),
  'mapped_workflow_ids':len(cases),'roots':len(roots),'root_pc_link_count':len(pc_to_root),
  'root_crosswalk_complete':True,'root_singletons':sum(len(r['constituent_pcs'])==1 for r in roots),
  'uncertain_root_count':sum(r['boundary_uncertain']=='YES' for r in roots),
  'root_size_dist':dict(sorted(collections.Counter(len(r['constituent_pcs']) for r in roots).items())),
  'pc_partition_counts':dict(parts),'pc_families':dict(families),
  'matched_pairs':len(pairs),'match_tier_counts':dict(matching),
  'same_repo_pairs':sum(x['same_repository']=='1' for x in pairs),
  'unmatched_pc_rows':sum(unmatched.values()),'unmatched_pc_case_counts':dict(unmatched),
  'matched_positive_without_pc':sorted(matched-cases),
  'matched_positive_pc_rows':sum(x['Case ID'] in matched for x in pcs),
  'unresolved_introduction_rows':len(unresolved),
  'unresolved_case_ids':dict(collections.Counter(x['Case ID'] for x in unresolved)),
  'unresolved_families':dict(collections.Counter(x['Finding Family'] for x in unresolved)),
  'dossier_counts':dict(dossiers),'positive_full_frozen_diff':len(full_diffs),
  'positive_targeted_patch':len(target_patches),'positive_scanner_summary':len(scanners),
  'missing_rule_id_rows':sum(not x['Rule ID(s)'].strip() for x in pcs),
 }
 assert result['root_pc_link_count']==455 and result['same_repo_pairs']==115 and result['matched_positive_pc_rows']==416
 assert result['dossier_counts']=={'positive':38,'control':38,'additional':13}

w=openpyxl.load_workbook(W,data_only=True,read_only=True)
def rec(name):
 it=iter(w[name].values);head=next(it)
 return [dict(zip(head,v)) for v in it if any(x is not None for x in v)]
base=rec('Issue_PR_Master_122')
findings=rec('Step1_Canonical_Findings')
attr=rec('Step3_Attribution')
risks=rec('Risk_Assessment')
context=rec('Context_Source_122')
excl=rec('Excluded_16')
assert len(base)==122 and len(findings)==605 and len(attr)==322 and len(risks)==122 and len(excl)==16
ages=[float(x['Account Age at Issue (Days)']) for x in context]
prior=[float(x['Prior Repo Issues/PRs Before Issue']) for x in context]
delay=[float(x['Issue to PR Creation Delay (Hours)']) for x in context]
risk_labels=collections.Counter(x['Final Risk Label'] for x in risks)
old={
 'source_sha256':H(W),'cases':len(base),'canonical_findings':len(findings),
 'producing_changes':len(attr),'unique_canonical_ids':len({x['Canonical Finding ID'] for x in findings}),
 'unique_pc_ids':len({x['Producing Change ID'] for x in attr}),
 'attribution':dict(collections.Counter(x['Final Attribution'] for x in attr)),
 'risk_label_counts':dict(risk_labels),
 'filled_human_risk_review_cells':sum(x['Human Review / Correction'] not in ('',None) for x in risks),
 'excluded_cases':len(excl),
 'issue_to_pr_delay_median_hours':statistics.median(delay),
 'issue_to_pr_negative_delay_cases':[str(x['Case ID']) for x in context if float(x['Issue to PR Creation Delay (Hours)'])<0],
 'account_age_at_least_365':sum(a>=365 for a in ages),
 'zero_prior_repository_activity':sum(p==0 for p in prior),
 'denominators':{'age_nonnull':len(ages),'prior_activity_nonnull':len(prior),'delay_nonnull':len(delay)},
}
assert old['attribution']=={'Direct':91,'Side-effect':228,'Unclear':3}
assert old['risk_label_counts']=={'Benign ordinary':117,'Benign ambiguous':5}
assert old['filled_human_risk_review_cells']==0
owp=list(csv.DictReader(O.open(encoding='utf-8-sig',newline='')))
paired=[x for x in owp if x['O_new_claimed']!='NOT_UPLOADED']
assert len(owp)==14 and len(paired)==12
owp_result={
 'source_sha256':H(O),'case_rows':len(owp),'triplets':len(paired),'missing_original_arm':[x['case_id'] for x in owp if x['O_new_claimed']=='NOT_UPLOADED'],
 'arm_scans':{a:sum(x[a+'_new_claimed']!='NOT_UPLOADED' for x in owp) for a in ('O','W','P')},
 'archived_claimed_new_alerts':{a:sum(int(x[a+'_new_claimed']) for x in owp if x[a+'_new_claimed']!='NOT_UPLOADED') for a in ('O','W','P')},
 'paired_zero_claims':{a:sum(int(x[a+'_new_claimed'])==0 for x in paired) for a in ('O','W','P')},
 'paired_fewer_than_original_claims':{a:sum(int(x[a+'_new_claimed'])<int(x['O_new_claimed']) for x in paired) for a in ('W','P')},
 'paired_equal_original_claims':{a:sum(int(x[a+'_new_claimed'])==int(x['O_new_claimed']) for x in paired) for a in ('W','P')},
 'jsx_syntax_fails': [x['case_id']+'-'+a for x in owp for a in ('O','W','P') if x[a+'_syntax_JSX']=='SYNTAX_FAIL'],
 'source_archive_before_SARIF_included':False,
}
assert owp_result['archived_claimed_new_alerts']=={'O':21,'W':10,'P':15}
assert owp_result['jsx_syntax_fails']==['16633-O']
source={'C1_workflows_remote_recount':3809,'C1_positives_remote_recount':192,'C1_comparison_pool_remote_recount':3617,
 'C1_method':'Read all 841710 source bytes in 26 base64 chunks via AserverV4-DCR; parsed 3807 complete rows within 3 segments and 2 rows crossing segment boundaries (one positive, one negative); no scanner rerun',
 'C1_remote_artifact':'matched_control_c1_v1_1/C1_CASE_SCANNER_OPPORTUNITY_3809.csv'}
out={'source_byte_checks':{'evidence_zip':H(Z),'historical_122_xlsx':H(W),'owp14_case_counts':H(O),'intellectual_history_zip':H(P)},
 'cluster_direct_recount':source,'research_export':result,'historical_122':old,'owp14_archived_observations':owp_result,
 'scope_limitations':['Recounting tables does not independently rerun any scanner','Repo CSV O/W/P counts labelled new are historical claims; before SARIF is absent','Root packets do not contain final root-route adjudication','C6/C7 inferential p-values cannot be recalculated without paired row-level coding','AI-coded intent classifications are not independent human assessments']}
(B/'ARNO_INDEPENDENT_PRIMARY_VERIFICATION_v2.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'C1_remote':source,'research_export':result,'historical_122':old,'owp14_archived_observations':owp_result},indent=2,ensure_ascii=False)[:11500])
