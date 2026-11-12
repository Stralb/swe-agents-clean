"""R6: shared action-feature value learning from native experience.
A compact online linear SARSA(lambda) critic ranks generic candidate actions.
It transfers observed reward/failure credit across similar local appearances
within the current game. No game ID, semantic palette label, known goal, human
trajectory or saved solution is read. E106 is the exploration policy, unchanged.
"""
from collections import Counter
from pathlib import Path
import hashlib,random
import numpy as np
from E106_online_explorer_v0 import AdaptiveExplorer
import E106_online_explorer_v0 as source

EXPECTED='9bbcb04e7f1c2c1797e878e60aceeb4150bdbd0bf5a2346bb661859682dca304'
if hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest()!=EXPECTED:
    raise RuntimeError('E106 exploration source changed')
D=4096


def feature_ids(frame,action,descriptor):
    f=np.asarray(frame,dtype=np.uint8)
    typ=int(action) if action<6 else 6
    values,counts=np.unique(f,return_counts=True)
    modal=int(values[np.argmax(counts)])
    background=int(round(float(counts.max())/f.size*8))
    keys=[('bias',typ),('appearance',descriptor),('context',typ,len(values),background)]
    if action>=6:
        y,x=divmod(int(action)-6,64)
        central=f[y,x]
        for dy in (-2,-1,0,1,2):
            for dx in (-2,-1,0,1,2):
                ny,nx=y+dy,x+dx
                if not (0<=ny<64 and 0<=nx<64):label=3
                elif f[ny,nx]==central:label=0
                elif f[ny,nx]==modal:label=1
                else:label=2
                keys.append(('patch',dy,dx,label))
        keys.append(('boundary_distance',min(x,63-x,y,63-y,4)))
    else:
        # Coarse occupancy relative to the observed modal colour, not a
        # semantic color map or a fixed object-location objective.
        patches=(f!=modal).reshape(8,8,8,8).transpose(0,2,1,3).mean((2,3))
        for y in range(8):
            for x in range(8):keys.append(('occupancy',typ,y,x,min(3,int(patches[y,x]*4))))
    return np.asarray(sorted({int.from_bytes(hashlib.blake2s(repr(k).encode(),digest_size=4).digest(),'little')%D for k in keys}),dtype=np.int64)


class Agent:
    def __init__(self,seed,candidates_fn,descriptor_fn,use_memory=True):
        self.explorer=AdaptiveExplorer(seed,'full')
        self.candidates_fn=candidates_fn;self.descriptor_fn=descriptor_fn
        self.enabled=bool(use_memory);self.stats=Counter()
        self.rng=random.Random(seed+811)
        self.weights=np.zeros(D,dtype=float);self.elig=np.zeros(D,dtype=float)
        self.pending=None;self.previous_td=None;self.started=False
        self.gamma=.97;self.lam=.8;self.alpha=.12
        self.cached_frame=None;self.cached_features={}

    def _value(self,features):return float(self.weights[features].mean())

    def _learn(self,features,reward,next_value,terminal=False):
        if not self.enabled:return
        old=self._value(features)
        delta=reward+(0. if terminal else self.gamma*next_value)-old
        self.elig*=self.gamma*self.lam
        self.elig[features]=1.
        change=self.alpha*delta*self.elig
        self.weights+=change
        self.stats['linear_td_updates']+=1
        self.stats['absolute_td_error']+=abs(delta)
        self.stats['weight_update_l1']+=float(np.abs(change).sum())
        if terminal:self.elig[:]=0

    def episode_reset(self):
        self.explorer.active=None;self.explorer.option_age=0;self.explorer.blocked=None
        self.explorer.frame_history.clear();self.explorer.cached_frame=None
        self.pending=None;self.previous_td=None;self.elig[:]=0
        self.stats['eligibility_reset_at_retry']+=1
        # Learned within-game feature weights are retained across retries.

    def decide(self,frame,legal):
        if not self.started:self.explorer.reset(frame);self.started=True
        proposed,reason,prediction=self.explorer.decide(frame,legal)
        candidates=list(self.candidates_fn(frame,legal))
        if legal[6:].any():
            possible=np.flatnonzero(legal[6:])
            for _ in range(8):
                a=6+int(possible[self.rng.randrange(len(possible))]);candidates.append((a,.1,'unrestricted'))
        menu=sorted({int(x[0]) for x in candidates if legal[int(x[0])]}|{int(proposed)})
        fs={a:feature_ids(frame,a,self.descriptor_fn(frame,a)) for a in menu}
        chosen=int(proposed);greedy=max(menu,key=lambda a:(self._value(fs[a]),-a))
        # All legal actions preserve nonzero exploration probability.
        if self.rng.random()<.05:
            types=list(map(int,np.flatnonzero(legal[:6])))
            if legal[6:].any():types.append(6)
            t=self.rng.choice(types)
            if t==6:
                p=np.flatnonzero(legal[6:]);chosen=6+int(p[self.rng.randrange(len(p))])
            else:chosen=t
            if chosen not in fs:fs[chosen]=feature_ids(frame,chosen,self.descriptor_fn(frame,chosen))
            reason='unrestricted_legal_probe'
        elif self.enabled and self._value(fs[greedy])>self._value(fs[chosen])+.015:
            chosen=greedy;reason='native_shared_value_choice'
            self.stats['learned_value_changed_decisions']+=1
        next_value=self._value(fs[chosen])
        if self.previous_td is not None:
            phi,reward=self.previous_td
            self._learn(phi,reward,next_value,False)
            self.previous_td=None
        if chosen!=proposed:
            self.explorer.active=None;self.explorer.option_age=0
            self.explorer.selection=('probe',chosen,self.explorer.prediction(chosen)[0])
            self.explorer.selected_descriptor=self.descriptor_fn(frame,chosen)
        self.pending=(chosen,fs[chosen],next_value)
        self.stats['decisions']+=1
        return chosen,reason,{'native_value_before_update':next_value,
            'learned_features':len(fs[chosen]),'exploration_proposal':int(proposed),
            'exploration_prediction':prediction}

    def update(self,before,after,action,native_reward,advanced,terminal):
        if self.pending is None or self.pending[0]!=action:raise AssertionError('SARSA transition misalignment')
        _,features,pred=self.pending
        evidence=self.explorer.update(before,after,action,native_reward,advanced)
        reward=float(native_reward)+(-.2 if terminal and not native_reward else 0.)
        if terminal or advanced:
            self._learn(features,reward,0.,True)
            self.previous_td=None
        else:self.previous_td=(features,reward)
        if advanced:
            self.stats['native_advancements']+=float(native_reward)
            self.explorer.active=None;self.explorer.blocked=None
            self.explorer.action_counts.clear();self.explorer.class_counts.clear()
            self.explorer.signatures.clear();self.explorer.visits.clear();self.explorer.cached_frame=None
        if terminal:self.stats['native_terminal_failures']+=1
        self.stats['transitions_observed']+=1
        self.pending=None
        evidence.update({'native_reward_unmodified':float(native_reward),
          'internal_failure_cost':reward-float(native_reward),
          'linear_value_learning_enabled':self.enabled,'value_at_choice':pred})
        # The last nonterminal transition at budget truncation has no next
        # sampled action and is intentionally not bootstrapped or counted.
        return evidence


def selftest():
    f=np.zeros((64,64),np.uint8);f[4:9,8:12]=2
    d=('click',2,2,1);a=6+6*64+9
    phi=feature_ids(f,a,d)
    relabeled=np.where(f==2,91,44).astype(np.uint8)
    assert np.array_equal(phi,feature_ids(relabeled,a,d))
    props=lambda f,m:[(int(i),1.,'test') for i in np.flatnonzero(m)]
    desc=lambda f,i:('primitive',i)
    learner=Agent(2,props,desc)
    features=np.asarray([10,13,17],dtype=np.int64)
    for _ in range(60):learner._learn(features,1.,0.,True)
    assert .99<learner._value(features)<=1.
    no=Agent(2,props,desc,False);no._learn(features,1.,0.,True)
    assert no.stats['linear_td_updates']==0 and not no.weights.any()
    mask=np.zeros(4102,bool);mask[[0,1,2,3]]=True
    model=Agent(4,props,desc)
    for k in range(10):
        idx,_,_=model.decide(f,mask);assert mask[idx]
        model.update(f,f,idx,0.,False,False)
    assert model.stats['linear_td_updates']==9
    idx,_,_=model.decide(f,mask);model.update(f,f,idx,1.,True,False)
    assert model.stats['native_advancements']==1
    print('R6_UNIT_PASS',{'palette_invariance':True,'TD_updates_verified':model.stats['linear_td_updates'],
      'native_reward_learning':learner._value(features),'disabled_control':True})

if __name__=='__main__':selftest()
