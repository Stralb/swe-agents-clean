"""R2: plan to under-explored states through a learned transition graph.
All edges come from this run's observed actions. No simulator rollouts,
recorded solutions, game names, fixed goal locations, or color meanings.
"""
from collections import deque
import hashlib
from pathlib import Path
import numpy as np
import policy_r1_v1 as parent

EXPECTED_PARENT='fa64f8ac36680154ba65f44694d7428e4214ffbdb0c6a4e88b19d8f7a57a116d'
if hashlib.sha256(Path(parent.__file__).read_bytes()).hexdigest()!=EXPECTED_PARENT:
    raise RuntimeError('Changed R1 parent source')
state_key=parent.state_key


class Agent(parent.Agent):
    def __init__(self,seed,candidates_fn,descriptor_fn,use_memory=True):
        super().__init__(seed,candidates_fn,descriptor_fn,use_memory)
        self.menus={}
        self.route=[]
        self.route_target=None
        self.route_pending=False

    def _pool(self,frame,legal):
        pool=super()._pool(frame,legal)
        self.menus[state_key(frame)]=tuple(p[0] for p in pool)
        return pool

    def episode_reset(self):
        super().episode_reset()
        self.route=[];self.route_target=None;self.route_pending=False

    def _frontier_value(self,key):
        menu=self.menus.get(key,())
        if not menu:return 0.
        uncertainty=sum(1/(1+self.state_actions[(key,a)])**.5 for a in menu)/len(menu)
        return .8/(1+self.state_trials[key])**.5 + .5*uncertainty

    def _route_to_frontier(self,start,legal):
        # Search only the graph observed by the current agent, not the game.
        adj={}
        for (s,a),counts in self.edges.items():
            if not counts:continue
            nxt,count=counts.most_common(1)[0]
            confidence=count/sum(counts.values())
            if nxt==s or confidence<.8:continue
            adj.setdefault(s,[]).append((a,nxt,confidence))
        queue=deque([(start,[])])
        visited={start};best=None;bestscore=.06
        origin_value=self._frontier_value(start)
        while queue and len(visited)<=256:
            key,path=queue.popleft()
            if path:
                value=(self._frontier_value(key)-origin_value)/(1+.25*len(path))
                if value>bestscore:
                    bestscore=value;best=(path,key)
            if len(path)>=6:continue
            for a,nxt,conf in sorted(adj.get(key,())):
                if not path and not legal[a]:continue
                if nxt in visited:continue
                visited.add(nxt)
                queue.append((nxt,path+[(key,a,nxt,conf)]))
        self.stats['frontier_graph_searches']+=1
        self.stats['frontier_search_states']+=len(visited)
        return best

    def decide(self,frame,legal):
        action,reason,belief=super().decide(frame,legal)
        key=state_key(frame)
        self.route_pending=False
        if not self.use_memory or reason=='unrestricted_legal_probe':
            return action,reason,belief
        if self.route and (self.route[0][0]!=key or not legal[self.route[0][1]]):
            self.route=[];self.stats['route_precondition_failures']+=1
        if not self.route and self.state_trials[key]>=3 and self.state_actions[(key,action)]>=1:
            proposal=self._route_to_frontier(key,legal)
            if proposal:
                self.route,self.route_target=proposal
                self.stats['frontier_plans_found']+=1
        if not self.route:return action,reason,belief
        source,chosen,predicted,confidence=self.route.pop(0)
        assert source==key and legal[chosen]
        self.pending=(key,chosen,self.descriptor_fn(frame,chosen),predicted)
        self.repeat_action=None;self.repeat_age=0
        self.route_pending=True
        self.stats['frontier_plan_actions']+=1
        self.stats['frontier_changed_decisions']+=int(chosen!=action)
        return chosen,'learned_graph_frontier_plan',{
            'predicted_state':predicted,'confidence':confidence,
            'target_state':self.route_target,'remaining_plan_length':len(self.route)}

    def update(self,before,after,action,native_reward,advanced,terminal):
        route_expected=self.pending[3] if self.route_pending and self.pending else None
        # Retain the learned graph over retries and earlier levels of THIS game.
        # Reset coordinate/action preferences at level boundaries, not the graph.
        result=super().update(before,after,action,native_reward,False,terminal)
        if route_expected is not None:
            matched=state_key(after)==route_expected
            self.stats['route_predictions_checked']+=1
            self.stats['route_predictions_correct' if matched else 'route_predictions_failed']+=1
            if not matched:self.route=[]
        if advanced:
            self.route=[];self.repeat_action=None;self.repeat_age=0
            self.action_trials.clear();self.action_effect.clear();self.classes.clear()
            self.rewards.clear();self.history.clear()
            self.stats['level_execution_resets']+=1
        if terminal:self.route=[]
        self.route_pending=False
        return result


def selftest():
    parent.selftest()
    props=lambda f,m:[(int(i),1.,'test') for i in np.flatnonzero(m)]
    desc=lambda f,i:('test',i)
    a=np.zeros((64,64),np.uint8);b=a.copy();b[8:16,8:16]=3
    ka,kb=state_key(a),state_key(b)
    p=Agent(5,props,desc)
    mask=np.zeros(4102,bool);mask[[0,1,2]]=True
    p.menus[ka]=(0,1,2);p.menus[kb]=(0,1,2)
    p.state_trials[ka]=12;p.state_trials[kb]=1
    for i in (0,1,2):p.state_actions[(ka,i)]=5
    p.edges[(ka,1)][kb]=3
    route=p._route_to_frontier(ka,mask)
    assert route and route[0][0][1]==1
    i,reason,pred=p.decide(a,mask)
    assert i==1 and reason=='learned_graph_frontier_plan',(i,reason)
    p.update(a,b,i,0.,False,False)
    assert p.stats['route_predictions_correct']==1
    print('R2_UNIT_PASS',{'route_actions':p.stats['frontier_plan_actions'],
                         'verified':p.stats['route_predictions_correct']})
if __name__=='__main__':selftest()
