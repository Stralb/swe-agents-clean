"""Build a neutral research dataset without rewriting original evidence payloads."""
import argparse,hashlib,json,os,re,sqlite3,time
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--rules');p.add_argument('--prefix',default='study_');a=p.parse_args()
 source=Path(a.source);dest=Path(a.output);dest.mkdir(parents=True,exist_ok=False)
 rules=json.loads(Path(a.rules).read_text()) if a.rules else {'identifiers':{},'display':[]}
 mapping=rules['identifiers']
 def clean(v):
  if not isinstance(v,str):return v
  for old,new in sorted(mapping.items(),key=lambda x:-len(x[0])):v=v.replace(old,new)
  for old,new in rules.get('display',[]):v=re.sub(re.escape(old),new,v,flags=re.I)
  return v
 def quote(v):return '"'+v.replace('"','""')+'"'
 src=sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True);src.row_factory=sqlite3.Row
 objects=[dict(r) for r in src.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")]
 all_tables={o['name']:o for o in objects if o['type']=='table'}
 chosen={n for n in all_tables if n.startswith(a.prefix) or n.startswith('review_')}|{'cases','repos','issues','pull_requests'}
 assert chosen<=all_tables.keys()
 partial=dest/'adversarial-swe-agents.sqlite.partial';db=sqlite3.connect(str(partial));db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA foreign_keys=OFF')
 db.execute('ATTACH DATABASE ? AS input',(source.resolve().as_uri()+'?mode=ro',))
 report={'state':'BUILDING','tables':{},'source_evidence_policy':'Binary payloads and source-record text copied unchanged; derivative catalogs use neutral display labels.','excluded_operational_tables':len(all_tables)-len(chosen)}
 def save(): (dest/'BUILD_STATUS.json').write_text(json.dumps(report,indent=2));print(report['state'],len(report['tables']),flush=True)
 save()
 for n in sorted(chosen):db.execute(clean(all_tables[n]['sql']))
 for n in sorted(chosen):
  where=''
  if n=='issues':where=' WHERE id IN (SELECT issue_id FROM input.cases)'
  elif n=='repos':where=' WHERE id IN (SELECT repo_id FROM input.cases)'
  elif n=='pull_requests':where=' WHERE id IN (SELECT pr_id FROM input.cases)'
  db.execute('INSERT INTO '+quote(clean(n))+' SELECT * FROM input.'+quote(n)+where)
  count=db.execute('SELECT COUNT(*) FROM '+quote(clean(n))).fetchone()[0]
  expected=src.execute('SELECT COUNT(*) FROM '+quote(n)+where.replace('input.','')).fetchone()[0]
  assert count==expected,(n,count,expected)
  report['tables'][clean(n)]={'rows':count};db.commit();save()
 # Only derived navigation catalogs are relabelled. Original records and archives are immutable.
 relabelled=0
 for n in sorted(x for x in chosen if x.startswith('review_')):
  columns=[r[1] for r in db.execute('PRAGMA table_info('+quote(n)+')')]
  rows=db.execute('SELECT rowid,* FROM '+quote(n)).fetchall()
  for row in rows:
   vals=[]
   for key,value in zip(columns,row[1:]):
    if key=='source_pk_json' and value:
     value=json.dumps({clean(k):v for k,v in json.loads(value).items()},sort_keys=True)
    elif key in {'table_name','source_table','parent_table','child_table','column_name','parent_column','child_column','purpose','notes','interpretation','issue','policy_key','rule','classification_basis','selection_policy','evidence_json','value'}:
     value=clean(value)
    vals.append(value)
   if tuple(vals)!=tuple(row[1:]):
    db.execute('UPDATE '+quote(n)+' SET '+','.join(quote(k)+'=?' for k in columns)+' WHERE rowid=?',vals+[row[0]]);relabelled+=1
 # Remove catalog entries for operational tables not exported into this edition.
 names={clean(n) for n in chosen}
 if 'review_table_catalog' in names:
  for n, in db.execute('SELECT table_name FROM review_table_catalog').fetchall():
   if n not in names:
    db.execute('DELETE FROM review_table_catalog WHERE table_name=?',(n,));db.execute('DELETE FROM review_column_catalog WHERE table_name=?',(n,))
 for o in objects:
  if o['type']=='index' and o['tbl_name'] in chosen:db.execute(clean(o['sql']))
 for o in objects:
  if o['type']=='view' and o['name'].startswith('review_'):
   sql=clean(o['sql'])
   try:db.execute(sql);db.execute('SELECT * FROM '+quote(clean(o['name']))+' LIMIT 0').fetchall()
   except sqlite3.OperationalError as e:raise RuntimeError('View dependency not exported: '+clean(o['name'])) from e
 checks={'review_v_cases':3809,'review_v_original122':122,'review_v_new70_final_findings':237,'review_v_producing_changes':455,'review_v_final_root_coding':342,'review_v_matched_pairs':190,'review_v_runs':68,'review_v_archived_owp_runs':40}
 for n,want in checks.items():assert db.execute('SELECT COUNT(*) FROM '+quote(n)).fetchone()[0]==want,n
 definitions=[dict(zip(['type','name','table','sql'],r)) for r in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL")]
 forbidden=rules.get('forbidden',[])
 assert not any(re.search(re.escape(term),o['name']+' '+(o['sql'] or ''),re.I) for term in forbidden for o in definitions)
 db.commit();db.close();src.close();final=dest/'adversarial-swe-agents.sqlite';os.replace(partial,final)
 (dest/'SCHEMA.sql').write_text('\n\n'.join(o['sql']+';' for o in definitions)+'\n')
 report.update(state='COMPLETE',database=final.name,database_bytes=final.stat().st_size,checks=checks,derivative_catalog_rows_relabelled=relabelled,binary_payloads_modified=False,original_source_unmodified=True,database_sha256_status='NOT_CALCULATED')
 save()
 # Record residual terms in source text without rewriting the evidence.
 c=sqlite3.connect(final.as_uri()+'?mode=ro',uri=True);residual=[]
 for n in names:
  if n.startswith('review_'):continue
  cols=[r[1] for r in c.execute('PRAGMA table_info('+quote(n)+')') if 'TEXT' in r[2].upper()]
  for col in cols:
   for term in forbidden:
    k=c.execute('SELECT COUNT(*) FROM '+quote(n)+' WHERE instr(lower('+quote(col)+'),?)>0',(term.lower(),)).fetchone()[0]
    if k:residual.append({'table':n,'column':clean(col),'term_class':forbidden.index(term)+1,'rows':k,'policy':'ORIGINAL_EVIDENCE_TEXT_RETAINED'})
 (dest/'SOURCE_TEXT_EXCEPTIONS.json').write_text(json.dumps(residual,indent=2));c.close()
if __name__=='__main__':main()
