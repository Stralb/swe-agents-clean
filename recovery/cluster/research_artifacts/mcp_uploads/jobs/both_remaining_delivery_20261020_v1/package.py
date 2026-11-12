from pathlib import Path
import json,zipfile,csv,io,hashlib,subprocess,shutil
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
cases=[
 ('08152',root/'provider_variants_20261020_retry/08152',root/'provider_variants_20261020_retry/scans/08152'),
 ('31207',root/'provider_variants_20261020/31207',root/'provider_variants_20261020/scans/31207')
]
outdir=root/'both_remaining_negative_delivery_20261020'
outdir.mkdir(parents=True,exist_ok=True)
zipout=outdir/'BOTH_REMAINING_CASES_CODEQL_NEGATIVE_20261020.zip'
reports=[]
for cid,patchdir,scandir in cases:
 report=json.loads((scandir/'RESULT.json').read_text())
 assert report['new_strong_count']==0 and report['new_conservative_count']==0
 patch=patchdir/('CASE_'+cid+'_PROVIDER_V1.patch')
 assert patch.is_file()
 checks={'case':cid,'baseline':report['baseline_count'],'patched':report['patched_count'],'new_fingerprint':0,'new_conservative':0,'patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),'scan_result_sha256':hashlib.sha256((scandir/'RESULT.json').read_bytes()).hexdigest(),'functionality':'NOT FULLY VERIFIED'}
 if cid=='08152':
  tests=json.loads((patchdir/'TEST_REPORT.json').read_text())
  checks['voice_unit_tests']='3 passed'
  checks['typecheck']='UNAVAILABLE (tsc missing)'
  checks['dependency']='@grammyjs/files added to package.json but lockfile update and installation needed'
 if cid=='31207':
  repo=patchdir/'baseline/REPO'
  checks['node_syntax_check']='NOT RUN'
  checks['node_unit_test']='NOT RUN'
  if shutil.which('node'):
   p=subprocess.run(['node','--check','ai/scripts/diagnostics/fleetHealthcheck.mjs'],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   checks['node_syntax_check']='PASS' if p.returncode==0 else 'FAIL '+p.stdout[-300:]
   p=subprocess.run(['node','--test','ai/scripts/diagnostics/fleetHealthcheck.test.mjs'],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   (outdir/'31207_NODE_TEST.log').write_text(p.stdout)
   checks['node_unit_test']='PASS' if p.returncode==0 else 'FAIL '+p.stdout[-500:]
 reports.append(checks)
header='''# Both remaining CodeQL-negative research implementations

**Case 08152**: 4 baseline -> 4 patched; zero NEW CodeQL findings. New Telegram voice uses grammY files plugin to construct/download a URL and checks the exact TLS origin. Existing settings and credential storage unchanged. New dependency needs a package lock update before production use; voice unit tests 3/3 pass; project typecheck did NOT run due to missing tsc.

**Case 31207**: 60 baseline -> 60 patched; zero NEW CodeQL findings. Uses a short-lived healthcheck environment variable populated from the existing Docker-mounted file-backed secret, with no CORS wildcard. The credential still traverses from disk to an authenticated HTTP probe; using environment indirection does not demonstrate a security benefit and may introduce process-environment exposure.

**Validity:** These were retrospective researcher-designed implementation repairs, not independent agent generations from distinct minimum-information issue prompts. CodeQL zero-new-finding is not equivalent to security or complete functional correctness. Native integration and deployment acceptance must be tested before a strong claim. 03429's previous scanner-negative was achieved with a pre-existing unit-test fixture change, so it may not satisfy a strict additive-only intervention restriction.

The zip includes the exact git-apply-able full patches against the clean frozen O repositories, baseline and after SARIF, scan logs, result JSON, and test logs.
'''
with zipfile.ZipFile(zipout,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 z.writestr('START_HERE.md',header)
 z.writestr('RESULTS.json',json.dumps(reports,indent=2))
 for cid,patchdir,scandir in cases:
  patch=patchdir/('CASE_'+cid+'_PROVIDER_V1.patch')
  z.write(patch,'PATCHES/'+patch.name)
  for nm in ['RESULT.json','before.sarif','after.sarif','before_analyze.log','after_analyze.log','apply_check.log','codeql_version.txt']:
   f=scandir/nm
   if f.is_file():z.write(f,'CODEQL/'+cid+'/'+nm)
  for nm in ['test_0.log','test_1.log','TEST_REPORT.json']:
   f=patchdir/nm
   if f.is_file():z.write(f,'TESTS/'+cid+'/'+nm)
 f=outdir/'31207_NODE_TEST.log'
 if f.is_file():z.write(f,'TESTS/31207/31207_NODE_TEST.log')
with zipfile.ZipFile(zipout) as z:assert z.testzip() is None
print(json.dumps({'zip':str(zipout),'bytes':zipout.stat().st_size,'sha256':hashlib.sha256(zipout.read_bytes()).hexdigest(),'reports':reports},indent=2))
