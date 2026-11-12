import csv,zipfile,hashlib,json,re,collections,pathlib,os
ROOT=pathlib.Path('/mnt/data')
z=zipfile.ZipFile(ROOT/'ARNO_RESEARCH_INTELLECTUAL_HISTORY_v1_0.zip')
prefix='ARNO_RESEARCH_INTELLECTUAL_HISTORY_v1_0/'
reads=lambda n: z.read(prefix+n)
lines=lambda n: reads(n).decode('utf-8-sig').splitlines()
main=list(csv.DictReader((ROOT/'ARNO_RESEARCH_IDEAS_AND_FINDINGS_HISTORY_v1_0.csv').open(encoding='utf-8-sig',newline='')))
reg=list(csv.DictReader((ROOT/'ARNO_HISTORY_SOURCE_REGISTER_v1_0.csv').open(encoding='utf-8-sig',newline='')))
links=list(csv.DictReader((ROOT/'ARNO_IDEA_EVOLUTION_LINKS_v1_0.csv').open(encoding='utf-8-sig',newline='')))
byid={x['source_id']:x for x in reg}
mid={x['record_id']:x for x in main}
qa={'main_entries':len(main),'source_records':len(reg),'links':len(links),'file_missing':[],'source_sha_mismatch':[],'record_source_sha_mismatch':[],'source_locator_mismatch':[],'excerpt_outside_window':[],'window_invalid':[],'linked_missing':[],'link_key_mismatch':[],'missing_columns':[],'duplicate_record_id':[],'duplicate_record_key':[],'empty_statement':[],'other_warnings':[]}

for r in reg:
 arc=r['archive_path']
 try: dat=reads(arc)
 except KeyError:qa['file_missing'].append(r['source_id']);continue
 sha=hashlib.sha256(dat).hexdigest()
 if sha!=r['text_sha256']:qa['source_sha_mismatch'].append(r['source_id'])

for r in main:
 rid,sid=r['record_id'],r['source_id']
 if sid not in byid:qa['source_locator_mismatch'].append((rid,'source id nonexistent'));continue
 if byid[sid]['text_sha256']!=r['source_sha256']:qa['record_source_sha_mismatch'].append(rid)
 arc=byid[sid]['archive_path']
 expect=arc+'#L'+r['source_line_start']+'-L'+r['source_line_end']
 if r['source_locator']!=expect:qa['source_locator_mismatch'].append((rid,r['source_locator'],expect))
 try:lo=int(r['source_line_start']);hi=int(r['source_line_end'])
 except ValueError:qa['window_invalid'].append((rid,'invalid integer'));continue
 allines=lines(arc)
 if lo<1 or hi>len(allines) or lo>hi:qa['window_invalid'].append((rid,lo,hi,len(allines)));continue
 src='\n'.join(allines[lo-1:hi]);ex=r['original_excerpt'].lstrip("'")
 if ex.endswith('...'):ex=ex[:-3]
 if ex and ex not in src:
  # tolerate newlines, whitespace normalized
  norm=lambda s:' '.join(s.split())
  if norm(ex) not in norm(src):qa['excerpt_outside_window'].append((rid,ex[:80],src[:80]))

for link in links:
 for side in ['from','to']:
  id=link[side+'_record_id'];key=link[side+'_key']
  if id not in mid:qa['linked_missing'].append((link['link_id'],side,id))
  elif mid[id]['record_key']!=key:qa['link_key_mismatch'].append((link['link_id'],side,key,mid[id]['record_key']))

for k in ['record_id','record_key']:
 cnt=collections.Counter(x[k] for x in main)
 qa['duplicate_'+k]=[x for x,v in cnt.items() if v>1]
qa['empty_statement']=[x['record_id'] for x in main if not x['statement'].strip()]
manifest=json.loads(reads('MANIFEST.json'))
qa['manifest_files_total']=len(manifest['files'])
qa['manifest_file_verification']={
 'bytes_match':sum((len(reads(x['path']))==x['bytes']) for x in manifest['files']),
 'sha256_match':sum(hashlib.sha256(reads(x['path'])).hexdigest()==x['sha256'] for x in manifest['files'])}
qa['main_zip_copy_match']=reads('ARNO_RESEARCH_IDEAS_AND_FINDINGS_HISTORY_v1_0.csv') == (ROOT/'ARNO_RESEARCH_IDEAS_AND_FINDINGS_HISTORY_v1_0.csv').read_bytes()
qa['links_zip_copy_match']=reads('ARNO_IDEA_EVOLUTION_LINKS_v1_0.csv') == (ROOT/'ARNO_IDEA_EVOLUTION_LINKS_v1_0.csv').read_bytes()
qa['sources_duplicate_sha']={k:v for k,v in collections.defaultdict(list,((s['text_sha256'],[x['source_id'] for x in reg if x['text_sha256']==s['text_sha256']]) for s in reg)).items() if len(v)>1}
qa['source_span_coverage']={'distinct_sources_referenced':len({x['source_id'] for x in main}),'distinct_source_kinds_referenced':len({x['source_kind'] for x in main})}
out=ROOT/'ARNO_HISTORY_INDEPENDENT_VERIFICATION_20261022.json';out.write_text(json.dumps(qa,indent=2,ensure_ascii=False),encoding='utf-8')
for k,v in qa.items():
 print(k, ((len(v),str(v[:5])) if isinstance(v,list) else v))
