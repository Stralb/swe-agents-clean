"""Recompute from source-authenticated E067 and 4,256 genuine E068 native events."""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from e074_pipeline import parent_reference,sha
src=ROOT/'reference/native_source5_smoke/native_self_play_5.npz'
ref=parent_reference()
with np.load(src,allow_pickle=False) as z:
 r=z['reward'];a=z['action']; f=z['family']; pos=np.where(r>0)[0]
 positive_by_action={str(int(x)):int(r[(a==x)&(r>0)].sum()) for x in np.unique(a[pos])}
 rows=int(len(a));reward_rows=int(len(pos))
 assert int(r.sum())==3 and len(pos)==3 and rows==4256
 report={
 'decision':'NO_FURTHER_LOCAL_SPARSE_REWARD_SCALING',
 'actual_native_steps_in_E074':0,
 'actual_human_parquet_files_acquired_in_E074':0,
 'human_pretraining_completed_in_E074':False,
 'closed_prospective_games':ref['frozen_prospective_source_test_families'],
 'known_source_families_fitting_only':ref['frozen_train_families'],
 'native_self_play_steps':rows,
 'native_self_play_rewards':int(r.sum()),
 'native_self_play_reward_rows':reward_rows,
 'native_self_play_reward_action_types':positive_by_action,
 'independent_native_success_families':ref['successful_families'],
 'E071_PPO_random_level1_results':'PPO=0/15 and uniform random=0/15; frozen parent audit, not rerun E074',
 'native_self_play_sha256':sha(src),
 'human_data_dependency':'verified pinned 340-record public dataset, raw Parquet not locally accessible',
 'optimizer_smoke_test_status':'two genuinely executed updates, source-five data only, NOT human RL',
 'official_RHAE':None}
 path=ROOT/'results/E074_SOURCE_EVIDENCE.json';path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
