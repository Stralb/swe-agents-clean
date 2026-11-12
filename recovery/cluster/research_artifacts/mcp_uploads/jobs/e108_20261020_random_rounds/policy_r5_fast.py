"""R5 entrypoint: avoid motion extraction when only coordinate actions are legal.
This uses the observed legal mask, never a game family or game identifier.
"""
from pathlib import Path
import hashlib,numpy as np
import policy_r5 as parent
if hashlib.sha256(Path(parent.__file__).read_bytes()).hexdigest()!='3222cc66137b05fb3dadb930994c01da36a16854adffc3e4242d8c60d640e2f9':
    raise RuntimeError('R5 motion model changed')

class Agent(parent.Agent):
    def decide(self,frame,legal):
        if not np.any(legal[:6]):
            self.pending=None
            self.stats['no_primitive_mask_fast_path']+=1
            return self.base.decide(frame,legal)
        return super().decide(frame,legal)

    def update(self,before,after,action,native_reward,advanced,terminal):
        if action<6:return super().update(before,after,action,native_reward,advanced,terminal)
        if self.pending is not None:raise AssertionError('Motion plan/action mismatch')
        result=self.base.update(before,after,action,native_reward,advanced,terminal)
        self.cached=None
        result.update({'motion_prediction_checked':False,'motion_object_hypotheses':len(self.locations)})
        if advanced:
            self.motion.clear();self.locations.clear();self.position_visits.clear()
            self.attempts.clear();self.blocked.clear();self.graph.clear()
        return result

def selftest():
    parent.selftest()
    f=np.zeros((64,64),np.uint8);mask=np.zeros(4102,bool);mask[6:]=True
    props=lambda f,m:[(100,1.,'test')]
    desc=lambda f,i:('click',)
    p=Agent(2,props,desc)
    idx,reason,pred=p.decide(f,mask);assert mask[idx]
    p.update(f,f,idx,0.,False,False)
    assert p.stats['no_primitive_mask_fast_path']==1
    assert p.stats['real_td_updates']==1
    print('R5_FAST_UNIT_PASS')
if __name__=='__main__':selftest()
