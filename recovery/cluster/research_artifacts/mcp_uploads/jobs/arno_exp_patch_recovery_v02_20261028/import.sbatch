#!/bin/bash
#SBATCH --job-name=arno_exp_patches_v02
#SBATCH --partition=stampede
#SBATCH --time=00:14:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
python3 - <<'PY'
from pathlib import Path
import re,io,tarfile,base64,lzma,zlib,csv,hashlib,sqlite3,json,collections,datetime
root=Path.home()/'research_artifacts'
db=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=root/'mcp_uploads/jobs/arno_exp_patch_recovery_v02_20261028'
out.mkdir(parents=True,exist_ok=True)
dirs={
 'screen65_O_iter3':root/'mcp_uploads/screen65_iter3_20261019_transfer_v1',
 'seven_case_P1':root/'mcp_uploads/seven_case_20261020',
 'seven_case_issues':root/'mcp_uploads/seven_minimal_info_intake_20261020',
 'phase2_ten':root/'mcp_uploads/phase2_ten_20261017',
 'issue_ablation_O_P_2rep':root/'mcp_uploads/issue_ablation_O_rep1rep2_20261019',
 'owp14_case668':root/'mcp_uploads/owp14_20261018_v1'
}
report={'status':'STARTED','scope':'Historical upload/patch source artifacts. Raw evidence recovery only, no scanner or test outcomes inferred.'}
try:
 filebytes={}
 filegroups={}
 for group,d in dirs.items():
  files=sorted(x for x in d.iterdir() if x.is_file())
  if not files:raise ValueError('Source empty: '+group)
  for p in files:
   rel=str(p.relative_to(root))
   filebytes[rel]=p.read_bytes()
   filegroups[rel]=group
 expected_sizes={'screen65_O_iter3':47,'seven_case_P1':7,'seven_case_issues':8,'phase2_ten':13,'issue_ablation_O_P_2rep':22,'owp14_case668':5}
 groupcounts=collections.Counter(filegroups.values())
 if groupcounts!=expected_sizes:raise ValueError('Source file-count mismatch '+str(groupcounts))
 screen_parts=[p for p in sorted((root/'mcp_uploads/screen65_iter3_20261019_transfer_v1').glob('chunk_*.txt'))]
 if [int(x.stem.split('_')[1]) for x in screen_parts]!=list(range(1,48)):raise ValueError('Screen65 chunk order/gap')
 original_transport=b''.join(p.read_bytes().strip() for p in screen_parts)
 archive=lzma.decompress(base64.b64decode(original_transport,validate=True))
 if hashlib.sha256(archive).hexdigest()!='18c5d4d7f2c69ca860e1f5e7c6408c8a4d24af40047d5311072cfb2a425e1eae':
  raise ValueError('Screen65 assembled tar digest mismatch')
 tarfiles={}
 with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as tf:
  for m in tf.getmembers():
   if m.isfile():
    if m.name in tarfiles:raise ValueError('Duplicate tar member')
    tarfiles[m.name]=tf.extractfile(m).read()
 screenpatches={name:b for name,b in tarfiles.items() if re.fullmatch(r'O_CASE_[0-9]+\.patch',name)}
 if len(screenpatches)!=65 or set(tarfiles)-set(screenpatches)!={'RESULTS_INDEX.csv'}:
  raise ValueError('Screen65 expected 65 patches and one index')
 index=list(csv.DictReader(io.StringIO(tarfiles['RESULTS_INDEX.csv'].decode('utf-8-sig'))))
 if len(index)!=65:raise ValueError('Expected 65 original index rows')
 if {x['filename'] for x in index}!=set(screenpatches):raise ValueError('Screen65 index filenames differ from archived files')
 patches=[]
 def add(key,case,cond,rep,kind,source_paths,data):
  if not isinstance(case,int) or case<1 or not data:raise ValueError('Invalid patch '+key)
  patches.append({'key':key,'case':case,'condition':cond,'rep':rep,'kind':kind,'sources':source_paths,'bytes':data,
                  'git_diff_header':int(data.startswith(b'diff --git ')),
                  'has_diff_marker':int(b'diff --git ' in data[:500])})
 for name,b in screenpatches.items():
  case=int(re.search(r'CASE_([0-9]+)\.patch',name).group(1))
  add('SCREEN65_ITER3:'+name,case,'O','iter3','tar_patch_from_base64_xz_screen65',
      [str(p.relative_to(root)) for p in screen_parts],b)
 for path,data in filebytes.items():
  if filegroups[path]=='seven_case_P1':
   p=Path(path)
   m=re.fullmatch(r'CASE_([0-9]+)_P1\.zlib\.base64\.txt',p.name)
   if not m:raise ValueError('Unexpected seven-case archive filename '+p.name)
   decoded=zlib.decompress(base64.b64decode(data.strip(),validate=True))
   add('SEVEN_CASE_P1:'+p.name,int(m.group(1)),'P','P1','zlib_base64_patch',[path],decoded)
 def add_groups(group,extract):
  gr=collections.defaultdict(list)
  for path,data in filebytes.items():
   if filegroups[path]!=group:continue
   filename=Path(path).name
   base,part,case,cond,rep=extract(filename)
   gr[base].append((part,path,data,case,cond,rep))
  for base,lst in sorted(gr.items()):
   lst.sort(key=lambda x:x[0])
   ns=[x[0] for x in lst]
   if len(ns)!=len(set(ns)) or ns!=list(range(ns[0],ns[0]+len(ns))) or ns[0] not in (0,1):
    raise ValueError('Missing/repeated fragments '+group+' '+base+': '+str(ns))
   if len({(x[3],x[4],x[5]) for x in lst})!=1:raise ValueError('Group parse mismatch '+base)
   assembled=b''.join(x[2] for x in lst)
   meta=lst[0]
   if b'diff --git ' in assembled[:500]:
    add(group+':'+base,meta[3],meta[4],meta[5],'concatenated_text_parts' if len(lst)>1 else 'direct_text_patch',[x[1] for x in lst],assembled)
   else:
    report.setdefault('non_patch_upload_groups',[]).append({'group':group,'base':base,'parts':len(lst),'source_paths':[x[1] for x in lst]})
 def extract_ablation(s):
  m=re.fullmatch(r'(CASE_([0-9]+)_([OP])_(rep[0-9]+)\.patch)(?:\.part([0-9]+))?\.txt',s)
  if not m:raise ValueError('Invalid ablation filename '+s)
  return (m.group(1),int(m.group(5) or 0),int(m.group(2)),m.group(3),m.group(4))
 def extract_owp(s):
  m=re.fullmatch(r'(USER_CASE_([0-9]+)_([OWP]))(?:_part([0-9]+))?\.txt',s)
  if not m:raise ValueError('Invalid OWP filename '+s)
  return (m.group(1),int(m.group(4) or 0),int(m.group(2)),m.group(3),'initial')
 def extract_phase2(s):
  m=re.fullmatch(r'(([0-9]+)(?:_([OWP][0-9]+))?)(?:_part([0-9]+))?\.txt',s)
  if not m:raise ValueError('Invalid phase2 filename '+s)
  return (m.group(1),int(m.group(4) or 0),int(m.group(2)),m.group(3) or 'UNSPECIFIED','phase2')
 add_groups('issue_ablation_O_P_2rep',extract_ablation)
 add_groups('owp14_case668',extract_owp)
 add_groups('phase2_ten',extract_phase2)
 if len({x['key'] for x in patches})!=len(patches):raise ValueError('Non-unique output patch key')
 bad={x['key'] for x in patches if not x['has_diff_marker']}
 if bad:raise ValueError('Unexpected reconstructed non-git patch: '+str(sorted(bad)[:15]))
 conn=sqlite3.connect(str(db),timeout=90)
 conn.execute('PRAGMA busy_timeout=90000')
 conn.execute('PRAGMA foreign_keys=ON')
 baseline={r[0] for r in conn.execute('SELECT id FROM cases')}
 absent={x['case'] for x in patches}-baseline
 if absent:raise ValueError('Patch case IDs not in mining master '+str(sorted(absent)))
 for r in index:
  cid=int(re.fullmatch(r'(?:CASE_)?([0-9]+)',r['case_id']).group(1))
  patch=int(re.search(r'CASE_([0-9]+)\.patch',r['filename']).group(1))
  if cid!=patch or cid not in baseline:raise ValueError('Screen65 index case mismatch')
 conn.execute('BEGIN IMMEDIATE')
 conn.execute('''CREATE TABLE arno_exp_transfer_files(
    source_path TEXT PRIMARY KEY,
    source_group TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    original_byte_count INTEGER NOT NULL,
    original_zlib BLOB NOT NULL,
    provenance_status TEXT NOT NULL DEFAULT 'ORIGINAL_UPLOAD_VERIFIED'
 )''')
 conn.execute('''CREATE TABLE arno_recovered_agent_patch_bytes(
    patch_key TEXT PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    experimental_condition TEXT NOT NULL,
    replicate_token TEXT NOT NULL,
    origin_kind TEXT NOT NULL,
    original_provenance_json TEXT NOT NULL,
    patch_sha256 TEXT NOT NULL,
    original_byte_count INTEGER NOT NULL,
    patch_zlib BLOB NOT NULL,
    git_unified_diff_header INTEGER NOT NULL CHECK(git_unified_diff_header IN (0,1)),
    patch_execution_status TEXT NOT NULL DEFAULT 'NOT_VERIFIED',
    patch_scanner_status TEXT NOT NULL DEFAULT 'NOT_IMPORTED',
    recovered_at_utc TEXT NOT NULL
 )''')
 conn.execute('''CREATE TABLE arno_patch_fragment_lineage(
    patch_key TEXT NOT NULL REFERENCES arno_recovered_agent_patch_bytes(patch_key),
    source_path TEXT NOT NULL REFERENCES arno_exp_transfer_files(source_path),
    sequence_number INTEGER NOT NULL,
    PRIMARY KEY(patch_key,source_path)
 )''')
 conn.execute('''CREATE TABLE arno_screen65_original_results_index(
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    patch_key TEXT NOT NULL UNIQUE REFERENCES arno_recovered_agent_patch_bytes(patch_key),
    source_status TEXT,source_notes TEXT,source_filename TEXT NOT NULL,
    original_row_json TEXT NOT NULL,
    provenance_scope TEXT NOT NULL DEFAULT 'UNVERIFIED_EXPERIMENT_INDEX_NOT_A_SCANNER_RESULT'
 )''')
 for path,b in filebytes.items():
  conn.execute('INSERT INTO arno_exp_transfer_files VALUES(?,?,?,?,?,?,?)',(
     path,filegroups[path],Path(path).name,hashlib.sha256(b).hexdigest(),
     len(b),zlib.compress(b,9),'ORIGINAL_UPLOAD_VERIFIED'))
 utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
 for p in patches:
  conn.execute('INSERT INTO arno_recovered_agent_patch_bytes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(
   p['key'],p['case'],p['condition'],p['rep'],p['kind'],
   json.dumps({'source_paths':p['sources'],'transformation':p['kind'],'byte_order':'file fragments concatenated by part suffix when applicable'},
              ensure_ascii=False,sort_keys=True),
   hashlib.sha256(p['bytes']).hexdigest(),len(p['bytes']),
   zlib.compress(p['bytes'],9),p['git_diff_header'],
   'NOT_VERIFIED','NOT_IMPORTED',utc))
  for indexseq,path in enumerate(p['sources']):
   conn.execute('INSERT INTO arno_patch_fragment_lineage VALUES(?,?,?)',(p['key'],path,indexseq))
 for row in index:
  k='SCREEN65_ITER3:'+row['filename']
  conn.execute('INSERT INTO arno_screen65_original_results_index VALUES(?,?,?,?,?,?,?)',(
   int(re.fullmatch(r'(?:CASE_)?([0-9]+)',row['case_id']).group(1)),k,row['status'],row['notes'],row['filename'],
   json.dumps(row,ensure_ascii=False,sort_keys=True),
   'UNVERIFIED_EXPERIMENT_INDEX_NOT_A_SCANNER_RESULT'))
 conn.execute("UPDATE arno_stage_ledger SET status='partial',detail=detail||'; imported original October experiment transfer uploads and reconstructed generated patch bytes with SHA/provenance; patch application/scanners NOT VERIFIED',last_updated_utc=? WHERE stage_number=9",(utc,))
 conn.commit()
 report['counts']={
  'raw_transfer_files':conn.execute('SELECT COUNT(*) FROM arno_exp_transfer_files').fetchone()[0],
  'recovered_patch_files':conn.execute('SELECT COUNT(*) FROM arno_recovered_agent_patch_bytes').fetchone()[0],
  'unique_patch_cases':conn.execute('SELECT COUNT(DISTINCT case_id) FROM arno_recovered_agent_patch_bytes').fetchone()[0],
  'patch_fragment_links':conn.execute('SELECT COUNT(*) FROM arno_patch_fragment_lineage').fetchone()[0],
  'screen65_index_rows':conn.execute('SELECT COUNT(*) FROM arno_screen65_original_results_index').fetchone()[0],
  'first122_preserved':conn.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0],
  'matched_controls_preserved':conn.execute('SELECT COUNT(*) FROM arno_matched_control_pairs_C2').fetchone()[0]}
 report['patches_by_origin']=dict(conn.execute('SELECT origin_kind,COUNT(*) FROM arno_recovered_agent_patch_bytes GROUP BY origin_kind'))
 report['patches_by_condition']=dict(conn.execute('SELECT experimental_condition,COUNT(*) FROM arno_recovered_agent_patch_bytes GROUP BY experimental_condition'))
 report['raw_sha_roundtrip']=all(hashlib.sha256(zlib.decompress(b)).hexdigest()==h for b,h in conn.execute('SELECT original_zlib,source_sha256 FROM arno_exp_transfer_files'))
 report['patch_sha_roundtrip']=all(hashlib.sha256(zlib.decompress(b)).hexdigest()==h for b,h in conn.execute('SELECT patch_zlib,patch_sha256 FROM arno_recovered_agent_patch_bytes'))
 report['foreign_key_errors']=sum(len(conn.execute('PRAGMA foreign_key_check('+t+')').fetchall()) for t in ('arno_recovered_agent_patch_bytes','arno_patch_fragment_lineage','arno_screen65_original_results_index'))
 report['screen65_original_tar_sha256']=hashlib.sha256(archive).hexdigest()
 conn.close()
 if report['counts']['raw_transfer_files']!=102 or report['counts']['screen65_index_rows']!=65 or report['counts']['first122_preserved']!=122 or report['counts']['matched_controls_preserved']!=190 or not report['raw_sha_roundtrip'] or not report['patch_sha_roundtrip'] or report['foreign_key_errors']:
  raise ValueError('Post-commit verification failed')
 report['status']='COMPLETE'
except Exception as exc:
 report['status']='FAILED';report['error']=type(exc).__name__+': '+str(exc)
 raise
finally:
 (out/'EXPERIMENT_PATCH_RECOVERY_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
PY