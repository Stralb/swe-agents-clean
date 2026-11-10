#!/usr/bin/env python3
"""E106 generic online affordance/causal evidence engine; no game-specific logic.

Learns action-effect hypotheses in one episode from its OWN SDK observations.
Do not describe as a trained neural RL policy or a universal game solver.
"""
from collections import Counter,defaultdict,deque
import random
import numpy as np
from E106_perception_v0 import candidates,descriptor,signature,frame_digest

MODES=("full","no_causal","no_drift","no_transfer")

class AdaptiveExplorer:
    def __init__(self,seed=0,mode="full"):
        assert mode in MODES
        self.mode=mode;self.seed=seed;self.rng=random.Random(seed)
        self.action_counts=defaultdict(Counter)
        self.signatures=defaultdict(Counter)
        self.class_counts=defaultdict(Counter)
        self.rewards=Counter()
        self.visits=Counter()
        self.micro_history=deque(maxlen=12)
        self.frame_history=deque(maxlen=4)
        self.stats=Counter()
        self.cached_frame=None
        self.cached_proposals=[]
        self.active=None
        self.option_age=0
        self.blocked=None
        self.changed_since_blocked=False
        self.selection=None
        self.selected_descriptor=None

    def reset(self,frame):
        self.action_counts.clear()
        self.signatures.clear()
        self.class_counts.clear()
        self.rewards.clear()
        self.visits.clear()
        self.micro_history.clear()
        self.frame_history.clear()
        self.frame_history.append(np.asarray(frame,dtype=np.uint8).copy())
        self.stats.clear()
        self.cached_frame=None
        self.cached_proposals=[]
        self.active=None
        self.option_age=0
        self.blocked=None
        self.changed_since_blocked=False
        self.selection=None
        self.selected_descriptor=None

    def belief(self,index,cls):
        action=self.action_counts[index]
        group=self.class_counts[cls] if self.mode!="no_transfer" else Counter()
        good=action["effect"]+group["effect"]
        bad=action["none"]+group["none"]
        return (good+1)/(good+bad+2),good+bad

    def prediction(self,index):
        distribution=self.signatures.get(index)
        if not distribution:return None,0.
        pred,num=distribution.most_common(1)[0]
        return pred,(num+1)/(sum(distribution.values())+len(distribution)+2)

    def drift_sites(self):
        if self.mode=="no_drift":return set()
        # Background positions changing under diverse actions without
        # large state changes are not evidence of the chosen action's effect.
        sites=defaultdict(set)
        for action,locations in self.micro_history:
            for position in locations:
                sites[position].add(action)
        return {p for p,actions in sites.items() if len(actions)>=3}

    def decide(self,frame,mask):
        legal=np.asarray(mask,dtype=bool)
        if self.active is not None:
            if legal[self.active] and self.option_age<7:
                idx=self.active
                self.selection=("option",idx,self.prediction(idx)[0])
                self.selected_descriptor=descriptor(frame,idx)
                self.stats["option_decisions"]+=1
                return idx,"verify_repeatable_effect",self.prediction(idx)[0]
            self.active=None;self.option_age=0
        key=frame_digest(frame)
        if self.cached_frame!=key:
            self.cached_proposals=candidates(frame,legal)
            self.cached_frame=key
        pool=[p for p in self.cached_proposals if legal[p[0]]]
        if not pool:
            pool=candidates(frame,legal)
        if self.blocked is not None and self.changed_since_blocked and legal[self.blocked]:
            if self.blocked in [idx for idx,_,_ in pool]:
                idx=self.blocked
                self.blocked=None;self.changed_since_blocked=False
                self.selection=("retest",idx,self.prediction(idx)[0])
                self.selected_descriptor=descriptor(frame,idx)
                self.stats["retested_blocked_hypotheses"]+=1
                return idx,"test_prerequisite_reactivation",self.prediction(idx)[0]
        primitives=[v for v in pool if v[0]<6]
        clicks=[v for v in pool if v[0]>=6]
        # Respect heterogeneous legal interfaces, rather than click-only assumptions.
        if primitives and clicks:
            subset=primitives if self.stats["decisions"]%4==0 else clicks
        else:subset=pool
        self.stats["decisions"]+=1
        self.rng.shuffle(subset)
        # Descriptor predictions share evidence between VISUALLY SIMILAR
        # action opportunities, not between game names or screen coordinates.
        def utility(item):
            idx,prior,kind=item
            visits=self.visits[idx]
            cls=descriptor(frame,idx)
            p,samples=self.belief(idx,cls)
            info=4*p*(1-p)
            exploration=2.0/(1+visits)
            reuse=.75*p if self.action_counts[idx]["effect"]>0 else 0.
            if self.mode=="no_causal":reuse=0.;info=0.
            if self.mode=="no_transfer":reuse*=.8
            rewarded=1.5*self.rewards[idx]/(visits+1)
            return exploration+.45*prior+.45*info+reuse+rewarded+.03*self.rng.random()
        idx,_,kind=max(subset,key=utility)
        self.selection=("probe",idx,self.prediction(idx)[0])
        self.selected_descriptor=descriptor(frame,idx)
        self.stats["probes"]+=1
        return idx,"test_affordance_"+kind,self.prediction(idx)[0]

    def update(self,before,after,index,native_reward=0.,advanced=False):
        a=np.asarray(before,dtype=np.uint8)
        b=np.asarray(after,dtype=np.uint8)
        idx=int(index)
        change=a!=b
        raw=int(change.sum())
        # Passive-dynamics model based only on preceding independent
        # actions; current action's evidence never trains its own control.
        passive=self.drift_sites()
        effectmask=change.copy()
        if passive:
            effectmask.ravel()[list(passive)]=False
        n=int(effectmask.sum())
        result_sig=signature(a,b,effectmask)
        predicted,confidence=self.prediction(idx)
        if predicted is not None:
            self.stats["predictions_evaluated"]+=1
            self.stats["predictions_correct" if predicted==result_sig else "predictions_wrong"]+=1
        if raw>0 and raw<=3:
            coords=tuple(map(int,np.flatnonzero(change)))
            self.micro_history.append((idx,coords))
            self.stats["micro_change_actions"]+=1
        effect=bool(n>=6 or native_reward>0.)
        # Single-pixel changes are not categorically ignored: track them
        # as uncertain observations, requiring repetition before commitment.
        if effect:self.stats["significant_changes"]+=1
        else:self.stats["weak_or_no_changes"]+=1
        cls=self.selected_descriptor or descriptor(a,idx)
        self.visits[idx]+=1
        if self.mode!="no_causal":
            self.action_counts[idx]["effect" if effect else "none"]+=1
            self.signatures[idx][result_sig]+=1
            if self.mode!="no_transfer":
                self.class_counts[cls]["effect" if effect else "none"]+=1
        if native_reward>0.:
            self.rewards[idx]+=float(native_reward)
            self.stats["advancement_rewards_observed"]+=1
        if self.selection and self.selection[0]=="option":
            self.option_age+=1
            if not effect or advanced or self.option_age>=7:
                self.active=None;self.option_age=0
                self.stats["options_terminated"]+=1
                if not effect:
                    self.blocked=idx
                    self.changed_since_blocked=False
                    self.stats["blocked_hypotheses"]+=1
        elif effect and self.mode!="no_causal":
            self.active=idx;self.option_age=0
            self.stats["effect_options_started"]+=1
        if effect and self.blocked is not None and idx!=self.blocked:
            self.changed_since_blocked=True
        if advanced:
            self.active=None;self.blocked=None
            self.option_age=0;self.changed_since_blocked=False
            self.stats["stage_boundaries"]+=1
        self.frame_history.append(b.copy())
        if len(self.frame_history)>=4:self.stats["four_frame_history_seen"]+=1
        self.stats["action_transitions"]+=1
        return {"raw_changed":raw,"residual_pixels":n,
            "passive_pixel_discounted":raw-n,
            "observed_signature":list(result_sig),
            "effect_meaningful":effect,
            "prediction_made":predicted is not None,
            "prediction_correct":predicted==result_sig if predicted is not None else None,
            "evidence_count":sum(self.action_counts[idx].values()),
            "native_reward":float(native_reward)}

def selftest():
    src=np.zeros((64,64),np.uint8)
    src[5:11,10:18]=3;src[22:31,40:43]=4
    legalsets=[]
    for ids in ([0,1,4],range(6,4102),list(range(6))+list(range(6,4102))):
        m=np.zeros(4102,bool);m[list(ids)]=True;legalsets.append(m)
    for mode in MODES:
        for mask in legalsets:
            model=AdaptiveExplorer(17,mode);model.reset(src)
            for t in range(13):
                idx,why,prior=model.decide(src,mask)
                assert mask[idx],(mode,idx)
                other=src.copy()
                if t%2==0:other[5:11,10:18]=6
                rec=model.update(src,other,idx,0,False)
                assert rec["raw_changed"] in (0,48)
            assert model.stats["action_transitions"]==13
            assert model.stats["probes"]>=1
    m=AdaptiveExplorer(2);m.reset(src)
    mask=legalsets[1]
    idx,reason,pred=m.decide(src,mask)
    after=src.copy();after[5:11,10:18]=6
    ev=m.update(src,after,idx)
    assert ev["effect_meaningful"] and m.active==idx
    print("E106_GENERAL_CAUSAL_SELFTEST_PASS",{"methods":list(MODES),"actions":3*13},flush=True)
if __name__=="__main__":selftest()
