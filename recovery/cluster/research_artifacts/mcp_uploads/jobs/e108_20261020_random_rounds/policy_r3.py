"""R3: nuisance-aware belief state for the existing learned frontier graph.
Raw observations remain available to legal-action proposals. Tiny transitions
are provisionally treated as same-state, NOT assumed to be irrelevant truth.
Reward, terminal events and retries override this approximation. No game IDs,
semantic colors, solution coordinates, saved trajectories or engine introspection.
"""
from collections import Counter
from pathlib import Path
import hashlib
import numpy as np
import policy_r2 as parent

EXPECTED_PARENT='24ed9d333af915f3cd394b75acc928102fb62098cedf25c73076d7032f941014'
if hashlib.sha256(Path(parent.__file__).read_bytes()).hexdigest()!=EXPECTED_PARENT:
    raise RuntimeError('R2 source changed')


class Agent:
    def __init__(self,seed,candidates_fn,descriptor_fn,use_memory=True):
        self.raw=None;self.belief=None
        self.candidates_fn=candidates_fn;self.descriptor_fn=descriptor_fn
        # Perception acts on the actual input; only memory keys use the belief.
        self.inner=parent.Agent(seed,self._propose,self._describe,use_memory)
        self.stats=self.inner.stats
        self.last_after=None
        self.noise_events=0

    def _propose(self,frame,legal):
        return self.candidates_fn(self.raw if self.raw is not None else frame,legal)

    def _describe(self,frame,action):
        return self.descriptor_fn(self.raw if self.raw is not None else frame,action)

    def episode_reset(self):
        self.raw=None;self.belief=None;self.last_after=None
        self.inner.episode_reset()
        self.stats['belief_retry_clears']+=1

    def decide(self,frame,legal):
        self.raw=np.asarray(frame,dtype=np.uint8).copy()
        if self.belief is None:
            self.belief=self.raw.copy()
        if self.last_after is not None and not np.array_equal(self.last_after,self.raw):
            # Never fabricate a link across an unobserved adapter reset.
            self.belief=self.raw.copy();self.inner.episode_reset()
            self.stats['unobserved_boundary_reconciled']+=1
        return self.inner.decide(self.belief,legal)

    def update(self,before,after,action,native_reward,advanced,terminal):
        before=np.asarray(before,dtype=np.uint8)
        after=np.asarray(after,dtype=np.uint8)
        if self.raw is None or not np.array_equal(before,self.raw):
            raise AssertionError('Actual action observation is not aligned')
        change=before!=after;count=int(change.sum())
        model_before=self.belief.copy()
        # Hypothesis only: 1-3 changed cells without terminal/native reward may
        # be clock animation. Full frames are retained in the evaluator.
        tiny=(0<count<=3 and not native_reward and not advanced and not terminal)
        if tiny:
            model_after=model_before.copy()
            self.stats['micro_transitions_not_new_states']+=1
            self.stats['micro_pixels_withheld']+=count
        elif count==0:
            model_after=model_before.copy()
        else:
            # Apply the observed spatial delta, not the entire frame. This keeps
            # previously withheld nuisance locations from re-entering the state.
            model_after=model_before.copy();model_after[change]=after[change]
            if native_reward or advanced or terminal:model_after=after.copy()
            self.stats['substantive_model_transitions']+=1
        self.raw=before
        result=self.inner.update(model_before,model_after,action,native_reward,advanced,terminal)
        self.belief=model_after.copy();self.last_after=after.copy();self.raw=after.copy()
        result.update({'raw_pixels':count,'micro_event_provisionally_elided':tiny,
          'belief_differs_from_observation':bool(np.any(model_after!=after)),
          'pixels':count,'hypothesis_not_a_causal_proof':True})
        if advanced:
            # Coordinate-specific evidence must not leak into the new level.
            self.inner.edges.clear();self.inner.state_actions.clear()
            self.inner.state_trials.clear();self.inner.menus.clear()
            self.stats['new_level_graph_cleared']+=1
        return result


def selftest():
    parent.selftest()
    props=lambda f,m:[(int(i),1.,'test') for i in np.flatnonzero(m)]
    desc=lambda f,i:('primitive',i)
    f=np.zeros((64,64),np.uint8);f[20:24,30:34]=8
    mask=np.zeros(4102,bool);mask[[0,1,2]]=True
    agent=Agent(3,props,desc)
    frames=[f.copy()]
    for k in range(18):
        before=frames[-1];after=before.copy();after[0,k]=4
        a,why,pred=agent.decide(before,mask)
        u=agent.update(before,after,a,0.,False,False)
        assert u['micro_event_provisionally_elided']
        frames.append(after)
    assert len(agent.inner.state_trials)==1, len(agent.inner.state_trials)
    assert agent.stats['micro_transitions_not_new_states']==18
    before=frames[-1];after=before.copy();after[20:24,30:34]=5
    a,_,_=agent.decide(before,mask)
    u=agent.update(before,after,a,0.,False,False)
    assert u['state_changed'] and not u['micro_event_provisionally_elided']
    a,_,_=agent.decide(after,mask)
    rewarded=after.copy();rewarded[9,9]=1
    u=agent.update(after,rewarded,a,1.,True,False)
    assert not u['micro_event_provisionally_elided']
    assert np.array_equal(agent.belief,rewarded)
    assert not agent.inner.edges
    agent.episode_reset();assert agent.belief is None
    # All primitive legal actions remain available; no game-based switch exists.
    print('R3_UNIT_PASS',{'microstates_collapsed':18,'reward_override_test':True,
       'new_level_graph_cleared':True})

if __name__=='__main__':selftest()
