"""Build a paper-facing dataset; read SQLite only, retain all historical HF files."""
import argparse,hashlib,json,sqlite3,sys
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--database',required=True);ap.add_argument('--output',required=True);ap.add_argument('--publish',action='store_true');ap.add_argument('--path-token',action='append',default=[]);ap.add_argument('--code-revision',required=True);a=ap.parse_args()
 import pyarrow as pa
 import pyarrow.parquet as pq
 out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
 db=Path(a.database)
 certificate_path=db.parent/'MANIFEST.json'
 certificate=json.loads(certificate_path.read_text()) if certificate_path.exists() else {}
 source_record=certificate.get('files',{}).get(db.name,{})
 if not source_record.get('sha256'):
  status=json.loads((db.parent/'BUILD_STATUS.json').read_text())
  assert status['state']=='COMPLETE','Source build is not complete'
 c=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON')
 tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
 candidates=[n for n in tables if n.endswith('_classifications')]
 assert len(candidates)==1,'Cannot uniquely identify source annotations'
 physical_prefix=candidates[0][:-len('classifications')]
 def rows(sql):return [dict(r) for r in c.execute(sql.replace('study_',physical_prefix))]
 original={r['case_id']:r for r in rows('SELECT case_id,issue_request_summary,issue_purpose,instruction_specificity,imported_source_key FROM study_classifications')}
 new={r['case_id'] for r in rows('SELECT case_id FROM study_new70_context_frozen')}
 assert len(original)==122 and len(new)==70 and not(set(original)&new)
 positives=set(original)|new
 pcs=rows('SELECT * FROM study_frozen_broad_attribution');mapped={r['case_id'] for r in pcs}
 pairs=rows('SELECT * FROM study_matched_control_pairs_C2');pos_pairs={r['positive_case_id'] for r in pairs};controls={r['control_case_id'] for r in pairs}
 runs=rows('SELECT * FROM review_v_runs');historical={r['case_id'] for r in runs if r['evidence_class']=='ARCHIVED_ORIGINAL_OWP'}
 roots=rows('SELECT * FROM study_d7_final_roots_342')
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
 'original122_annotations':rows('SELECT * FROM study_classifications'),
 'new70_final_findings':rows('SELECT * FROM study_new70_final_findings'),
 'historical_runs':[r for r in runs if r['evidence_class']=='ARCHIVED_ORIGINAL_OWP'],
 'later_runs':[r for r in runs if r['evidence_class']!='ARCHIVED_ORIGINAL_OWP'],
 'artifacts':rows('SELECT * FROM review_v_artifacts')}
 manifest={'release':'paper-cases-20261111-v3','source_database':'adversarial-swe-agents.sqlite','source_database_sha256':source_record.get('sha256'),'source_database_hash_basis':'Source build count checks passed; whole SQLite hash not calculated by this exporter.','paper_code_commit':a.code_revision,'default_config':'paper_cases','primary_key':'case_id','membership_basis':'Explicit original122/new70 source membership, frozen producing changes, frozen matched pairs and archived-original run classification; not inferred from dates or mining labels.','files':{},'counts':{'corpus':3809,'positives':192,'original122':122,'new70':70,'mapped_cases':191,'matched_pairs':190,'producing_changes':455,'roots':342,'archived_runs':40,'archived_run_cases':14},'limitations':['No reannotation or experiment regeneration.','Scanner positive does not mean verified vulnerability.','Later runs are separate from archived originals.','Null original122 annotations for other cohorts are not negative labels.']}
 for name,data in frames.items():
  tab=pa.Table.from_pylist(data);p=out/(name+'.parquet');pq.write_table(tab,p,compression='zstd');back=pq.read_table(p);assert back.to_pylist()==tab.to_pylist();manifest['files'][p.name]={'rows':len(data),'sha256':sha(p),'columns':tab.column_names}
 # Document every primary column's source; no claims of reconciled cross-cohort annotation labels.
 sources={
 'repository':'repos.full_name','repository_url':'repos.html_url','language':'repos.language',
 'recorded_agent_cohort':'cases.ai_cohort','mining_status':'cases.status','recorded_mining_label':'cases.final_label',
 'in_paper_corpus':'cases membership','in_finding_positive_cohort':'study_classifications UNION study_new70_context_frozen',
 'in_original122':'study_classifications membership','in_new70':'study_new70_context_frozen membership',
 'in_mapped191':'study_frozen_broad_attribution distinct case_id','in_rq2_positive':'study_matched_control_pairs_C2.positive_case_id',
 'in_rq2_control':'study_matched_control_pairs_C2.control_case_id','in_archived_owp14':"review_v_runs.evidence_class = ARCHIVED_ORIGINAL_OWP (14 cases, not 12 complete triples)",
 'producing_change_count':'COUNT study_frozen_broad_attribution by case_id','final_root_count':'COUNT study_d7_final_roots_342 by case_id'}
 for col in frames['cases'][0]:
  if col.startswith('original122_'):sources[col]='study_classifications.'+{'original122_issue_summary':'issue_request_summary','original122_annotation_source_key':'imported_source_key'}.get(col,col.removeprefix('original122_'))
  elif col.startswith('issue_'):sources[col]='issues.'+col.removeprefix('issue_')
  elif col.startswith('pr_'):sources[col]='pull_requests.'+col.removeprefix('pr_')
  elif col in ['head_sha','base_sha','merged_at']:sources[col]='pull_requests.'+col
 sources['case_id']='cases.id'
 (out/'COLUMN_SOURCES.json').write_text(json.dumps(sources,indent=2))
 prefix='data/paper-cases-20261111-v3'
 configs=[]
 for name in frames:
  conf='paper_cases' if name=='cases' else name
  configs+=['- config_name: '+conf]+(['  default: true'] if name=='cases' else [])+['  data_files:','  - split: train','    path: '+prefix+'/'+name+'.parquet']
 card='---\nconfigs:\n'+'\n'.join(configs)+'\n---\n\n# Study research dataset\n\nStart with **`paper_cases`**: one row per issue–PR case in the paper’s 3,809-case corpus, with repository, issue/PR URLs and text, and explicit analysis-membership flags. `train` is a transport split name, not an ML training/evaluation assignment.\n\n```python\nfrom datasets import load_dataset\ncases = load_dataset("Stralb/adversarial-swe-agents", "paper_cases", split="train", token=True)\npositives = cases.filter(lambda row: row["in_finding_positive_cohort"])\n```\n\nPin the Hugging Face revision returned by the upload receipt for reproducible use. Access is private.\n\n| Population | Size | Selection |\n|---|---:|---|\n| Corpus | 3,809 cases | default `paper_cases` |\n| Finding-positive | 192 cases | `in_finding_positive_cohort` |\n| Original annotations | 122 cases | `in_original122` |\n| Later annotation cohort | 70 cases | `in_new70` |\n| Exactly mapped | 191 cases | `in_mapped191` |\n| Matched comparison | 190 pairs | `matched_pairs` config |\n| Original replay records | 40 runs, 14 cases | `historical_runs` config; 12 complete triples |\n\nSupporting configs preserve their units: findings, producing changes, roots, pairs, runs and artifacts. Do not join these into cases without handling one-to-many multiplicity. `later_runs` is supplementary and must not fill missing historical arms. Original122 annotation fields are cohort-specific, not harmonised labels for all 192 cases. `artifacts` contains evidence locators for the preserved SQLite database; large binary evidence remains in the master.\n\nThe paper snapshot, column sources, exact membership basis, counts and Parquet checksums are recorded in ['+prefix+'/MANIFEST.json]('+prefix+'/MANIFEST.json) and [COLUMN_SOURCES.json]('+prefix+'/COLUMN_SOURCES.json). The preserved database and review documentation are in [archives/INDEX.json](archives/INDEX.json). Older mining snapshots and older Parquet exports remain historical; they are not loaded by the default configuration.\n\nA scanner warning is not a confirmed vulnerability. This export does not reannotate cases, establish causal effects or regenerate historical experiments.\n'
 (out/'DATASET_CARD.md').write_text(card);(out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
 if a.publish:publish(out,frames,manifest,card,prefix,a.path_token)
 print(json.dumps({'state':'EXPORT_VALIDATED','counts':manifest['counts'],'output':str(out)},indent=2),flush=True)

def artifact_interface(records,tokens):
 import re
 result=[]
 for row in records:
  if 'artifact_id' in row:result.append(row);continue
  source=row['source_table']
  alias='study_'+source.split('_',1)[1] if '_' in source and any(token.casefold() in source.split('_',1)[0].casefold() for token in tokens) else source
  role=row.get('role')
  if role:
   for token in tokens:role=re.sub(re.escape(token),'record',role,flags=re.I)
  result.append({'artifact_id':'artifact_'+hashlib.sha256(row['artifact_key'].encode()).hexdigest(),'case_id':row.get('case_id'),'run_id':row.get('run_id'),'role':role,'source_table_alias':alias,'sha256':row.get('sha256'),'original_bytes':row.get('original_bytes'),'embedded':bool(row.get('embedded')),'encoding':row.get('encoding')})
 return result

def publish(out,frames,manifest,card,prefix,path_tokens):
 import re,yaml
 from huggingface_hub import HfApi,CommitOperationAdd,CommitOperationCopy,CommitOperationDelete,hf_hub_download
 from datasets import load_dataset
 frames['artifacts']=artifact_interface(frames['artifacts'],path_tokens)
 import pyarrow as pa,pyarrow.parquet as pq
 artifact_file=out/'artifacts.parquet';artifact_table=pa.Table.from_pylist(frames['artifacts']);pq.write_table(artifact_table,artifact_file,compression='zstd')
 assert pq.read_table(artifact_file).to_pylist()==frames['artifacts']
 manifest['files']['artifacts.parquet']={'rows':len(frames['artifacts']),'sha256':sha(artifact_file),'columns':artifact_table.column_names}
 manifest['artifact_id_policy']='artifact_ followed by full SHA-256 of the frozen artifact_key; source_table_alias is a neutral display label. Use resolve_artifact.py against the original snapshot to recover the exact source record.'
 repo='Stralb/adversarial-swe-agents';api=HfApi();info=api.repo_info(repo,repo_type='dataset',files_metadata=True)
 assert info.private,'Expected the existing private dataset; access permissions will not be changed'
 before=info.sha;items={f.rfilename:f for f in info.siblings}
 def ident(f):
  lfs=getattr(f,'lfs',None)
  if lfs:
   digest=lfs.get('sha256') if isinstance(lfs,dict) else getattr(lfs,'sha256',None)
   return {'kind':'sha256','digest':digest,'bytes':f.size}
  return {'kind':'git_blob','digest':f.blob_id,'bytes':f.size}
 def safe_path(path):
  for token in path_tokens:path=re.sub(re.escape(token),'legacy',path,flags=re.I)
  return path
 old_card=Path(hf_hub_download(repo,'README.md',repo_type='dataset',revision=before)).read_bytes() if 'README.md' in items else b''
 previous=old_card.decode('utf-8')
 if previous.startswith('---\n'):
  old_meta=yaml.safe_load(previous.split('---',2)[1]) or {};new_meta=yaml.safe_load(card.split('---',2)[1])
  metadata={k:v for k,v in old_meta.items() if k not in ('configs','dataset_info','pretty_name')};metadata.update(new_meta)
  card='---\n'+yaml.safe_dump(metadata,sort_keys=False)+'---'+card.split('---',2)[2]
 # Preserve the exact old tree on a named ref before relocating any current files.
 branch='preservation-'+before[:12];api.create_branch(repo,branch=branch,repo_type='dataset',revision=before,exist_ok=True)
 archive_prefix='archives/snapshot-'+before[:12]
 ops=[];archive_index=[];destinations=set();moves=[]
 protected={'.gitattributes','README.md','DATASET.json','UPLOAD_RECEIPT.json'}
 for path,f in sorted(items.items()):
  if path in protected or path.startswith('archives/') or path.startswith(prefix+'/'):continue
  target=archive_prefix+'/'+safe_path(path)
  assert target not in destinations and target not in items,'Archive destination collision'
  destinations.add(target)
  if getattr(f,'lfs',None):ops.append(CommitOperationCopy(src_path_in_repo=path,path_in_repo=target,src_revision=before))
  else:
   assert (f.size or 0)<50_000_000,'Unexpected large regular Git file'
   local=hf_hub_download(repo,path,repo_type='dataset',revision=before)
   ops.append(CommitOperationAdd(path_in_repo=target,path_or_fileobj=local))
  ops.append(CommitOperationDelete(path_in_repo=path));moves.append((path,target,ident(f)))
  archive_index.append({'path':target,**ident(f)})
 # Preserve the previous card bytes without keeping them in the default interface.
 if old_card:ops.append(CommitOperationAdd(path_in_repo=archive_prefix+'/original_dataset_card.md',path_or_fileobj=old_card))
 if 'archives/INDEX.json' in items:
  prior_index=json.loads(Path(hf_hub_download(repo,'archives/INDEX.json',repo_type='dataset',revision=before)).read_text())
  by_path={entry['path']:entry for entry in prior_index.get('files',[])}
  by_path.update({entry['path']:entry for entry in archive_index});archive_index=list(by_path.values())
 archive_info={'source_revision':before,'preservation_ref':branch,'files':archive_index,'note':'Original snapshots and evidence retain their original bytes and may contain historical identifiers. These files are not the default case table.'}
 # Keep an audit of verbatim source-text occurrences. Source text is never silently redacted.
 exceptions=[]
 for name,data in frames.items():
  for col in data[0] if data else []:
   n=sum(any(token.casefold() in str(row.get(col,'')).casefold() for token in path_tokens) for row in data)
   if n:exceptions.append({'table':name,'column':col,'rows':n,'policy':'VERBATIM_SOURCE_RECORD_OR_IDENTIFIER_RETAINED'})
 (out/'SOURCE_TEXT_EXCEPTIONS.json').write_text(json.dumps(exceptions,indent=2))
 (out/'ARCHIVE_INDEX.json').write_text(json.dumps(archive_info,indent=2))
 (out/'resolve_artifact.py').write_text('"""Resolve a neutral artifact ID against a preserved evidence snapshot."""\nimport argparse,hashlib,json,sqlite3\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument(\'--db\',type=Path,required=True);p.add_argument(\'--artifact-id\',required=True);a=p.parse_args()\nc=sqlite3.connect(a.db.resolve().as_uri()+\'?mode=ro\',uri=True);c.row_factory=sqlite3.Row\nfor r in c.execute(\'SELECT * FROM review_artifact_index\'):\n if \'artifact_\'+hashlib.sha256(r[\'artifact_key\'].encode()).hexdigest()==a.artifact_id:\n  print(json.dumps(dict(r),indent=2));break\nelse:raise SystemExit(\'Artifact ID not found in this snapshot\')\n')
 card=card.replace('The preserved database and review documentation are in [archives/INDEX.json](archives/INDEX.json).','Historical snapshot availability is recorded in [the archive index](archives/INDEX.json). The source snapshot hash in the manifest identifies the input; it does not imply that a full snapshot matching that hash has been uploaded.')
 card+='\nArtifact locators use stable IDs and neutral table aliases. Run `python resolve_artifact.py --db adversarial-swe-agents.sqlite --artifact-id ID` to recover an exact frozen source record.\n'
 card+='\nOriginal author credits, case text, identifiers and evidence are preserved verbatim. [Source-text exceptions]('+prefix+'/SOURCE_TEXT_EXCEPTIONS.json) identifies fields retaining historical wording.\n'
 # These are exact neutral schema aliases, not a claim that archived SQLite identifiers changed.
 manifest['source_schema_alias_policy']='Column sources use neutral study_* aliases. Frozen source snapshot identifiers and source records are unchanged.'
 manifest['archive_index']='archives/INDEX.json';manifest['python_dependencies']={}
 import importlib.metadata
 for package in ('pyarrow','datasets','huggingface_hub','PyYAML'):manifest['python_dependencies'][package]=importlib.metadata.version(package)
 (out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2));(out/'DATASET_CARD.md').write_text(card)
 for p in out.iterdir():
  if p.is_file() and p.name!='UPLOAD_RECEIPT.json':ops.append(CommitOperationAdd(path_in_repo=prefix+'/'+p.name,path_or_fileobj=str(p)))
 ops.extend([CommitOperationAdd(path_in_repo='README.md',path_or_fileobj=card.encode()),CommitOperationAdd(path_in_repo='archives/INDEX.json',path_or_fileobj=json.dumps(archive_info,indent=2).encode()),CommitOperationAdd(path_in_repo='DATASET.json',path_or_fileobj=json.dumps({'release':manifest['release'],'default_config':'paper_cases','manifest':prefix+'/MANIFEST.json','primary_key':'case_id','counts':manifest['counts']},indent=2).encode())])
 print(json.dumps({'state':'UPLOAD_PLAN','archive_moves':len(moves),'new_tables':len(frames),'old_revision':before,'preservation_ref':branch}),flush=True)
 commit=api.create_commit(repo_id=repo,repo_type='dataset',parent_commit=before,operations=ops,commit_message='Organise canonical paper cases and preserve historical snapshots under archives')
 after=api.repo_info(repo,repo_type='dataset',revision=commit.oid,files_metadata=True);remote={f.rfilename:f for f in after.siblings}
 for entry in archive_info['files']:
  assert entry['path'] in remote and ident(remote[entry['path']])=={k:entry[k] for k in ('kind','digest','bytes')},'Archived object identity mismatch'
 for source,target,want in moves:
  assert target in remote and ident(remote[target])==want,'Archive object identity mismatch'
  assert source not in remote,'Old path unexpectedly retained'
 if old_card:assert Path(hf_hub_download(repo,archive_prefix+'/original_dataset_card.md',repo_type='dataset',revision=commit.oid)).read_bytes()==old_card
 assert Path(hf_hub_download(repo,'README.md',repo_type='dataset',revision=commit.oid)).read_bytes()==card.encode()
 for p in out.iterdir():
  if p.is_file() and p.name!='UPLOAD_RECEIPT.json':assert sha(Path(hf_hub_download(repo,prefix+'/'+p.name,repo_type='dataset',revision=commit.oid)))==sha(p),p.name
 # Exercise the real consumer interface at the pinned uploaded revision.
 loaded=load_dataset(repo,split='train',revision=commit.oid,token=True)
 assert len(loaded)==3809 and len(set(loaded['case_id']))==3809
 assert sum(loaded['in_finding_positive_cohort'])==192
 assert sum(loaded['in_original122'])==122 and sum(loaded['in_new70'])==70
 assert sum(loaded['in_mapped191'])==191
 pair_data=load_dataset(repo,'matched_pairs',split='train',revision=commit.oid,token=True);assert len(pair_data)==190
 receipt={'state':'REMOTE_FILES_AND_LOAD_DATASET_VERIFIED','commit':commit.oid,'previous_commit':before,'preservation_ref':branch,'default_config':'paper_cases','case_rows':3809,'positive_cases':192,'matched_pairs':190,'archived_files_verified':len(archive_info['files']),'archive_moves_this_commit':len(moves),'source_text_exception_fields':len(exceptions),'permissions_unchanged':True,'history_rewritten':False}
 (out/'UPLOAD_RECEIPT.json').write_text(json.dumps(receipt,indent=2));api.upload_file(repo_id=repo,repo_type='dataset',path_or_fileobj=str(out/'UPLOAD_RECEIPT.json'),path_in_repo='UPLOAD_RECEIPT.json',commit_message='Record verified dataset entry point and archived object identities')
 print(json.dumps(receipt,indent=2),flush=True)

if __name__=='__main__':
 if '--bootstrap' in sys.argv:
  import subprocess,os
  deps=Path(__file__).resolve().parent/'dependencies'
  subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--only-binary=:all:','--target',str(deps),'pyarrow','PyYAML','datasets','huggingface_hub'],check=True)
  env=dict(os.environ);env['PYTHONPATH']=str(deps)
  subprocess.run([sys.executable,str(Path(__file__).resolve()),*[a for a in sys.argv[1:] if a!='--bootstrap']],check=True,env=env)
 else:main()
