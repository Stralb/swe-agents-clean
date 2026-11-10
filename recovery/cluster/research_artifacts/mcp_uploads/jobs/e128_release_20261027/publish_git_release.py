#!/usr/bin/env python3
"""Commit and publish only verified E126 files on existing GitHub feature branch.
Never force push or modify main; PR merge is a separate explicit operation.
"""
import os,subprocess
from pathlib import Path
H=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027')
G=H/'git_checkout'
BRANCH='feat/e126-kaggle-release-20261027'
BASE='31d5b3ad6d52f61f1e02ff1b2eddfcfd59d2c2c3'
ENV=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never')
def git(*args,timeout=120):
    result=subprocess.run(['git','-C',str(G),*args],env=ENV,capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError(('git',args,result.returncode,result.stderr[-700:]))
    return result.stdout.strip(),result.stderr.strip()
remote,_=git('ls-remote','origin','refs/heads/'+BRANCH)
assert remote.split()[0]==BASE,(remote,BASE)
current,_=git('rev-parse','HEAD')
assert current==BASE,(current,BASE)
expected={
 'README.md','notebooks/README.md','reports/INDEX.md',
 'src/e126_submission_agent.py',
 'notebooks/E126_Kaggle_Candidate.ipynb',
 'assets/e126/effect_prior_s11.pt',
 'experiments/E126/manifest.json',
 'experiments/E126/e126_template.py',
 'experiments/E126/build_candidate.py',
 'experiments/E126/cluster_verify_reference.py',
 'experiments/E126/README.md',
 'experiments/E126/results/all_arms.csv',
 'experiments/E126/results/paired_changes.csv',
 'experiments/E126/results/per_game.csv',
 'experiments/E126/results/integrated_audit.json',
 'experiments/E126/results/E127_AUDIT.md',
 'experiments/E126/results/robustness_summary.csv',
 'experiments/E126/results/robustness_per_game.csv',
 'experiments/E126/results/robustness_protocol.json',
 'reports/E126_SUBMISSION_CANDIDATE.md'}
for f in sorted(expected):
 assert (G/f).is_file(),f
git('add','--',*sorted(expected))
staged,_=git('diff','--cached','--name-only')
actual=set(staged.splitlines())
assert actual==expected,(sorted(actual^expected))
assert not any('.env' in f or 'secret' in f.lower() for f in actual)
assert (G/'src/best_public_agent.py').is_file()
baseline_diff,_=git('diff','--','src/best_public_agent.py')
assert baseline_diff=='','Frozen N117 source changed'
print('E128_FILES_COMMIT',len(actual),flush=True)
for f in sorted(actual): print('COMMIT_FILE',f,flush=True)
commit,_=git('-c','user.name=ARC Research Automation',
              '-c','user.email=research-release@users.noreply.github.com',
              'commit','-m','Release E126 hybrid Kaggle candidate with reproducible public SDK evidence')
head,_=git('rev-parse','HEAD')
assert head!=BASE
print('E128_LOCAL_COMMIT',head,flush=True)
stdout,stderr=git('push','origin','HEAD:refs/heads/'+BRANCH,timeout=120)
print('E128_GIT_PUSH_OUT',stdout[-200:],flush=True)
print('E128_GIT_PUSH_ERR',stderr[-350:],flush=True)
remote,_=git('ls-remote','origin','refs/heads/'+BRANCH)
assert remote.split()[0]==head,(remote,head)
print('E128_REMOTE_COMMIT_VERIFIED',head,flush=True)
