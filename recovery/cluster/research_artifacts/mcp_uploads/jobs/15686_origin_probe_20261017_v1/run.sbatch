#!/bin/bash
#SBATCH --job-name=github_origin_test
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:04:00
export PATH="$HOME/.bun/bin:$HOME/tools/node/bin:$PATH"
python3 - <<'PY'
from pathlib import Path
import os,json,zipfile,subprocess,tempfile
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
packet=root/'screen5_blind_batch_job70117/CASE_04_15686.zip'
out=root/('github_origin_probe_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
tmp=Path(tempfile.mkdtemp(prefix='github_origin_probe_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
target=tmp/'github.ts'
with zipfile.ZipFile(packet) as z:target.write_bytes(z.read('REPO/src/lib/github.ts'))
test=tmp/'probe.ts'
test.write_text("""
process.env.GITHUB_TOKEN='REDACTED_CREDENTIAL';
let seenUrl: unknown=null;
let seenAuth: unknown=null;
(globalThis as any).fetch=async (url: string, options: any) => {
 seenUrl=url;
 seenAuth=options?.headers?.Authorization;
 return new Response('{}',{status:200});
};
const {githubFetch}=await import('./github.ts');
await githubFetch('https://other-origin.invalid/health');
const report={
 'actual_url':seenUrl,
 'authorization_sent':seenAuth,
 'token_is_dummy':seenAuth==='Bearer TEST_CREDENTIAL_NEVER_REAL',
 'off_github_origin_accepted':seenUrl==='https://other-origin.invalid/health',
 'network_mocked':true
};
console.log(JSON.stringify(report));
if (!report.token_is_dummy || !report.off_github_origin_accepted) process.exit(2);
""")
with (out/'PROBE_STDOUT.json').open('w') as logfile:
 p=subprocess.run(['bun','run',str(test)],cwd=tmp,stdout=logfile,stderr=subprocess.STDOUT,timeout=90)
summary={'returncode':p.returncode,'output':(out/'PROBE_STDOUT.json').read_text()[:2500],'source_revision':'8386cfbec0abf36aa9b9b9a0571c3a9792dfc54b','note':'Proves accepted absolute URL and credential forwarding at helper API only; does not prove any current untrusted caller reaches this API.'}
(out/'RESULT.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
PY