from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import re
from collections import defaultdict, Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse, stats
from scipy.sparse import hstack, csr_matrix
from scipy.sparse.linalg import lsqr
from sklearn.metrics import mutual_info_score

from v21_common import (
    SEED, EXPECTED_CASES, REPO_SAMPLE_FRAC, assert_source_blind, bh_fdr, checkpoint,
    effective_number, feature_role, feature_root, feature_source, infer_kind, is_generated_assignment,
    load_frame, load_sparse, align_sparse_rows, now_iso, repo_block_sample_indices,
    safe_name, save_frame, write_csv, write_json,
)

def read_csv_safe(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def stage_audit(source: Path, outroot: Path) -> None:
    out = outroot / "00_audit"; out.mkdir(parents=True, exist_ok=True)
    st = assert_source_blind(source)
    required = [
        "09_associations/discovery_feature_table",
        "01_raw/cases_linkage",
        "01_raw/case_scalar_features",
        "01_raw/patch_coverage.csv",
        "05_latent_topics/sparse_registry.csv",
        "06_templates/template_groups.csv",
        "06_templates/template_members.csv",
    ]
    rows=[]
    for r in required:
        p=source/r
        exists = p.exists() or p.with_suffix(".parquet").exists() or p.with_suffix(".pkl").exists()
        rows.append({"artifact":r,"exists":bool(exists)})
        if not exists: raise RuntimeError(f"REQUIRED_SOURCE_ARTIFACT_MISSING={r}")
    cases=load_frame(source/"01_raw"/"cases_linkage")
    if len(cases)!=EXPECTED_CASES or cases.case_id.nunique()!=EXPECTED_CASES:
        raise RuntimeError(f"CASE_INVARIANT_FAIL rows={len(cases)} unique={cases.case_id.nunique()}")
    write_csv(pd.DataFrame(rows),out/"required_artifacts.csv")
    write_json(out/"SOURCE_STATUS.json",st)
    write_json(out/"V21_MANIFEST.json",{
        "method":"Full-Corpus Outcome-Blind Discovery QC v2.1",
        "created_at":now_iso(),
        "source_runroot":str(source.resolve()),
        "source_status":"PASS",
        "source_security_outcomes_read":False,
        "source_outcome_overlay_performed":False,
        "principle":"Correct statistical/representation artifacts before outcome reveal. No scanner/security outcome is read.",
    })


def _series_hash(s: pd.Series) -> str:
    # Stable content hash including missingness. pandas hashing is deterministic for primitive values.
    h = pd.util.hash_pandas_object(s, index=False, categorize=True).to_numpy(dtype=np.uint64)
    return hashlib.sha256(h.tobytes()).hexdigest()


class DSU:
    def __init__(self, items): self.p={x:x for x in items}
    def find(self,x):
        p=self.p[x]
        if p!=x: self.p[x]=self.find(p)
        return self.p[x]
    def union(self,a,b):
        ra,rb=self.find(a),self.find(b)
        if ra!=rb:self.p[rb]=ra


def stage_redundancy(source: Path, outroot: Path) -> None:
    out=outroot/"01_redundancy"; out.mkdir(parents=True,exist_ok=True)
    df=load_frame(source/"09_associations"/"discovery_feature_table")
    base_cols=[c for c in ["case_id","repo_id"] if c in df.columns]
    feats=[c for c in df.columns if c not in base_cols]

    # v2 mixed raw/objective measurements with assignments/topics/templates produced by the
    # very models being analyzed.  Those generated features are useful for decoding and as
    # stratification controls, but putting them back into generic association/pattern mining
    # creates circular "discoveries".  v2.1 therefore freezes an explicit provenance role.
    roles={c:feature_role(c) for c in feats}
    primary_feats=[c for c in feats if roles[c]=="primary_observed"]
    excluded_feats=[c for c in feats if roles[c]!="primary_observed"]

    audit=[]; hashes=defaultdict(list)
    for c in feats:
        s0=df[c]; kind=infer_kind(s0,c); nun=int(s0.nunique(dropna=True)); miss=float(s0.isna().mean())
        src=feature_source(c); root=feature_root(c); role=roles[c]
        hv=_series_hash(s0)
        if role=="primary_observed": hashes[hv].append(c)
        audit.append({"feature":c,"kind":kind,"nunique":nun,"missing_fraction":miss,
                      "source_family":src,"root":root,"analysis_role":role,"hash":hv})
    adf=pd.DataFrame(audit)

    dsu=DSU(primary_feats)
    exact_rows=[]
    for hv,cols in hashes.items():
        if len(cols)>1:
            ref=cols[0]
            for c in cols[1:]:
                if df[ref].equals(df[c]):
                    dsu.union(ref,c)
                    exact_rows.append({"a":ref,"b":c,"reason":"exact_identical","score":1.0})

    # Near-redundancy is only assessed among primary objective measurements.  Cross-view
    # agreement below near-identity is deliberately retained because it can itself be evidence.
    reps0=[]; seen=set()
    for c in primary_feats:
        r=dsu.find(c)
        if r not in seen:
            seen.add(r); reps0.append(c)
    numeric=[c for c in reps0 if infer_kind(df[c],c) in {"numeric","binary"}]
    near_rows=[]
    if numeric:
        X=df[numeric].apply(pd.to_numeric,errors="coerce")
        R=X.rank(axis=0,method="average",na_option="keep").corr(method="pearson",min_periods=100)
        vals=R.to_numpy(); roots={c:feature_root(c) for c in numeric}; srcs={c:feature_source(c) for c in numeric}
        for i,a in enumerate(numeric):
            for j in range(i+1,len(numeric)):
                rho=vals[i,j]
                if pd.isna(rho): continue
                ar=abs(float(rho)); b=numeric[j]
                redundant = ar>=0.995 or (
                    ar>=0.975 and (
                        roots[a]==roots[b]
                        or (srcs[a]==srcs[b] and roots[a].split("__")[-1]==roots[b].split("__")[-1])
                    )
                )
                if redundant:
                    dsu.union(a,b)
                    near_rows.append({"a":a,"b":b,"reason":"near_rank_identical","score":float(rho),
                                      "same_source":srcs[a]==srcs[b],"same_root":roots[a]==roots[b]})

    groups=defaultdict(list)
    for c in primary_feats: groups[dsu.find(c)].append(c)
    meta=adf.set_index("feature")
    representatives={}; group_rows=[]
    for gid,(root,cols) in enumerate(sorted(groups.items(),key=lambda z:(-len(z[1]),z[0])),1):
        def score(c):
            m=meta.loc[c]
            derived_penalty=int(str(c).startswith("template__"))+int("__sum" in c or "__min" in c or "__max" in c)
            return (1-float(m.missing_fraction),-derived_penalty,-len(c))
        rep=max(cols,key=score)
        for c in cols: representatives[c]=rep
        group_rows.append({"redundancy_group":gid,"representative":rep,"group_size":len(cols),"members":" | ".join(cols)})

    keep=[c for c in primary_feats if representatives[c]==c]
    pruned=df[base_cols+keep].copy()
    save_frame(pruned,out/"feature_table_pruned")

    adf["representative"]=adf.feature.map(representatives)
    adf["is_representative"]=adf.feature.map(lambda c: representatives.get(c)==c)
    adf["included_in_primary_discovery"]=adf.feature.isin(keep)
    write_csv(adf,out/"feature_audit.csv")
    write_csv(adf[adf.analysis_role!="primary_observed"].copy(),out/"excluded_generated_or_provenance_features.csv")
    write_csv(pd.DataFrame(group_rows),out/"redundancy_groups.csv")
    write_csv(pd.DataFrame(exact_rows+near_rows),out/"redundancy_edges.csv")
    write_json(out/"STATUS.json",{
        "status":"OK",
        "input_features":len(feats),
        "primary_observed_features":len(primary_feats),
        "excluded_generated_or_provenance_features":len(excluded_feats),
        "retained_primary_features":len(keep),
        "removed_primary_redundant_features":len(primary_feats)-len(keep),
        "redundancy_groups":len(groups),
        "exact_edges":len(exact_rows),
        "near_edges":len(near_rows),
        "excluded_role_counts":adf.loc[adf.analysis_role!="primary_observed","analysis_role"].value_counts().to_dict(),
    })


def cramers_v_corrected(a,b):
    tab=pd.crosstab(pd.Series(a),pd.Series(b))
    if tab.empty:return np.nan
    n=float(tab.to_numpy().sum()); r,k=tab.shape
    if n<=1 or r<2 or k<2:return np.nan
    try:chi2=stats.chi2_contingency(tab,correction=False)[0]
    except Exception:return np.nan
    phi2=chi2/n
    phi2corr=max(0.0,phi2-((k-1)*(r-1))/(n-1))
    rcorr=r-((r-1)**2)/(n-1); kcorr=k-((k-1)**2)/(n-1)
    den=min(kcorr-1,rcorr-1)
    return math.sqrt(phi2corr/den) if den>0 else 0.0


def eta_omega_squared(num,cat):
    x=pd.to_numeric(pd.Series(num),errors="coerce")
    c=pd.Series(cat,index=x.index)
    m=x.notna()&c.notna(); x=x[m]; c=c[m]
    n=len(x); k=int(c.nunique())
    if n<30 or k<2:return (np.nan,np.nan,n,k)
    gm=float(x.mean())
    g=x.groupby(c,observed=True)
    means=g.mean(); counts=g.size()
    ss_between=float(((means-gm)**2*counts).sum())
    ss_total=float(((x-gm)**2).sum())
    if ss_total<=0:return (0.0,0.0,n,k)
    ss_within=max(0.0,ss_total-ss_between)
    df_within=max(1,n-k)
    ms_within=ss_within/df_within
    eta2=max(0.0,min(1.0,ss_between/ss_total))
    omega2=max(0.0,(ss_between-(k-1)*ms_within)/(ss_total+ms_within))
    return (float(eta2),float(min(1.0,omega2)),n,k)


def normalized_mi(a,b,bins=10):
    sa=pd.Series(a); sb=pd.Series(b); m=sa.notna()&sb.notna(); sa=sa[m]; sb=sb[m]
    if len(sa)<30:return np.nan
    def disc(s):
        if pd.api.types.is_numeric_dtype(s) and s.nunique()>bins:
            try:return pd.qcut(pd.to_numeric(s),q=bins,duplicates="drop").astype(str)
            except Exception:return s.astype(str)
        return s.astype(str)
    aa=disc(sa); bb=disc(sb)
    mi=mutual_info_score(aa,bb); ha=mutual_info_score(aa,aa); hb=mutual_info_score(bb,bb)
    den=math.sqrt(ha*hb)
    return float(mi/den) if den>0 else 0.0


def _within_repo_centered_spearman(df,a,b):
    x=pd.to_numeric(df[a],errors="coerce"); y=pd.to_numeric(df[b],errors="coerce")
    xr=x-x.groupby(df.repo_id).transform("mean"); yr=y-y.groupby(df.repo_id).transform("mean")
    m=xr.notna()&yr.notna()
    if m.sum()<100 or xr[m].nunique()<2 or yr[m].nunique()<2:return np.nan
    return float(stats.spearmanr(xr[m],yr[m]).statistic)


def stage_associations(source: Path, outroot: Path) -> None:
    out=outroot/"02_associations"; out.mkdir(parents=True,exist_ok=True)
    df=load_frame(outroot/"01_redundancy"/"feature_table_pruned")
    feats=[c for c in df.columns if c not in {"case_id","repo_id"}]
    kinds={c:infer_kind(df[c],c) for c in feats}
    num=[c for c in feats if kinds[c] in {"numeric","binary"}]
    cat=[c for c in feats if kinds[c]=="categorical"]
    rows=[]

    if num:
        X=df[num].apply(pd.to_numeric,errors="coerce")
        rank=X.rank(axis=0,method="average",na_option="keep")
        R=rank.corr(method="pearson",min_periods=100); vals=R.to_numpy()
        V=X.notna().astype(np.int32).to_numpy(); N=V.T@V
        for i,a in enumerate(num):
            for j in range(i+1,len(num)):
                e=vals[i,j]; n=int(N[i,j]); b=num[j]
                if n<100 or pd.isna(e):continue
                metric="phi" if kinds[a]==kinds[b]=="binary" else "spearman"
                if metric=="phi":
                    xx=pd.to_numeric(df[a],errors="coerce"); yy=pd.to_numeric(df[b],errors="coerce"); m=xx.notna()&yy.notna()
                    e=float(xx[m].corr(yy[m])) if m.sum()>=100 else np.nan
                rows.append({"a":a,"b":b,"kind_a":kinds[a],"kind_b":kinds[b],"metric":metric,"effect":float(e),"effect_strength":abs(float(e)),"n":n})

    for i,a in enumerate(cat):
        for b in cat[i+1:]:
            m=df[a].notna()&df[b].notna(); n=int(m.sum())
            if n<100:continue
            e=cramers_v_corrected(df.loc[m,a],df.loc[m,b])
            if pd.notna(e):rows.append({"a":a,"b":b,"kind_a":"categorical","kind_b":"categorical","metric":"cramers_v","effect":e,"effect_strength":e,"n":n})

    for a in num:
        for b in cat:
            eta,omega,n,k=eta_omega_squared(df[a],df[b])
            if n<100 or pd.isna(omega):continue
            rows.append({"a":a,"b":b,"kind_a":kinds[a],"kind_b":"categorical","metric":"omega2","effect":omega,"effect_strength":math.sqrt(max(0.0,omega)),"eta2":eta,"omega2":omega,"category_levels":k,"n":n})

    rel=pd.DataFrame(rows)
    if rel.empty:
        write_csv(rel,out/"relationships_v21.csv");return
    rel["source_a"]=rel.a.map(feature_source); rel["source_b"]=rel.b.map(feature_source)
    rel["root_a"]=rel.a.map(feature_root); rel["root_b"]=rel.b.map(feature_root)
    rel["same_source_family"]=rel.source_a==rel.source_b
    rel["same_root"]=rel.root_a==rel.root_b
    # Near-deterministic associations are retained in the audit file but not promoted as
    # scientific discoveries: in this feature store they are overwhelmingly arithmetic/duplicate
    # measurements (e.g. a total and a count derived from the same rows).  The threshold is a
    # generic statistical guard, not a domain-specific question.
    rel["near_deterministic"]=rel.effect_strength>=0.95
    rel["mechanical_candidate"]=(rel.same_root)|(rel.near_deterministic)

    # Evaluate nonlinear agreement only for high-effect, nonmechanical candidates.
    rel["normalized_mi"]=np.nan
    idxs=rel[~rel.mechanical_candidate].nlargest(min(2000,len(rel)),"effect_strength").index
    for idx in idxs:
        r=rel.loc[idx]
        try:rel.at[idx,"normalized_mi"]=normalized_mi(df[r.a],df[r.b])
        except Exception:pass

    # Repository-centered effect for numeric pairs, which distinguishes corpus composition from within-repo association.
    rel["within_repo_effect"]=np.nan
    idxs2=rel[(rel.metric.isin(["spearman","phi"])) & (~rel.mechanical_candidate)].nlargest(min(1000,len(rel)),"effect_strength").index
    for idx in idxs2:
        r=rel.loc[idx]
        try:rel.at[idx,"within_repo_effect"]=_within_repo_centered_spearman(df,r.a,r.b)
        except Exception:pass

    # Metric-family percentiles avoid comparing eta/omega, rho, and V on raw scales.
    rel["effect_percentile"]=rel.groupby("metric")["effect_strength"].rank(pct=True)
    rel["cross_source_bonus"]=(~rel.same_source_family).astype(float)
    rel["candidate_score"]=rel.effect_percentile + 0.15*rel.cross_source_bonus + 0.15*rel.normalized_mi.fillna(0) - 1.0*rel.mechanical_candidate.astype(float)
    rel=rel.sort_values(["mechanical_candidate","candidate_score","effect_strength"],ascending=[True,False,False])
    write_csv(rel,out/"relationships_v21.csv")
    write_csv(pd.DataFrame([{"feature":c,"kind":kinds[c],"source_family":feature_source(c),"root":feature_root(c),"nunique":int(df[c].nunique(dropna=True)),"missing_fraction":float(df[c].isna().mean())} for c in feats]),out/"feature_types_v21.csv")
    write_json(out/"STATUS.json",{"status":"OK","retained_features":len(feats),"relationships":len(rel),"mechanical_candidates":int(rel.mechanical_candidate.sum()),"nonlinear_evaluated":len(idxs),"within_repo_evaluated":len(idxs2)})


def _itemize_presence(df: pd.DataFrame, type_audit: pd.DataFrame):
    kinds=type_audit.set_index("feature").kind.to_dict()
    transactions=[[] for _ in range(len(df))]
    item_rows=[]; missing_rows=[]; item_feature={}; item_tids={}
    repo=df.repo_id.to_numpy()
    n=len(df)
    for c in [x for x in df.columns if x not in {"case_id","repo_id"}]:
        kind=kinds.get(c,infer_kind(df[c],c)); s=df[c]
        miss=s.isna().to_numpy()
        if miss.mean()>=0.01:
            ridx=np.flatnonzero(miss); rc=pd.Series(repo[ridx]).value_counts()
            missing_rows.append({"feature":c,"missing_count":len(ridx),"missing_support":len(ridx)/n,"repository_count":len(rc),"top_repository_share":float(rc.iloc[0]/len(ridx)) if len(ridx) else np.nan})
        candidates=[]
        if kind=="binary":
            x=pd.to_numeric(s,errors="coerce")
            # Presence-only event itemization. The complementary zero state is deliberately not mined;
            # missingness is analyzed separately above.
            mask=(x==1).to_numpy()
            if mask.mean()>=0.005 and mask.mean()<=0.95:
                candidates.append((f"{c}::PRESENT",mask,"binary_presence"))
        elif kind=="categorical":
            vals=s.astype("object")
            vc=vals.dropna().astype(str).value_counts()
            for val,count in vc.items():
                support=count/n
                if support<0.005 or support>0.95:continue
                mask=(vals.astype(str)==str(val)).to_numpy() & vals.notna().to_numpy()
                candidates.append((f"{c}::LEVEL::{val}",mask,"categorical_level"))
        elif kind=="numeric":
            x=pd.to_numeric(s,errors="coerce"); valid=x.notna()
            if valid.sum()<100 or x[valid].nunique()<8:continue
            try:
                q=pd.qcut(x[valid],q=4,duplicates="drop")
                labels=q.astype(str)
                for lab,count in labels.value_counts().items():
                    support=count/n
                    if support<0.005 or support>0.95:continue
                    mask=np.zeros(n,dtype=bool); mask[labels.index[labels==lab].to_numpy()]=True
                    candidates.append((f"{c}::Q::{lab}",mask,"numeric_quantile"))
            except Exception:pass
        for item,mask,ikind in candidates:
            idx=np.flatnonzero(mask); rc=pd.Series(repo[idx]).value_counts()
            if len(idx)<3:continue
            top=float(rc.iloc[0]/len(idx)) if len(rc) else 1.0
            row={"item":item,"feature":c,"kind":ikind,"case_count":len(idx),"support":len(idx)/n,"repository_count":len(rc),"top_repository_share":top,"effective_repositories":effective_number(rc.values)}
            item_rows.append(row); item_feature[item]=c; item_tids[item]=set(idx.tolist())
            for i in idx:transactions[i].append(item)
    return transactions,pd.DataFrame(item_rows),pd.DataFrame(missing_rows),item_feature,item_tids


def stage_patterns(source: Path, outroot: Path) -> None:
    out=outroot/"03_patterns"; out.mkdir(parents=True,exist_ok=True)
    df=load_frame(outroot/"01_redundancy"/"feature_table_pruned").reset_index(drop=True)
    ta=pd.read_csv(outroot/"02_associations"/"feature_types_v21.csv")
    transactions,items,missing,item_feature,item_tids=_itemize_presence(df,ta)
    write_csv(items,out/"itemization_v21.csv");write_csv(missing,out/"missingness_events_separate.csv")
    if items.empty:
        write_json(out/"STATUS.json",{"status":"OK","items":0,"pairs":0});return
    # Generalizability prefilter prevents one-repository quirks from dominating the combinatorial stage.
    eligible=items[(items.support>=0.01)&(items.repository_count>=5)&(items.top_repository_share<=0.80)].copy()
    item_names=eligible.item.tolist(); index={it:j for j,it in enumerate(item_names)}
    rows=[]; cols=[]
    for i,tr in enumerate(transactions):
        for it in tr:
            j=index.get(it)
            if j is not None:rows.append(i);cols.append(j)
    X=sparse.csr_matrix((np.ones(len(rows),dtype=np.int32),(rows,cols)),shape=(len(df),len(item_names)),dtype=np.int32)
    C=(X.T@X).tocoo(); marg=np.asarray(X.sum(axis=0)).ravel().astype(float); n=len(df); minc=math.ceil(0.01*n)
    pair_rows=[]; strong_adj=defaultdict(set)
    for i,j,cnt in zip(C.row,C.col,C.data):
        if i>=j or cnt<minc:continue
        a=item_names[i];b=item_names[j]
        if item_feature[a]==item_feature[b]:continue
        p=cnt/n; pa=marg[i]/n;pb=marg[j]/n; exp=pa*pb
        if exp<=0:continue
        lift=p/exp; lev=p-exp
        pmi=math.log(max(p,1e-12)/max(exp,1e-12)); npmi=pmi/max(1e-12,-math.log(max(p,1e-12)))
        conf_ab=p/pa;conf_ba=p/pb
        tids=item_tids[a]&item_tids[b]; rc=pd.Series(df.repo_id.iloc[list(tids)].to_numpy()).value_counts() if tids else pd.Series(dtype=int)
        top=float(rc.iloc[0]/len(tids)) if len(rc) else np.nan
        z=(cnt-n*exp)/math.sqrt(max(1e-12,n*exp*(1-exp)))
        pair_rows.append({"items":f"{a} | {b}","a":a,"b":b,"length":2,"case_count":int(cnt),"support":p,"lift":lift,"leverage":lev,"npmi":npmi,"z_independence":z,"confidence_a_to_b":conf_ab,"confidence_b_to_a":conf_ba,"repository_count":len(rc),"repository_coverage":len(rc)/df.repo_id.nunique(),"top_repository_share":top})
        # Surprise-first graph for higher-order candidates. This is a statistical filter, not a domain taxonomy.
        if lift>=1.25 and lev>=0.003 and npmi>=0.10 and len(rc)>=5 and top<=0.80:
            strong_adj[a].add(b);strong_adj[b].add(a)
    pairs=pd.DataFrame(pair_rows)
    if not pairs.empty:pairs=pairs.sort_values(["npmi","leverage","support"],ascending=False)
    write_csv(pairs,out/"pair_patterns_v21.csv")

    # Enumerate only higher-order sets whose every pair already shows positive surprise. This prevents the
    # combinatorial explosion that caused v2's 500k truncation while preserving nontrivial interactions.
    higher=[]; seen3=set(); seen4=set(); nodes=sorted(strong_adj)
    for a in nodes:
        na={x for x in strong_adj[a] if x>a}
        for b in sorted(na):
            common=na & {x for x in strong_adj[b] if x>b}
            for c in sorted(common):
                tri=(a,b,c)
                if tri in seen3:continue
                seen3.add(tri)
                tids=item_tids[a]&item_tids[b]&item_tids[c]
                if len(tids)>=minc:
                    probs=[len(item_tids[x])/n for x in tri]; p=len(tids)/n; lift=p/max(1e-12,np.prod(probs))
                    rc=pd.Series(df.repo_id.iloc[list(tids)].to_numpy()).value_counts();top=float(rc.iloc[0]/len(tids)) if len(rc) else np.nan
                    higher.append({"items":" | ".join(tri),"length":3,"case_count":len(tids),"support":p,"independence_lift":lift,"repository_count":len(rc),"repository_coverage":len(rc)/df.repo_id.nunique(),"top_repository_share":top})
                common4=common & {x for x in strong_adj[c] if x>c}
                for d in sorted(common4):
                    quad=(a,b,c,d)
                    if quad in seen4:continue
                    seen4.add(quad)
                    tids=item_tids[a]&item_tids[b]&item_tids[c]&item_tids[d]
                    # Quads require 2% support to keep only broad interactions.
                    if len(tids)>=math.ceil(0.02*n):
                        probs=[len(item_tids[x])/n for x in quad]; p=len(tids)/n; lift=p/max(1e-12,np.prod(probs))
                        rc=pd.Series(df.repo_id.iloc[list(tids)].to_numpy()).value_counts();top=float(rc.iloc[0]/len(tids)) if len(rc) else np.nan
                        higher.append({"items":" | ".join(quad),"length":4,"case_count":len(tids),"support":p,"independence_lift":lift,"repository_count":len(rc),"repository_coverage":len(rc)/df.repo_id.nunique(),"top_repository_share":top})
    hdf=pd.DataFrame(higher)
    if not hdf.empty:hdf=hdf.sort_values(["independence_lift","support"],ascending=False)
    write_csv(hdf,out/"higher_order_patterns_v21.csv")

    # Closed-pattern filter across the discovered pair/triple/quad sets: remove a subset when a strict superset has identical support.
    allp=[]
    if not pairs.empty:
        for _,r in pairs.iterrows():allp.append((frozenset([r.a,r.b]),int(r.case_count),r.to_dict()))
    if not hdf.empty:
        for _,r in hdf.iterrows():allp.append((frozenset(str(r['items']).split(" | ")),int(r.case_count),r.to_dict()))
    closed=[]
    bycnt=defaultdict(list)
    for s,c,r in allp:bycnt[c].append((s,r))
    for c,ls in bycnt.items():
        for s,r in ls:
            if any(s<t for t,_ in ls):continue
            rr=dict(r);rr["closed"]=True;closed.append(rr)
    cdf=pd.DataFrame(closed)
    if not cdf.empty:
        npmi_term = cdf.get("npmi", pd.Series(0.0, index=cdf.index)).fillna(0.0)
        lift_term = cdf.get("independence_lift", pd.Series(np.nan, index=cdf.index))
        if "lift" in cdf.columns:
            lift_term = lift_term.fillna(cdf["lift"])
        lift_term = lift_term.fillna(0.0).clip(lower=0.0)
        score = npmi_term + 0.25 * np.log1p(lift_term) + cdf["support"].fillna(0.0)
        cdf["surprise_score"]=score
        cdf=cdf.sort_values(["surprise_score","support"],ascending=False)
    write_csv(cdf,out/"closed_patterns_v21.csv")
    write_json(out/"STATUS.json",{"status":"OK","raw_items":len(items),"eligible_items":len(item_names),"pair_patterns":len(pairs),"strong_pair_edges":int(sum(len(v) for v in strong_adj.values())/2),"triple_candidates":len(seen3),"quad_candidates":len(seen4),"higher_patterns":len(hdf),"closed_patterns":len(cdf),"result_cap_used":False})


def _registry_map(source: Path):
    p=source/"05_latent_topics"/"sparse_registry.csv"
    reg=pd.read_csv(p)
    return {str(r.view):Path(str(r.base)) for _,r in reg.iterrows() if pd.notna(r.get("base"))}


def _presence_csc(source: Path, base: Path, base_ids: np.ndarray):
    X,ids,features,meta=load_sparse(base)
    X=align_sparse_rows(base_ids,ids,X)
    X=(X>0).astype(np.int8).tocsc()
    return X, list(map(str,features or [])), meta


def _repo_stats(indices: np.ndarray, repos: np.ndarray):
    if len(indices)==0:return 0,np.nan,0.0
    vc=pd.Series(repos[indices]).value_counts()
    return int(len(vc)),float(vc.iloc[0]/len(indices)),effective_number(vc.values)


def _paired_sparse_asymmetry(source:Path, base_ids, repos, reg, view_a,view_d):
    if view_a not in reg or view_d not in reg:return pd.DataFrame()
    A,fa,_=_presence_csc(source,reg[view_a],base_ids);D,fd,_=_presence_csc(source,reg[view_d],base_ids)
    ma={f:i for i,f in enumerate(fa)};md={f:i for i,f in enumerate(fd)}
    total_add=float(A.nnz); total_del=float(D.nnz); baseline_add=total_add/max(1.0,total_add+total_del)
    baseline_log2=math.log2((total_add+0.5)/(total_del+0.5))
    rows=[]
    for f in set(ma).intersection(md):
        ia,idd=ma[f],md[f]
        ca=A.indptr[ia+1]-A.indptr[ia];cd=D.indptr[idd+1]-D.indptr[idd]
        if ca+cd<20:continue
        ai=A.indices[A.indptr[ia]:A.indptr[ia+1]];di=D.indices[D.indptr[idd]:D.indptr[idd+1]]
        both=np.intersect1d(ai,di,assume_unique=True).size
        ao=int(ca-both);do=int(cd-both);disc=ao+do
        if disc<10:continue
        # Compare against the representation-wide add/delete exposure, not a naive 50/50 null.
        occ=int(ca+cd)
        p=float(stats.binomtest(int(ca),occ,p=baseline_add,alternative="two-sided").pvalue) if occ else np.nan
        log2odds=float(math.log2((ao+0.5)/(do+0.5)))
        relative_log2=float(math.log2((ca+0.5)/(cd+0.5))-baseline_log2)
        union=np.union1d(ai,di);rc,top,eff=_repo_stats(union,repos)
        rows.append({"feature":f,"add_view":view_a,"del_view":view_d,"add_cases":int(ca),"del_cases":int(cd),"both_cases":int(both),"add_only":ao,"del_only":do,"discordant":disc,"log2_add_delete_odds":log2odds,"relative_log2_add_delete_odds":relative_log2,"baseline_add_presence":baseline_add,"p_value":p,"repository_count":rc,"top_repository_share":top,"effective_repositories":eff})
    x=pd.DataFrame(rows)
    if not x.empty:
        x["fdr_q"]=bh_fdr(x.p_value.to_numpy(float));x["abs_log2_odds"]=x.log2_add_delete_odds.abs();x["abs_relative_log2_odds"]=x.relative_log2_add_delete_odds.abs()
        x=x.sort_values(["fdr_q","abs_relative_log2_odds","repository_count"],ascending=[True,False,False])
    return x


def _transfer_sparse(source:Path,base_ids,repos,reg,src_view,tgt_view):
    if src_view not in reg or tgt_view not in reg:return pd.DataFrame()
    S,fs,_=_presence_csc(source,reg[src_view],base_ids);T,ft,_=_presence_csc(source,reg[tgt_view],base_ids)
    ms={f:i for i,f in enumerate(fs)};mt={f:i for i,f in enumerate(ft)};n=len(base_ids);rows=[]
    for f in set(ms).intersection(mt):
        i,j=ms[f],mt[f];cs=S.indptr[i+1]-S.indptr[i];ct=T.indptr[j+1]-T.indptr[j]
        if cs<10 or ct<10 or cs>0.6*n or ct>0.6*n:continue
        si=S.indices[S.indptr[i]:S.indptr[i+1]];ti=T.indices[T.indptr[j]:T.indptr[j+1]]
        both=int(np.intersect1d(si,ti,assume_unique=True).size)
        if both<max(5,math.ceil(0.005*n)):continue
        ps=cs/n;pt=ct/n;pij=both/n;lift=pij/(ps*pt)
        pmi=math.log(max(pij,1e-12)/max(ps*pt,1e-12));npmi=pmi/max(1e-12,-math.log(pij))
        rc,top,eff=_repo_stats(np.intersect1d(si,ti,assume_unique=True),repos)
        if rc<5:continue
        # Standardized independence residual; later ranking uses this with lift/support/repository spread.
        exp=n*ps*pt;z=(both-exp)/math.sqrt(max(1e-12,exp*(1-ps*pt)))
        rows.append({"feature":f,"source_view":src_view,"target_view":tgt_view,"source_cases":int(cs),"target_cases":int(ct),"joint_cases":both,"joint_support":pij,"lift":lift,"npmi":npmi,"z_independence":z,"repository_count":rc,"top_repository_share":top,"effective_repositories":eff})
    x=pd.DataFrame(rows)
    if not x.empty:x=x.sort_values(["npmi","lift","joint_support"],ascending=False)
    return x


def _call_sets(texts):
    # Generic callee-shape extraction. This is syntax extraction, not a semantic API list.
    call_re=re.compile(r"(?<![A-Za-z0-9_$])([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*){0,3})\s*\(")
    syntax_words={"if","for","while","switch","catch","function","return","typeof","sizeof","new"}
    out=[]
    for txt in texts:
        vals=set()
        for m in call_re.finditer(str(txt or "")):
            c=m.group(1)
            if c.lower() in syntax_words:continue
            vals.add(c)
        out.append(vals)
    return out


def _call_asymmetry(adds, dels, repos):
    amap=defaultdict(set); dmap=defaultdict(set)
    for i,ss in enumerate(adds):
        for f in ss: amap[f].add(i)
    for i,ss in enumerate(dels):
        for f in ss: dmap[f].add(i)
    total_add=float(sum(len(z) for z in adds)); total_del=float(sum(len(z) for z in dels))
    baseline_add=total_add/max(1.0,total_add+total_del)
    baseline_log2=math.log2((total_add+0.5)/(total_del+0.5))
    rows=[]
    for f in set(amap)|set(dmap):
        ai=amap.get(f,set()); di=dmap.get(f,set()); both=len(ai&di); ao=len(ai-di); do=len(di-ai); disc=ao+do
        if len(ai)+len(di)<20 or disc<10: continue
        occ=len(ai)+len(di)
        p=float(stats.binomtest(len(ai),occ,p=baseline_add).pvalue) if occ else np.nan
        log2odds=math.log2((ao+.5)/(do+.5))
        relative_log2=math.log2((len(ai)+.5)/(len(di)+.5))-baseline_log2
        union=np.asarray(sorted(ai|di),dtype=int); rc,top,eff=_repo_stats(union,np.asarray(repos))
        rows.append({"callee":f,"add_cases":len(ai),"del_cases":len(di),"both_cases":both,"add_only":ao,"del_only":do,
                     "log2_add_delete_odds":log2odds,"relative_log2_add_delete_odds":relative_log2,
                     "baseline_add_presence":baseline_add,"p_value":p,"repository_count":rc,
                     "top_repository_share":top,"effective_repositories":eff})
    x=pd.DataFrame(rows)
    if not x.empty:
        x["fdr_q"]=bh_fdr(x.p_value.to_numpy(float)); x["abs_log2_odds"]=x.log2_add_delete_odds.abs();
        x["abs_relative_log2_odds"]=x.relative_log2_add_delete_odds.abs();
        x=x.sort_values(["fdr_q","abs_relative_log2_odds","repository_count"],ascending=[True,False,False])
    return x



def _cross_view_transition_motifs(source:Path,base_ids,repos,reg,del_view,add_view,max_features=2500):
    if del_view not in reg or add_view not in reg:return pd.DataFrame()
    D,fd,_=_presence_csc(source,reg[del_view],base_ids);A,fa,_=_presence_csc(source,reg[add_view],base_ids);n=len(base_ids)
    cd=np.asarray(D.sum(axis=0)).ravel();ca=np.asarray(A.sum(axis=0)).ravel()
    def choose(counts,feats):
        cand=[]
        for i,c in enumerate(counts):
            p=c/n
            if c>=max(5,math.ceil(.005*n)) and p<=.5:
                info=-(p*math.log(max(p,1e-12))+(1-p)*math.log(max(1-p,1e-12)))
                cand.append((info,i))
        return [i for _,i in sorted(cand,reverse=True)[:max_features]]
    di=choose(cd,fd);ai=choose(ca,fa)
    if not di or not ai:return pd.DataFrame()
    Ds=D[:,di].astype(np.int32).tocsr();As=A[:,ai].astype(np.int32).tocsr();C=(Ds.T@As).tocoo();minc=math.ceil(.005*n);raw=[]
    for ii,jj,cnt in zip(C.row,C.col,C.data):
        if cnt<minc:continue
        fdel=fd[di[ii]];fadd=fa[ai[jj]]
        if str(fdel)==str(fadd):continue
        pdv=cd[di[ii]]/n;pav=ca[ai[jj]]/n;pij=cnt/n;exp=pdv*pav
        if exp<=0:continue
        lift=pij/exp;pmi=math.log(max(pij,1e-12)/max(exp,1e-12));npmi=pmi/max(1e-12,-math.log(pij))
        if lift<1.5 or npmi<.10:continue
        raw.append((npmi,lift,int(cnt),ii,jj,fdel,fadd,pij))
    raw=sorted(raw,reverse=True)[:3000];rows=[]
    Dc=Ds.tocsc();Ac=As.tocsc()
    for npmi,lift,cnt,ii,jj,fdel,fadd,pij in raw:
        dx=Dc.indices[Dc.indptr[ii]:Dc.indptr[ii+1]];ax=Ac.indices[Ac.indptr[jj]:Ac.indptr[jj+1]];joint=np.intersect1d(dx,ax,assume_unique=True)
        rc,top,eff=_repo_stats(joint,repos)
        if rc<5 or top>.8:continue
        rows.append({"deleted_feature":fdel,"added_feature":fadd,"del_view":del_view,"add_view":add_view,"case_count":cnt,"support":pij,"lift":lift,"npmi":npmi,"repository_count":rc,"top_repository_share":top,"effective_repositories":eff})
    return pd.DataFrame(rows).sort_values(["npmi","lift","repository_count"],ascending=False) if rows else pd.DataFrame()


def _path_cochange_surprises(source:Path,base_ids,repos,reg):
    view="paths__path_items_binary"
    if view not in reg:return pd.DataFrame()
    X,feats,_=_presence_csc(source,reg[view],base_ids);n=len(base_ids);cnt=np.asarray(X.sum(axis=0)).ravel()
    sel=[]
    for i,c in enumerate(cnt):
        p=c/n
        if c>=math.ceil(.01*n) and p<=.5:
            info=-(p*math.log(max(p,1e-12))+(1-p)*math.log(max(1-p,1e-12)))
            sel.append((info,i))
    sel=[i for _,i in sorted(sel,reverse=True)[:3000]]
    if len(sel)<2:return pd.DataFrame()
    S=X[:,sel].astype(np.int32).tocsr();C=(S.T@S).tocoo();minc=math.ceil(.01*n);raw=[]
    for ii,jj,c in zip(C.row,C.col,C.data):
        if ii>=jj or c<minc:continue
        pa=cnt[sel[ii]]/n;pb=cnt[sel[jj]]/n;pij=c/n;exp=pa*pb
        if exp<=0:continue
        lift=pij/exp;pmi=math.log(max(pij,1e-12)/max(exp,1e-12));npmi=pmi/max(1e-12,-math.log(pij))
        if lift>=1.5 and npmi>=.10:raw.append((npmi,lift,int(c),ii,jj,pij))
    raw=sorted(raw,reverse=True)[:3000];Sc=S.tocsc();rows=[]
    for npmi,lift,c,ii,jj,pij in raw:
        ia=Sc.indices[Sc.indptr[ii]:Sc.indptr[ii+1]];ib=Sc.indices[Sc.indptr[jj]:Sc.indptr[jj+1]];joint=np.intersect1d(ia,ib,assume_unique=True)
        rc,top,eff=_repo_stats(joint,repos)
        if rc<5 or top>.8:continue
        rows.append({"path_item_a":feats[sel[ii]],"path_item_b":feats[sel[jj]],"case_count":c,"support":pij,"lift":lift,"npmi":npmi,"repository_count":rc,"top_repository_share":top,"effective_repositories":eff})
    return pd.DataFrame(rows).sort_values(["npmi","lift","repository_count"],ascending=False) if rows else pd.DataFrame()

def stage_motifs(source: Path, outroot: Path) -> None:
    out=outroot/"04_motifs";out.mkdir(parents=True,exist_ok=True)
    cases=load_frame(source/"01_raw"/"cases_linkage");base_ids=cases.case_id.to_numpy();repos=cases.repo_id.to_numpy();reg=_registry_map(source)
    asym=[]
    pairings=[
        ("patch__patch_add_raw__word","patch__patch_del_raw__word"),
        ("patch__patch_add_norm_tfidf","patch__patch_del_norm_tfidf"),
        ("syntax__syntax_add_tfidf","syntax__syntax_del_tfidf"),
    ]
    for a,d in pairings:
        x=_paired_sparse_asymmetry(source,base_ids,repos,reg,a,d)
        if not x.empty:asym.append(x)
    asymdf=pd.concat(asym,ignore_index=True) if asym else pd.DataFrame();write_csv(asymdf,out/"add_delete_motif_asymmetry.csv")

    # Patch-coverage sensitivity: code-level effects should persist after excluding incomplete stored diffs.
    cov_path=source/"01_raw"/"patch_coverage.csv"
    high_asym=[]
    high_mask=np.ones(len(base_ids),dtype=bool)
    if cov_path.exists():
        cov=pd.read_csv(cov_path).set_index("case_id")
        ratios=np.asarray([cov.patch_line_coverage_ratio.get(int(cid),np.nan) for cid in base_ids],dtype=float)
        high_mask=np.isfinite(ratios)&(ratios>=0.80)
        high_ids=base_ids[high_mask];high_repos=repos[high_mask]
        for a,d in pairings:
            x=_paired_sparse_asymmetry(source,high_ids,high_repos,reg,a,d)
            if not x.empty:
                x=x.rename(columns={"log2_add_delete_odds":"highcov_log2_add_delete_odds","relative_log2_add_delete_odds":"highcov_relative_log2_add_delete_odds","fdr_q":"highcov_fdr_q","add_cases":"highcov_add_cases","del_cases":"highcov_del_cases","both_cases":"highcov_both_cases","repository_count":"highcov_repository_count","top_repository_share":"highcov_top_repository_share"})
                high_asym.append(x[[c for c in ["feature","add_view","del_view","highcov_log2_add_delete_odds","highcov_relative_log2_add_delete_odds","highcov_fdr_q","highcov_add_cases","highcov_del_cases","highcov_both_cases","highcov_repository_count","highcov_top_repository_share"] if c in x.columns]])
    if high_asym and not asymdf.empty:
        ha=pd.concat(high_asym,ignore_index=True)
        asymdf=asymdf.merge(ha,on=["feature","add_view","del_view"],how="left")
        asymdf["coverage_effect_same_direction"]=np.sign(asymdf.relative_log2_add_delete_odds)==np.sign(asymdf.highcov_relative_log2_add_delete_odds)
        write_csv(asymdf,out/"add_delete_motif_asymmetry.csv")

    transfers=[]
    transfer_pairs=[
        ("text__issue_body__word","patch__patch_add_raw__word"),
        ("text__pr_body__word","patch__patch_add_raw__word"),
        ("text__issue_title__word","paths__path_token_tfidf"),
        ("text__issue_body__word","paths__path_token_tfidf"),
        ("text__pr_body__word","paths__path_token_tfidf"),
    ]
    for s,t in transfer_pairs:
        x=_transfer_sparse(source,base_ids,repos,reg,s,t)
        if not x.empty:transfers.append(x)
    tdf=pd.concat(transfers,ignore_index=True) if transfers else pd.DataFrame();write_csv(tdf,out/"cross_artifact_token_transfer.csv")

    # Direct call-shape motifs from added vs deleted patch text.
    calls=pd.DataFrame()
    try:
        docs=load_frame(source/"03_views"/"patch"/"patch_documents")
        if not np.array_equal(docs.case_id.to_numpy(),base_ids):
            docs=cases[["case_id"]].merge(docs,on="case_id",how="left")
        adds=_call_sets(docs.add_raw.fillna("").tolist()); dels=_call_sets(docs.del_raw.fillna("").tolist())
        calls=_call_asymmetry(adds,dels,repos)
        # Repeat on high-coverage stored diffs.  A call-shape candidate is promoted only if its
        # direction survives this sensitivity analysis when coverage information is available.
        if high_mask.sum()>=100:
            hidx=np.flatnonzero(high_mask)
            hcalls=_call_asymmetry([adds[i] for i in hidx],[dels[i] for i in hidx],repos[hidx])
            if not hcalls.empty and not calls.empty:
                hcalls=hcalls.rename(columns={
                    "relative_log2_add_delete_odds":"highcov_relative_log2_add_delete_odds",
                    "fdr_q":"highcov_fdr_q",
                    "add_cases":"highcov_add_cases",
                    "del_cases":"highcov_del_cases",
                    "both_cases":"highcov_both_cases",
                    "repository_count":"highcov_repository_count",
                    "top_repository_share":"highcov_top_repository_share",
                })
                keep=[c for c in ["callee","highcov_relative_log2_add_delete_odds","highcov_fdr_q",
                                  "highcov_add_cases","highcov_del_cases","highcov_both_cases",
                                  "highcov_repository_count","highcov_top_repository_share"] if c in hcalls.columns]
                calls=calls.merge(hcalls[keep],on="callee",how="left")
                calls["coverage_effect_same_direction"]=np.sign(calls.relative_log2_add_delete_odds)==np.sign(calls.highcov_relative_log2_add_delete_odds)
    except Exception as exc:
        write_json(out/"CALL_EXTRACTION_ERROR.json",{"error":repr(exc)})
    write_csv(calls,out/"call_shape_asymmetry.csv")

    # Standalone interpretable motif prevalence for added code/syntax/path items.
    prev=[]
    for view in ["patch__patch_add_raw__word","patch__patch_add_norm_tfidf","syntax__syntax_add_tfidf","paths__path_items_binary"]:
        if view not in reg:continue
        X,feats,_=_presence_csc(source,reg[view],base_ids);counts=np.diff(X.indptr).astype(int) if False else np.asarray(X.sum(axis=0)).ravel().astype(int)
        # NOTE X is CSC; sum(axis=0) is document frequency because X is binary.
        for j,cnt in enumerate(counts):
            if cnt<max(5,math.ceil(.005*len(base_ids))) or cnt>.8*len(base_ids):continue
            idx=X.indices[X.indptr[j]:X.indptr[j+1]];rc,top,eff=_repo_stats(idx,repos)
            if rc<3:continue
            p=cnt/len(base_ids);info=-(p*math.log(max(p,1e-12))+(1-p)*math.log(max(1-p,1e-12)))
            prev.append({"view":view,"feature":feats[j],"case_count":int(cnt),"support":p,"repository_count":rc,"top_repository_share":top,"effective_repositories":eff,"information":info})
    pdf=pd.DataFrame(prev)
    if not pdf.empty:pdf=pdf.sort_values(["information","repository_count","case_count"],ascending=False)
    write_csv(pdf,out/"interpretable_motif_prevalence.csv")
    transitions=[]
    for dv,av in [("patch__patch_del_raw__word","patch__patch_add_raw__word"),("patch__patch_del_norm_tfidf","patch__patch_add_norm_tfidf"),("syntax__syntax_del_tfidf","syntax__syntax_add_tfidf")]:
        x=_cross_view_transition_motifs(source,base_ids,repos,reg,dv,av)
        if not x.empty:transitions.append(x)
    transdf=pd.concat(transitions,ignore_index=True) if transitions else pd.DataFrame();write_csv(transdf,out/"edit_transition_motifs.csv")
    pathdf=_path_cochange_surprises(source,base_ids,repos,reg);write_csv(pathdf,out/"path_cochange_surprises.csv")
    write_json(out/"STATUS.json",{"status":"OK","asymmetry_rows":len(asymdf),"transfer_rows":len(tdf),"call_rows":len(calls),"prevalence_rows":len(pdf),"edit_transition_rows":len(transdf),"path_cochange_rows":len(pathdf)})


def stage_templates(source: Path, outroot: Path) -> None:
    out=outroot/"05_template_decoding";out.mkdir(parents=True,exist_ok=True)
    groups=pd.read_csv(source/"06_templates"/"template_groups.csv");members=pd.read_csv(source/"06_templates"/"template_members.csv")
    cases=load_frame(source/"01_raw"/"cases_linkage");base_ids=cases.case_id.to_numpy();repos=cases.set_index("case_id").repo_id.to_dict();reg=_registry_map(source)
    cov_map={}
    if (source/"01_raw"/"patch_coverage.csv").exists():
        cv=pd.read_csv(source/"01_raw"/"patch_coverage.csv");cov_map=cv.set_index("case_id").patch_line_coverage_ratio.to_dict()
    rows=[]; examples=[]
    # Cache each sparse view once.
    cache={}
    for view,gdf in groups.groupby("view"):
        if view not in reg:continue
        try:
            X,feats,_=_presence_csc(source,reg[view],base_ids)
            # Reload weighted matrix for feature contrasts, still aligned.
            W,ids,wfeats,_=load_sparse(reg[view]);W=align_sparse_rows(base_ids,ids,W).tocsr();wfeats=list(map(str,wfeats or feats))
            cache[view]=(W,wfeats)
        except Exception as exc:
            rows.append({"template_id":"<VIEW_ERROR>","view":view,"decode_error":repr(exc)});continue
        W,wfeats=cache[view];global_mean=np.asarray(W.mean(axis=0)).ravel();pos={int(cid):i for i,cid in enumerate(base_ids)}
        for _,gr in gdf.iterrows():
            tid=str(gr.template_id);m=members[members.template_id==tid];cids=[int(x) for x in m.case_id.tolist() if int(x) in pos]
            if len(cids)<3:continue
            idx=np.asarray([pos[x] for x in cids],dtype=int);gm=np.asarray(W[idx].mean(axis=0)).ravel();contrast=gm-global_mean
            # Prefer terms that are both characteristic and present; contrast alone can over-rank tiny noise.
            score=contrast*np.sqrt(np.maximum(gm,0))
            topidx=np.argsort(score)[-20:][::-1];top=[wfeats[j] for j in topidx if score[j]>0][:20]
            # Centroid-nearest representative cases.
            centroid=np.asarray(W[idx].mean(axis=0)).ravel();norm=np.linalg.norm(centroid)
            if norm>0:
                subw=W[idx]
                row_norm=np.sqrt(np.asarray(subw.multiply(subw).sum(axis=1)).ravel())
                denom=np.maximum(1e-12,row_norm*norm)
                sims=np.asarray(subw.dot(centroid)).ravel()/denom
                reps=[cids[k] for k in np.argsort(sims)[-5:][::-1]]
            else:reps=cids[:5]
            rc=pd.Series([repos[x] for x in cids]).value_counts();toprepo=float(rc.iloc[0]/len(cids)) if len(rc) else np.nan
            boilerplate=bool("reltext_ai_markers" in view)
            charview=bool("__char" in view)
            highcov=float(np.mean([float(cov_map.get(x,np.nan))>=0.80 for x in cids if pd.notna(cov_map.get(x,np.nan))])) if any(pd.notna(cov_map.get(x,np.nan)) for x in cids) else np.nan
            rows.append({"template_id":tid,"view":view,"case_count":len(cids),"repository_count":len(rc),"top_repository_share":toprepo,"cross_repository":int(len(rc)>1),"high_patch_coverage_fraction":highcov,"likely_provenance_boilerplate":boilerplate,"char_ngram_view":charview,"top_contrast_features":" | ".join(top),"representative_case_ids":" | ".join(map(str,reps)),"original_threshold":gr.get("threshold")})
            if len(rc)>=3 and not boilerplate and not charview:
                examples.append((tid,view,len(cids),len(rc),top,reps))
    d=pd.DataFrame(rows)
    if not d.empty:d=d.sort_values(["likely_provenance_boilerplate","char_ngram_view","repository_count","case_count"],ascending=[True,True,False,False])
    write_csv(d,out/"decoded_templates_v21.csv")
    lines=["# Cross-Repository Template Decoding v2.1","","Only outcome-blind representations are used. Template names are not semantic labels; top contrast features and representative case IDs support later inspection.",""]
    for tid,view,n,nr,top,reps in sorted(examples,key=lambda x:(-x[3],-x[2]))[:150]:
        lines += [f"## {tid}",f"- View: `{view}`",f"- Cases: {n}; repositories: {nr}",f"- Representative cases: {', '.join(map(str,reps))}",f"- Top contrast features: {' | '.join(top[:15])}",""]
    (out/"TEMPLATE_DECODING.md").write_text("\n".join(lines),encoding="utf-8")
    write_json(out/"STATUS.json",{"status":"OK","templates":len(d),"decoded_nonboilerplate_nonchar":len(examples)})


def _demean_multi(values: np.ndarray, factors: list[np.ndarray], valid: np.ndarray, iterations: int=8):
    r=np.asarray(values,dtype=float).copy();r[~valid]=np.nan
    idx=np.flatnonzero(valid)
    if not len(idx):return r
    for _ in range(iterations):
        for f in factors:
            sf=pd.Series(f[idx]);rv=pd.Series(r[idx])
            means=rv.groupby(sf,dropna=False).transform("mean").to_numpy()
            r[idx]-=means
    return r


def _rank_array(x):
    return pd.Series(x).rank(method="average",na_option="keep").to_numpy(float)


def stage_temporal(source: Path, outroot: Path) -> None:
    out=outroot/"06_temporal_adjusted";out.mkdir(parents=True,exist_ok=True)
    raw=load_frame(source/"01_raw"/"case_scalar_features").reset_index(drop=True)
    feat=load_frame(outroot/"01_redundancy"/"feature_table_pruned").reset_index(drop=True)
    if not np.array_equal(raw.case_id.to_numpy(),feat.case_id.to_numpy()):feat=raw[["case_id"]].merge(feat,on="case_id",how="left")
    topics=pd.read_csv(source/"05_latent_topics"/"topic_assignments.csv")
    topics=feat[["case_id"]].merge(topics,on="case_id",how="left")
    factors=[feat.repo_id.fillna(-1).to_numpy()]
    for c in ["text__reltext_ai_markers_marker_text__char__topic","text__issue_body__word__topic"]:
        if c in topics.columns:factors.append(topics[c].fillna(-1).to_numpy())
    time_cols=[c for c in ["pr__created_at","issue__created_at"] if c in raw.columns]
    numeric=[c for c in feat.columns if c not in {"case_id","repo_id"} and infer_kind(feat[c],c) in {"numeric","binary"}]
    rows=[];series=[]
    for tc in time_cols:
        t=pd.to_datetime(raw[tc],errors="coerce",utc=True)
        tnum=t.astype("int64").to_numpy(dtype=float)/86400e9
        tnum[t.isna().to_numpy()]=np.nan
        period=t.dt.to_period("M").astype(str)
        period_counts=period.value_counts();valid_months=set(period_counts[period_counts>=30].index)
        for c in numeric:
            y=pd.to_numeric(feat[c],errors="coerce").to_numpy(float);valid=np.isfinite(tnum)&np.isfinite(y)
            if valid.sum()<200:continue
            rt=_rank_array(tnum);ry=_rank_array(y)
            rho=float(np.corrcoef(rt[valid],ry[valid])[0,1]) if np.std(rt[valid])>0 and np.std(ry[valid])>0 else np.nan
            # Repository-only fixed effect and repo+agent-provenance-topic+issue-topic fixed effects.
            tr=_demean_multi(rt,[factors[0]],valid);yr=_demean_multi(ry,[factors[0]],valid)
            repo_rho=float(np.corrcoef(tr[valid],yr[valid])[0,1]) if np.std(tr[valid])>0 and np.std(yr[valid])>0 else np.nan
            tr2=_demean_multi(rt,factors,valid);yr2=_demean_multi(ry,factors,valid)
            adj=float(np.corrcoef(tr2[valid],yr2[valid])[0,1]) if np.std(tr2[valid])>0 and np.std(yr2[valid])>0 else np.nan

            tmp=pd.DataFrame({"period":period,"y":y,"repo":feat.repo_id}).loc[valid]
            tmp=tmp[tmp.period.isin(valid_months)]
            if len(tmp):
                agg=tmp.groupby("period").agg(value=("y","median"),case_count=("y","size")).reset_index().sort_values("period")
                month_rho=float(stats.spearmanr(np.arange(len(agg)),agg.value).statistic) if len(agg)>=6 and agg.value.nunique()>1 else np.nan
            else:agg=pd.DataFrame();month_rho=np.nan
            # Repository-level direction consistency.
            rr=[]
            for rid,gidx in feat.loc[valid].groupby("repo_id").groups.items():
                gi=np.asarray(list(gidx),dtype=int)
                if len(gi)<10:continue
                tv=tnum[gi];yv=y[gi]
                if np.nanmax(tv)-np.nanmin(tv)<60 or len(np.unique(yv))<2:continue
                rrho=stats.spearmanr(tv,yv).statistic
                if pd.notna(rrho):rr.append(float(rrho))
            med_repo=float(np.median(rr)) if rr else np.nan;sign_frac=float(np.mean(np.sign(rr)==np.sign(adj))) if rr and pd.notna(adj) and adj!=0 else np.nan
            rows.append({"time_column":tc,"feature":c,"source_family":feature_source(c),"n":int(valid.sum()),"repositories":int(feat.loc[valid,"repo_id"].nunique()),"case_spearman":rho,"monthly_median_spearman":month_rho,"repo_fixed_effect_rank_corr":repo_rho,"repo_agent_task_adjusted_rank_corr":adj,"repo_level_median_spearman":med_repo,"repo_direction_consistency":sign_frac,"repo_slope_count":len(rr),"first_period":agg.period.iloc[0] if len(agg) else None,"last_period":agg.period.iloc[-1] if len(agg) else None,"first_month_median":agg.value.iloc[0] if len(agg) else np.nan,"last_month_median":agg.value.iloc[-1] if len(agg) else np.nan})
            if pd.notna(adj) and abs(adj)>=0.20 and len(agg):
                for _,r in agg.iterrows():series.append({"time_column":tc,"feature":c,"period":r.period,"median":r.value,"case_count":r.case_count})
    d=pd.DataFrame(rows)
    if not d.empty:
        d["composition_drop"]=d.case_spearman.abs()-d.repo_agent_task_adjusted_rank_corr.abs()
        d["adjusted_abs"]=d.repo_agent_task_adjusted_rank_corr.abs()
        d=d.sort_values(["adjusted_abs","repo_direction_consistency","repositories"],ascending=False)
    write_csv(d,out/"temporal_adjusted_v21.csv");write_csv(pd.DataFrame(series),out/"strong_adjusted_series.csv")
    write_json(out/"STATUS.json",{"status":"OK","time_columns":time_cols,"numeric_features":len(numeric),"trends":len(d),"adjustment_factors":["repo_id","agent_marker_topic_if_available","issue_body_topic_if_available"]})


def _effect_for_relationship(df:pd.DataFrame,r):
    a,b,metric=r.a,r.b,r.metric
    if a not in df or b not in df:return np.nan
    sa,sb=df[a],df[b];m=sa.notna()&sb.notna()
    if m.sum()<100:return np.nan
    if metric in {"spearman","phi"}:
        x=pd.to_numeric(sa[m],errors="coerce");y=pd.to_numeric(sb[m],errors="coerce")
        if x.nunique()<2 or y.nunique()<2:return np.nan
        if metric=="phi":return float(x.corr(y))
        return float(stats.spearmanr(x,y).statistic)
    if metric=="cramers_v":return cramers_v_corrected(sa[m],sb[m])
    if metric=="omega2":
        if infer_kind(sa,a) in {"numeric","binary"}:return eta_omega_squared(sa[m],sb[m])[1]
        return eta_omega_squared(sb[m],sa[m])[1]
    return np.nan


def _select_relationships(rel:pd.DataFrame,max_total=300):
    x=rel[~rel.mechanical_candidate.astype(bool)].dropna(subset=["effect_strength"]).copy()
    chunks=[]
    per=max(25,max_total//max(1,x.metric.nunique()))
    for metric,g in x.groupby("metric"):
        chunks.append(g.nlargest(min(per,len(g)),"candidate_score"))
    y=pd.concat(chunks).drop_duplicates(subset=["a","b","metric"]) if chunks else pd.DataFrame()
    if len(y)<max_total:
        extra=x.drop(index=y.index,errors="ignore").nlargest(max_total-len(y),"candidate_score")
        y=pd.concat([y,extra])
    return y.head(max_total)



def _validate_binary_pair_motifs(source:Path, feat:pd.DataFrame, rows:pd.DataFrame,
                                 view_a_col:str, feature_a_col:str, view_b_col:str, feature_b_col:str,
                                 id_prefix:str, max_candidates:int=80,
                                 boot_iters:int=100, null_iters:int=100, seed_offset:int=0):
    """Generic repository-blocked stability + within-repository null for binary pair motifs."""
    if rows.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    cases=load_frame(source/"01_raw"/"cases_linkage")
    base_ids=cases.case_id.to_numpy()
    if not np.array_equal(feat.case_id.to_numpy(),base_ids):
        base=cases[["case_id","repo_id"]].merge(feat,on="case_id",how="left")
    else:
        base=feat
    reg=_registry_map(source); cache={}; fmap={}
    def get_vec(view,feature):
        key=str(view)
        if key not in reg:return None
        if key not in cache:
            X,features,_=_presence_csc(source,reg[key],base_ids)
            cache[key]=X;fmap[key]={str(f):j for j,f in enumerate(features)}
        j=fmap[key].get(str(feature))
        if j is None:return None
        X=cache[key]
        idx=X.indices[X.indptr[j]:X.indptr[j+1]]
        arr=np.zeros(len(base_ids),dtype=bool);arr[idx]=True
        return arr
    # Keep the strongest broad motifs; all full rows remain in the motif audit outputs.
    rank_cols=[c for c in ["npmi","lift","support"] if c in rows.columns]
    sel=rows.sort_values(rank_cols,ascending=[False]*len(rank_cols)).head(min(max_candidates,len(rows))).copy() if rank_cols else rows.head(min(max_candidates,len(rows))).copy()
    sel["motif_validation_id"]=[f"{id_prefix}{i+1:04d}" for i in range(len(sel))]
    rng=np.random.default_rng(SEED+seed_offset)
    groups=[np.asarray(ix,dtype=int) for ix in base.groupby("repo_id").indices.values()]
    boot_rows=[]; null_rows=[]; summaries=[]
    for _,r in sel.iterrows():
        a=get_vec(r[view_a_col],r[feature_a_col]);b=get_vec(r[view_b_col],r[feature_b_col])
        if a is None or b is None:continue
        obs=float(np.mean(a & b));pa=float(a.mean());pb=float(b.mean());obs_lift=obs/max(1e-12,pa*pb)
        supports=[];lifts=[]
        for it in range(boot_iters):
            idx=repo_block_sample_indices(base,rng,REPO_SAMPLE_FRAC)
            if not len(idx):continue
            aa=a[idx];bb=b[idx];sup=float(np.mean(aa&bb));paa=float(aa.mean());pbb=float(bb.mean())
            supports.append(sup);lifts.append(sup/max(1e-12,paa*pbb))
            boot_rows.append({"motif_validation_id":r.motif_validation_id,"iteration":it,"support":sup,"lift":lifts[-1],"n":len(idx)})
        null_support=[]
        for q in range(null_iters):
            bp=b.copy()
            for ix in groups:
                if len(ix)>1:bp[ix]=b[rng.permutation(ix)]
            null_support.append(float(np.mean(a&bp)))
        narr=np.asarray(null_support,dtype=float)
        pval=float((1+np.sum(narr>=obs))/(1+len(narr))) if len(narr) else np.nan
        null_rows.append({"motif_validation_id":r.motif_validation_id,"observed_support":obs,
                          "observed_lift":obs_lift,"null_mean_support":float(narr.mean()) if len(narr) else np.nan,
                          "null_sd_support":float(narr.std()) if len(narr) else np.nan,
                          "empirical_upper_p":pval,"permutations":len(narr)})
        sa=np.asarray(supports,dtype=float);la=np.asarray(lifts,dtype=float)
        summaries.append({"motif_validation_id":r.motif_validation_id,
                          view_a_col:r[view_a_col],feature_a_col:r[feature_a_col],
                          view_b_col:r[view_b_col],feature_b_col:r[feature_b_col],
                          "full_support":obs,"full_lift":obs_lift,
                          "median_support":float(np.median(sa)) if len(sa) else np.nan,
                          "support_p025":float(np.quantile(sa,.025)) if len(sa) else np.nan,
                          "support_p975":float(np.quantile(sa,.975)) if len(sa) else np.nan,
                          "median_lift":float(np.median(la)) if len(la) else np.nan,
                          "lift_p025":float(np.quantile(la,.025)) if len(la) else np.nan,
                          "lift_p975":float(np.quantile(la,.975)) if len(la) else np.nan,
                          "support_retention":float(np.mean(sa>=0.5*obs)) if len(sa) and obs>0 else np.nan,
                          "bootstrap_n":len(sa),"empirical_upper_p":pval})
    return pd.DataFrame(summaries),pd.DataFrame(boot_rows),pd.DataFrame(null_rows)


def stage_stability(source:Path,outroot:Path)->None:
    out=outroot/"07_stability_null";out.mkdir(parents=True,exist_ok=True)
    feat=load_frame(outroot/"01_redundancy"/"feature_table_pruned")
    rel=pd.read_csv(outroot/"02_associations"/"relationships_v21.csv")
    sel=_select_relationships(rel,300).copy();sel["relationship_id"]=[f"R{i+1:04d}" for i in range(len(sel))]
    write_csv(sel,out/"selected_relationships.csv")
    rng=np.random.default_rng(SEED);boot=[];boot_iters=int(os.environ.get("V21_REL_BOOTSTRAPS","500"))
    for it in range(boot_iters):
        idx=repo_block_sample_indices(feat,rng,REPO_SAMPLE_FRAC);sub=feat.iloc[idx]
        for _,r in sel.iterrows():
            e=_effect_for_relationship(sub,r);boot.append({"relationship_id":r.relationship_id,"iteration":it,"effect":e,"n":len(sub)})
    bdf=pd.DataFrame(boot);write_csv(bdf,out/"relationship_bootstrap_iterations_v21.csv")
    summ=[]
    for _,r in sel.iterrows():
        x=bdf[bdf.relationship_id==r.relationship_id].effect.dropna();signed=r.metric in {"spearman","phi"}
        summ.append({"relationship_id":r.relationship_id,"a":r.a,"b":r.b,"metric":r.metric,"full_effect":r.effect,"effect_strength":r.effect_strength,"bootstrap_median":x.median() if len(x) else np.nan,"p025":x.quantile(.025) if len(x) else np.nan,"p975":x.quantile(.975) if len(x) else np.nan,"direction_stability":float(np.mean(np.sign(x)==np.sign(r.effect))) if signed and len(x) else np.nan,"retention_ge_half_full":float(np.mean(np.abs(x)>=0.5*abs(r.effect))) if len(x) and r.effect!=0 else np.nan,"bootstrap_n":len(x),"source_a":r.source_a,"source_b":r.source_b})
    srel=pd.DataFrame(summ)

    # Within-repository permutation null for the best corrected relationships.
    null=[];groups=[np.asarray(ix,dtype=int) for ix in feat.groupby("repo_id").indices.values()];top=sel.head(min(200,len(sel)));null_iters=int(os.environ.get("V21_REL_NULLS","200"))
    for _,r in top.iterrows():
        obs=float(r.effect);vals=[]
        for q in range(null_iters):
            perm=np.arange(len(feat))
            for ix in groups:
                if len(ix)>1:perm[ix]=rng.permutation(ix)
            tmp=feat[[r.a,r.b]].copy();tmp[r.b]=feat[r.b].iloc[perm].to_numpy();vals.append(_effect_for_relationship(tmp,r))
        arr=np.asarray([z for z in vals if pd.notna(z)],dtype=float)
        p=float((1+np.sum(np.abs(arr)>=abs(obs)))/(1+len(arr))) if len(arr) else np.nan
        null.append({"relationship_id":r.relationship_id,"a":r.a,"b":r.b,"metric":r.metric,"observed_effect":obs,"null_mean":float(arr.mean()) if len(arr) else np.nan,"null_sd":float(arr.std()) if len(arr) else np.nan,"empirical_two_sided_p":p,"permutations":len(arr)})
    ndf=pd.DataFrame(null);write_csv(ndf,out/"relationship_within_repo_null_v21.csv")
    if not ndf.empty:srel=srel.merge(ndf[["relationship_id","empirical_two_sided_p"]],on="relationship_id",how="left")
    write_csv(srel,out/"relationship_stability_v21.csv")

    # Pattern support/lift stability under repository-blocked resampling.
    patt=read_csv_safe(outroot/"03_patterns"/"closed_patterns_v21.csv")
    psummary=[];pboot=[]
    if not patt.empty:
        ta=pd.read_csv(outroot/"02_associations"/"feature_types_v21.csv")
        transactions,items,missing,item_feature,item_tids=_itemize_presence(feat.reset_index(drop=True),ta)
        patt=patt.nlargest(min(200,len(patt)),"surprise_score").copy();patt["pattern_id"]=[f"P{i+1:04d}" for i in range(len(patt))]
        for it in range(int(os.environ.get("V21_PATTERN_BOOTSTRAPS","200"))):
            idx=repo_block_sample_indices(feat,rng,REPO_SAMPLE_FRAC);S=set(idx.tolist());den=len(S)
            for _,r in patt.iterrows():
                its=[z.strip() for z in str(r["items"]).split(" | ") if z.strip()]
                tids=set.intersection(*(item_tids.get(z,set()) for z in its)) if its else set();obs=len(tids&S)/den if den else np.nan
                marg=[len(item_tids.get(z,set())&S)/den for z in its] if den else []
                lift=obs/max(1e-12,np.prod(marg)) if marg else np.nan
                pboot.append({"pattern_id":r.pattern_id,"iteration":it,"support":obs,"lift":lift,"n":den})
        pb=pd.DataFrame(pboot);write_csv(pb,out/"pattern_bootstrap_iterations_v21.csv")
        for _,r in patt.iterrows():
            g=pb[pb.pattern_id==r.pattern_id];s=g.support.dropna();l=g.lift.dropna()
            psummary.append({"pattern_id":r.pattern_id,"items":r["items"],"length":r.length,"full_support":r.support,"full_surprise_score":r.surprise_score,"median_support":s.median() if len(s) else np.nan,"support_p025":s.quantile(.025) if len(s) else np.nan,"support_p975":s.quantile(.975) if len(s) else np.nan,"median_lift":l.median() if len(l) else np.nan,"lift_p025":l.quantile(.025) if len(l) else np.nan,"lift_p975":l.quantile(.975) if len(l) else np.nan,"support_retention":float(np.mean(s>=0.5*r.support)) if len(s) else np.nan})
        psdf=pd.DataFrame(psummary)
        # Within-repository permutation null for the most surprising patterns. Items are shuffled independently
        # inside repositories, preserving each item's repo-specific prevalence while destroying cross-item coupling.
        pnull=[];topnull=patt.head(min(100,len(patt)));null_iters=int(os.environ.get("V21_PATTERN_NULLS","100"))
        if len(topnull):
            groups=[np.asarray(ix,dtype=int) for ix in feat.groupby("repo_id").indices.values()]
            unique_items=sorted({z.strip() for x in topnull["items"].astype(str) for z in x.split(" | ") if z.strip()})
            orig={it:np.asarray([i in item_tids.get(it,set()) for i in range(len(feat))],dtype=bool) for it in unique_items}
            null_support={pid:[] for pid in topnull.pattern_id}
            for q in range(null_iters):
                permuted={}
                for it,arr0 in orig.items():
                    arr=arr0.copy()
                    for ix in groups:
                        if len(ix)>1:arr[ix]=arr0[rng.permutation(ix)]
                    permuted[it]=arr
                for _,r in topnull.iterrows():
                    its=[z.strip() for z in str(r["items"]).split(" | ") if z.strip()]
                    z=np.ones(len(feat),dtype=bool)
                    for it in its:z &= permuted[it]
                    null_support[r.pattern_id].append(float(z.mean()))
            for _,r in topnull.iterrows():
                arr=np.asarray(null_support[r.pattern_id],dtype=float);obs=float(r.support);p=float((1+np.sum(arr>=obs))/(1+len(arr)))
                pnull.append({"pattern_id":r.pattern_id,"observed_support":obs,"null_mean_support":float(arr.mean()),"null_sd_support":float(arr.std()),"empirical_upper_p":p,"permutations":len(arr)})
        pndf=pd.DataFrame(pnull);write_csv(pndf,out/"pattern_within_repo_null_v21.csv")
        if not pndf.empty:psdf=psdf.merge(pndf[["pattern_id","empirical_upper_p"]],on="pattern_id",how="left")
        write_csv(psdf,out/"pattern_stability_v21.csv")

    # Validate code-edit transitions and path co-change motifs with the same generic controls:
    # whole-repository resampling for stability, then within-repository permutation preserving
    # each feature's repo-specific prevalence.
    mboot=int(os.environ.get("V21_MOTIF_BOOTSTRAPS","120"));mnull=int(os.environ.get("V21_MOTIF_NULLS","100"))
    trans=read_csv_safe(outroot/"04_motifs"/"edit_transition_motifs.csv")
    tval,tboot,tnull=_validate_binary_pair_motifs(
        source,feat,trans,"del_view","deleted_feature","add_view","added_feature","ET",
        max_candidates=100,boot_iters=mboot,null_iters=mnull,seed_offset=101)
    write_csv(tval,out/"edit_transition_stability_v21.csv");write_csv(tboot,out/"edit_transition_bootstrap_iterations_v21.csv");write_csv(tnull,out/"edit_transition_within_repo_null_v21.csv")

    pathm=read_csv_safe(outroot/"04_motifs"/"path_cochange_surprises.csv")
    if not pathm.empty:
        pathm=pathm.copy();pathm["view_a"]="paths__path_items_binary";pathm["view_b"]="paths__path_items_binary"
    pvalm,pbmot,pnullm=_validate_binary_pair_motifs(
        source,feat,pathm,"view_a","path_item_a","view_b","path_item_b","PC",
        max_candidates=100,boot_iters=mboot,null_iters=mnull,seed_offset=202)
    write_csv(pvalm,out/"path_cochange_stability_v21.csv");write_csv(pbmot,out/"path_cochange_bootstrap_iterations_v21.csv");write_csv(pnullm,out/"path_cochange_within_repo_null_v21.csv")

    # Bootstrap the strongest composition-adjusted temporal effects by repository blocks.
    tr=read_csv_safe(outroot/"06_temporal_adjusted"/"temporal_adjusted_v21.csv")
    trows=[]
    if not tr.empty:
        raw=load_frame(source/"01_raw"/"case_scalar_features");topics=pd.read_csv(source/"05_latent_topics"/"topic_assignments.csv");topics=feat[["case_id"]].merge(topics,on="case_id",how="left")
        toptr=tr.nlargest(min(80,len(tr)),"adjusted_abs")
        titers=int(os.environ.get("V21_TEMP_BOOTSTRAPS","150"))
        for _,r in toptr.iterrows():
            t=pd.to_datetime(raw[r.time_column],errors="coerce",utc=True);tn=t.astype("int64").to_numpy(dtype=float)/86400e9;tn[t.isna().to_numpy()]=np.nan;y=pd.to_numeric(feat[r.feature],errors="coerce").to_numpy(float)
            vals=[]
            for it in range(titers):
                idx=repo_block_sample_indices(feat,rng,REPO_SAMPLE_FRAC);valid=np.isfinite(tn[idx])&np.isfinite(y[idx])
                if valid.sum()<100:continue
                ii=idx[valid];rt=_rank_array(tn[ii]);ry=_rank_array(y[ii]);facs=[feat.repo_id.iloc[ii].fillna(-1).to_numpy()]
                for c in ["text__reltext_ai_markers_marker_text__char__topic","text__issue_body__word__topic"]:
                    if c in topics.columns:facs.append(topics[c].iloc[ii].fillna(-1).to_numpy())
                vv=np.ones(len(ii),dtype=bool);trr=_demean_multi(rt,facs,vv);yrr=_demean_multi(ry,facs,vv)
                if np.std(trr)>0 and np.std(yrr)>0:vals.append(float(np.corrcoef(trr,yrr)[0,1]))
            arr=np.asarray(vals,dtype=float)
            trows.append({"time_column":r.time_column,"feature":r.feature,"full_adjusted":r.repo_agent_task_adjusted_rank_corr,"bootstrap_median":float(np.median(arr)) if len(arr) else np.nan,"p025":float(np.quantile(arr,.025)) if len(arr) else np.nan,"p975":float(np.quantile(arr,.975)) if len(arr) else np.nan,"direction_stability":float(np.mean(np.sign(arr)==np.sign(r.repo_agent_task_adjusted_rank_corr))) if len(arr) else np.nan,"bootstrap_n":len(arr)})
    write_csv(pd.DataFrame(trows),out/"temporal_stability_v21.csv")
    write_json(out/"STATUS.json",{"status":"OK","relationships_bootstrapped":len(sel),"relationship_bootstrap_iterations":boot_iters,"relationships_nulled":len(top),"patterns_bootstrapped":len(psummary),"edit_transitions_validated":len(tval),"path_cochanges_validated":len(pvalm),"motif_bootstrap_iterations":mboot,"motif_null_iterations":mnull,"temporal_bootstrapped":len(trows)})


def _pct(s):
    return pd.Series(s).rank(pct=True).fillna(0.0)


def stage_catalog(source:Path,outroot:Path)->None:
    out=outroot/"08_catalog";out.mkdir(parents=True,exist_ok=True)
    cand=[]
    def add(**kw):
        kw.setdefault("evidence_grade","B")
        kw.setdefault("novelty_class","exploratory_recurrence")
        kw.setdefault("evidence_basis","")
        cand.append(kw)

    # Corrected relationships: require both repository-blocked stability and an actual
    # within-repository permutation result.  Near-deterministic/mechanical pairs never promote.
    sr=read_csv_safe(outroot/"07_stability_null"/"relationship_stability_v21.csv")
    rel=read_csv_safe(outroot/"02_associations"/"relationships_v21.csv")
    if not sr.empty and not rel.empty:
        cols=["a","b","metric","candidate_score","same_source_family","mechanical_candidate","within_repo_effect","normalized_mi"]
        m=sr.merge(rel[[c for c in cols if c in rel.columns]],on=["a","b","metric"],how="left")
        for _,r in m.iterrows():
            if bool(r.get("mechanical_candidate",False)):continue
            stab=r.direction_stability if pd.notna(r.get("direction_stability")) else r.retention_ge_half_full
            p=r.get("empirical_two_sided_p",np.nan)
            if pd.isna(p) or float(p)>0.05:continue
            if pd.isna(stab) or float(stab)<0.80:continue
            if float(r.effect_strength)<0.15:continue
            add(type="relationship",description=f"{r.a} <-> {r.b}",effect=r.effect_strength,support=1.0,
                repository_coverage=np.nan,stability=stab,null_p=p,
                interpretability=1.0 if not bool(r.get('same_source_family',False)) else .65,
                evidence_grade="A",novelty_class="surprise_validated",
                evidence_basis="within-repo permutation + repository-blocked bootstrap",
                evidence_path="07_stability_null/relationship_stability_v21.csv",
                detail=f"metric={r.metric}; within_repo={r.get('within_repo_effect')}; nmi={r.get('normalized_mi')}")

    # Multi-feature interactions: require broad repository support, bootstrap retention, lift,
    # and a within-repository permutation null.  Missingness/absence states never enter these items.
    ps=read_csv_safe(outroot/"07_stability_null"/"pattern_stability_v21.csv")
    cp=read_csv_safe(outroot/"03_patterns"/"closed_patterns_v21.csv")
    if not ps.empty and not cp.empty:
        m=ps.merge(cp[[c for c in ["items","repository_coverage","top_repository_share","surprise_score"] if c in cp.columns]],on="items",how="left",suffixes=("","_raw"))
        for _,r in m.iterrows():
            if r.repository_coverage<5/723 or r.top_repository_share>0.8:continue
            if pd.isna(r.get("median_lift")) or float(r.median_lift)<1.25:continue
            if pd.isna(r.get("empirical_upper_p")) or float(r.empirical_upper_p)>0.05:continue
            if pd.isna(r.get("support_retention")) or float(r.support_retention)<0.80:continue
            add(type="interaction_pattern",description=str(r['items']),effect=r.full_surprise_score,support=r.full_support,
                repository_coverage=r.repository_coverage,stability=r.support_retention,null_p=r.empirical_upper_p,
                interpretability=.85,evidence_grade="A",novelty_class="surprise_validated",
                evidence_basis="presence-only itemization + within-repo permutation + repository bootstrap",
                evidence_path="07_stability_null/pattern_stability_v21.csv",detail=f"median_lift={r.median_lift}; len={r.length}")

    # Code/syntax add-vs-delete motifs.  The null is the representation-wide add/delete exposure,
    # not 50/50; significant candidates must also keep direction in >=80% patch-coverage cases.
    asym=read_csv_safe(outroot/"04_motifs"/"add_delete_motif_asymmetry.csv")
    if not asym.empty:
        q=asym[(asym.fdr_q<=.05)&(asym.repository_count>=5)&(asym.top_repository_share<=.8)&(asym.abs_relative_log2_odds>=.75)]
        for _,r in q.head(1500).iterrows():
            if "coverage_effect_same_direction" in asym.columns and pd.notna(r.get("coverage_effect_same_direction")) and not bool(r.coverage_effect_same_direction):continue
            direction="added" if r.relative_log2_add_delete_odds>0 else "removed"
            add(type="code_motif_asymmetry",description=f"{r.feature} disproportionately {direction} relative to view baseline",
                effect=r.abs_relative_log2_odds,support=(r.add_cases+r.del_cases-r.both_cases)/EXPECTED_CASES,
                repository_coverage=r.repository_count/723,stability=1-r.top_repository_share,null_p=r.fdr_q,
                interpretability=(0.65 if "syntax__" in str(r.add_view) else (0.8 if "norm" in str(r.add_view) else 1.0)),
                evidence_grade="A",novelty_class="surprise_validated",
                evidence_basis="global add/delete exposure null + BH-FDR + patch-coverage sensitivity",
                evidence_path="04_motifs/add_delete_motif_asymmetry.csv",detail=f"view={r.add_view}; add={r.add_cases}; del={r.del_cases}")

    calls=read_csv_safe(outroot/"04_motifs"/"call_shape_asymmetry.csv")
    if not calls.empty:
        q=calls[(calls.fdr_q<=.05)&(calls.repository_count>=5)&(calls.top_repository_share<=.8)&(calls.abs_relative_log2_odds>=.75)]
        for _,r in q.head(1000).iterrows():
            if "coverage_effect_same_direction" in calls.columns and pd.notna(r.get("coverage_effect_same_direction")) and not bool(r.coverage_effect_same_direction):continue
            direction="added" if r.relative_log2_add_delete_odds>0 else "removed"
            add(type="call_shape_motif",description=f"call `{r.callee}(...)` disproportionately {direction} relative to all calls",
                effect=r.abs_relative_log2_odds,support=(r.add_cases+r.del_cases-r.both_cases)/EXPECTED_CASES,
                repository_coverage=r.repository_count/723,stability=1-r.top_repository_share,null_p=r.fdr_q,
                interpretability=1.0,evidence_grade="A",novelty_class="surprise_validated",
                evidence_basis="all-call add/delete exposure null + BH-FDR + patch-coverage sensitivity",
                evidence_path="04_motifs/call_shape_asymmetry.csv",detail=f"add={r.add_cases}; del={r.del_cases}")

    # Cross-artifact same-token transfer is useful evidence of grounding but conceptually expected.
    # Preserve it in the full catalogue while keeping it out of the strict surprise-first catalogue.
    trans=read_csv_safe(outroot/"04_motifs"/"cross_artifact_token_transfer.csv")
    if not trans.empty:
        filt=trans[(trans.lift>=1.5)&(trans.npmi>=.1)&(trans.repository_count>=5)&(trans.top_repository_share<=.8)]
        for _,r in filt.head(1500).iterrows():
            add(type="artifact_transfer_motif",description=f"`{r.feature}` transfers {r.source_view} -> {r.target_view}",
                effect=r.npmi,support=r.joint_support,repository_coverage=r.repository_count/723,
                stability=1-r.top_repository_share,null_p=np.nan,interpretability=.8,
                evidence_grade="C",novelty_class="descriptive_grounding",
                evidence_basis="cross-artifact lift/NPMI; retained as supporting evidence, not surprise claim",
                evidence_path="04_motifs/cross_artifact_token_transfer.csv",detail=f"lift={r.lift}; joint_cases={r.joint_cases}")

    # Edit-transition motifs receive dedicated repo-blocked/bootstrap + within-repo null validation.
    transitions=read_csv_safe(outroot/"04_motifs"/"edit_transition_motifs.csv")
    tv=read_csv_safe(outroot/"07_stability_null"/"edit_transition_stability_v21.csv")
    if not transitions.empty and not tv.empty:
        keys=["del_view","deleted_feature","add_view","added_feature"]
        mm=transitions.merge(tv,on=keys,how="inner",suffixes=("","_val"))
        for _,r in mm.iterrows():
            if r.repository_count<5 or r.top_repository_share>.8:continue
            if pd.isna(r.empirical_upper_p) or r.empirical_upper_p>.05:continue
            if pd.isna(r.support_retention) or r.support_retention<.8:continue
            if pd.isna(r.median_lift) or r.median_lift<1.5:continue
            add(type="edit_transition_motif",description=f"remove `{r.deleted_feature}` -> add `{r.added_feature}`",
                effect=r.npmi,support=r.support,repository_coverage=r.repository_count/723,
                stability=r.support_retention,null_p=r.empirical_upper_p,interpretability=1.0,
                evidence_grade="A",novelty_class="surprise_validated",
                evidence_basis="within-repo permutation + repository-blocked support/lift stability",
                evidence_path="07_stability_null/edit_transition_stability_v21.csv",
                detail=f"lift={r.lift}; median_boot_lift={r.median_lift}; views={r.del_view}->{r.add_view}")

    pathc=read_csv_safe(outroot/"04_motifs"/"path_cochange_surprises.csv")
    pv=read_csv_safe(outroot/"07_stability_null"/"path_cochange_stability_v21.csv")
    if not pathc.empty and not pv.empty:
        # Validation file carries generic view_a/view_b columns in addition to path item keys.
        mm=pathc.merge(pv,on=["path_item_a","path_item_b"],how="inner",suffixes=("","_val"))
        for _,r in mm.iterrows():
            if r.repository_count<5 or r.top_repository_share>.8:continue
            if pd.isna(r.empirical_upper_p) or r.empirical_upper_p>.05:continue
            if pd.isna(r.support_retention) or r.support_retention<.8:continue
            if pd.isna(r.median_lift) or r.median_lift<1.5:continue
            add(type="path_cochange_motif",description=f"paths `{r.path_item_a}` + `{r.path_item_b}` co-change",
                effect=r.npmi,support=r.support,repository_coverage=r.repository_count/723,
                stability=r.support_retention,null_p=r.empirical_upper_p,interpretability=1.0,
                evidence_grade="A",novelty_class="surprise_validated",
                evidence_basis="within-repo permutation + repository-blocked support/lift stability",
                evidence_path="07_stability_null/path_cochange_stability_v21.csv",
                detail=f"lift={r.lift}; median_boot_lift={r.median_lift}; cases={r.case_count}")

    # Decoded repeated templates are potentially valuable but remain exploratory until their
    # representative cases are inspected.  Boilerplate/character-ngram template families are excluded.
    td=read_csv_safe(outroot/"05_template_decoding"/"decoded_templates_v21.csv")
    if not td.empty:
        f=td[(td.cross_repository==1)&(~td.likely_provenance_boilerplate.astype(bool))&(~td.char_ngram_view.astype(bool))&(td.repository_count>=5)&(td.top_repository_share<=.8)]
        for _,r in f.iterrows():
            if (str(r.view).startswith("patch__") or str(r.view).startswith("syntax__")) and pd.notna(r.get("high_patch_coverage_fraction")) and float(r.high_patch_coverage_fraction)<0.80:continue
            add(type="cross_repo_template",description=f"{r.view}: {r.top_contrast_features}",
                effect=math.log1p(r.case_count),support=r.case_count/EXPECTED_CASES,
                repository_coverage=r.repository_count/723,stability=1-r.top_repository_share,null_p=np.nan,
                interpretability=1.0,evidence_grade="B",novelty_class="decoded_recurrence",
                evidence_basis="cross-repository near-duplicate group + decoded contrast features + representatives",
                evidence_path="05_template_decoding/decoded_templates_v21.csv",detail=f"template={r.template_id}; reps={r.representative_case_ids}")

    # Composition-adjusted temporal effects: require repository/task/provenance adjustment and
    # stable direction under whole-repository resampling.
    tr=read_csv_safe(outroot/"06_temporal_adjusted"/"temporal_adjusted_v21.csv")
    ts=read_csv_safe(outroot/"07_stability_null"/"temporal_stability_v21.csv")
    if not tr.empty:
        tm=tr.merge(ts,on=["time_column","feature"],how="left") if not ts.empty else tr
        for _,r in tm.iterrows():
            adj=r.repo_agent_task_adjusted_rank_corr
            if pd.isna(adj) or abs(adj)<.20:continue
            ds=r.get("direction_stability",np.nan)
            if pd.isna(ds) or ds<.80:continue
            add(type="adjusted_temporal",description=f"{r.time_column}: {r.feature}",effect=abs(adj),
                support=r.n/EXPECTED_CASES,repository_coverage=r.repositories/723,stability=ds,null_p=np.nan,
                interpretability=.9,evidence_grade="A",novelty_class="composition_adjusted_trend",
                evidence_basis="repo+task+provenance fixed-effect rank residual + repository bootstrap",
                evidence_path="06_temporal_adjusted/temporal_adjusted_v21.csv",
                detail=f"unadjusted={r.case_spearman}; repo_FE={r.repo_fixed_effect_rank_corr}; adjusted={adj}; first={r.first_month_median}; last={r.last_month_median}")

    cat=pd.DataFrame(cand)
    if cat.empty:
        write_csv(cat,out/"DISCOVERY_CATALOG_V21.csv");write_csv(cat,out/"STRICT_DISCOVERY_CATALOG_V21.csv");return
    cat["effect_pct"]=cat.groupby("type")["effect"].rank(pct=True).fillna(.5)
    cat["support_pct"]=cat.groupby("type")["support"].rank(pct=True).fillna(.5)
    cat["repo_pct"]=cat.groupby("type")["repository_coverage"].rank(pct=True).fillna(.5)
    cat["stability_pct"]=cat.groupby("type")["stability"].rank(pct=True).fillna(.5)
    cat["null_strength"]=cat.null_p.apply(lambda p: 0.4 if pd.isna(p) else min(1.0,max(0.0,-math.log10(max(float(p),1e-12))/4)))
    grade_bonus=cat.evidence_grade.map({"A":1.0,"B":.55,"C":.15}).fillna(.3)
    cat["rank_score"]=(1.3*cat.effect_pct + .7*cat.support_pct + 1.2*cat.repo_pct + 1.2*cat.stability_pct + .9*cat.null_strength + .8*cat.interpretability + 1.2*grade_bonus)/7.3
    order={"A":0,"B":1,"C":2};cat["_grade_order"]=cat.evidence_grade.map(order).fillna(9)
    cat=cat.sort_values(["_grade_order","rank_score","repository_coverage","effect"],ascending=[True,False,False,False]).drop(columns="_grade_order").reset_index(drop=True)
    cat.insert(0,"discovery_id",[f"V21-D{i+1:05d}" for i in range(len(cat))])
    strict=cat[cat.evidence_grade=="A"].copy().reset_index(drop=True)
    strict.insert(0,"strict_rank",np.arange(1,len(strict)+1))
    write_csv(cat,out/"DISCOVERY_CATALOG_V21.csv")
    write_csv(strict,out/"STRICT_DISCOVERY_CATALOG_V21.csv")
    write_json(out/"STATUS.json",{"status":"OK","discoveries":len(cat),"strict_grade_a":len(strict),"types":cat.type.value_counts().to_dict(),"grades":cat.evidence_grade.value_counts().to_dict()})


def _markdown_table(df:pd.DataFrame,cols:list[str],limit=30):
    if df.empty:return ["No qualifying results."]
    d=df.head(limit);cols=[c for c in cols if c in d.columns]
    lines=["| "+" | ".join(cols)+" |","| "+" | ".join(["---"]*len(cols))+" |"]
    for _,r in d.iterrows():
        vals=[]
        for c in cols:
            v=r[c];txt="" if pd.isna(v) else str(v).replace("|","\\|").replace("\n"," ")
            if len(txt)>220:txt=txt[:217]+"..."
            vals.append(txt)
        lines.append("| "+" | ".join(vals)+" |")
    return lines


def stage_report(source:Path,outroot:Path)->None:
    out=outroot/"09_report";out.mkdir(parents=True,exist_ok=True)
    cat=read_csv_safe(outroot/"08_catalog"/"DISCOVERY_CATALOG_V21.csv")
    strict=read_csv_safe(outroot/"08_catalog"/"STRICT_DISCOVERY_CATALOG_V21.csv")
    red=json.loads((outroot/"01_redundancy"/"STATUS.json").read_text())
    pat=json.loads((outroot/"03_patterns"/"STATUS.json").read_text())
    mot=json.loads((outroot/"04_motifs"/"STATUS.json").read_text())
    stab=json.loads((outroot/"07_stability_null"/"STATUS.json").read_text())
    lines=[
        "# Full-Corpus Outcome-Blind Discovery QC v2.1","",
        "## Purpose",
        "This is a corrective, outcome-blind extension of the completed v2.0 run. It reuses the expensive text/path/patch/syntax representations but fixes statistical and representation artifacts discovered during interpretation. No scanner/security outcome or manual risk label is read.","",
        "## Why v2.1 exists",
        "v2.0 optimized primarily for frequency and stability. That allowed mathematically valid but scientifically weak structures—absence+absence itemsets, generated cluster/topic/template features, arithmetic duplicates, and a broken mixed-type eta-squared calculation—to occupy the top of the catalogue. v2.1 changes the discovery objective to surprise + stability + cross-repository support + interpretability, without introducing a software-domain hypothesis taxonomy.","",
        "## Corrections",
        f"- Feature provenance gate: {red.get('input_features')} v2 features -> {red.get('primary_observed_features')} objective primary features before redundancy pruning -> {red.get('retained_primary_features')} retained representatives. Generated model/topic/template/anomaly features and provenance-text artifacts are preserved for decoding/controls but cannot enter the primary association/pattern/temporal miner.",
        f"- Redundancy: {red.get('removed_primary_redundant_features')} objective features removed as exact/near duplicates; near-deterministic relationships are audit-only.",
        "- Mixed numeric/categorical effects use a correct between-group variance calculation (omega-squared; eta-squared retained only as an audit value).",
        "- Frequent-pattern mining is presence/event based. Binary zero complements and missingness are not mixed into the primary itemset vocabulary.",
        f"- Surprise-first interaction mining produced {pat.get('pair_patterns')} pair candidates and {pat.get('higher_patterns')} higher-order candidates without a silent 500,000-result cap.",
        f"- Code-level discovery produced {mot.get('asymmetry_rows')} add/delete lexical/syntax asymmetry rows, {mot.get('call_rows')} generic call-shape rows, {mot.get('edit_transition_rows')} edit-transition rows, and {mot.get('path_cochange_rows')} raw path co-change rows.",
        "- Add/delete motifs use the representation-wide add/delete exposure as the null rather than assuming a 50/50 baseline; patch-derived candidates receive >=80% patch-coverage sensitivity checks.",
        "- Code edit-transition and path co-change motifs receive within-repository permutation nulls plus whole-repository bootstrap stability.",
        "- Repeated cross-repository templates are decoded into characteristic terms/nodes and cosine-nearest representative case IDs instead of opaque template IDs.",
        "- Temporal effects are adjusted for repository, agent-provenance topic, and issue-body task topic; strong effects receive repository-blocked stability checks.",
        f"- Stability stage: {stab.get('relationships_bootstrapped')} relationships bootstrapped, {stab.get('relationships_nulled')} relationships permuted within repositories, {stab.get('patterns_bootstrapped')} interaction patterns bootstrapped, {stab.get('edit_transitions_validated')} edit transitions validated, and {stab.get('path_cochanges_validated')} path co-changes validated.","",
        "## Strict validated discoveries (Grade A)",
        "Only candidates with the strongest available generic evidence are shown here. Descriptive token transfer and decoded-but-not-null-tested templates are deliberately kept out of this strict table.",
    ]
    lines += _markdown_table(strict,["strict_rank","discovery_id","type","description","effect","support","repository_coverage","stability","null_p","rank_score","evidence_basis","detail"],75)
    lines += ["","## Broader decoded/exploratory candidates (Grades B/C)"]
    other=cat[cat.evidence_grade!="A"] if not cat.empty and "evidence_grade" in cat.columns else pd.DataFrame()
    lines += _markdown_table(other,["discovery_id","evidence_grade","type","description","effect","support","repository_coverage","rank_score","evidence_basis","detail"],40)
    lines += ["","## Candidate counts"]
    if not cat.empty:
        vc=cat.groupby(["evidence_grade","type"],dropna=False).size().reset_index(name="count")
        lines += _markdown_table(vc,["evidence_grade","type","count"],100)
    lines += [
        "","## Interpretation boundary",
        "Grade A means the candidate survived the relevant statistical/generalizability/stability gates; it does not automatically mean the pattern is novel in the scientific literature or causal. Human interpretation must still decode the highest-ranked code/path motifs and inspect representative cases while the outcome overlay remains hidden.","",
        "**V2_1_QC_COMPLETE — OUTCOME_OVERLAY_NOT_PERFORMED**"
    ]
    (outroot/"V2_1_DISCOVERY_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    write_json(outroot/"00_audit"/"FINAL_STATUS_V21.json",{
        "status":"PASS","completed_at":now_iso(),"source_runroot":str(source.resolve()),
        "outcome_overlay_performed":False,"security_outcomes_read":False,
        "discoveries":len(cat),"strict_grade_a_discoveries":len(strict),
        "report":"V2_1_DISCOVERY_REPORT.md"
    })

