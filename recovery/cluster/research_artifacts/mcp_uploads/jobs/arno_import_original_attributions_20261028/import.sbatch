#!/bin/bash
#SBATCH --job-name=arno_attribution_122_70
#SBATCH --partition=stampede
#SBATCH --time=00:10:00
#SBATCH --mem=3G
python3 - <<'PY'
from pathlib import Path
import collections,datetime,json,re,sqlite3,hashlib
root=Path.home()/'research_artifacts'
db=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=root/'mcp_uploads/jobs/arno_import_original_attributions_20261028'
out.mkdir(parents=True,exist_ok=True)
report={'status':'STARTED','description':'Frozen Direct Side-effect Unclear producing-change attribution and canonical finding ID linkage. Does not claim complete Step1 finding descriptive records.'}
try:
 conn=sqlite3.connect(str(db),timeout=90)
 conn.execute('PRAGMA busy_timeout=90000')
 conn.execute('PRAGMA foreign_keys=ON')
 xs=list(conn.execute("SELECT decision_id,case_id,evidence_json FROM arno_mechanism_selection"))
 rootmap=dict(conn.execute('SELECT producing_change_id,root_id FROM arno_pc_root_lineage'))
 if len(xs)!=455 or len(rootmap)!=455:raise ValueError('Missing 455 PC mappings')
 source=[]
 for decision_id,case_id,text in xs:
  r=json.loads(text)
  cohort=r.get('PROV_Source Cohort')
  origin=r.get('PROV_Source Producing Change ID')
  label=r.get('PROV_Frozen Broad Attribution')
  why=r.get('PROV_Broad Attribution Reason')
  kind=r.get('PROV_Broad Attribution Basis')
  cfs=re.findall(r'(?:N70-)?CF-[0-9]{4}',r.get('PROV_Canonical Finding ID(s)') or '')
  if not cohort or not origin or not label or not cfs:
    raise ValueError('Missing cohort, PC ID, broad label or CF IDs for '+decision_id)
  source.append({'cohort':cohort,'study_pc':decision_id,'case_id':case_id,
    'origin_pc':origin,'label':label,'reason':why,'basis':kind,
    'cf_ids':cfs,'root_id':rootmap[decision_id]})
 counts=collections.Counter((x['cohort'],x['label']) for x in source)
 expected={('original122','Direct'):91,('original122','Side-effect'):228,
  ('original122','Unclear'):3,('new70','Direct'):43,('new70','Side-effect'):90}
 if counts!=expected:raise ValueError('Attribution frozen counts do not match expected: '+str(counts))
 canonical=collections.defaultdict(list)
 for x in source:
  for cf in x['cf_ids']:
   canonical[(x['cohort'],cf)].append(x)
 orig_cfs={cf for (cohort,cf) in canonical if cohort=='original122'}
 new_cfs={cf for (cohort,cf) in canonical if cohort=='new70'}
 if len(orig_cfs)!=605:raise ValueError('Expected exactly 605 original canonical IDs, got '+str(len(orig_cfs)))
 duplicates=[(cf,len(rows)) for (cohort,cf),rows in canonical.items() if len(rows)>1]
 if duplicates:raise ValueError('Canonical IDs mapped to multiple PCs '+str(duplicates[:5]))
 if len({x['origin_pc'] for x in source if x['cohort']=='original122'})!=322:
  raise ValueError('Expected 322 distinct original PC IDs')
 if len({x['origin_pc'] for x in source if x['cohort']=='new70'})!=133:
  raise ValueError('Expected 133 distinct NEW70 PC IDs')
 conn.execute('''CREATE TABLE arno_frozen_broad_attribution(
  cohort TEXT NOT NULL CHECK(cohort IN('original122','new70')),
  producing_change_id TEXT NOT NULL,
  study_pc_id TEXT NOT NULL UNIQUE REFERENCES arno_mechanism_selection(decision_id),
  case_id INTEGER NOT NULL REFERENCES cases(id),
  root_id TEXT NOT NULL REFERENCES arno_root_decisions(root_id),
  attribution TEXT NOT NULL,
  attribution_basis TEXT,
  attribution_reason TEXT,
  source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
  provenance_kind TEXT NOT NULL,
  PRIMARY KEY(cohort,producing_change_id))''')
 conn.execute('''CREATE TABLE arno_canonical_id_pc_links(
  canonical_finding_id TEXT PRIMARY KEY,
  cohort TEXT NOT NULL,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  producing_change_id TEXT NOT NULL,
  study_pc_id TEXT NOT NULL REFERENCES arno_mechanism_selection(decision_id),
  root_id TEXT NOT NULL REFERENCES arno_root_decisions(root_id),
  source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
  detailed_step1_import_status TEXT NOT NULL CHECK(detailed_step1_import_status IN ('PENDING_ORIGINAL_SHEET','PENDING_NEW70_FINAL_SHEET')),
  FOREIGN KEY(cohort,producing_change_id) REFERENCES arno_frozen_broad_attribution(cohort,producing_change_id))''')
 for x in source:
  conn.execute('''INSERT INTO arno_frozen_broad_attribution VALUES(?,?,?,?,?,?,?,?,?,?)''',(
   x['cohort'],x['origin_pc'],x['study_pc'],x['case_id'],x['root_id'],
   x['label'],x['basis'],x['reason'],'d1_root_pc_crosswalk',
   'ORIGINAL_FROZEN_BROAD_LABEL_REUSED_IN_LATER_PROVENANCE_EXPORT'))
  for cf in x['cf_ids']:
   conn.execute('''INSERT INTO arno_canonical_id_pc_links VALUES(?,?,?,?,?,?,?,?)''',(
     cf,x['cohort'],x['case_id'],x['origin_pc'],x['study_pc'],x['root_id'],
     'd1_root_pc_crosswalk',
     'PENDING_ORIGINAL_SHEET' if x['cohort']=='original122' else 'PENDING_NEW70_FINAL_SHEET'))
 stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
 conn.execute("UPDATE arno_stage_ledger SET detail=detail||'; 322 original and 133 NEW70 frozen broad attribution rows plus linked canonical IDs, detailed Step1 sheets still pending', last_updated_utc=? WHERE stage_number=4",(stamp,))
 conn.commit()
 report['attribution_counts']={cohort:{label:n for (co,label),n in counts.items() if co==cohort} for cohort in ('original122','new70')}
 report['canonical_id_counts']={'original122':len(orig_cfs),'new70':len(new_cfs)}
 report['crosswalk_links']=conn.execute("SELECT COUNT(*) FROM arno_canonical_id_pc_links").fetchone()[0]
 report['attribution_rows']=conn.execute("SELECT COUNT(*) FROM arno_frozen_broad_attribution").fetchone()[0]
 report['no_duplicate_canonical_ids']=not bool(duplicates)
 report['foreign_key_violations']=sum(len(conn.execute('PRAGMA foreign_key_check('+n+')').fetchall()) for n in ('arno_frozen_broad_attribution','arno_canonical_id_pc_links'))
 report['all_cases_exist']=conn.execute('SELECT COUNT(DISTINCT case_id) FROM arno_frozen_broad_attribution').fetchone()[0]
 conn.close()
 if report['foreign_key_violations']!=0 or report['attribution_rows']!=455 or report['crosswalk_links']!=605+len(new_cfs):
  raise ValueError('Post-import verification invalid')
 report['status']='COMPLETE'
except Exception as ex:
 report['status']='FAILED';report['error']=type(ex).__name__+': '+str(ex)
 raise
finally:
 (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2),flush=True)
PY