"""2-update BC/DDQN smoke on authentic E068 source-five native SELF-PLAY only.

Not human data. No native SDK evaluation, no claim of learned reasoning.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'vendor/e069/code'),str(ROOT/'vendor/e068/code')]
from history_ddqn import train

if __name__=='__main__':
 src=ROOT/'reference/native_source5_smoke/native_self_play_5.npz'
 out=ROOT/'results/native_smoke'
 results=[]
 for mode in ('bc','ddqn'):
  a=train(src,out,mode,updates=2,batch=16,seed=20261019)
  results.append({'mode':mode,'optimizer_updates':a['genuine_td_updates'],
    'source_provenance':a['source_provenance']['kind'],
    'native_reward_events':a['true_native_level_events'],
    'checkpoint_sha256':a['sha256']})
 (out/'E074_NATIVE_SMOKE.json').write_text(json.dumps({'synthetic':False,'human':False,
    'native_source5_only':True,'source5_full_training_has_not_been_run':True,
    'inference_or_native_evaluation_performed':False,'models':results},indent=2)+'\n')
 print(json.dumps(results,indent=2))
