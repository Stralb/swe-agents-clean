import sys,base64,zlib,importlib.util,hashlib,subprocess,shutil,json
from pathlib import Path
cid=sys.argv[1]
root=Path.home()/'research_artifacts'
folder=root/'prevention_pilot_phase2/provider_variants_20261020'/cid
repo=folder/'baseline/REPO'
patch=folder/('CASE_'+cid+'_PROVIDER_V1.patch')
tests=[]
checks=([['bun','run','typecheck'],['bun','test','src/telegram/voice.test.ts']] if cid=='08152' else [['node','--check','ai/scripts/diagnostics/fleetHealthcheck.mjs'],['node','--test','ai/scripts/diagnostics/fleetHealthcheck.test.mjs']])
for i,cmd in enumerate(checks):
 if not shutil.which(cmd[0]):tests.append({'command':cmd,'status':'UNAVAILABLE'});continue
 with (folder/('test_'+str(i)+'.log')).open('w') as fp:
  res=subprocess.run(cmd,cwd=repo,stdout=fp,stderr=subprocess.STDOUT,timeout=120)
 tests.append({'command':cmd,'exit':res.returncode})
(folder/'TEST_REPORT.json').write_text(json.dumps(tests,indent=2))
upload=folder/'upload'
upload.mkdir(exist_ok=True)
(upload/('CASE_'+cid+'_P1.zlib.base64.txt')).write_text(base64.b64encode(zlib.compress(patch.read_bytes())).decode())
sp=importlib.util.spec_from_file_location('scanner',root/'mcp_uploads/jobs/seven_case_new_scans_20261020_v1/scan.py')
scanner=importlib.util.module_from_spec(sp)
sp.loader.exec_module(scanner)
scanner.RUN=root/'prevention_pilot_phase2/provider_variants_20261020/scans'
scanner.UPLOAD=upload
scanner.SHAS[cid]=hashlib.sha256(patch.read_bytes()).hexdigest()
scanner.main(cid)
