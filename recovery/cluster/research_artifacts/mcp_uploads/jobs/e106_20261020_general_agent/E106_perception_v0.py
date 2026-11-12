#!/usr/bin/env python3
"""Generic visual click affordances; no game IDs or semantic palette constants."""
from collections import Counter
import hashlib
import numpy as np

def frame_digest(frame):
    return hashlib.blake2s(np.asarray(frame,dtype=np.uint8).tobytes(),
                           digest_size=12).hexdigest()

def candidates(frame,legal):
    """Small components, local edges, uniform coverage, all legal primitives."""
    arr=np.asarray(frame,dtype=np.uint8)
    if arr.shape!=(64,64):raise ValueError("expected public SDK 64x64 frame")
    mask=np.asarray(legal,dtype=bool)
    values,counts=np.unique(arr,return_counts=True)
    modal=int(values[np.argmax(counts)])
    visited=np.zeros((64,64),dtype=bool)
    proposals={}
    def add(x,y,score,kind):
        x,y=int(x),int(y)
        if not (0<=x<64 and 0<=y<64):return
        idx=6+64*y+x
        if idx>=len(mask) or not mask[idx]:return
        if idx not in proposals or proposals[idx][0]<score:
            proposals[idx]=(float(score),kind)
    for color in values:
        col=int(color)
        if col==modal:continue
        positions=np.argwhere(arr==col)
        if len(positions)>1300:continue
        for y,x in positions:
            y,x=int(y),int(x)
            if visited[y,x]:continue
            stack=[(y,x)];visited[y,x]=True;points=[]
            while stack:
                cy,cx=stack.pop()
                points.append((cy,cx))
                for ny,nx in ((cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)):
                    if (0<=ny<64 and 0<=nx<64 and
                        not visited[ny,nx] and arr[ny,nx]==col):
                        visited[ny,nx]=True;stack.append((ny,nx))
            if len(points)>350:continue
            center_y=sum(p[0] for p in points)/len(points)
            center_x=sum(p[1] for p in points)/len(points)
            near=min(points,key=lambda p:(p[0]-center_y)**2+(p[1]-center_x)**2)
            picks=[near,min(points,key=lambda p:p[0]),max(points,key=lambda p:p[0]),
                   min(points,key=lambda p:p[1]),max(points,key=lambda p:p[1])]
            strength=1.1 if len(points)<=96 else .52
            for yy,xx in picks:add(xx,yy,strength,"component")
    for y in range(4,64,8):
        for x in range(4,64,8):
            add(x,y,.22,"coverage")
    for y in range(2,64,8):
        for x in range(2,64,8):
            if arr[y,x]!=arr[y,min(63,x+1)] or arr[y,x]!=arr[min(63,y+1),x]:
                add(x,y,.65,"boundary")
    for i in np.flatnonzero(mask[:6]):
        proposals[int(i)]=(1.0,"primitive")
    if not proposals:
        for i in np.flatnonzero(mask)[:16]:
            proposals[int(i)]=(.08,"legal_mask_fallback")
    return [(idx,score,kind) for idx,(score,kind) in sorted(proposals.items())]

def descriptor(frame,idx):
    """Action class based on local heterogeneity, invariant to palette permutation."""
    if idx<6:return ("primitive",int(idx))
    y,x=divmod(idx-6,64)
    img=np.asarray(frame,dtype=np.uint8)
    patch=img[max(0,y-2):min(64,y+3),max(0,x-2):min(64,x+3)]
    values,counts=np.unique(patch,return_counts=True)
    homogeneity=int(4*np.mean(patch==img[y,x]))
    edge=(np.count_nonzero(patch[1:]!=patch[:-1])+
          np.count_nonzero(patch[:,1:]!=patch[:,:-1]))
    return ("click",homogeneity,min(5,len(values)),min(7,int(edge//3)))

def signature(before,after,mask):
    n=int(mask.sum())
    if n==0:return ("no_effect",)
    ys,xs=np.nonzero(mask)
    return ("effect",min(6,int(n).bit_length()-1),
            int(np.median(xs)//8),int(np.median(ys)//8))

def selftest():
    img=np.zeros((64,64),dtype=np.uint8)
    img[4:8,10:15]=2;img[25:36,41:45]=7
    for legal in (list(range(6)),list(range(6,4102)),[0,3,6+64*5+12]):
        mask=np.zeros(4102,dtype=bool);mask[legal]=True
        found=candidates(img,mask)
        assert found and all(mask[i] for i,_,_ in found),found
        assert all(len(descriptor(img,i))>=2 for i,_,_ in found)
    assert signature(img,img,np.zeros((64,64),bool))==("no_effect",)
    print("E106_PERCEPTION_SELFTEST_PASS",flush=True)
if __name__=="__main__":selftest()
