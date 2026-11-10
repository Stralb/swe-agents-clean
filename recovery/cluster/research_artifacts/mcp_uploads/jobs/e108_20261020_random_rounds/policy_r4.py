"""R4: online Dyna-style native-reward and terminal-risk credit assignment.
This extends R3's generic state/frontier model; no stored trajectories, semantic
palette labels, game names or goal coordinates. Auxiliary failure cost is used
ONLY internally; benchmark rewards and scores are never altered.
"""
from collections import Counter,defaultdict,deque
from pathlib import Path
import hashlib,random
import numpy as np
import policy_r3 as parent

EXPECTED='2ca9930232d63597b77b988b833cd60f5dad0999273b327ec2792c347a9c8edd'
if hashlib.sha256(Path(parent.__file__).read_bytes()).hexdigest()!=EXPECTED:
    raise RuntimeError('R3 parent has changed')
state_key=parent.parent.state_key


class Agent:
    def __init__(self,seed,candidates_fn,descriptor_fn,use_memory=True):
        self.base=parent.Agent(seed,candidates_fn,descriptor_fn,use_memory)
        self.stats=self.base.stats;self.enabled=bool(use_memory)
        self.rng=random.Random(seed+170003)
        self.q=defaultdict(float);self.model={};self.predecessors=defaultdict(set)
        self.menus={};self.pending=None;self.keys=[];self.alpha=.35;self.gamma=.97
        self.rewarded=0;self.failures=0

    def episode_reset(self):
        self.base.episode_reset();self.pending=None
        self.stats['dyna_kept_within_game_on_retry']+=1

    def _max(self,state):
        # Unknown legal actions retain value zero: never invent an optimistic
        # high value for an unsupported click or action.
        return max([0.]+[self.q[(state,a)] for a in self.menus.get(state,())])

    def _backup(self,key):
        if key not in self.model:return
        nxt,rew,terminal=self.model[key]
        target=rew+(0. if terminal else self.gamma*self._max(nxt))
        old=self.q[key];self.q[key]+=self.alpha*(target-old)
        self.stats['model_td_backups']+=1
        self.stats['absolute_td_change']+=abs(self.q[key]-old)

    def decide(self,frame,legal):
        proposed,reason,pred=self.base.decide(frame,legal)
        key=state_key(self.base.belief)
        # Include all legal primitive actions and observed candidate clicks;
        # R3 still retains its unrestricted legal-coordinate exploration.
        menu=set(self.menus.get(key,()))
        menu.add(int(proposed));menu.update(map(int,np.flatnonzero(legal[:6])))
        self.menus[key]=tuple(sorted(a for a in menu if legal[a]))
        chosen=proposed
        if self.enabled and reason!='unrestricted_legal_probe' and self.rng.random()>.1:
            scored=[(self.q[(key,a)],a) for a in self.menus[key]]
            if scored:
                val,choice=max(scored)
                if val>self.q[(key,proposed)]+.025:
                    chosen=choice
                    expected,confidence=self.base.inner._prediction(key,chosen)
                    self.base.inner.pending=(key,chosen,self.base.descriptor_fn(frame,chosen),expected)
                    self.base.inner.repeat_action=None;self.base.inner.repeat_age=0
                    self.base.inner.route=[];self.base.inner.route_pending=False
                    reason='native_value_model_decision'
                    pred={'expected_state':expected,'confidence':confidence,
                          'learned_Q':val,'previous_choice_Q':self.q[(key,proposed)]}
                    self.stats['q_changed_actions']+=1
        self.pending=(key,int(chosen))
        return int(chosen),reason,pred

    def update(self,before,after,action,native_reward,advanced,terminal):
        if self.pending is None or self.pending[1]!=action:
            raise AssertionError('Dyna action/update misaligned')
        key=self.pending
        result=self.base.update(before,after,action,native_reward,advanced,terminal)
        nxt=state_key(self.base.belief)
        # Sparse native learning is kept distinct from survival shaping.
        failure_cost=-.2 if terminal and not native_reward else 0.
        learning_reward=float(native_reward)+failure_cost
        if key not in self.model:self.keys.append(key)
        previous=self.model.get(key)
        if previous and previous[0]!=nxt:self.stats['model_transition_revisions']+=1
        self.model[key]=(nxt,learning_reward,bool(terminal))
        self.predecessors[nxt].add(key)
        if self.enabled:
            self._backup(key);self.stats['real_td_updates']+=1
            # Propagate actual rewards and terminal failures backward through
            # previously observed transitions, not simulated game rollouts.
            queue=deque([key]);seen=set()
            while queue and len(seen)<32:
                edge=queue.popleft()
                if edge in seen:continue
                seen.add(edge);self._backup(edge)
                queue.extend(sorted(self.predecessors.get(edge[0],())))
            if self.keys:
                for _ in range(8):self._backup(self.keys[self.rng.randrange(len(self.keys))])
        if native_reward:
            self.stats['native_reward_observations']+=float(native_reward)
            self.rewarded+=1
        if failure_cost:
            self.stats['terminal_failure_observations']+=1;self.failures+=1
        result.update({'native_reward_unmodified':float(native_reward),
            'internal_terminal_cost':failure_cost,'Q_after':self.q[key],
            'model_learning_enabled':self.enabled,'neural_gradient_updates':0})
        self.pending=None
        return result


def selftest():
    parent.selftest()
    props=lambda f,m:[(int(i),1.,'test') for i in np.flatnonzero(m)]
    desc=lambda f,i:('primitive',i)
    a=Agent(7,props,desc)
    a.model[('s',0)]=('g',1.,True);a.keys=[('s',0)]
    for _ in range(20):a._backup(('s',0))
    assert .99<a.q[('s',0)]<=1.
    a.menus['s']=(0,1)
    a.model[('p',1)]=('s',0.,False)
    for _ in range(20):a._backup(('p',1))
    assert .95<a.q[('p',1)]<.98
    f=np.zeros((64,64),np.uint8);mask=np.zeros(4102,bool);mask[[0,1]]=True
    learner=Agent(42,props,desc)
    idx,why,pred=learner.decide(f,mask)
    learner.update(f,f,idx,0.,False,True)
    assert learner.stats['real_td_updates']==1
    assert learner.q[(state_key(f),idx)]<0
    untrained=Agent(42,props,desc,False)
    idx,_,_=untrained.decide(f,mask)
    untrained.update(f,f,idx,1.,True,True)
    assert untrained.stats['real_td_updates']==0
    print('R4_UNIT_PASS',{'reward_credit':a.q[('s',0)],'delayed_credit':a.q[('p',1)],
        'no_update_control_verified':True})

if __name__=='__main__':selftest()
