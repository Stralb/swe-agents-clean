"""Rerun the frozen fourth panel with immutable public SDK observations.
All original failures are retained. No policy/game/seed/budget tuning.
"""
from pathlib import Path
import json,sys
H=Path('/home-mscluster/astrauss')
S=H/'research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds'
sys.path[:0]=[str(H/'RL-ARC-AGI-3-Project'),str(S)]
import random_round_runner as base
import src.adapter as adapter
import snapshot_adapter as capture
if base.sha(base.__file__)!='fa2fc448aadd255d76fe469341485d904db85f854164e1dbbaa8d87125b5fb62':
    raise RuntimeError('Evaluator changed')
CAPTURE_SHA='b8c6a2ad760500ac51e7c789721c1dd4db00f28f5b09df259ef2cf6d52378d8e'
if base.sha(capture.__file__)!=CAPTURE_SHA:raise RuntimeError('Capture shim changed')
adapter.ArcSession=capture.SnapshotArcSession


def frozen_panel(args):
    if args.round!=4:raise ValueError('Not the fourth panel')
    old=base.WORK/'round_04'
    origin=json.loads((old/'SELECTION_FROZEN.json').read_text())
    result=json.loads((old/'ROUND_RESULT.json').read_text())
    if len(result['errors'])!=6:raise RuntimeError('Original failure record changed')
    if (origin['candidate']!=args.candidate or origin['previous']!=args.previous
        or origin['policy_seeds']!=args.seeds or origin['budget']!=args.budget):
        raise RuntimeError('Cannot change policy, game sample or settings after exposure')
    base.verify(origin['source_hashes']);capture.selftest()
    policy=base.load(S/args.candidate,'candidate_unit');policy.selftest()
    root=base.WORK/'round_04_immutable_frames';root.mkdir(parents=True,exist_ok=True)
    repaired=dict(origin)
    repaired.update({'evaluation_condition':'immutable public SDK frames',
      'harness_repair_not_new_random_draw':True,
      'original_selection_sha256':base.sha(old/'SELECTION_FROZEN.json'),
      'original_result_sha256':base.sha(old/'ROUND_RESULT.json'),
      'source_hashes':dict(origin['source_hashes'],**{str(S/'snapshot_adapter.py'):CAPTURE_SHA}),
      'repair_driver_sha256':base.sha(__file__),
      'original_errors_retained':6,'repeat_interactions_counted_as_additional_compute':True})
    lock=root/'SELECTION_FROZEN.json'
    if lock.exists():
        if json.loads(lock.read_text())!=repaired:raise RuntimeError('Conflicting repaired protocol')
    else:base.write_json(lock,repaired)
    print('IMMUTABLE_FRAME_PANEL_REPEAT',json.dumps({'games':origin['selected_games'],
      'same_policy_sources':True,'budget':args.budget,'seeds':args.seeds,
      'original_errors_retained':6,'snapshot_sha256':CAPTURE_SHA}),flush=True)
    return root,repaired


base.freeze_and_draw=frozen_panel
if __name__=='__main__':base.main()
