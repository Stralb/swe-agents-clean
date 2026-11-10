#!/bin/bash
#SBATCH --job-name=p2pilot3ctx
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
#SBATCH --time=00:25:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_context_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_context_%j.err

set -euo pipefail
python3 - <<'PY'
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
import time
from urllib.request import Request, urlopen
import zipfile

HOME=Path.home()
ROOT=HOME/'research_artifacts'/'prevention_pilot_phase2'
SOURCE=ROOT/'case_screen_issue_recovery_v1_job69671'/'RESEARCHER_CORPUS_ISSUES_24.json'
OUTPUT=ROOT/'pilot3_context_20261017_v1'
SELECTED=[8,16,18]
ROOT_IDS={8:'CROOT-21942-01',16:'CROOT-00313-01',18:'CROOT-03582-01'}
SEED_SHA256='037f98a0bf66a6e3906ad8af68133011827f5dfa1c07f0e178019c5a55ec5664'

assert SOURCE.is_file(), 'Missing prior recovery job JSON'
assert not OUTPUT.exists(), 'Output directory already exists, refusing to overwrite'
OUTPUT.mkdir(parents=False)
raw=json.loads(SOURCE.read_text(encoding='utf-8'))
records=raw['records']
manifest={'protocol':'Exploratory 3-case baseline screen','frozen_random_seed_sha256':SEED_SHA256,
    'selected_frozen_ranks':SELECTED,'source':str(SOURCE),'cases':[],
    'warning':'Historical target details stay out of generation ZIP. Issue bodies stored after PR edits may carry hindsight.'}
MAX_TOTAL_TEXT_BYTES=55_000_000
MAX_SINGLE_FILE_BYTES=600_000
SKIP_PARTS={'.git','node_modules','.next','dist','build','coverage','vendor','.venv','venv','target',
    '__pycache__','.turbo','.cache','out','generated','__snapshots__'}
BINARY_EXT={'.png','.jpg','.jpeg','.gif','.webp','.ico','.svg','.pdf','.zip','.gz','.tar','.jar',
    '.woff','.woff2','.ttf','.otf','.exe','.dll','.so','.mp4','.mp3','.lockb','.sqlite','.db','.bin','.wasm','.map'}
TEXT_EXT={'.ts','.tsx','.js','.jsx','.mts','.mjs','.cjs','.json','.md','.mdx','.html','.css','.scss',
    '.yaml','.yml','.toml','.ini','.py','.sh','.bash','.zsh','.txt','.xml','.graphql','.gql','.sql',
    '.rs','.go','.java','.kt','.gradle','.vue','.svelte','.astro','.php','.properties','.gitignore'}

def digest(data): return hashlib.sha256(data).hexdigest()
def valid_source(name):
    p=Path(name)
    if any(x in SKIP_PARTS for x in p.parts): return False
    if any(x.startswith('.') and x not in {'.github','.gitignore','.npmrc','.env.example'} for x in p.parts):return False
    if p.suffix.lower() in BINARY_EXT:return False
    return p.suffix.lower() in TEXT_EXT or p.name in {'Dockerfile','Makefile','LICENSE','AGENTS.md','package.json','tsconfig.json','pnpm-workspace.yaml'}
def base_tarball(repo,sha):
    url='https://codeload.github.com/'+repo+'/tar.gz/'+sha
    last_error=None
    for attempt in range(3):
        try:
            req=Request(url,headers={'User-Agent':'Wits-Research-Pilot3-2026','Accept':'application/octet-stream'})
            with urlopen(req,timeout=90) as resp:
                content=resp.read(160_000_001)
            if len(content)>160_000_000:raise RuntimeError('Archive exceeds 160MB download safety limit')
            with tarfile.open(fileobj=io.BytesIO(content),mode='r:gz') as t:
                members=t.getmembers()
                if not members or not members[0].name:raise RuntimeError('Empty source archive')
            return content,url
        except Exception as exc:
            last_error=str(exc)
            print('FETCH_RETRY',repo,attempt+1,last_error,flush=True)
            time.sleep(2*(attempt+1))
    raise RuntimeError('Unable to retrieve frozen repository: '+str(last_error))

def read_source_files(data):
    all_names=[]
    files={}
    total=0
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tf:
        for member in tf:
            if not member.isfile() or member.size>MAX_SINGLE_FILE_BYTES:continue
            parts=Path(member.name).parts
            if len(parts)<2:continue
            rel='/'.join(parts[1:])
            if not valid_source(rel):continue
            stream=tf.extractfile(member)
            if stream is None:continue
            buf=stream.read(MAX_SINGLE_FILE_BYTES+1)
            if len(buf)>MAX_SINGLE_FILE_BYTES or b'\x00' in buf:continue
            try:txt=buf.decode('utf-8')
            except UnicodeDecodeError:continue
            all_names.append(rel)
            if total+len(buf)<=MAX_TOTAL_TEXT_BYTES:
                files[rel]=txt
                total+=len(buf)
    return sorted(all_names),files

def relevant_files(files,query):
    # No PR diffs, warning names, historical changed-file mapping or future artifacts consulted.
    terms=re.findall(r'[a-zA-Z][a-zA-Z0-9_-]{3,}',query.lower())
    stop={'this','that','with','from','when','then','have','into','some','been','does','there','should','would','could','were','your','will','also','just','need','issue','please','while','using','after','before','what','where','which','only','being','same','error'}
    terms=list(dict.fromkeys([t for t in terms if t not in stop]))[:100]
    ranked=[]
    for name,txt in files.items():
        low=name.lower()
        score=sum((12 if t in low else 0) for t in terms)
        excerpt=txt[:22000].lower()
        score+=sum(min(4,excerpt.count(t)) for t in terms)
        if name.endswith(('README.md','AGENTS.md')):score+=8
        if name in {'package.json','pnpm-workspace.yaml'}:score+=8
        ranked.append((score,name))
    ranked.sort(key=lambda x:(-x[0],x[1]))
    return ranked

for rank in SELECTED:
    found=[x for x in records if x.get('queue_rank')==rank and x.get('source_index')==2 and x.get('case_found')]
    assert len(found)==1, ('Expected one case in frozen final snapshot',rank,len(found))
    r=found[0]
    assert r['root_id']==ROOT_IDS[rank]
    assert r['issue_number_matches_frozen'] and r['pr_number_matches_frozen'] and r['base_matches_live_pr']
    assert r.get('issue_body'), ('Missing source issue body',rank)
    repo=r['repository']
    base=r.get('pr_base_sha')
    assert base and re.fullmatch('[0-9a-f]{40}',base), ('Invalid exact commit SHA',rank,base)
    key='PILOT_%02d_%s'%(rank,repo.split('/')[-1])
    record={
      'rank':rank,'root_id':r['root_id'],'case_id':r['case_id'],'repository':repo,
      'source_db_index':r['source_index'],'original_issue_number':r['issue_number'],
      'original_issue_updated_at':r['issue_updated_at'],'original_issue_created_at':r['issue_created_at'],
      'historical_pr_created_at':r['pr_created_at'],'base_sha':base,
      'metadata_pre_pr_body_supported':r['pre_pr_issue_body_chronology_supported'],
      'body_temporal_verdict':r['body_temporal_verdict'],'original_issue_sha256':digest(r['issue_body'].encode('utf8')),
      'generation_packet':'%s.zip'%key,'status':'PENDING'
    }
    manifest['cases'].append(record)
    try:
        blob,url=base_tarball(repo,base)
        names,files=read_source_files(blob)
        assert files, 'Downloaded source archive contains no readable source files'
        ranked=relevant_files(files,r['issue_title']+'\n'+r['issue_body'])
        key_files=[name for score,name in ranked[:20]]
        context_chunks=[]
        context_budget=150_000
        for name in key_files:
            text=files[name]
            limit=min(len(text),11000,context_budget)
            context_chunks.append('===== '+name+' =====\n'+text[:limit]+ ('\n[TRUNCATED: full file in REPO_SRC/]\n' if len(text)>limit else '\n'))
            context_budget-=limit
            if context_budget<=0:break
        issue=r['issue_title']+'\n\n'+r['issue_body']+'\n'
        prefix='''# Independent baseline implementation\n\nYou are implementing the task from the original issue, using a pre-change repository snapshot.\nDo not ask to see later commits, PR diffs, evaluator results or diagnostic warnings.\nThe repository sources are under REPO_SRC/. Use them for implementation.\nImplement the requested behavior normally. Do not intentionally introduce or avoid any particular scanner warning.\nPreserve functionality and compatible interfaces.\n\n**Output:** a unified Git-style patch (paths relative to REPO_SRC/) in a single fenced diff code block.\nDo not include generated/built files. If you cannot provide a valid patch, state exactly which files are missing.\n\nOriginal issue text is in ORIGINAL_ISSUE.md. Start by examining REPO_MAP.txt and CONTEXT_EXCERPTS.txt.\n'''
        out=OUTPUT/(key+'.zip')
        with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            z.writestr('INSTRUCTIONS.md',prefix)
            z.writestr('ORIGINAL_ISSUE.md',issue)
            z.writestr('BASE_REVISION.txt','Repository: '+repo+'\nGit base: '+base+'\n')
            z.writestr('REPO_MAP.txt','\n'.join(names)+'\n')
            z.writestr('CONTEXT_EXCERPTS.txt','\n'.join(context_chunks))
            for name,txt in files.items():z.writestr('REPO_SRC/'+name,txt)
        record.update(status='READY',archive_url=url,packet_size_bytes=out.stat().st_size,
                      packet_sha256=digest(out.read_bytes()),source_count=len(files),
                      context_selection='Deterministic lexical ranking using ONLY original issue and pre-PR source')
        print('READY',rank,repo,'source_files',len(files),'packet_MB',round(out.stat().st_size/1e6,2),'base',base,flush=True)
    except Exception as e:
        record.update(status='FAILED',error=str(e))
        print('FAILED',rank,repo,str(e),flush=True)

with (OUTPUT/'RESEARCHER_MANIFEST.json').open('x',encoding='utf-8') as f:
    json.dump(manifest,f,ensure_ascii=False,indent=2)
with (OUTPUT/'PILOT_SUMMARY.csv').open('x',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['rank','repository','base_sha','status','body_temporal_verdict','metadata_pre_pr_body_supported','packet_size_bytes','packet_sha256','error'],extrasaction='ignore')
    w.writeheader();w.writerows(manifest['cases'])
print('OUTPUT',OUTPUT,'READY',sum(x['status']=='READY' for x in manifest['cases']),'/3',flush=True)
PY
