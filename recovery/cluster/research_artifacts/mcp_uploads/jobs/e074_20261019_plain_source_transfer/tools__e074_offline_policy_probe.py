#!/usr/bin/env python3
"""Source-five-only, post-freeze policy sensitivity diagnostic.

Offline and read-only: no ARC SDK, held-out trajectories, or optimizer.
A positive action divergence is NOT evidence of better game-solving.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path
import numpy as np


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def choose_indices(families, per_family=200):
    result=[]
    for fam in range(5):
        ids=np.flatnonzero(families==fam)
        if len(ids):
            result.extend(ids[np.unique(np.linspace(0,len(ids)-1,
                    num=min(len(ids),per_family),dtype=int))].tolist())
    return np.asarray(result,dtype=np.int64)


def policy_predictions(path, ids, seq, legal):
    import torch
    from history_ddqn import load
    model, payload=load(path)
    if payload['source_type']!='hash_locked_public_human_sessions':
        raise PermissionError('Policy probe requires human-trained checkpoint only')
    actual=[];chosen=[];grid=[];values=[]
    with torch.inference_mode():
        for chunk in np.array_split(ids,max(1,(len(ids)+63)//64)):
            if not len(chunk):continue
            q,xy=model(torch.from_numpy(seq['s'][chunk]),
                      torch.from_numpy(seq['a_prev'][chunk]),
                      torch.from_numpy(seq['xy_prev'][chunk]))
            mask=torch.from_numpy(legal[chunk]).bool()
            if q.shape[-1]!=8 or xy.shape[-1]!=256:
                raise ValueError('Unexpected E074 action representation')
            masked=q.masked_fill(~mask,-1e9)
            a=masked.argmax(1)
            chosen.extend(a.numpy().tolist())
            grid.extend(xy.argmax(1).numpy().tolist())
            values.extend(masked.max(1).values.numpy().tolist())
    return np.array(chosen),np.array(grid),np.array(values),payload


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True,type=Path)
    p.add_argument('--work',required=True,type=Path)
    p.add_argument('--per-family',type=int,default=200)
    a=p.parse_args()
    root=a.root.resolve();work=a.work.resolve()
    sys.path[:0]=[str(root/'vendor/e069/code'),str(root/'vendor/e068/code'),str(root/'code')]
    from history_ddqn import prep_data,sequence_arrays
    from source_audit import audit_source
    from e068_split import TRAIN_FAMILIES
    frozen_path=work/'E074_TRAINING_COMPLETE_FREEZE.json'
    frozen=json.loads(frozen_path.read_text())
    data=work/'trained_human/human_train_source5.npz'
    manifest=work/'trained_human/HUMAN_PRETRAIN_VERIFIED.json'
    evidence=audit_source(data,manifest)
    if frozen['human_data_sha256']!=sha(data) or evidence['kind']!='hash_locked_public_human_sessions':
        raise PermissionError('Source5 human merge not hash-verified')
    chk={m['mode']:m['sha256'] for m in frozen['models']}
    modes=('bc','ddqn','shuffled','no_history')
    if set(chk)!=set(modes):raise ValueError('Four-model freeze incomplete')
    d=prep_data(data)
    ids=choose_indices(d['family'],per_family=a.per_family)
    if not len(ids):raise ValueError('Empty source5 sample')
    seq=sequence_arrays(d)
    fam=d['family'][ids]
    human=d['action'][ids]
    legal=d['legal']
    support={i:set(d['action'][d['family']==i].astype(int).tolist()) for i in range(5)}
    out={'kind':'E074_SOURCE5_OFFLINE_ACTION_SENSITIVITY_ONLY',
         'training_provenance':evidence['kind'],
         'heldout_trajectories_accessed':False,
         'native_environment_actions_executed':0,
         'official_arc_score':None,
         'source_sha256':sha(data),
         'number_of_training_transitions':int(len(d['action'])),
         'sample_count':int(len(ids)),
         'sample_ids_sha256':hashlib.sha256(ids.tobytes()).hexdigest(),
         'sample_count_by_family':{TRAIN_FAMILIES[i]:int((fam==i).sum()) for i in range(5)},
         'mode_results':{}, 'pairwise_action_disagreement':{}}
    predictions={}
    for mode in modes:
        ck=work/f'trained_human/history_{mode}.pt'
        if sha(ck)!=chk[mode]:raise PermissionError('Checkpoint hash mismatch '+mode)
        choice,grid,qval,payload=policy_predictions(ck,ids,seq,legal)
        if not np.all(legal[ids,choice]):raise ValueError('Illegal greedy action '+mode)
        predictions[mode]=choice
        is_click=human==6
        selected_xy=d['xy'][ids][is_click]
        right_bin=(selected_xy[:,1]//4*16+selected_xy[:,0]//4).clip(0,255)
        unsupported=np.array([int(act) not in support[int(f)] for f,act in zip(fam,choice)])
        qval=np.asarray(qval)
        out['mode_results'][mode]={
            'checkpoint_sha256':chk[mode],
            'checkpoint_update_count':payload['updates'],
            'greedy_human_action_type_agreement':float(np.mean(choice==human)),
            'greedy_action_counts':dict(Counter(str(x) for x in choice.tolist())),
            'chosen_actions_outside_empirical_family_type_support':int(unsupported.sum()),
            'fraction_outside_empirical_family_type_support':float(unsupported.mean()),
            'mean_greedy_action_q':float(qval.mean()),
            'click_4x4_bin_accuracy_on_recorded_clicks':float(np.mean(grid[is_click]==right_bin)) if is_click.any() else None,
            'recorded_click_examples':int(is_click.sum()),
        }
    for left,right in (('ddqn','bc'),('ddqn','shuffled'),('ddqn','no_history')):
        diff=predictions[left]!=predictions[right]
        out['pairwise_action_disagreement'][left+'_vs_'+right]={
            'count':int(diff.sum()),'fraction':float(diff.mean()),
            'by_family':{TRAIN_FAMILIES[i]:float(diff[fam==i].mean()) if (fam==i).any() else None for i in range(5)},
        }
    target=work/'E074_OFFLINE_POLICY_PROBE.json'
    target.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
