#!/usr/bin/env python3
"""Stage validated E126 release in isolated GitHub checkout, without pushing."""
import hashlib,os,shutil,subprocess
from pathlib import Path
R=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
H=R/'e128_release_20261027'
G=H/'git_checkout'
RELEASE=H/'release'
E127=R/'click_integrated_audit_e127_20261026/analysis'
FROZEN_SHA='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
AGENT_SHA='84f27a2589575558ddb85dff2539f68d1937c6dc1a048cb3b133f6ae7005178c'
NOTEBOOK_SHA='6bbbbc5c4011d5c781e24065e70f8fea731250c07e994980c932fad41ee30b56'
MODEL_SHA='c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9'
MAIN='31d5b3ad6d52f61f1e02ff1b2eddfcfd59d2c2c3'
BRANCH='feat/e126-kaggle-release-20261027'
ENV=dict(os.environ,GIT_TERMINAL_PROMPT='0')
def git(*args):
    r=subprocess.run(['git','-C',str(G),*args],text=True,capture_output=True,env=ENV,timeout=70)
    if r.returncode:raise RuntimeError(('git failed',args,r.stderr[-500:]))
    return r.stdout.strip()
def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()
assert git('status','--porcelain')==''
git('fetch','origin',BRANCH)
assert git('rev-parse','origin/'+BRANCH)==MAIN
git('reset','--hard','origin/'+BRANCH)
assert git('rev-parse','HEAD')==MAIN
assert sha(RELEASE/'my_agent.py')==AGENT_SHA
assert sha(RELEASE/'E126_Kaggle_Candidate.ipynb')==NOTEBOOK_SHA
assert sha(RELEASE/'e126_effect_prior.pt')==MODEL_SHA
assert sha(G/'src/best_public_agent.py')==FROZEN_SHA
def copy(source,target):
    assert source.is_file(),source
    dest=G/target
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,dest)
    print('COPIED',target,sha(dest),dest.stat().st_size,flush=True)
copy(RELEASE/'my_agent.py','src/e126_submission_agent.py')
copy(RELEASE/'E126_Kaggle_Candidate.ipynb','notebooks/E126_Kaggle_Candidate.ipynb')
copy(RELEASE/'e126_effect_prior.pt','assets/e126/effect_prior_s11.pt')
copy(RELEASE/'manifest.json','experiments/E126/manifest.json')
copy(H/'e126_template.py','experiments/E126/e126_template.py')
copy(H/'verify_release.py','experiments/E126/cluster_verify_reference.py')
for old,new in [('all_arms.csv','all_arms.csv'),('paired_changes.csv','paired_changes.csv'),
                ('per_game.csv','per_game.csv'),('RESULTS.json','integrated_audit.json'),
                ('REPORT.md','E127_AUDIT.md')]:
    copy(E127/old,'experiments/E126/results/'+new)
copy(H/'robustness/holdout_summary.csv','experiments/E126/results/robustness_summary.csv')
copy(H/'robustness/holdout_per_game.csv','experiments/E126/results/robustness_per_game.csv')
copy(H/'robustness/holdout_summary.json','experiments/E126/results/robustness_protocol.json')
builder=(H/'build_release.py').read_text()
changes={
 "import base64,hashlib,json,runpy,shutil,textwrap,zlib":"import base64,hashlib,json,os,runpy,shutil,textwrap,zlib",
 "ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')":"ROOT=Path(__file__).resolve().parents[2]",
 "HERE=ROOT/'e128_release_20261027'":"HERE=Path(__file__).resolve().parent",
 "OUT=HERE/'release'":"OUT=Path(os.environ.get('E126_OUTPUT_DIR',str(HERE/'build')))",
 "FROZEN=ROOT/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'":"FROZEN=ROOT/'src/best_public_agent.py'",
 "PEER=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project/assets/dqn_v1/checkpoints/E-onehotcnn__T-stack2__A-vector__U-effect__f0__s11.pt')":"PEER=ROOT/'assets/e126/effect_prior_s11.pt'",
}
for a,b in changes.items():
    assert builder.count(a)==1,(a,builder.count(a))
    builder=builder.replace(a,b)
assert '/home-mscluster/' not in builder
compile(builder,'build_candidate.py','exec')
(G/'experiments/E126/build_candidate.py').write_text(builder)
print('PORTABLE_BUILDER_WRITTEN',flush=True)
