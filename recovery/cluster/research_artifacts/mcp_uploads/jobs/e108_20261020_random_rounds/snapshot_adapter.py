"""Immutable snapshots at the public ARC SDK boundary.
Fixes aliasing when a subsequent step mutates a previously returned buffer.
This copies public data only and does not alter actions, rewards or scoring.
"""
import numpy as np
from src.adapter import ArcSession as OriginalArcSession,RawFrame


def snapshot(raw):
    return RawFrame([np.array(f,copy=True) for f in raw.frames],raw.state,
        raw.levels_completed,raw.win_levels,list(raw.available_actions))


class SnapshotArcSession(OriginalArcSession):
    def _send(self,action_id,xy):
        return snapshot(super()._send(action_id,xy))
    def _reset(self):
        return snapshot(super()._reset())


def selftest():
    shared=np.zeros((64,64),dtype=np.int8)
    raw=RawFrame([shared],'NOT_FINISHED',0,7,[1,6])
    first=snapshot(raw)
    shared[5:9,12:15]=4
    second=snapshot(raw)
    assert not first.frames[0].any()
    assert (second.frames[0]==4).sum()==12
    shared[:]=7
    assert not first.frames[0].any()
    assert (second.frames[0]==4).sum()==12
    assert not np.shares_memory(first.frames[0],second.frames[0])
    assert first.available_actions==raw.available_actions
    raw.available_actions.append(7)
    assert first.available_actions==[1,6]
    print('SDK_SNAPSHOT_CONTRACT_UNIT_PASSED')
