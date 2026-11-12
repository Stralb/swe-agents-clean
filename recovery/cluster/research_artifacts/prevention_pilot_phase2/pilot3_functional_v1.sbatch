#!/usr/bin/env bash
#SBATCH --job-name=p3functional
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00
#SBATCH --array=0-2%2
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_functional_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_functional_%A_%a.err
set -euo pipefail
# Execute only on an allocated compute node. No writes to original repositories or results.
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/bun/bin:$PATH"
export PILOT3_TASK="${SLURM_ARRAY_TASK_ID:?Run as array}" 
export PILOT3_JOB="${SLURM_ARRAY_JOB_ID:?Run as array}"
python3 - <<'PY'
import ast,base64,hashlib,io,json,os,pathlib,re,shutil,subprocess,sys,tarfile,time,urllib.request,zipfile,zlib
ROOT=pathlib.Path.home()/'research_artifacts'/'prevention_pilot_phase2'
CASES={0:(8,'Soul-Brews-Studio/arra-oracle-skills-cli','639150316e6f14cdc78e7dba8c6263504895b2e1','0e013e16a4c8f772ae404fddfbb0faad100ed13e041ecf7ab594e6b4a01bca4b'),
       1:(16,'gsd-build/gsd-2','fe0e218954d5e42d2045192f8b8234c0cd56b8c6','518c968e7b38600a2157d9376da1ba7c33e54944f6ba30fff6dcd10d8fa429f8'),
       2:(18,'breaking-brake/cc-wf-studio','cb9a1de74972ccf5b732749da386115fbe0ad81d','7d15583d4567ace172704ee0bb00764be5f134c7872657a1878b27bd70a0d300')}
rank,repo,base,expect_sha=CASES[int(os.environ['PILOT3_TASK'])]
job=os.environ['PILOT3_JOB']; temp=pathlib.Path(os.getenv('SLURM_TMPDIR') or '/tmp')/('astrauss_pilot3_functional_'+job+'_'+str(rank))
temp.mkdir(exist_ok=False,parents=True)
out=ROOT/('pilot3_functional_job'+job)/('rank_'+str(rank));out.mkdir(exist_ok=False,parents=True)
source=temp/'repo';source.mkdir()
logs=out/'logs';logs.mkdir()
result={'rank':rank,'repo':repo,'base_sha':base,'patch_sha256':expect_sha,'status':'STARTED','functional_correctness':'UNDETERMINED','checks':[]}
# Use isolated caches and home, avoid reading research credentials during installs/tests.
env=os.environ.copy(); env['HOME']=str(temp/'home');pathlib.Path(env['HOME']).mkdir()
env.update({'XDG_CACHE_HOME':str(temp/'cache'),'npm_config_cache':str(temp/'npm_cache'),'COREPACK_HOME':str(temp/'corepack'),
            'CI':'1','PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD':'1','PUPPETEER_SKIP_DOWNLOAD':'1',
            'npm_config_audit':'false','npm_config_fund':'false','npm_config_ignore_scripts':'true'})
for key in list(env):
    if any(s in key.upper() for s in ('TOKEN','PASSWORD','SECRET','API_KEY','PRIVATE_KEY','GITHUB_','AWS_','HF_','WANDB_','SLACK_')):env.pop(key,None)

def log(*parts):print(*parts,flush=True)
def save():
    (out/'RESULT.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    log('RESULT',json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
def run(name,command,timeout=420,cwd=None,required=False):
    log('RUN',name,' '.join(map(str,command)))
    try:
        proc=subprocess.run(command,cwd=cwd or source,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                            text=True,encoding='utf8',errors='replace',timeout=timeout)
        rc=proc.returncode;data=proc.stdout
    except subprocess.TimeoutExpired as exc:
        rc=124;data='TIMEOUT after '+str(timeout)+'s\n'+str(exc.stdout or '')[-3000:]
    except Exception as exc:
        rc=127;data='EXCEPTION '+repr(exc)
    (logs/(name+'.log')).write_text(data)
    entry={'name':name,'command':command,'exit_code':rc,'log':str(logs/(name+'.log')),'tail':data[-850:]}
    result['checks'].append(entry); log('EXIT',name,rc,'log_bytes',len(data));save()
    if required and rc!=0:raise RuntimeError(name+' failed: '+data[-800:])
    return rc
try:
    # Patches were preserved verbatim in the prior frozen scan script; verify full SHA256.
    old=(ROOT/'pilot3_evaluate_3patches_20261017_v2_nodefix.sbatch').read_text()
    line=next((line for line in old.splitlines() if line.startswith('PATCHES=')),None)
    if line is None:raise RuntimeError('Frozen patch map missing')
    patchmap=ast.literal_eval(line.partition('=')[2]);patch=zlib.decompress(base64.b64decode(patchmap[str(rank)]))
    assert hashlib.sha256(patch).hexdigest()==expect_sha,'Frozen patch SHA mismatch'
    patchfile=temp/'generated.patch';patchfile.write_bytes(patch)
    url='https://codeload.github.com/'+repo+'/tar.gz/'+base
    blob=None
    for tries in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Wits-Research-Pilot3-Functional'})
            with urllib.request.urlopen(req,timeout=150) as resp:blob=resp.read(180_000_001)
            if len(blob)>180_000_000:raise RuntimeError('Archive size cap exceeded')
            break
        except Exception as exc:
            log('FETCH_RETRY',tries,repr(exc));time.sleep(3)
    if blob is None:raise RuntimeError('Unable to fetch exact pre-PR source')
    result['source_archive_sha256']=hashlib.sha256(blob).hexdigest()
    with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as tf:
        for member in tf:
            parts=pathlib.PurePosixPath(member.name).parts
            if len(parts)<2:continue
            rel=pathlib.PurePosixPath(*parts[1:])
            if '..' in rel.parts:raise RuntimeError('Unsafe archive member')
            target=source.joinpath(*rel.parts)
            if member.isdir():target.mkdir(exist_ok=True,parents=True)
            elif member.isfile():
                target.parent.mkdir(exist_ok=True,parents=True)
                with tf.extractfile(member) as f, target.open('xb') as h:shutil.copyfileobj(f,h)
    run('git_apply_check',['git','apply','--check',str(patchfile)],required=True)
    run('git_apply',['git','apply',str(patchfile)],required=True)
    package_file=source/'package.json'
    package=json.loads(package_file.read_text()) if package_file.exists() else {}
    scripts=package.get('scripts',{})
    result['package_manager']=package.get('packageManager','unspecified')
    result['available_scripts']=scripts
    result['runtime_detected']={x:shutil.which(x,path=env.get('PATH')) for x in ('node','npm','corepack','bun','pnpm')}
    save()
    if rank==16:
        # This patch changes Markdown instructions only. Validate the concrete JSON example and template contract.
        prompt=(source/'src/resources/extensions/gsd/prompts/complete-milestone.md').read_text()
        template=(source/'src/resources/extensions/gsd/templates/milestone-summary.md').read_text()
        blocks=re.findall(r'```json\s*\n(.*?)```',prompt,re.S)
        assert blocks,'No JSON example found'
        obj=json.loads(blocks[-1])
        for key in ('keyDecisions','keyFiles','lessonsLearned'):
            assert isinstance(obj.get(key),list) and all(isinstance(v,str) for v in obj[key]),key
        assert 'Pass keyDecisions, keyFiles, and lessonsLearned' in template
        result['checks'].append({'name':'prompt_json_schema_example','exit_code':0,'detail':'Example JSON parses and three array-valued arguments conform to claimed format'})
        result['status']='STATIC_CHECK_COMPLETE';result['functional_correctness']='NOT_ESTABLISHED';save()
        log('CASE_DONE',rank,'documentation-only; no behavioral test from static check');sys.exit(0)
    # First attempt a project-supported runtime, without mutating shared environments.
    if rank==8:
        if not shutil.which('bun',path=env['PATH']):
            # Official Bun published binary archive. Job-private download, never a remote shell installer.
            bunv='1.3.9';bunurl=f'https://github.com/oven-sh/bun/releases/download/bun-v{bunv}/bun-linux-x64.zip'
            try:
                req=urllib.request.Request(bunurl,headers={'User-Agent':'Wits-Research-Pilot3-Functional'})
                with urllib.request.urlopen(req,timeout=150) as res:bb=res.read(90_000_001)
                if len(bb)>90_000_000:raise RuntimeError('Bun archive too large')
                with zipfile.ZipFile(io.BytesIO(bb)) as bz:
                    members=[n for n in bz.namelist() if n.endswith('/bun') or n=='bun']
                    if len(members)!=1:raise RuntimeError('Unexpected bun archive members')
                    p=temp/'bun-bin';p.mkdir();binfile=p/'bun';binfile.write_bytes(bz.read(members[0]));binfile.chmod(0o755)
                env['PATH']=str(p)+':'+env['PATH']
                log('BUN_READY',bunv,'archive_sha256',hashlib.sha256(bb).hexdigest())
            except Exception as exc:
                result['status']='ENVIRONMENT_BLOCKED';result['reason']='Bun unavailable: '+repr(exc);save();sys.exit(0)
        run('bun_version',['bun','--version'],timeout=20,required=True)
        manifest=source/'bun.lock'
        cmd=['bun','install','--ignore-scripts']
        if manifest.exists():cmd.append('--frozen-lockfile')
        rc=run('dependency_install',cmd,timeout=900)
        if rc!=0:
            result['status']='ENVIRONMENT_BLOCKED';result['reason']='Dependency installation failed';save();sys.exit(0)
        rc=run('codex_plugin_tests',['bun','test','__tests__/codex-plugin.test.ts'],timeout=600)
        result['status']='TESTS_COMPLETE' if rc==0 else 'TESTS_FAILED'
        result['functional_correctness']='TESTS_PASS' if rc==0 else 'TESTS_FAIL_OR_BASELINE_UNKNOWN'
        save();sys.exit(0)
    # rank 18: VSCode extension. Compile/typecheck and unit tests if repository has a suitable script.
    runtime=shutil.which('node',path=env['PATH'])
    if not runtime:
        result['status']='ENVIRONMENT_BLOCKED';result['reason']='Node.js unavailable';save();sys.exit(0)
    run('node_version',['node','--version'],timeout=20,required=True)
    pm=package.get('packageManager','')
    if (source/'pnpm-lock.yaml').exists() or pm.startswith('pnpm'):
        if shutil.which('pnpm',path=env['PATH']):installer=['pnpm','install','--frozen-lockfile','--ignore-scripts']
        elif shutil.which('corepack',path=env['PATH']):installer=['corepack','pnpm','install','--frozen-lockfile','--ignore-scripts']
        else:
            result['status']='ENVIRONMENT_BLOCKED';result['reason']='pnpm required but unavailable';save();sys.exit(0)
        runner=['pnpm','run'] if shutil.which('pnpm',path=env['PATH']) else ['corepack','pnpm','run']
    elif (source/'package-lock.json').exists():
        installer=['npm','ci','--ignore-scripts','--no-audit','--no-fund'];runner=['npm','run']
    else:
        installer=['npm','install','--ignore-scripts','--no-audit','--no-fund'];runner=['npm','run']
    rc=run('dependency_install',installer,timeout=1200)
    if rc!=0:
        result['status']='ENVIRONMENT_BLOCKED';result['reason']='Dependency installation failed';save();sys.exit(0)
    checks_run=[]
    for task in ('check-types','typecheck','type-check','compile','build'):
        if task in scripts:
            rc=run('project_'+task.replace('-','_'),runner+[task],timeout=720)
            checks_run.append((task,rc));break
    for task in ('test:unit','test:run','test:ci'):
        if task in scripts:
            rc=run('project_'+task.replace(':','_'),runner+[task],timeout=600)
            checks_run.append((task,rc));break
    if not checks_run:
        result['status']='NO_AUTOMATED_CHECKS_AVAILABLE';result['functional_correctness']='NOT_ESTABLISHED'
    elif all(rc==0 for task,rc in checks_run):
        result['status']='CHECKS_PASS';result['functional_correctness']='BUILD_OR_UNIT_PASS_ONLY'
    else:
        result['status']='CHECKS_FAIL';result['functional_correctness']='TESTS_FAIL_OR_BASELINE_UNKNOWN'
    save()
except Exception as exc:
    result['status']='EVALUATION_ERROR';result['reason']=repr(exc);save();log('EVALUATION_ERROR',repr(exc))
PY
