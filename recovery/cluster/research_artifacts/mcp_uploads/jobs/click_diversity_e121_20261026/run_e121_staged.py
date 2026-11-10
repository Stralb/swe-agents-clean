#!/usr/bin/env python3
"""Follow-up E121 gate: retain original N117 at Level 1, expand clicks at Level 2+ only."""
import run_e121 as r
OLD=r.apply_arm
r.ARMS=r.ARMS+('l2_near2','l2_diverse2','l2_diverse3')
def apply_arm(arm):
    if arm not in ('l2_near2','l2_diverse2','l2_diverse3'):
        return OLD(arm)
    mode=arm[3:]
    def restricted(self,frame,legal):
        if getattr(self,'level',-1)<1:
            return r.ORIGINAL_CANDIDATES(self,frame,legal)
        return r.spatial_candidates(self,frame,legal,mode)
    r.original.PortableAgentCore.candidates=restricted
r.apply_arm=apply_arm
if __name__=='__main__':
    r.main()
