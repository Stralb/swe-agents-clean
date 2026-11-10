from __future__ import annotations

import itertools
import math
import re
import os
from pathlib import Path

import numpy as np
import pandas as pd

from deep_common import load_frame, write_csv, write_json


def _itemize(df: pd.DataFrame) -> tuple[list[list[str]], pd.DataFrame]:
    items_per_case=[[] for _ in range(len(df))]
    audit=[]
    for c in df.columns:
        if c in {"case_id","repo_id"}: continue
        s=df[c]; nun=int(s.nunique(dropna=True)); miss=float(s.isna().mean())
        if miss>0:
            mask=s.isna().to_numpy()
            if mask.mean()>=0.01:
                item=f"{c}::__MISSING__"
                for i in np.flatnonzero(mask): items_per_case[i].append(item)
                audit.append({"feature":c,"item":item,"kind":"missing","support":float(mask.mean())})
        if pd.api.types.is_numeric_dtype(s) and nun>2:
            x=pd.to_numeric(s,errors="coerce")
            valid=x.notna()
            if valid.sum()<30: continue
            try:
                q=pd.qcut(x[valid],q=4,duplicates="drop")
                labels=q.astype(str)
                for lab,n in labels.value_counts().items():
                    support=n/len(df)
                    if support<0.005: continue
                    item=f"{c}::Q::{lab}"
                    idx=labels.index[labels==lab]
                    for i in idx: items_per_case[i].append(item)
                    audit.append({"feature":c,"item":item,"kind":"numeric_quantile","support":support})
            except Exception: pass
        else:
            vals=s.fillna("<missing>").astype(str)
            vc=vals.value_counts()
            for val,n in vc.items():
                support=n/len(df)
                if support<0.005 or support>0.995: continue
                item=re.sub(r"\s+"," ",f"{c}::V::{val}")[:240]
                for i in vals.index[vals==val]: items_per_case[i].append(item)
                audit.append({"feature":c,"item":item,"kind":"categorical_level","support":support})
    return items_per_case,pd.DataFrame(audit)


def _eclat(transactions: list[list[str]], min_support_count: int, max_len: int=4, max_single_items: int=500, max_results: int=500000):
    tid={}
    for i,tr in enumerate(transactions):
        for item in set(tr): tid.setdefault(item,set()).add(i)
    n=max(1,len(transactions))
    singles=[(it,t) for it,t in tid.items() if len(t)>=min_support_count]
    # Generic information-content bound: favor non-degenerate items rather than only the most common ones.
    def info(pair):
        p=len(pair[1])/n
        return -(p*math.log(max(p,1e-12)) + (1-p)*math.log(max(1-p,1e-12)))
    singles=sorted(singles,key=info,reverse=True)[:max_single_items]
    # Eclat is more efficient when low-support candidates are considered first.
    singles=sorted(singles,key=lambda z:len(z[1]))
    results=[]; stopped=False
    def rec(prefix, prefix_tids, suffix, depth):
        nonlocal stopped
        if stopped:return
        for pos,(item,itids) in enumerate(suffix):
            nt=itids if prefix_tids is None else prefix_tids & itids
            if len(nt)<min_support_count: continue
            pat=prefix+(item,); results.append((pat,len(nt)))
            if len(results)>=max_results:
                stopped=True; return
            if depth<max_len:
                nxt=[]
                for item2,t2 in suffix[pos+1:]:
                    inter=nt & t2
                    if len(inter)>=min_support_count: nxt.append((item2,t2))
                if nxt: rec(pat,nt,nxt,depth+1)
                if stopped:return
    rec(tuple(),None,singles,1)
    return results,stopped


def stage_frequent_patterns(runroot: Path) -> None:
    out=runroot/"09b_frequent_patterns"; out.mkdir(parents=True,exist_ok=True)
    df=load_frame(runroot/"09_associations"/"discovery_feature_table").reset_index(drop=True)
    transactions,audit=_itemize(df); write_csv(audit,out/"itemization_audit.csv")
    n=len(df); all_rows=[]; support_maps={}; truncation=[]
    if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1":
        settings=[(0.02,2,80)]
    else:
        settings=[(0.005,2,300),(0.01,3,400),(0.02,4,500),(0.05,4,600)]
    for s,max_len,max_items in settings:
        minc=max(3,int(math.ceil(s*n)))
        pats,stopped=_eclat(transactions,minc,max_len=max_len,max_single_items=max_items,max_results=500000)
        sm={tuple(p):c/n for p,c in pats}; support_maps[s]=sm
        truncation.append({"min_support":s,"max_len":max_len,"max_items":max_items,"patterns":len(pats),"result_cap_hit":bool(stopped)})
        for p,c in pats:
            all_rows.append({"min_support_setting":s,"length":len(p),"items":" | ".join(p),"case_count":c,"support":c/n})
    freq=pd.DataFrame(all_rows); write_csv(freq.sort_values(["min_support_setting","support","length"],ascending=[True,False,False]),out/"frequent_itemsets.csv")
    # Association rules from the primary 1% frequent itemsets.
    primary_support = 0.02 if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1" else 0.01
    sm=support_maps[primary_support]; rules=[]
    for items,supp in sm.items():
        if len(items)<2: continue
        st=set(items)
        for r in range(1,len(items)):
            for ant in itertools.combinations(items,r):
                ant=tuple(sorted(ant)); cons=tuple(sorted(st-set(ant)))
                sa=sm.get(ant); sc=sm.get(cons)
                if not sa or not sc: continue
                conf=supp/sa; lift=conf/sc; leverage=supp-sa*sc; conviction=(1-sc)/(1-conf) if conf<1 else np.inf
                if conf>=0.25:
                    rules.append({"antecedent":" | ".join(ant),"consequent":" | ".join(cons),"support":supp,"confidence":conf,"lift":lift,"leverage":leverage,"conviction":conviction,"length":len(items)})
    rdf=pd.DataFrame(rules)
    if not rdf.empty: rdf=rdf.sort_values(["lift","support"],ascending=False)
    write_csv(rdf,out/"association_rules.csv")
    # Case-item sparse-ish long table for later support/generalizability/stability.
    long=[]
    for i,tr in enumerate(transactions):
        for item in tr: long.append({"case_id":df.at[i,"case_id"],"item":item})
    write_csv(pd.DataFrame(long),out/"case_items.csv")
    write_csv(pd.DataFrame(truncation),out/"mining_bounds_audit.csv")
    write_json(out/"STATUS.json",{"status":"OK","cases":n,"item_vocabulary":int(audit.item.nunique()) if not audit.empty else 0,"frequent_itemsets":len(freq),"rules":len(rdf),"settings":truncation})
