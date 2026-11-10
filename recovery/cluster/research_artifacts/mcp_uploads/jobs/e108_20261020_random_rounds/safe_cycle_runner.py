"""Rotating random development panels with the verified immutable-frame boundary.
Snapshotting changes neither game choices nor native scoring. No existing
experiment is overwritten. All dependencies are frozen before a panel opens.
"""
from pathlib import Path
import sys,json
H=Path('/home-mscluster/astrauss')
S=H/'research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds'
sys.path[:0]=[str(H/'RL-ARC-AGI-3-Project'),str(S)]
import random_cycle_runner as cycle
import random_round_runner as base
import snapshot_adapter as capture
import src.adapter as adapter
EXTRA={
 str(S/'random_cycle_runner.py'):'75d70edce5f18da4802b1ad4f1f71ed308863b00e208c4273fceec7a049e7e44',
 str(S/'snapshot_adapter.py'):'b8c6a2ad760500ac51e7c789721c1dd4db00f28f5b09df259ef2cf6d52378d8e',
 str(S/'policy_r4.py'):'fb1b8482deb5b56b58bf6f674fccf42731ce2969a7db5a4398e8f271599204aa',
 str(S/'policy_r5.py'):'3222cc66137b05fb3dadb930994c01da36a16854adffc3e4242d8c60d640e2f9'}
base.verify(EXTRA)
adapter.ArcSession=capture.SnapshotArcSession
previous_freeze=cycle.freeze_draw

def freeze(args):
    if args.round<5:raise RuntimeError('Earlier round manifests are immutable')
    fix=json.loads((base.WORK/'round_04_immutable_frames/ROUND_RESULT.json').read_text())
    if fix['completed_trials']!=60 or fix['errors']:raise RuntimeError('Frame repair has not passed native checks')
    base.verify(EXTRA);capture.selftest()
    root,data=previous_freeze(args)
    contract={'input_observations':'deep-copied public SDK buffers',
      'prior_frame_contract_fix_verified_on_five_games':True,
      'additional_source_hashes':dict(EXTRA,**{str(Path(__file__)):base.sha(__file__)}),
      'before_any_sample_environment_created':True,
      'frame_fix_changes_no_actions_rewards_or_score_rules':True,
      'previous_round_repair_SHA256':base.sha(base.WORK/'round_04_immutable_frames/ROUND_RESULT.json')}
    path=root/'OBSERVATION_CONTRACT.json'
    if path.exists():
        if json.loads(path.read_text())!=contract:raise RuntimeError('Changed observation contract')
    else:base.write_json(path,contract)
    return root,data

base.freeze_and_draw=freeze
if __name__=='__main__':base.main()
