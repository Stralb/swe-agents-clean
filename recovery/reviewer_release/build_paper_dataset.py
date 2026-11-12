"""Build a paper-facing dataset; read SQLite only, retain all historical HF files."""
import argparse,hashlib,json,sqlite3,sys
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--database',required=True);ap.add_argument('--output',required=True);ap.add_argument('--publish',action='store_true');a=ap.parse_args()
 import pyarrow as pa
 import pyarrow.parquet as pq
 out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
 db=Path(a.database)
 certificate=json.loads((db.parent/'MANIFEST.json').read_text())
 assert certificate['files'][db.name]['sha256']=='b9734456db5b6c1abb1ef72ec146eb4db2cacbb75115b64cfae34b95223d5011'
 assert db.stat().st_size==42187345920
 c=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON')
 tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
 def rows(sql):return [dict(r) for r in c.execute(sql)]
 original={r['case_id']:r for r in rows('SELECT case_id,issue_request_summary,issue_purpose,instruction_specificity,imported_source_key FROM arno_classifications')}
 new={r['case_id'] for r in rows('SELECT case_id FROM arno_new70_context_frozen')}
 assert len(original)==122 and len(new)==70 and not(set(original)&new)
 positives=set(original)|new
 pcs=rows('SELECT * FROM arno_frozen_broad_attribution');mapped={r['case_id'] for r in pcs}
 pairs=rows('SELECT * FROM arno_matched_control_pairs_C2');pos_pairs={r['positive_case_id'] for r in pairs};controls={r['control_case_id'] for r in pairs}
 runs=rows('SELECT * FROM review_v_runs');historical={r['case_id'] for r in runs if r['evidence_class']=='ARCHIVED_ORIGINAL_OWP'}
 roots=rows('SELECT * FROM arno_d7_final_roots_342')
 from collections import Counter
 pc_counts=Counter(r['case_id'] for r in pcs);root_counts=Counter(r['case_id'] for r in roots)
 core=rows('''SELECT c.id AS case_id,r.full_name AS repository,r.html_url AS repository_url,r.language,
 i.number AS issue_number,i.url AS issue_url,i.title AS issue_title,i.body AS issue_body,
 p.number AS pr_number,p.url AS pr_url,p.title AS pr_title,p.body AS pr_body,p.head_sha,p.base_sha,p.merged_at,
 c.ai_cohort AS recorded_agent_cohort,c.status AS mining_status,c.final_label AS recorded_mining_label
 FROM cases c LEFT JOIN repos r ON r.id=c.repo_id LEFT JOIN issues i ON i.id=c.issue_id LEFT JOIN pull_requests p ON p.id=c.pr_id ORDER BY c.id''')
 for r in core:
  k=r['case_id'];v=original.get(k,{})
  r.update(in_paper_corpus=True,in_finding_positive_cohort=k in positives,in_original122=k in original,in_new70=k in new,in_mapped191=k in mapped,in_rq2_positive=k in pos_pairs,in_rq2_control=k in controls,in_archived_owp14=k in historical,producing_change_count=pc_counts[k],final_root_count=root_counts[k],original122_issue_summary=v.get('issue_request_summary'),original122_issue_purpose=v.get('issue_purpose'),original122_instruction_specificity=v.get('instruction_specificity'),original122_annotation_source_key=v.get('imported_source_key'))
 ids={r['case_id'] for r in core};assert len(core)==len(ids)==3809
 assert positives<=ids and mapped<=positives and len(mapped)==191
 assert len(pcs)==455 and len(roots)==342 and len(pairs)==190
 assert pos_pairs<=positives and controls<=ids and not(controls&positives)
 assert len(historical)==14 and len([r for r in runs if r['evidence_class']=='ARCHIVED_ORIGINAL_OWP'])==40
 # This case table is the sole default entry point. Other tables retain their analysis unit.
 frames={'cases':core,'finding_positive_cases':[r for r in core if r['in_finding_positive_cohort']],
 'producing_changes':pcs,'final_roots':roots,'matched_pairs':pairs,
 'original122_annotations':rows('SELECT * FROM arno_classifications'),
 'new70_final_findings':rows('SELECT * FROM arno_new70_final_findings'),
 'historical_runs':[r for r in runs if r['evidence_class']=='ARCHIVED_ORIGINAL_OWP'],
 'later_runs':[r for r in runs if r['evidence_class']!='ARCHIVED_ORIGINAL_OWP'],
 'artifacts':rows('SELECT * FROM review_v_artifacts')}
 manifest={'release':'arno-paper-cases-20261111-v1','source_database':db.name,'source_database_sha256':'b9734456db5b6c1abb1ef72ec146eb4db2cacbb75115b64cfae34b95223d5011','source_database_hash_basis':'Existing verified review-release certificate; not rehashed by this exporter.','paper_code_commit':'b7bd30f0bc2ed0f5424de8c46d251164e7f48b6e','default_config':'paper_cases','primary_key':'case_id','membership_basis':'Explicit original122/new70 source membership, frozen producing changes, frozen matched pairs and archived-original run classification; not inferred from dates or mining labels.','files':{},'counts':{'corpus':3809,'positives':192,'original122':122,'new70':70,'mapped_cases':191,'matched_pairs':190,'producing_changes':455,'roots':342,'archived_runs':40,'archived_run_cases':14},'limitations':['No reannotation or experiment regeneration.','Scanner positive does not mean verified vulnerability.','Later runs are separate from archived originals.','Null original122 annotations for other cohorts are not negative labels.']}
 for name,data in frames.items():
  tab=pa.Table.from_pylist(data);p=out/(name+'.parquet');pq.write_table(tab,p,compression='zstd');back=pq.read_table(p);assert back.to_pylist()==tab.to_pylist();manifest['files'][p.name]={'rows':len(data),'sha256':sha(p),'columns':tab.column_names}
 # Document every primary column's source; no claims of reconciled cross-cohort annotation labels.
 sources={
 'repository':'repos.full_name','repository_url':'repos.html_url','language':'repos.language',
 'recorded_agent_cohort':'cases.ai_cohort','mining_status':'cases.status','recorded_mining_label':'cases.final_label',
 'in_paper_corpus':'cases membership','in_finding_positive_cohort':'arno_classifications UNION arno_new70_context_frozen',
 'in_original122':'arno_classifications membership','in_new70':'arno_new70_context_frozen membership',
 'in_mapped191':'arno_frozen_broad_attribution distinct case_id','in_rq2_positive':'arno_matched_control_pairs_C2.positive_case_id',
 'in_rq2_control':'arno_matched_control_pairs_C2.control_case_id','in_archived_owp14':"review_v_runs.evidence_class = ARCHIVED_ORIGINAL_OWP (14 cases, not 12 complete triples)",
 'producing_change_count':'COUNT arno_frozen_broad_attribution by case_id','final_root_count':'COUNT arno_d7_final_roots_342 by case_id'}
 for col in frames['cases'][0]:
  if col.startswith('original122_'):sources[col]='arno_classifications.'+{'original122_issue_summary':'issue_request_summary','original122_annotation_source_key':'imported_source_key'}.get(col,col.removeprefix('original122_'))
  elif col.startswith('issue_'):sources[col]='issues.'+col.removeprefix('issue_')
  elif col.startswith('pr_'):sources[col]='pull_requests.'+col.removeprefix('pr_')
  elif col in ['head_sha','base_sha','merged_at']:sources[col]='pull_requests.'+col
 sources['case_id']='cases.id'
 (out/'COLUMN_SOURCES.json').write_text(json.dumps(sources,indent=2))
 prefix='paper/arno-paper-cases-20261111-v1'
 configs=[]
 for name in frames:
  conf='paper_cases' if name=='cases' else name
  configs+=['- config_name: '+conf]+(['  default: true'] if name=='cases' else [])+['  data_files:','  - split: train','    path: '+prefix+'/'+name+'.parquet']
 card='---\nconfigs:\n'+'\n'.join(configs)+'\n---\n\n# Arno research dataset\n\nStart with **`paper_cases`**: one row per issue–PR case in the paper’s 3,809-case corpus, with repository, issue/PR URLs and text, and explicit analysis-membership flags. `train` is a transport split name, not an ML training/evaluation assignment.\n\n```python\nfrom datasets import load_dataset\ncases = load_dataset("Stralb/malicious-issue-miner-data", "paper_cases", split="train", token=True)\npositives = cases.filter(lambda row: row["in_finding_positive_cohort"])\n```\n\nPin the Hugging Face revision returned by the upload receipt for reproducible use. Access is private.\n\n| Population | Size | Selection |\n|---|---:|---|\n| Corpus | 3,809 cases | default `paper_cases` |\n| Finding-positive | 192 cases | `in_finding_positive_cohort` |\n| Original annotations | 122 cases | `in_original122` |\n| Later annotation cohort | 70 cases | `in_new70` |\n| Exactly mapped | 191 cases | `in_mapped191` |\n| Matched comparison | 190 pairs | `matched_pairs` config |\n| Original replay records | 40 runs, 14 cases | `historical_runs` config; 12 complete triples |\n\nSupporting configs preserve their units: findings, producing changes, roots, pairs, runs and artifacts. Do not join these into cases without handling one-to-many multiplicity. `later_runs` is supplementary and must not fill missing historical arms. Original122 annotation fields are cohort-specific, not harmonised labels for all 192 cases. `artifacts` contains evidence locators for the preserved SQLite database; large binary evidence remains in the master.\n\nThe paper snapshot, column sources, exact membership basis, counts and Parquet checksums are recorded in ['+prefix+'/MANIFEST.json]('+prefix+'/MANIFEST.json) and [COLUMN_SOURCES.json]('+prefix+'/COLUMN_SOURCES.json). The preserved database and review documentation are in [research/arno-review-20261111-v1](research/arno-review-20261111-v1). Older mining snapshots and older Parquet exports remain historical; they are not loaded by the default configuration.\n\nA scanner warning is not a confirmed vulnerability. This export does not reannotate cases, establish causal effects or regenerate historical experiments.\n'
 (out/'DATASET_CARD.md').write_text(card);(out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
 print(json.dumps({'state':'EXPORT_VALIDATED','counts':manifest['counts'],'output':str(out)},indent=2),flush=True)
 if a.publish:
  from huggingface_hub import HfApi,CommitOperationAdd
  api=HfApi();repo='Stralb/malicious-issue-miner-data';info=api.repo_info(repo,repo_type='dataset');assert info.private,'Expected the previously authorised private dataset'
  from huggingface_hub import hf_hub_download
  old=Path(hf_hub_download(repo,'README.md',repo_type='dataset',revision=info.sha)).read_bytes()
  import yaml
  previous=old.decode('utf-8')
  if previous.startswith('---\n'):
   previous_metadata=yaml.safe_load(previous.split('---',2)[1]) or {}
   new_metadata=yaml.safe_load(card.split('---',2)[1])
   metadata={k:v for k,v in previous_metadata.items() if k not in ('configs','dataset_info')}
   metadata.update(new_metadata)
   card='---\n'+yaml.safe_dump(metadata,sort_keys=False)+'---'+card.split('---',2)[2]
  (out/'PREVIOUS_HF_LAYOUT.json').write_text(json.dumps({'previous_commit':info.sha,'files':api.list_repo_files(repo,repo_type='dataset',revision=info.sha)},indent=2))
  ops=[CommitOperationAdd(path_in_repo=prefix+'/'+p.name,path_or_fileobj=str(p)) for p in out.iterdir() if p.is_file()]
  archive='archive/dataset-card-before-paper-entrypoint-20261111.md'
  if not api.file_exists(repo,archive,repo_type='dataset',revision=info.sha):ops.append(CommitOperationAdd(path_in_repo=archive,path_or_fileobj=old))
  ops.append(CommitOperationAdd(path_in_repo='README.md',path_or_fileobj=card.encode()))
  ops.append(CommitOperationAdd(path_in_repo='PAPER_DATASET.json',path_or_fileobj=json.dumps({'release':manifest['release'],'default_config':'paper_cases','manifest':prefix+'/MANIFEST.json','source_database':manifest['source_database'],'paper_code_commit':manifest['paper_code_commit']},indent=2).encode()))
  commit=api.create_commit(repo_id=repo,repo_type='dataset',operations=ops,parent_commit=info.sha,commit_message='Add canonical paper case entry point and explicit Hugging Face configs')
  for p in out.iterdir():
   if not p.is_file():continue
   remote=Path(hf_hub_download(repo,prefix+'/'+p.name,repo_type='dataset',revision=commit.oid));assert sha(remote)==sha(p),p.name
  receipt={'state':'REMOTE_BYTES_VERIFIED','commit':commit.oid,'previous_commit':info.sha,'prefix':prefix,'default_config':'paper_cases','files':len(list(out.iterdir())),'counts':manifest['counts']}
  (out/'UPLOAD_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2),flush=True)
if __name__=='__main__':main()
