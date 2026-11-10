import pathlib,json,base64,hashlib,sqlite3,ast,zlib,re,csv,io,zipfile,xml.etree.ElementTree as ET,os
R=pathlib.Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
groups={};attempts=[]
for p in sorted(R.glob('*.json')):
 try:x=json.loads(p.read_text())
 except ValueError:continue
 if 'path' not in x or 'result' not in x:continue
 result=x['result'];v=result.get('structuredContent',{})
 if 'base64' not in v:
  attempts.append({'path':x['path'],'observation':p.name,'status':'READ_FAILED','error':result.get('content')});continue
 b=base64.b64decode(v['base64']);assert len(b)==v['chunk_bytes'] and sha(b)==v['chunk_sha256']
 g=groups.setdefault(x['path'],{'size':v['total_bytes'],'chunks':{}});assert g['size']==v['total_bytes'];g['chunks'][v['offset']]=b
 attempts.append({'path':x['path'],'observation':p.name,'status':'CHUNK_HASH_VERIFIED','offset':v['offset'],'sha256':sha(b)})
artifacts=[]
for path,g in groups.items():
 data=b'';at=0
 for offset,b in sorted(g['chunks'].items()):
  if offset!=at:break
  data+=b;at+=len(b)
 if len(data)!=g['size']:raise RuntimeError('Incomplete source: '+path)
 artifacts.append({'source_path':'/home-mscluster/astrauss/research_artifacts/'+path,'sha256':sha(data),'bytes':len(data),'data':data,'type':'original_cluster_file'})
if not artifacts:
 journal_path=R/'source_journal.json'
 if not journal_path.exists():journal_path=R.parent.parent.parent/'arno-cluster-db-20261025-v1'/'source_journal.json'
 prior=json.loads(journal_path.read_text())
 for a in prior['source_artifacts']:
  p=pathlib.Path(a['source_path']);p.relative_to('/home-mscluster/astrauss/research_artifacts')
  b=p.read_bytes();assert sha(b)==a['sha256'] and len(b)==a['bytes']
  artifacts.append({**a,'data':b,'type':'original_cluster_file'})
out=R/'arno_cluster_evidence_20261025_v1.sqlite'
if out.exists():raise SystemExit('Refusing overwrite')
c=sqlite3.connect(out);c.execute('pragma foreign_keys=ON');c.executescript('''
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE objects(sha256 TEXT PRIMARY KEY,byte_size INTEGER,payload BLOB NOT NULL);
CREATE TABLE sources(source_id INTEGER PRIMARY KEY,path TEXT,sha256 TEXT REFERENCES objects,kind TEXT,relation TEXT);
CREATE TABLE cases(case_id TEXT PRIMARY KEY,repository TEXT,issue_number TEXT,pr_number TEXT,root_id TEXT);
CREATE TABLE records(record_id INTEGER PRIMARY KEY,source_sha256 TEXT REFERENCES objects,locator TEXT,record_json TEXT);
CREATE TABLE run_records(run_id TEXT PRIMARY KEY,case_id TEXT REFERENCES cases,source_sha256 TEXT REFERENCES objects,status TEXT,patch_sha256 TEXT REFERENCES objects,base_revision TEXT,record_json TEXT);
CREATE TABLE patches(patch_sha256 TEXT REFERENCES objects,source_sha256 TEXT REFERENCES objects,locator TEXT,case_id TEXT REFERENCES cases,rank TEXT,role TEXT,PRIMARY KEY(patch_sha256,source_sha256,locator));
CREATE TABLE run_artifacts(run_id TEXT REFERENCES run_records,role TEXT,object_sha256 TEXT REFERENCES objects,relation_basis TEXT,PRIMARY KEY(run_id,role));
CREATE TABLE scanner_reports(object_sha256 TEXT REFERENCES objects,run_id TEXT REFERENCES run_records,role TEXT,tool_name TEXT,tool_version TEXT,result_count INTEGER,PRIMARY KEY(object_sha256,run_id,role));
CREATE TABLE warnings(report_sha256 TEXT REFERENCES objects,run_index INTEGER,result_index INTEGER,rule_id TEXT,message TEXT,locations_json TEXT,fingerprints_json TEXT,original_result_json TEXT,PRIMARY KEY(report_sha256,run_index,result_index));
CREATE TABLE spreadsheet_cells(workbook_sha256 TEXT REFERENCES objects,sheet TEXT,cell TEXT,value_json TEXT,formula TEXT,xml TEXT,PRIMARY KEY(workbook_sha256,sheet,cell));
CREATE TABLE source_retrieval_attempts(attempt_id INTEGER PRIMARY KEY,details_json TEXT);
CREATE TABLE gaps(category TEXT,detail TEXT);
''')
for k,v in {'version':'cluster-original increment v1','previous_recovery_status':'Previous generated recovery/increment/audit databases unavailable; not replaced or represented as recovered here','experiments_executed':'NONE','full_project_complete':'FALSE'}.items():c.execute('insert into metadata values(?,?)',(k,v))
def obj(b):
 h=sha(b);c.execute('insert or ignore into objects values(?,?,?)',(h,len(b),b));return h
for a in artifacts:obj(a['data']);c.execute('insert into sources(path,sha256,kind,relation) values(?,?,?,?)',(a['source_path'],a['sha256'],a['type'],'Original bytes assembled from contiguous individually SHA-256 verified V6 chunks'))
identity=next(a for a in artifacts if a['source_path'].endswith('PREAUDIT_24_RESEARCHER.csv'))
mapping={}
for i,row in enumerate(csv.DictReader(io.StringIO(identity['data'].decode('utf-8-sig'))),2):
 c.execute('insert into records(source_sha256,locator,record_json) values(?,?,?)',(identity['sha256'],'CSV row '+str(i),json.dumps(row,ensure_ascii=False)))
 rank=row.get('queue_rank');root=row.get('root_id','');m=re.fullmatch(r'CROOT-(\d+)-\d+',root)
 if m:
  cid=str(int(m[1]));repo=row.get('repository');c.execute('insert or ignore into cases values(?,?,?,?,?)',(cid,repo,row.get('issue_number'),row.get('pr_number'),root));mapping[str(rank)]=cid
script=next(a for a in artifacts if a['source_path'].endswith('pilot3_evaluate_3patches_20261017_v2_nodefix.sbatch'))
embedded={}
for line in script['data'].decode().splitlines():
 if line.startswith('PATCHES='):
  for rank,encoded in ast.literal_eval(line.partition('=')[2]).items():
   b=zlib.decompress(base64.b64decode(encoded));h=obj(b);embedded[h]=str(rank)
   c.execute('insert into patches values(?,?,?,?,?,?)',(h,script['sha256'],'PATCHES['+str(rank)+']',mapping.get(str(rank)) if str(rank)=='8' else None,str(rank),'Original embedded patch; extracted as literal data; historical script not executed; case association outside rank 8 unverified'))
for a in artifacts:
 if a['source_path'].endswith('.patch'):
  c.execute('insert into patches values(?,?,?,?,?,?)',(a['sha256'],a['sha256'],'whole file',mapping.get('8'),'8','Original saved intervention patch; execution linkage not inferred'))
for a in artifacts:
 if not a['source_path'].endswith('/RESULT.json'):continue
 d=json.loads(a['data']);cid=mapping.get(str(d.get('rank')));ph=d.get('patch_sha256')
 if ph and c.execute('select 1 from objects where sha256=?',(ph,)).fetchone() is None:ph=None
 run=a['source_path'].rsplit('/RESULT.json',1)[0]
 c.execute('insert into run_records values(?,?,?,?,?,?,?)',(run,cid,a['sha256'],d.get('status'),ph,d.get('base_sha'),json.dumps(d,ensure_ascii=False)))
 c.execute('insert into run_artifacts values(?,?,?,?)',(run,'execution_record',a['sha256'],'Exact original RESULT.json'))
 for report in artifacts:
  if not report['source_path'].startswith(run+'/') or not report['source_path'].endswith('.sarif'):continue
  role='before' if report['source_path'].endswith('/base.sarif') else 'after';raw=json.loads(report['data']);total=0
  for ri,r in enumerate(raw.get('runs',[])):
   for ii,item in enumerate(r.get('results',[])):
    total+=1;c.execute('insert into warnings values(?,?,?,?,?,?,?,?)',(report['sha256'],ri,ii,item.get('ruleId'),item.get('message',{}).get('text'),json.dumps(item.get('locations',[])),json.dumps(item.get('partialFingerprints',{})),json.dumps(item,ensure_ascii=False)))
  driver=raw['runs'][0]['tool']['driver'];c.execute('insert into scanner_reports values(?,?,?,?,?,?)',(report['sha256'],run,role,driver.get('name'),driver.get('semanticVersion') or driver.get('version'),total));c.execute('insert into run_artifacts values(?,?,?,?)',(run,role,report['sha256'],'Original same-execution-directory output named by preserved scanner script'))
  expected=d.get('base_alerts' if role=='before' else 'patched_alerts');assert expected==total,(role,expected,total)
 for sh,rank in embedded.items():
  if sh==d.get('patch_sha256'):c.execute('insert into run_artifacts values(?,?,?,?)',(run,'patch',sh,'Exact RESULT.json patch_sha256 equals safely extracted original embedded patch bytes'))
book=R.parent/'project_sources/20-issue_pr_manual_evaluation_master_122-1-.xlsx'
if book.exists():
 b=book.read_bytes();h=obj(b);c.execute('insert into sources(path,sha256,kind,relation) values(?,?,?,?)',('project attachment: issue_pr_manual_evaluation_master_122(1).xlsx',h,'original_workbook','Raw workbook and cell XML preserved; human authorship/completion not inferred'))
 ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  strings=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
  wb=ET.fromstring(z.read('xl/workbook.xml'));rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'));targets={x.attrib['Id']:x.attrib['Target'] for x in rels}
  for sheet in wb.find('m:sheets',ns):
   target=targets[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']];target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
   for cell in ET.fromstring(z.read(target)).findall('.//m:c',ns):
    value=cell.find('m:v',ns);value=value.text if value is not None else None
    if cell.attrib.get('t')=='s' and value is not None:value=strings[int(value)]
    if cell.attrib.get('t')=='inlineStr':
     inline=cell.find('m:is',ns);value=''.join(inline.itertext()) if inline is not None else None
    f=cell.find('m:f',ns);c.execute('insert into spreadsheet_cells values(?,?,?,?,?,?)',(h,sheet.attrib['name'],cell.attrib['r'],json.dumps(value,ensure_ascii=False),f.text if f is not None else None,ET.tostring(cell,encoding='unicode')))
for a in attempts:c.execute('insert into source_retrieval_attempts(details_json) values(?)',(json.dumps(a),))
for cat,detail in [('complete_history','This is a new source-backed increment, not the lost 1699-source recovery or a complete project database.'),('old_patch_variants','The two earlier patch hashes c11d9b40... and a9817c6b... are not equated with scanned patch 0e013e16... .'),('conversations','No native ChatGPT conversations recovered in this increment.'),('Wits_database_binary','V6 cannot create/upload SQLite binaries. Original sources and the reconstruction journal are retained on Wits; this SQLite is delivered separately.'),('functional_acceptance','Completed scan records functionality NOT_TESTED. No task correctness inferred.'),('v5_and_frozen_miner','Not integrated; inaccessible source bytes not recreated.')]:c.execute('insert into gaps values(?,?)',(cat,detail))
c.commit();assert c.execute('pragma integrity_check').fetchone()[0]=='ok';assert c.execute('pragma foreign_key_check').fetchall()==[]
for h,n,b in c.execute('select * from objects'):assert len(b)==n and sha(b)==h
summary={'database':out.name,'sha256':sha(out.read_bytes()),'source_artifacts':[{'source_path':a['source_path'],'sha256':a['sha256'],'bytes':a['bytes']} for a in artifacts],'case_mapping':mapping,'run_records':[dict(zip(['run_id','case_id','status','patch_sha256'],row)) for row in c.execute('select run_id,case_id,status,patch_sha256 from run_records')],'reports':[dict(zip(['sha256','role','warnings'],row)) for row in c.execute('select object_sha256,role,result_count from scanner_reports')],'rows':{t:c.execute('select count(*) from '+t).fetchone()[0] for t in ['objects','records','patches','warnings','spreadsheet_cells']},'integrity_check':'ok','foreign_key_violations':0,'full_project_complete':False}
(R/'source_journal.json').write_text(json.dumps(summary,indent=2)+'\n');(R/(out.name+'.sha256')).write_text(summary['sha256']+'  '+out.name+'\n');print(json.dumps(summary,indent=2));c.close()
