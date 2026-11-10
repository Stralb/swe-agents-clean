#!/usr/bin/env python3
"""E095 structured Bayesian inverse/forward dynamics and A* prerequisite planning (game observation only).
This module reads no recorded actions, checkpoints, game source or oracle state.
"""
from __future__ import annotations
from collections import Counter,defaultdict,deque
import numpy as np,random

def components(frame):
 a=np.asarray(frame,dtype=np.uint8);seen=np.zeros((64,64),bool);out=defaultdict(list)
 for y in range(64):
  for x in range(64):
   if seen[y,x]:continue
   col=int(a[y,x]);q=[(y,x)];seen[y,x]=True;pts=[]
   while q:
    yy,xx=q.pop();pts.append((yy,xx))
    for ny,nx in ((yy+1,xx),(yy-1,xx),(yy,xx+1),(yy,xx-1)):
     if 0<=ny<64 and 0<=nx<64 and not seen[ny,nx] and a[ny,nx]==col:
      seen[ny,nx]=True;q.append((ny,nx))
   if len(pts)>180:continue
   ys=np.array([p[0] for p in pts]);xs=np.array([p[1] for p in pts])
   out[col].append(dict(n=len(pts),x=float(xs.mean()),y=float(ys.mean()),
       x0=int(xs.min()),x1=int(xs.max()),y0=int(ys.min()),y1=int(ys.max())))
 return out

def scene(frame,mask):
 a=np.asarray(frame,dtype=np.uint8)
 cp=components(a);color_candidates=[]
 for color,parts in cp.items():
  group=[q for q in parts if 3<=q['n']<=12 and q['y']>=50 and q['y0']>=48]
  if len(group)>=4 and len(group)%2==0 and max(z['y'] for z in group)-min(z['y'] for z in group)<3:
   color_candidates.append((len(group),color,group))
 color_candidates.sort(reverse=True)
 controls=[]
 if color_candidates:
  for item in color_candidates[0][2]:
   x,y=round(item['x']),round(item['y']);idx=6+y*64+x
   if idx<len(mask) and bool(mask[idx]):controls.append((idx,x,y))
 controls=sorted(set(controls),key=lambda t:t[1])
 pillars=[]
 for c,parts in cp.items():
  sticks=[v for v in parts if v['n']>=6 and v['x1']-v['x0']<=2 and v['y1']-v['y0']>=3]
  xs=sorted(set(round(v['x']) for v in sticks))
  if len(xs)>=3 and len(xs)>len(pillars):pillars=xs
 pairs=[]
 for p in pillars:
  near=[q for q in controls if abs(q[1]-p)<=3]
  if len(near)==2 and near[0][1]<p<near[1][1]:pairs.append((p,near))
 centers=[]
 if len(pillars)>=3 and controls:
  edges=[max(2,controls[0][1]-7)]+pillars+[min(62,controls[-1][1]+8)]
  if len(set(edges))==len(edges):
   centers=[round((i+j)/2) for i,j in zip(edges[:-1],edges[1:])]
 def heights(f):
  b=np.asarray(f,dtype=np.uint8)
  return tuple(int((b[3:58,x]==0).sum()) for x in centers)
 now=heights(a)
 goals=[]
 if len(now)>=4:
  target=[None]*len(now);markers=[]
  for c,parts in cp.items():
   if len(parts)!=2 or sorted(v['n'] for v in parts)!=[2,3]:continue
   moving=next(v for v in parts if v['n']==3)
   fixed=next(v for v in parts if v['n']==2)
   nearest=min(range(len(centers)),key=lambda j:abs(centers[j]-moving['x']))
   if abs(moving['x']-centers[nearest])>3 or target[nearest] is not None:continue
   target[nearest]=now[nearest]+round(moving['y']-fixed['y'])
   markers.append([c,nearest,round(moving['y']-fixed['y'])])
  proposed=tuple(0 if v is None else int(v) for v in target)
  if len(markers)>=3 and sum(proposed)==sum(now) and all(v>=0 and v%2==0 for v in proposed):
   goals.append(dict(kind='height',target=proposed,confidence=.92,evidence=markers))
 for c,parts in cp.items():
  if c in (0,3,5,7,9):continue
  good=[v for v in parts if 5<=v['n']<=60 and 5<v['y']<62]
  for i,x in enumerate(good):
   for y in good[i+1:]:
    if abs(x['x']-y['x'])<9 or not .35<=x['n']/y['n']<=3:continue
    goals.append(dict(kind='align',color=c,original_x=x['x'],reference_x=y['x'],
     offset=float(x['y']-y['y']),confidence=.15,evidence=[x['n'],y['n']]))
 goals.sort(key=lambda x:-x['confidence'])
 return dict(components=cp,controls=controls,pillars=pillars,pairs=pairs,
  centers=centers,heights=heights,now=now,goals=goals)

class ForwardInverseBayes:
 def __init__(self,memory):
  self.history=deque(maxlen=memory)
  self.forward=defaultdict(Counter);self.inverse=defaultdict(Counter)
  self.failed=defaultdict(set);self.yes=Counter();self.no=Counter()
  self.stats=Counter();self.taken=Counter()
  self.old_predictions=Counter()
 def start(self,frame):self.history.append(np.asarray(frame,dtype=np.int8).copy())
 def effect(self,before,after,action,old):
  a=np.asarray(before,dtype=np.int8);b=np.asarray(after,dtype=np.int8)
  raw=(a!=b)
  if len(self.history)>=4:
   xs=list(self.history)
   auto=np.sum([xs[i]!=xs[i-1] for i in range(1,len(xs))],axis=0)>=2
  else:auto=np.zeros(raw.shape,bool)
  n=int((raw&~auto).sum())
  start=old['heights'](a);end=old['heights'](b)
  delta=tuple(y-x for x,y in zip(start,end))
  supported=any(delta) and sum(delta)==0
  if supported:self.stats['conserved_transfers']+=1
  # A forward model over observed feature deltas; inverse P(action | delta).
  signature=delta if any(delta) else ('pix',min(10,n//16))
  known=self.forward[action]
  prior=known.most_common(1)[0][0] if known else None
  if prior is not None:self.stats['predictions_tested']+=1
  if prior is not None:self.stats['predictions_verified' if signature==prior else 'predictions_rejected']+=1
  known[signature]+=1;self.inverse[signature][action]+=1
  if n>=6:self.yes[action]+=1
  else:self.no[action]+=1
  if not any(delta):self.failed[start].add(action)
  else:self.failed[start].discard(action)
  self.taken[action]+=1
  self.history.append(b.copy())
  if len(self.history)>=4:self.stats['four_frame_updates']+=1
  if raw.sum()<=3:self.stats['microanimations_rejected']+=1
  self.stats['forward_updates']+=1;self.stats['inverse_updates']+=1
  return dict(delta=delta,effect_pixels=n,
   background_filtered_pixels=int(raw.sum())-n,
   predicted_signature=str(prior) if prior else None,
   signature=str(signature),transfer_conserved=supported)
 def predict(self,action,dims):
  counter=self.forward[action];total=sum(counter.values())
  if not total:return None,0.
  ranked=[(s,n) for s,n in counter.items() if len(s)==dims and all(isinstance(v,int) for v in s)]
  if not ranked:return None,0.
  sig,c=max(ranked,key=lambda x:x[1])
  return sig,(c+1)/(total+3)
 def uncertainty(self,action):
  y,n=self.yes[action],self.no[action];p=(y+1)/(y+n+2)
  return 4*p*(1-p)/(1+.2*(y+n))

class OnlineAgent:
 def __init__(self,mode,seed):
  self.mode=mode;self.rng=random.Random(seed+203)
  self.memory=ForwardInverseBayes(1 if mode=='no_memory' else 4)
  self.stage=None;self.stats=Counter()
  self.active=None;self.repeat_limit=0
 def reset(self,stage,frame):
  self.stage=stage;self.memory=ForwardInverseBayes(1 if self.mode=='no_memory' else 4)
  self.memory.start(frame);self.active=None;self.repeat_limit=0
  self.stats['stage_entries']+=1
 def astar_plan(self,sc,target):
  """Online A* through hypothesized causal transfers, not a cloned simulator.
  Build each abstract edge from a genuinely observed within-episode effect.
  Use 1D minimum transport distance as admissible heuristic.
  """
  import heapq
  state=tuple(sc['now']);target=tuple(target)
  if not state or len(state)!=len(target) or sum(state)!=sum(target):return None
  acts=[]
  for idx,_,_ in sc['controls']:
   counts=self.memory.forward[idx]
   valid=[(s,v) for s,v in counts.items() if len(s)==len(state) and
      all(isinstance(x,int) for x in s) and any(s) and sum(s)==0 and
      sum(abs(x) for x in s)==4]
   if not valid:continue
   move,n=max(valid,key=lambda x:x[1])
   if sum(abs(sum(move[:i])) for i in range(1,len(move)))!=2:continue
   acts.append((idx,tuple(move),(n+1)/(sum(counts.values())+3)))
  if len(acts)<2:return None
  def heuristic(a):
   total=0;balance=0
   for j in range(len(a)-1):
    balance+=target[j]-a[j]
    total+=abs(balance)//2
   return total
  todo=[(heuristic(state),0,0,state)]
  came={state:None};best={state:0};serial=0;max_depth=28
  while todo and len(best)<11000:
   f,g,_,current=heapq.heappop(todo)
   if g!=best.get(current):continue
   if current==target:
    path=[];node=current
    while came[node] is not None:
     prev,idx,delta,conf=came[node]
     path.append((idx,delta,conf))
     node=prev
    path.reverse()
    if not path:return None
    idx,delta,conf=path[0]
    self.stats['astar_paths_found']+=1
    self.stats['astar_goal_lookahead_depth_sum']+=len(path)
    return idx,{'expected':delta,'target':target,'lookahead':len(path),
      'predicted_confidence':round(conf,4)}
   if g>=max_depth:continue
   for idx,delta,conf in acts:
    if idx in self.memory.failed.get(current,set()):continue
    nxt=tuple(a+b for a,b in zip(current,delta))
    if min(nxt)<0 or max(nxt)>54:continue
    if nxt==current:continue
    nxtg=g+1
    if nxtg>=best.get(nxt,999):continue
    best[nxt]=nxtg;came[nxt]=(current,idx,delta,conf)
    serial+=1
    heapq.heappush(todo,(nxtg+heuristic(nxt),nxtg,serial,nxt))
  self.stats['astar_path_unavailable']+=1
  return None
 def choose(self,obs):
  sc=scene(obs.frame,obs.mask)
  controls=sc['controls']
  if not controls:
   # Legal candidate fallback from the pre-existing generic visual explorer
   return None,'no_structured_controls',None,sc
  current=sc['now']
  goal=sc['goals'][0] if self.mode!='no_goal' and sc['goals'] else None
  disabled=self.mode=='no_causal'
  if self.mode in ('full','no_memory') and goal and goal['kind']=='height':
   proposal=self.astar_plan(sc,goal['target'])
   if proposal is not None:
    idx,belief=proposal
    self.stats['astar_actions_executed']+=1
    return idx,'astar_prerequisite_transfer_plan',belief,sc
  options=[]
  if goal and goal['kind']=='height' and len(current)==len(goal['target']) and sc['pairs']:
   target=goal['target']
   flows=[(sum(target[:j+1])-sum(current[:j+1]))//2 for j in range(len(current)-1)]
   for j,flow in enumerate(flows):
    if not flow or j>=len(sc['pillars']):continue
    match=next((p for p in sc['pairs'] if p[0]==sc['pillars'][j]),None)
    if not match:continue
    for item in match[1]:
     idx=item[0]
     if idx in self.memory.failed.get(current,set()):continue
     delta,confidence=self.memory.predict(idx,len(current))
     if delta is not None and not disabled:
      nextstate=tuple(a+b for a,b in zip(current,delta))
      source=[k for k,x in enumerate(delta) if x<0]
      if min(nextstate)<0 or any(current[k]<-delta[k] for k in source):continue
      improve=sum(abs(a-b) for a,b in zip(current,target))-sum(abs(a-b) for a,b in zip(nextstate,target))
      if improve>0:
       options.append((100+improve*10+confidence-self.memory.taken[idx]*.02,idx,
        'verify_falsifiable_goal_operator',{'expected':delta,'target':target}))
     elif not disabled and not self.memory.forward[idx]:
      # Unknown action on a needed interface: high-value causal experiment
      options.append((60-self.memory.taken[idx],idx,'discover_goal_relevant_operator',
       {'required_boundary':j,'needed_flow':flow,'goal':target}))
   self.stats['recognized_conserved_goal']+=1
  # Weak visual alignment goal generates a test, not an assumption of success.
  if goal and goal['kind']=='align' and not disabled:
   for item in controls:
    idx=item[0]
    delta,conf=self.memory.predict(idx,len(current))
    novelty=self.memory.uncertainty(idx)
    options.append((4*novelty+3/(1+self.memory.taken[idx]),idx,
      'falsify_visible_marker_alignment',{'color':goal['color'],'offset':goal['offset']}))
  # Information-seeking exploration with Bayesian entropy over action effects.
  for item in controls:
   idx=item[0];v=self.memory.taken[idx]
   if idx in self.memory.failed.get(current,set()):continue
   bonus=1.8/(1+v)+self.memory.uncertainty(idx)
   if disabled or self.mode=='no_goal':
    bonus=1.8/(1+v)
   options.append((bonus+.04*self.rng.random(),idx,'active_causal_experiment',
    {'predicted_effect_probability':round((self.memory.yes[idx]+1)/
     (self.memory.yes[idx]+self.memory.no[idx]+2),4)}))
  if not options:
   options=[(self.rng.random(),it[0],'exhausted_preconditions_retest',None) for it in controls]
  score,idx,reason,hyp=max(options,key=lambda z:z[0])
  self.stats[reason]+=1
  return idx,reason,hyp,sc
 def observe(self,old,new,index,hyp,sc):
  result=self.memory.effect(old,new,index,sc)
  if hyp and 'expected' in hyp:
   ok=tuple(hyp['expected'])==tuple(result['delta'])
   self.stats['explicit_prediction_trials']+=1
   self.stats['explicit_prediction_success' if ok else 'explicit_prediction_failure']+=1
  return result

def selftest():
 f=np.full((64,64),3,dtype=np.int8)
 f[5:55,8:10]=0
 for x in (14,26,38,50):f[16:54,x:x+2]=5
 for x in (12,16,24,28,36,40,48,52):f[55:57,x:x+2]=9
 class O:pass
 o=O();o.frame=f;o.mask=np.zeros(4102,dtype=bool);o.mask[6:]=True
 layout=scene(o.frame,o.mask)
 assert layout['controls'] and layout['pillars']
 a=OnlineAgent('full',12);a.reset(2,f)
 idx,reason,pred,sc=a.choose(o)
 assert o.mask[idx]
 g=f.copy();g[25:35,8:10]=3
 evidence=a.observe(f,g,idx,pred,sc)
 assert a.memory.stats['forward_updates']==1
 assert a.memory.stats['inverse_updates']==1
 print('E093_CORE_SELFTEST_PASS',{'controls':len(layout['controls']),
  'pillars':layout['pillars'],'mode':reason,'evidence':evidence},flush=True)
if __name__=='__main__':selftest()
