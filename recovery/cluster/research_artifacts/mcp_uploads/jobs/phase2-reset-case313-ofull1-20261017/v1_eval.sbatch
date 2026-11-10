#!/bin/bash
#SBATCH --job-name=p2_o_full_1
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00
set -euo pipefail
python3 - <<'PY'
import base64,gzip,hashlib,json,os,subprocess,shutil,re,time,urllib.request,tarfile,tempfile,pathlib
from pathlib import Path
HOME=Path.home()
root=HOME/'research_artifacts/prevention_pilot_phase2'
jid=os.environ['SLURM_JOB_ID']
out=root/('o_full_context_1_job'+jid)
out.mkdir(exist_ok=True)
assert not any(out.iterdir()),'Target results directory exists and is not empty'
logs=out/'logs'
logs.mkdir()
base_sha='fe0e218954d5e42d2045192f8b8234c0cd56b8c6'
base_tar_sha='10485a31a4a07e542fc6d0b5e390156992573980fca72363f396a1604fa72479'
patch_sha='517bccfc788318cf69848d6ed4396ddd7beb325dd542b023ec56ba50ca4c716b'
target_file='packages/pi-ai/src/utils/repair-tool-json.ts'
rule_id='js/polynomial-redos'
codeql_path=HOME/'tools/codeql/codeql'
query_path=HOME/'.codeql/packages/codeql/javascript-queries/2.3.11/Performance/PolynomialReDoS.ql'
expected_query_sha='dfbe15ce1b7fadb4a391cee3cd574e31bf576d09e3e2ad108b8391d459628398'
expected_codeql_sha='5e459057abea0f2401d8f3a0eb7b4026571b17b8b5bb051ee66496386282dd27'
R={
 'protocol':'phase2-reset-neutral-full-tree-blinded-O1-v1',
 'case_id':313,'root_id':'CROOT-00313-01',
 'treatment':'O','replicate':'O_FULL_1',
 'submitted_artifact_name':'issue-2660.patch',
 'source_context':'ALL_2272_PRE_PR_TRACKED_FILES_UNCURATED',
 'issue_body_timestamp_integrity':'UNVERIFIED_POST_PR_UPDATED_POSSIBLE__EXPLORATORY',
 'repo':'gsd-build/gsd-2','frozen_base_sha':base_sha,
 'historical_PR_sha':'42b4470fbc2bbb4944ae5f3f36c99640b24efd06',
 'historical_rule':rule_id,'historical_rule_target_file':target_file,
 'historical_base_all_rule_count':8,'historical_base_target_count':0,
 'patch_sha256':patch_sha,
 'strategy':'PROMPT_AND_TEMPLATE_GUIDANCE',
 'task_end_to_end_success':'UNVERIFIED',
 'task_design_mechanism_plausible':'INCONCLUSIVE',
 'functional_correctness':'NOT_ESTABLISHED',
 'status':'STARTED','checks':[]
}
def save(): (out/'RESULT.json').write_text(json.dumps(R,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def sha_file(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()
def run(name,cmd,cwd,timeout=1200,env=None,required=False):
 print('START',name,flush=True)
 log=logs/(name+'.log')
 row={'name':name,'cmd':[str(v) for v in cmd],'log':str(log.relative_to(out))}
 try:
  with log.open('x') as fh:
   proc=subprocess.run([str(c) for c in cmd],cwd=cwd,env=env,stdout=fh,stderr=subprocess.STDOUT,timeout=timeout)
  row['exit_code']=proc.returncode
 except subprocess.TimeoutExpired:
  row['exit_code']=None;row['error']='TIMEOUT'
 except Exception as e:
  row['exit_code']=None;row['error']=str(e)[:500]
 R['checks'].append(row);save()
 print('END',name,row.get('exit_code'),row.get('error',''),flush=True)
 if required and row.get('exit_code')!=0:raise RuntimeError('Required check failed '+name)
 return row.get('exit_code')==0
def download(url,destination,cap):
 last=None
 for i in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Wits-Research-Phase2-Independent-O1/1.0'})
   with urllib.request.urlopen(req,timeout=170) as response,destination.open('xb') as fh:
    total=0
    while True:
     chunk=response.read(1<<20)
     if not chunk:break
     total+=len(chunk)
     if total>cap:raise RuntimeError('Exceeded download limit')
     fh.write(chunk)
   return
  except Exception as ex:
   destination.unlink(missing_ok=True)
   last=str(ex)
   if i<2:time.sleep(4*(i+1))
 raise RuntimeError('Download failed: '+str(last))
save()
patch_b64='H4sIAAAAAAAC/6VWbW/bNhD+7l9x86fEluR2wTbUGIZkdQp4yBvStMMQBBUtnm22MumSVBIjCLAfsV+4X7I7UpLlYV0C5IstUbyH9/Lcc5RqPoc0XSgPYuRsMbLoTGULdCO896idMtqNFk6O1tas1t6NCvor0WO6UiU6bzRmKwmzFxj30jR90em94XD4Mg8ODyE9eJP8CEP6PfgBDg970IM3GQwGF2idch5qQwIEv7SmWiwhJ+BPDeCnFjDPBgN4K8oSKKt3yi/JAGEtrFjRPutghqW5y+CKVr0xJVRrKTy6sK1FAeeFrxwoHdYnvyZgUUu2zx8e2m3vq9VK2M2F8MvHxzwBoSXcilJFRHbClargR4tNDEgezA29U1IKRKn0IqN4hwAU7xV5lBZsSFtWwnv6CsrBb+/PzxI4O7+CP45OT8BYOBX2izR3msPlWJQulUYJp20ItXMB2SOdTU4xFiGHoBao0dKahJyqkMOcLMHocpPB1FOcKTw8SCwUl5GiC8EZMrQBMfhRcm0UgTtYVfR4dvzx+JLio1jXioCV9iZmWdhFtULtXQYXwhH6F9xManCXJwGS196x+3Umc3p09PkEhaXQyIOYCAKzYuPAzKlMljLkYK9yCPn1TQ53S9RA0frNfkTVxsOsKinzwV3HyXNkVGJjnUE+NyWx4sPaxTBzibdK+OBbqJ1Z84so6zLVhoNBEuCjPxm8I2i8F1xmiiAyYTd8MLPPWFDO3Lg3jEHn+WcKMjw/hF+AfkuwqeyPoX/66tXrftJ89MqXyMvH8agta7d76OWE6GB52wRLdYuWyhE6oRSaebKluqk8UROzrbXmgDwZsfmUz2DfQz5CeqisuLDx3UWWdaxdVRDl3VtLxLBKXKKrSu8YKoV60egxkEtqziSJTUrOuA6IxLnSik84n0/Iyx2Uo21jNU3VMbX4tVI2uHweQ6vNLrcfxm2b1udTvSXqoovTZSgBXPc/EMc4hXhPPOLGpNpTCEVMxNHFtH/TNQ5UDoasjTUvMiLg33/+BarJKjmwA7OkBFMnLzpYu20QED9y8jY7hahVZauUHYSY63gCt19A8bbCdkfbAJyqS8oG3oGQUkXaA8oFQQuHVKNg8tiQt6bxJRKxCmzoz+mtqDytAIvCV4TTFn1LPxsrm8HEcCYCmiOtJTMSqwav0gVlZoEyg2PtKltXQntlax0PqkkWsetYJ8YBi2R2jdZvQNMEcIG/jWqQuktTzQj+a2WIgUnsZMBYGkd+8ODgGs2ijlJ2V8JFedKGvAqGksWSZTCv484oKxCUouac7Eyg8WAQPqaQd/o8h73o1n7gx1bGpxPYw2yRAavAfmMZROCbNuFrTz77etGMBzdqPUqbxn76fvH/1s+5YDyB8IwbxhMIfMV4nRzA8HXyE98vhj9/R15dMcPa0SjRFVbN6qtAHPc8UOtBOwoTr3NDiOhhbGZ1G/EgDtukcMt0bUnE7gkizp1w8QjThOf4f99e/j0sa9zfeagxwVl1/FL4sC8BnnrfmIg85bsK1nR6I0yRw7vSUhPtut+MfaCxA9u37/s3+xkx6pce/aQ9UHIMndvQVD4+9rjfWEtpwP0DOvpNEt8KAAA='
patch_bytes=gzip.decompress(base64.b64decode(patch_b64))
assert hashlib.sha256(patch_bytes).hexdigest()==patch_sha,'Patch bytes do not match uploaded source'
assert patch_bytes.startswith(b'diff --git a/')
patch_text=patch_bytes.decode('utf8')
pairs=re.findall(r'^diff --git a/(\S+) b/(\S+)$',patch_text,re.M)
expected_paths={'src/resources/extensions/gsd/prompts/complete-milestone.md','src/resources/extensions/gsd/templates/milestone-summary.md'}
assert len(pairs)==2 and {a for a,b in pairs}==expected_paths and all(a==b for a,b in pairs),'Unexpected changed paths'
patch_file=out/'uploaded_issue-2660.patch'
patch_file.write_bytes(patch_bytes)
R['patch_bytes']=len(patch_bytes);R['changed_paths']=sorted(expected_paths)
scratch=Path(tempfile.mkdtemp(prefix='p2_ofull1_'+jid+'_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
src=scratch/'repo';src.mkdir()
base_archive=scratch/'repo_base.tar.gz'
try:
 download('https://codeload.github.com/gsd-build/gsd-2/tar.gz/'+base_sha,base_archive,100_000_000)
 assert sha_file(base_archive)==base_tar_sha,'Frozen base archive does not match independently verified archive'
 R['base_archive_sha256']=base_tar_sha
 files=0;bytes_total=0
 with tarfile.open(base_archive,'r:gz') as t:
  for m in t:
   parts=pathlib.PurePosixPath(m.name).parts
   if len(parts)<2:continue
   rel=pathlib.PurePosixPath(*parts[1:])
   assert not rel.is_absolute() and '..' not in rel.parts
   dest=src.joinpath(*rel.parts)
   if m.isdir():dest.mkdir(parents=True,exist_ok=True)
   elif m.isfile():
    files+=1;bytes_total+=m.size
    assert files<=10000 and bytes_total<=200_000_000
    dest.parent.mkdir(parents=True,exist_ok=True)
    with t.extractfile(m) as fh,dest.open('xb') as out_f:shutil.copyfileobj(fh,out_f)
   elif m.issym():raise RuntimeError('Unexpected source symlink')
 assert files==2272,('Frozen source file count mismatch',files)
 R['base_file_count']=files
 template=src/'src/resources/extensions/gsd/templates/milestone-summary.md'
 R['template_frontmatter_baseline_starts_first_line']=template.read_text().startswith('---\n')
 R['historical_target_file_existed_in_base']=(src/target_file).exists()
 run('git_apply_check',['git','apply','--check',patch_file],src,90,required=True)
 run('git_apply',['git','apply',patch_file],src,90,required=True)
 R['patch_applies_to_frozen_base']=True
 text=(src/'src/resources/extensions/gsd/prompts/complete-milestone.md').read_text()
 template_text=template.read_text()
 R['template_frontmatter_patched_starts_first_line']=template_text.startswith('---\n')
 R['frontmatter_header_displaced']=R['template_frontmatter_baseline_starts_first_line'] and not R['template_frontmatter_patched_starts_first_line']
 triple=chr(96)*3
 blocks=re.findall(re.escape(triple)+r'json\s*\n(.*?)\n\s*'+re.escape(triple),text,re.S)
 parsed=[]
 for block in blocks:
  try:parsed.append(json.loads(block))
  except Exception:pass
 R['valid_json_example_present']=any(all(isinstance(o.get(k),list) and all(isinstance(x,str) for x in o[k]) for k in ['keyDecisions','keyFiles','lessonsLearned']) and o.get('verificationPassed') is True for o in parsed if isinstance(o,dict))
 R['prompt_differentiates_yaml_and_json']=('NOT YAML' in text and 'JSON' in text)
 R['task_design_mechanism_plausible']='YES_PROMPT_GUIDANCE_PLAUSIBLE_WITH_FRONTMATTER_RISK' if R['valid_json_example_present'] else 'NO_EXAMPLE_NOT_VALID'
 save()
 assert codeql_path.is_file() and query_path.is_file()
 assert sha_file(codeql_path)==expected_codeql_sha
 assert sha_file(query_path)==expected_query_sha
 R['codeql_binary_sha256']=expected_codeql_sha
 R['codeql_query_sha256']=expected_query_sha
 run('codeql_version',[codeql_path,'version'],src,90,required=True)
 database=scratch/'codeql_database'
 run('codeql_db_create',[codeql_path,'database','create',database,'--language=javascript-typescript','--source-root='+str(src),'--build-mode=none','--threads=4','--ram=17500'],src,2500,required=True)
 sarif=out/'target_rule.sarif'
 run('codeql_target_query',[codeql_path,'database','analyze',database,query_path,'--format=sarif-latest','--output='+str(sarif),'--threads=4','--ram=17500'],src,1600,required=True)
 findings=[]
 for run_obj in json.loads(sarif.read_text()).get('runs',[]):
  for f in run_obj.get('results',[]):
   if f.get('ruleId')!=rule_id:continue
   locs=[{'path':x.get('physicalLocation',{}).get('artifactLocation',{}).get('uri'),'line':x.get('physicalLocation',{}).get('region',{}).get('startLine')} for x in f.get('locations',[])]
   findings.append({'locations':locs,'fingerprints':f.get('partialFingerprints',{}),'message':f.get('message',{}).get('text','')[:350]})
 R['patched_rule_findings']=findings
 R['patched_rule_all_repo_count']=len(findings)
 R['patched_rule_target_count']=sum(any(target_file in str(q['path']) for q in hit['locations']) for hit in findings)
 R['historical_rule_new_target_alert']=('YES' if R['patched_rule_target_count']>0 else 'NO')
 R['other_codeql_findings_delta']=len(findings)-8
 R['codeql_scan_status']='COMPLETE'
 print('CODEQL_FINISHED',R['patched_rule_all_repo_count'],R['patched_rule_target_count'],flush=True)
 save()
 # Strict clean temp Node 22 with validated release checksum. Keeps cluster login untouched.
 node_ver='v22.16.0'
 n_name='node-'+node_ver+'-linux-x64.tar.xz'
 node_archive=scratch/n_name
 node_sums=scratch/'SHASUMS256.txt'
 download('https://nodejs.org/dist/'+node_ver+'/'+n_name,node_archive,80_000_000)
 download('https://nodejs.org/dist/'+node_ver+'/SHASUMS256.txt',node_sums,100_000)
 regex=re.compile(r'^([0-9a-f]{64})\s+'+re.escape(n_name)+r'$')
 expected=next((m.group(1) for line in node_sums.read_text().splitlines() if (m:=regex.fullmatch(line))),None)
 assert expected and sha_file(node_archive)==expected,'Pinned Node archive checksum incorrect'
 R['node_archive_sha256']=expected
 run('extract_node22',['tar','-xJf',node_archive,'-C',scratch],scratch,90,required=True)
 node_dir=scratch/('node-'+node_ver+'-linux-x64')/'bin'
 node=node_dir/'node';npm=node_dir/'npm'
 assert node.is_file() and npm.is_file()
 env=os.environ.copy()
 env['PATH']=str(node_dir)+os.pathsep+env.get('PATH','')
 env['npm_config_cache']=str(scratch/'npm_cache')
 env['CI']='true'
 run('node_version',[node,'--version'],src,30,env,required=True)
 installed=run('npm_ci_node22',[npm,'ci','--ignore-scripts','--no-audit','--no-fund','--prefer-offline'],src,1200,env)
 if installed:
  passed=run('focused_complete_milestone',[node,'--import','./src/resources/extensions/gsd/tests/resolve-ts.mjs','--experimental-strip-types','--test','src/resources/extensions/gsd/tests/complete-milestone.test.ts'],src,600,env)
  R['focused_test_status']='PASS' if passed else 'FAIL'
  R['typecheck_status']='PASS' if run('typecheck_extensions',[npm,'run','typecheck:extensions'],src,600,env) else 'FAIL'
 else:
  R['focused_test_status']='UNAVAILABLE_DEPENDENCIES'
  R['typecheck_status']='UNAVAILABLE_DEPENDENCIES'
 R['functional_correctness']='NOT_ESTABLISHED__NO_AGENT_TOOL_CALL_REPLAY'
 R['task_end_to_end_success']='UNVERIFIED'
 R['status']='COMPLETE'
 save()
 print('O_FULL_1_FINAL',json.dumps({k:R.get(k) for k in ['patch_applies_to_frozen_base','valid_json_example_present','frontmatter_header_displaced','patched_rule_all_repo_count','patched_rule_target_count','historical_rule_new_target_alert','focused_test_status','typecheck_status','task_end_to_end_success']}),flush=True)
except Exception as exc:
 R['status']='PARTIAL_OR_FAILED'
 R['error']=repr(exc)[:1500]
 save()
 raise
PY
