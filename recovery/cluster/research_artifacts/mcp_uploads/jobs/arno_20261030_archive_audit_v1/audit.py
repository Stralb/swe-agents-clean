#!/usr/bin/env python3
import hashlib,sqlite3,zipfile,json,csv,re,collections
from pathlib import Path
from datetime import datetime,timezone
R=Path.home()/'research_artifacts'
DB=R/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
O=R/'mcp_uploads/jobs/arno_20261030_archive_audit_v1'
TABLES=[('arno_sources','source_sha256'),('arno_codeql_oct19_original_archive_inventory','sha256'),('arno_evidence_assets','source_sha256'),('arno_exp_transfer_files','source_sha256'),('arno_recovered_agent_patch_bytes','patch_sha256'),('arno_generated_patches','content_sha256'),('arno_rq3_owp14_original_artifacts','source_sha256'),('arno_rq3_owp14_run_scans','result_sha256'),('arno_seven_final_repair_archive','original_sha256'),('arno_seven_final_repair_case_evidence','final_patch_sha256'),('arno_seven_final_repair_case_evidence','final_result_sha256'),('arno_seven_final_repair_case_evidence','final_after_sarif_sha256'),('arno_owp14_original_input_packet_inventory_20261029','sha256'),('arno_screen65_before_sarif_candidates_20261029','sha256')]
def sha(f):
 h=hashlib.sha256();n=0
 for buf in iter(lambda:f.read(4*1024*1024),b''):
  h.update(buf);n+=len(buf)
 return h.hexdigest(),n
def role(p):
 p=p.lower()
 if p.endswith('.sarif'):return 'SARIF'
 if p.endswith(('.patch','.diff')):return 'PATCH'
 if p.endswith(('.zip','.gz','.tar')):return 'ARCHIVE'
 if 'prompt' in p or 'trace' in p:return 'PROMPT_TRACE'
 if p.endswith('.log'):return 'LOG'
 if p.endswith(('.json','.jsonl')):return 'JSON'
 if p.endswith(('.py','.sh','.sbatch','.js','.ts','.yml','.yaml')):return 'CODE'
 if p.endswith(('.md','.txt')):return 'TEXT'
 if p.endswith('.csv'):return 'CSV'
 return 'OTHER'
def main():
 c=sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True,timeout=120);c.execute('PRAGMA query_only=ON')
 archives=c.execute('SELECT file_name,original_bytes,sha256 FROM arno_codeql_oct19_original_archive_inventory ORDER BY file_name').fetchall()
 if len(archives)!=10:raise ValueError('Archive census not 10')
 ix=collections.defaultdict(list)
 for table,col in TABLES:
  for (v,) in c.execute('SELECT '+col+' FROM '+table+' WHERE '+col+' IS NOT NULL'):
   if v:ix[str(v).lower()].append(table)
 c.close()
 rows=[];archive_counts=[]
 for name,size,digest in archives:
  p=R/'ARNO_CODEQL_EXPORT_20261019'/name
  if not p.exists() or p.stat().st_size!=size:raise ValueError('Missing '+name)
  with p.open('rb') as f:h,n=sha(f)
  if h!=digest:raise ValueError('Archive digest mismatch '+name)
  count=0;matched=0
  with zipfile.ZipFile(p) as z:
   for info in z.infolist():
    if info.is_dir():continue
    with z.open(info) as f:h,n=sha(f)
    if n!=info.file_size:raise ValueError('Member corrupt '+info.filename)
    match=sorted(set(ix.get(h,())))
    m=re.search(r'CASE_(\d{5})(?:\D|$)',info.filename,re.I)
    rows.append((name,info.filename,m.group(1) if m else '',role(info.filename),h,n,info.compress_size,int(bool(match)),';'.join(match)))
    count+=1;matched+=bool(match)
  archive_counts.append({'archive':name,'members':count,'sha_registered':matched})
  print('ARCHIVE_OK',name,'members',count,'matched',matched,flush=True)
 O.mkdir(parents=True,exist_ok=True)
 fields=['archive','member','case_id','role','sha256','size','compressed_size','digest_registered','matched_tables']
 with (O/'ALL_MEMBERS.csv').open('x',newline='') as f:
  w=csv.writer(f);w.writerow(fields);w.writerows(rows)
 gaps=[r for r in rows if r[7]==0 and r[3]!='OTHER']
 with (O/'UNREGISTERED_SCIENTIFIC_MEMBERS.csv').open('x',newline='') as f:
  w=csv.writer(f);w.writerow(fields);w.writerows(gaps)
 report={'status':'READ_ONLY_ARCHIVE_SHA_REGISTRY_AUDIT','utc':datetime.now(timezone.utc).isoformat(),
 'archives':archive_counts,'members':len(rows),'unique_sha256':len(set(r[4] for r in rows)),
 'registered_rows':sum(r[7] for r in rows),'unregistered_scientific_rows':len(gaps),
 'unregistered_roles':dict(collections.Counter(r[3] for r in gaps)),
 'limit':'SHA missing from indexed registry does NOT prove raw bytes missing from all SQLite blobs. Combined handoff ZIP duplicates archival content. No writes to sources or live master.'}
 with (O/'REPORT.json').open('x') as f:json.dump(report,f,indent=2)
 print(json.dumps(report),flush=True)
if __name__=='__main__':main()
