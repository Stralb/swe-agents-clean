"""E069 cluster stage. It MUST load a real verified Hugging Face snapshot first.

The sealed-source5 curriculum is the same as E064/E068. This command can never
substitute native agent-generated episodes or fixtures for real human sessions.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[3];E068=BASE/'vendor'/'e068'
sys.path[:0]=[str(E068/'code'),str(BASE/'code')]
from acquire_human import verify
from train_human_five import validate_and_merge
from history_ddqn import train
from source_audit import audit_source
from e068_split import sha


def run(snapshot,source,out,updates=2500):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    verified=verify(snapshot)
    merged,summary=validate_and_merge(source,out)
    human_manifest=out/'HUMAN_PRETRAIN_VERIFIED.json'
    proof=audit_source(merged,human_manifest)
    if proof['kind']!='hash_locked_public_human_sessions':
        raise PermissionError('Real human dataset not available')
    audits=[]
    for mode in ('bc','ddqn','shuffled','no_history'):
        audit=train(merged,out,mode,updates=updates,verified_manifest=human_manifest)
        audits.append(audit)
        print('E069_HUMAN_COMPLETED',mode,audit['sha256'],flush=True)
    freeze={'kind':'E069_PRE_HOLDOUT_MODEL_FREEZE','human_data_sha256':sha(merged),
        'source_manifest_sha256':sha(human_manifest),'source_families':proof['families'],
        'human_sessions':proof['human_sessions'],'native_reward_events':proof['native_reward_events'],
        'source_revision':proof['underlying_hf_revision'],
        'holdout_never_trained_on':True,'models':[{'mode':r['mode'],'sha256':r['sha256']} for r in audits],
        'policy_training_script_sha256':sha(BASE/'vendor'/'e069'/'code'/'history_ddqn.py'),
        'evaluation_unlocked':False,
        'stage':'four candidates fitted, NO native evaluation claimed'}
    (out/'E069_PRE_HOLDOUT_FREEZE.json').write_text(json.dumps(freeze,indent=2)+'\n')
    return freeze

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--updates',type=int,default=2500)
    a=p.parse_args();print(json.dumps(run(a.snapshot,a.source,a.out,a.updates),indent=2))
