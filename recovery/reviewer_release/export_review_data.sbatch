#!/bin/bash
#SBATCH --job-name=arno-review-exports
#SBATCH --partition=batch
#SBATCH --dependency=afterok:84751
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/review_exports_20261111_v1/job.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/review_exports_20261111_v1/job.err
/home-mscluster/astrauss/.venvs/huggingface/bin/python -u - <<'PY'
import csv,hashlib,json,sqlite3
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts');release=root/'ARNO_REVIEW_RELEASE_20261111_v1'
job=root/'mcp_uploads/jobs/review_exports_20261111_v1'
final=json.loads((root/'mcp_uploads/jobs/review_finalize_20261111_v1/report.json').read_text())
if final['state']!='complete':raise RuntimeError('Final checks not complete')
db=release/'ARNO_RESEARCH_MASTER_REVIEW.sqlite';before=(db.stat().st_size,db.stat().st_mtime_ns)
c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);c.execute('PRAGMA query_only=ON')
specs={'data/cases.csv':'review_v_cases','data/rq1_original122_annotations.csv':'review_v_original122','data/rq1_new70_final_findings.csv':'review_v_new70_final_findings','data/rq1_new70_case_risk_source.csv':'arno_new70_phase9_full_source','data/rq1_producing_changes.csv':'review_v_producing_changes','data/rq1_final_root_coding.csv':'review_v_final_root_coding','data/rq2_matched_pairs.csv':'review_v_matched_pairs','data/rq2_recorded_statistical_reproductions.csv':'review_v_reproduced_statistics','data/rq3_run_catalog.csv':'review_v_runs','history/annotation_events.csv':'review_v_annotation_history','history/new70_preliminary_candidates_NOT_FINAL.csv':'review_v_new70_preliminary_candidates','history/claim_evidence_history.csv':'review_v_claim_evidence_history'}
report={'state':'complete','database_unchanged':True,'exports':{}}
for relative,table in specs.items():
 cols=[r[1] for r in c.execute('PRAGMA table_info("'+table+'")') if r[2].upper()!='BLOB']
 if not cols:raise RuntimeError('No nonbinary columns in '+table)
 p=release/relative;p.parent.mkdir(exist_ok=True)
 if p.exists():raise RuntimeError('Refusing overwrite: '+relative)
 cur=c.execute('SELECT '+','.join('"'+x.replace('"','""')+'"' for x in cols)+' FROM "'+table+'"')
 n=0
 with p.open('x',newline='',encoding='utf-8') as f:
  w=csv.writer(f);w.writerow(cols)
  for row in cur:w.writerow(row);n+=1
 report['exports'][relative]={'source_table_or_view':table,'rows':n,'columns':cols,'blob_columns_exported':False}
c.close()
if before!=(db.stat().st_size,db.stat().st_mtime_ns):raise RuntimeError('Database changed during CSV exports')
(release/'CSV_EXPORTS.json').write_text(json.dumps(report,indent=2))
with (release/'README.md').open('a') as f:
 f.write('\n## Small data exports\n\nThe data/ folder exports the research-facing case, annotation, finding, producing-change, final-root, matched-pair, statistical-record and run tables as CSV. The history/ folder keeps preliminary candidates and event/status histories separate. These files preserve source field values and qualifications; selecting a file does not attest to its scientific validity. CSV_EXPORTS.json records every export source and row count. Binary payloads remain in the SQLite database and its artifact index.\n')
(release/'export_review_data.sbatch').write_bytes((job/'job.sbatch').read_bytes())
manifest=json.loads((release/'MANIFEST.json').read_text())
for p in sorted(release.rglob('*')):
 if not p.is_file() or p.name in ('MANIFEST.json','SHA256SUMS') or p==db:continue
 h=hashlib.sha256(p.read_bytes())
 manifest['files'][str(p.relative_to(release))]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
manifest['csv_exports']='Research-facing data separated from preliminary and historical exports; database unchanged.'
(release/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
(release/'SHA256SUMS').write_text(''.join(v['sha256']+'  '+k+'\n' for k,v in manifest['files'].items()))
(job/'report.json').write_text(json.dumps({'state':'complete','database_sha256':manifest['files'][db.name]['sha256'],'csv_export_count':len(report['exports']),'rows':{k:v['rows'] for k,v in report['exports'].items()},'original_master_unmodified':True},indent=2))
print((job/'report.json').read_text(),flush=True)
PY
