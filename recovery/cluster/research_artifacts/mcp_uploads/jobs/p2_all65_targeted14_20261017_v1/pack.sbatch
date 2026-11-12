#!/bin/bash
#SBATCH --job-name=all65_targeted14
#SBATCH --partition=batch
#SBATCH --array=0-13%4
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:40:00
export PYTHONUNBUFFERED=1
python3 - <<'PY'
from pathlib import Path,PurePosixPath
from urllib.parse import quote
import os,json,urllib.request,time,zipfile,tarfile,tempfile,hashlib,collections,shutil
home=Path.home()
root=home/'research_artifacts/prevention_pilot_phase2'
data=json.loads((root/'remaining65_metadata_job70235/PRIVATE_CASE_METADATA_65.json').read_text())
ids=[28354,16776,17660,608,21682,12344,3429,17428,31207,6145,6150,5267,7682,5264]
cid=ids[int(os.environ['SLURM_ARRAY_TASK_ID'])]
rows=[r for r in data if r['case_id']==cid]
assert len(rows)==1
m=rows[0]
out=root/'remaining65_targeted14_v1'
out.mkdir(exist_ok=True)
statusfile=out/('CASE_%05d_STATUS.json'%cid)
result={'case':cid,'repository':m['repository'],'pr_base_sha':m['pr_base_sha'],
        'queue_rank':m['queue_rank'],'issue_number':m['issue_number'],
        'issue_before_pr':m['issue_before_pr'],'chronology_issue':m['issue_before_pr'] is not True,
        'historical_body_fidelity_established':m['prepr_issue_text_temporally_supported'],
        'packet_type':'SOURCE_TEXT_SLICE_NOT_FULL_REPOSITORY',
        'status':'STARTED','excluded_categories':'Binary assets, media, generated datasets, very large single files, repository .git folders'}
def save():statusfile.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
save()
selected_ext={
 '.ts','.tsx','.js','.jsx','.mjs','.cjs','.json','.jsonc','.yaml','.yml','.toml','.py','.sh','.bash','.zsh','.css','.scss','.less',
 '.md','.mdx','.html','.htm','.vue','.svelte','.go','.rs','.java','.kt','.c','.cc','.cpp','.h','.hpp','.php','.swift','.sql',
 '.xml','.graphql','.gql','.prisma','.proto','.txt','.ini','.cfg','.properties','.test','.mts','.cts','.gitignore','.npmrc','.nvmrc',
 '.gradle','.bat','.ps1','.lock','.jsonl','.conf','.config','.env.example','.dockerignore','.editorconfig','.eslintrc'}
additional_names={'Dockerfile','Makefile','LICENSE','NOTICE','README','BUILD','WORKSPACE','tsconfig.json','package-lock.json','pnpm-lock.yaml',
  'yarn.lock','bun.lock','bun.lockb','Cargo.lock','go.sum','.gitignore','.npmrc','.env.example','vite.config.ts','webpack.config.js'}
ignored_dirs={'node_modules','.git','.next','.nuxt','.turbo','.cache','dist','build','coverage','target','.venv','venv','vendor',
 'site-packages','__pycache__','storybook-static','.output','tmp','temp','logs','data-dump','datasets'}
ignored_ext={'.png','.jpg','.jpeg','.gif','.webp','.bmp','.ico','.svgz','.mp4','.mov','.webm','.mkv','.wav','.mp3','.flac',
 '.pdf','.psd','.ai','.zip','.tar','.gz','.7z','.rar','.db','.sqlite','.sqlite3','.bin','.exe','.dll','.so','.dylib','.a','.o','.woff',
 '.woff2','.ttf','.otf','.eot','.parquet','.arrow','.pkl','.pickle','.pt','.pth','.ckpt','.onnx','.safetensors','.npy','.npz',
 '.jpg','.tif','.tiff','.svg','.wasm','.jar','.class','.lockb','.map'}
try:
 repo=m['repository'];sha=m['pr_base_sha']
 assert repo.count('/')==1 and len(sha)>12
 directory=Path(tempfile.mkdtemp(prefix='case65_extra_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 archive=directory/'source.tar.gz'
 url='https://codeload.github.com/'+quote(repo,safe='/')+'/tar.gz/'+quote(sha,safe='')
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Wits-Research-PrePR-Snapshot/1.0'})
   with urllib.request.urlopen(req,timeout=180) as res,archive.open('wb') as stream:
    size=0
    while True:
     chunk=res.read(1<<20)
     if not chunk:break
     size+=len(chunk)
     if size>650*(1<<20):raise ValueError('GZIP_EXCEEDS_650MB')
     stream.write(chunk)
   break
  except BaseException:
   archive.unlink(missing_ok=True)
   if attempt==2:raise
   time.sleep((attempt+1)*6)
 result['source_archive_compressed_bytes']=archive.stat().st_size
 issue=(m['issue_title'].strip()+'\n\n'+(m['issue_body'] or '').strip()+'\n').encode('utf8')
 assert 10<len(issue)<300000
 ziptemp=directory/'textslice.zip'
 scanned=0;kept=0;skip_binary=0;skip_size=0;skip_path=0;total_uncompressed=0;has_target=False
 target=str(m.get('changed_file') or '').strip().lstrip('/')
 with tarfile.open(archive,'r:gz') as tar,zipfile.ZipFile(ziptemp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4,allowZip64=True) as zipped:
  zipped.writestr('ISSUE.md',issue)
  for member in tar:
   if not member.isfile():continue
   rel=PurePosixPath(*PurePosixPath(member.name).parts[1:])
   if rel.is_absolute() or '..' in rel.parts:raise ValueError('UNSAFE_PATH')
   p=str(rel)
   if not p:continue
   scanned+=1
   if target and (p==target or p.endswith('/'+target)): has_target=True
   components=set(rel.parts)
   extension=Path(rel.name).suffix.lower()
   keep=rel.name in additional_names or extension in selected_ext or any(rel.name.endswith(z) for z in ['.config.js','.config.ts','.test.js','.test.ts','.spec.ts','.spec.js'])
   if ignored_dirs.intersection(components) or extension in ignored_ext or not keep:
    skip_binary+=1;continue
   if member.size>6*(1<<20):
    skip_size+=1;continue
   if kept>=15500 or total_uncompressed+member.size>210*(1<<20):
    skip_size+=1;continue
   if 'REPO/'+p not in zipped.namelist():
    stream=tar.extractfile(member)
    if not stream:skip_path+=1;continue
    data=stream.read()
    if b'\x00' in data[:8000]:skip_binary+=1;continue
    zipped.writestr('REPO/'+p,data)
    kept+=1;total_uncompressed+=len(data)
  info={
   'case':cid,'repository':repo,'base_sha':sha,'issue_number':m['issue_number'],'pr_number':m['pr_number'],
   'issue_created_after_pr':m['issue_before_pr'] is False,'temporally_verified_issue_body':m['prepr_issue_text_temporally_supported'],
   'source_kind':'FILTERED_SOURCE_SLICE_FOR_DISCOVERY','omitted_binary_or_unsupported_files':skip_binary,
   'omitted_large_files':skip_size,'kept_files':kept,'historical_changed_path':target,'historical_changed_path_present_in_archive':has_target,
   'warning':'CodeQL and functional checks must later use the original complete frozen repository, NOT this source slice.'
  }
  zipped.writestr('SOURCE_SLICE_NOTICE.json',json.dumps(info,indent=2)+'\n')
 if kept<5:raise ValueError('INSUFFICIENT_TEXT_FILES_'+str(kept))
 if ziptemp.stat().st_size>150*(1<<20):raise ValueError('SOURCE_SLICE_OVER_150MB')
 with zipfile.ZipFile(ziptemp) as verify:assert verify.testzip() is None
 targetzip=out/('CASE_%05d.zip'%cid)
 assert not targetzip.exists()
 shutil.copyfile(ziptemp,targetzip)
 result.update({'status':'READY','archive_name':targetzip.name,'archive_bytes':targetzip.stat().st_size,
  'archive_sha256':hashlib.sha256(targetzip.read_bytes()).hexdigest(),
  'scanned_files':scanned,'kept_files':kept,'skipped_unsupported':skip_binary,
  'skipped_oversized':skip_size,'retained_uncompressed_bytes':total_uncompressed,
  'historical_changed_path':target,'target_path_encountered':has_target})
except BaseException as e:
 result.update({'status':'FAILED','error':str(e)[:400]})
save()
print(cid,result['status'],result.get('kept_files'),result.get('archive_bytes'),result.get('error',''),flush=True)
PY
