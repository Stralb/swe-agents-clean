import sys,subprocess,importlib.util,hashlib,base64,zlib
from pathlib import Path
cid=sys.argv[1]
root=Path.home()/'research_artifacts'
out=root/'prevention_pilot_phase2/provider_variants_20261020_retry'/cid
repo=out/'baseline/REPO'
mods=[root/'mcp_uploads/jobs/two_provider_atomic_20261020_v1'/('mod_'+cid+'.py')]
if cid=='08152':mods.append(root/'mcp_uploads/jobs/two_provider_atomic_20261020_v1/tests_08152_v2.py')
for n,m in enumerate(mods):
 spec=importlib.util.spec_from_file_location('my_mod'+str(n),m)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.modify(repo)
subprocess.run(['git','add','-N','-A'],cwd=repo,check=True)
patch=out/('CASE_'+cid+'_PROVIDER_V1.patch')
with patch.open('wb') as f:subprocess.run(['git','diff','--binary','HEAD'],cwd=repo,stdout=f,check=True)
ud=out/'upload';ud.mkdir(exist_ok=True)
(ud/('CASE_'+cid+'_P1.zlib.base64.txt')).write_text(base64.b64encode(zlib.compress(patch.read_bytes())).decode())
print(cid,patch,hashlib.sha256(patch.read_bytes()).hexdigest())
