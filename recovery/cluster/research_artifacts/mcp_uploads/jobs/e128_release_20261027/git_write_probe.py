#!/usr/bin/env python3
"""Probe GitHub HTTPS write permissions with a local empty commit and dry-run push.
No remote mutation and no credential output.
"""
import os,subprocess
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027')
dst=root/'git_checkout'
url='https://github.com/Stralb/arc-agi-3-rl-research.git'
branch='feat/e126-kaggle-release-20261027'
env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never')
def run(args,timeout=60):
 p=subprocess.run(args,cwd=str(root),text=True,capture_output=True,timeout=timeout,env=env)
 print('COMMAND',args[:3],'CODE',p.returncode,'STDOUT',p.stdout[-220:].replace('\n',' '),'STDERR',p.stderr[-320:].replace('\n',' '),flush=True)
 return p
if not (dst/'.git').exists():
 r=run(['git','clone','--depth','1','--single-branch','-b',branch,url,str(dst)],timeout=75)
 if r.returncode:raise SystemExit(r.returncode)
r=run(['git','-C',str(dst),'rev-parse','HEAD'])
assert r.returncode==0 and r.stdout.strip()=='31d5b3ad6d52f61f1e02ff1b2eddfcfd59d2c2c3'
r=run(['git','-C',str(dst),'-c','user.name=ARC Research Release','-c','user.email=release-bot@example.invalid','commit','--allow-empty','-m','E126 remote write probe (dry run only)'])
if r.returncode:raise SystemExit(r.returncode)
r=run(['git','-C',str(dst),'-c','credential.interactive=never','-c','core.askPass=','push','--dry-run','origin','HEAD:refs/heads/'+branch],timeout=45)
print('GITHUB_HTTPS_WRITE_AUTH_AVAILABLE',r.returncode==0,flush=True)
