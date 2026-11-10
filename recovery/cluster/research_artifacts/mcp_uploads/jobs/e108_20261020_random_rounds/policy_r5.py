"""R5: infer action-conditioned object motion and explore spatial frontiers.
No game identity, goal coordinate, semantic palette label, or saved solution.
A movement model is eligible only when repeated observations support different
movement directions for different legal primitive actions. Otherwise use R4.
Predicted positions are hypotheses; obstacles are learned from actual failures.
"""
from collections import Counter,defaultdict,deque
from pathlib import Path
import hashlib
import numpy as np
import policy_r4 as parent

EXPECTED='fb1b8482deb5b56b58bf6f674fccf42731ce2969a7db5a4398e8f271599204aa'
if hashlib.sha256(Path(parent.__file__).read_bytes()).hexdigest()!=EXPECTED:
    raise RuntimeError('R4 parent changed')


def objects(frame):
    a=np.asarray(frame,dtype=np.uint8);seen=np.zeros(a.shape,bool);out=defaultdict(list)
    h,w=a.shape
    for y in range(h):
        for x in range(w):
            if seen[y,x]:continue
            color=int(a[y,x]);todo=[(y,x)];seen[y,x]=True;cells=[]
            while todo:
                yy,xx=todo.pop();cells.append((yy,xx))
                for ny,nx in ((yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)):
                    if 0<=ny<h and 0<=nx<w and not seen[ny,nx] and int(a[ny,nx])==color:
                        seen[ny,nx]=True;todo.append((ny,nx))
            if not 3<=len(cells)<=180:continue
            yy=np.array([c[0] for c in cells]);xx=np.array([c[1] for c in cells])
            rel=np.stack([yy-yy.min(),xx-xx.min()],axis=1)
            rel=rel[np.lexsort((rel[:,1],rel[:,0]))]
            shape=hashlib.blake2s(rel.astype(np.uint8).tobytes(),digest_size=6).hexdigest()
            key=(color,len(cells),shape)
            out[key].append((int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())))
    return out


class Agent:
    def __init__(self,seed,candidates_fn,descriptor_fn,use_memory=True):
        self.base=parent.Agent(seed,candidates_fn,descriptor_fn,use_memory)
        self.stats=self.base.stats;self.enabled=use_memory
        self.motion=defaultdict(Counter);self.locations=defaultdict(set)
        self.position_visits=Counter();self.attempts=Counter();self.blocked=set()
        self.graph=defaultdict(dict);self.pending=None;self.step=0
        self.cached=None;self.cached_objects={}

    def episode_reset(self):
        self.base.episode_reset();self.pending=None;self.cached=None
        # Keep within-game learned movements but reconsider obstacle hypotheses.
        self.blocked.clear();self.stats['motion_retry_preconditions_cleared']+=1

    def _objects(self,frame):
        key=hashlib.blake2s(np.asarray(frame,dtype=np.uint8).tobytes(),digest_size=8).digest()
        if key!=self.cached:
            self.cached_objects=objects(frame);self.cached=key
        return self.cached_objects

    def _model(self,parts,legal):
        best=None
        for obj,boxes in parts.items():
            if len(boxes)!=1:continue
            effects={};count=0
            for act in np.flatnonzero(legal[:6]):
                bag=self.motion[(obj,int(act))]
                if not bag:continue
                displacement,n=bag.most_common(1)[0]
                if displacement==(0,0) or n<2 or n/sum(bag.values())<.75:continue
                effects[int(act)]=displacement;count+=n
            # Exogenous motion with the same displacement under all actions
            # is insufficient evidence of controllability.
            if len(set(effects.values()))<2:continue
            position=boxes[0][:2]
            evidence=(len(effects),count,len(self.locations[obj]))
            if best is None or evidence>best[0]:best=(evidence,obj,position,effects,boxes[0])
        return best

    def _frontier(self,obj,position,effects,box):
        width=box[2]-box[0]+1;height=box[3]-box[1]+1
        queue=deque([(position,[])]);seen={position};best=None
        while queue and len(seen)<=256:
            p,path=queue.popleft()
            for act,delta in sorted(effects.items()):
                nxt=(p[0]+delta[0],p[1]+delta[1])
                if not (0<=nxt[0]<=64-width and 0<=nxt[1]<=64-height):continue
                if (obj,p,act) in self.blocked:continue
                tried=self.attempts[(obj,p,act)]
                if not tried:
                    # Head toward an untested action/position pair. This is
                    # exploration, not an invented task completion objective.
                    score=1./(1+len(path))+.1/(1+self.position_visits[(obj,nxt)])
                    candidate=(score,path+[act],nxt)
                    if best is None or candidate[0]>best[0]:best=candidate
                observed=self.graph[(obj,p)].get(act)
                if observed is not None and observed not in seen and len(path)<12:
                    seen.add(observed);queue.append((observed,path+[act]))
        self.stats['spatial_search_states']+=len(seen)
        return best

    def decide(self,frame,legal):
        proposed,reason,pred=self.base.decide(frame,legal)
        self.step+=1;self.pending=None
        # Preserve all-action exploration and allow unmodeled interactions.
        if not self.enabled or reason=='unrestricted_legal_probe' or self.step%5==0:
            return proposed,reason,pred
        parts=self._objects(frame);model=self._model(parts,legal)
        if model is None:return proposed,reason,pred
        evidence,obj,pos,effects,box=model
        plan=self._frontier(obj,pos,effects,box)
        if plan is None:return proposed,reason,pred
        _,steps,target=plan;chosen=steps[0]
        if not legal[chosen]:raise AssertionError('Spatial plan selected illegal action')
        expected=(pos[0]+effects[chosen][0],pos[1]+effects[chosen][1])
        # Keep the predecessor's learning contract aligned with the executed action.
        key=parent.state_key(self.base.base.belief)
        inner=self.base.base.inner
        nxt,confidence=inner._prediction(key,chosen)
        inner.pending=(key,chosen,self.base.base.descriptor_fn(frame,chosen),nxt)
        inner.repeat_action=None;inner.repeat_age=0;inner.route=[];inner.route_pending=False
        self.base.pending=(key,chosen)
        self.pending=(obj,pos,chosen,expected)
        self.stats['motion_model_decisions']+=1
        self.stats['motion_changed_choices']+=int(chosen!=proposed)
        self.stats['spatial_plan_length_sum']+=len(steps)
        return chosen,'online_learned_object_frontier',{'expected_position':expected,
          'object_shape':obj[2],'direction_model':effects,'lookahead':len(steps)}

    def update(self,before,after,action,native_reward,advanced,terminal):
        before_objects=self._objects(before);after_objects=objects(after)
        if action<6:
            for obj,boxes in before_objects.items():
                nextboxes=after_objects.get(obj,[])
                if len(boxes)!=1 or len(nextboxes)!=1:continue
                old=boxes[0][:2];new=nextboxes[0][:2]
                delta=(new[0]-old[0],new[1]-old[1])
                if max(abs(delta[0]),abs(delta[1]))>16:continue
                self.motion[(obj,int(action))][delta]+=1
                if delta!=(0,0):
                    self.locations[obj].add(old);self.locations[obj].add(new)
                    self.graph[(obj,old)][int(action)]=new
                    self.position_visits[(obj,new)]+=1
                    self.stats['observed_object_displacements']+=1
        if self.pending:
            obj,pos,act,expected=self.pending
            found=after_objects.get(obj,[])
            actual=found[0][:2] if len(found)==1 else None
            self.attempts[(obj,pos,act)]+=1
            self.stats['motion_predictions_checked']+=1
            if actual==expected:
                self.stats['motion_predictions_correct']+=1
                self.graph[(obj,pos)][act]=actual
            else:
                self.stats['motion_predictions_rejected']+=1
                if actual==pos:self.blocked.add((obj,pos,act))
        result=self.base.update(before,after,action,native_reward,advanced,terminal)
        result.update({'motion_prediction_checked':self.pending is not None,
          'motion_object_hypotheses':len(self.locations),'scene_source':'observations only'})
        self.pending=None;self.cached=None
        if advanced:
            self.motion.clear();self.locations.clear();self.position_visits.clear()
            self.attempts.clear();self.blocked.clear();self.graph.clear()
            self.stats['motion_new_level_reset']+=1
        return result


def selftest():
    parent.selftest()
    f=np.zeros((64,64),np.uint8);f[17:20,21:24]=7
    g=np.zeros_like(f);g[17:20,25:28]=7
    a=objects(f);b=objects(g)
    assert len(a)==1 and set(a)==set(b)
    obj=next(iter(a));assert b[obj][0][0]-a[obj][0][0]==4
    props=lambda f,m:[(int(i),1.,'test') for i in np.flatnonzero(m)]
    desc=lambda f,i:('primitive',i)
    p=Agent(1,props,desc);m=np.zeros(4102,bool);m[[0,1,2,3]]=True
    for act,d in [(0,(4,0)),(1,(-4,0)),(2,(0,4)),(3,(0,-4))]:p.motion[(obj,act)][d]=3
    model=p._model(a,m);assert model is not None
    plan=p._frontier(obj,a[obj][0][:2],model[3],a[obj][0]);assert plan
    idx,reason,pred=p.decide(f,m)
    assert reason=='online_learned_object_frontier' and m[idx]
    dx,dy=model[3][idx];h=np.zeros_like(f);h[17+dy:20+dy,21+dx:24+dx]=7
    p.update(f,h,idx,0.,False,False)
    assert p.stats['motion_predictions_correct']==1
    # Palette relabeling changes no geometric correspondence.
    recolor=np.where(f==7,2,13).astype(np.uint8)
    obj2=next(k for k in objects(recolor) if k[1]==9)
    assert obj2[2]==obj[2]
    print('R5_UNIT_PASS',{'learned_motion_verified':1,'palette_geometry_invariant':True})

if __name__=='__main__':selftest()
