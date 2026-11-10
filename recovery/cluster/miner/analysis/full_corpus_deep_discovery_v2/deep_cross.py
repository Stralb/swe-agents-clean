from __future__ import annotations

import itertools
import json
import math
import re
import os
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, mutual_info_score, silhouette_score
from sklearn.neighbors import LocalOutlierFactor, NearestNeighbors
from sklearn.preprocessing import StandardScaler

from deep_common import (
    REPO_SAMPLE_FRAC, SEED, align_by_case_ids, effective_number_from_counts,
    gini_from_counts, is_identifier_name, is_text_name, is_time_name, load_embedding,
    load_frame, repo_block_sample_indices, save_embedding, save_frame, write_csv,
    write_json, file_sha256s,
)
from deep_models import enumerate_embeddings


def _linear_cka(X, Y):
    X=np.asarray(X,dtype=float); Y=np.asarray(Y,dtype=float)
    X=X-X.mean(axis=0,keepdims=True); Y=Y-Y.mean(axis=0,keepdims=True)
    xy=X.T@Y; xx=X.T@X; yy=Y.T@Y
    num=np.sum(xy*xy); den=math.sqrt(np.sum(xx*xx)*np.sum(yy*yy))
    return float(num/den) if den>0 else np.nan


def _knn_sets(E,k=20):
    k=min(k,len(E)-1)
    nn=NearestNeighbors(n_neighbors=k+1,metric="euclidean",n_jobs=-1).fit(E)
    ind=nn.kneighbors(E,return_distance=False)[:,1:]
    return [set(row.tolist()) for row in ind]


def _hdbscan(E):
    try:
        from sklearn.cluster import HDBSCAN
        return HDBSCAN(min_cluster_size=max(20,int(0.01*len(E))),min_samples=10,cluster_selection_method="eom",copy=True).fit_predict(E),"sklearn.cluster.HDBSCAN"
    except Exception as exc1:
        try:
            import hdbscan
            return hdbscan.HDBSCAN(min_cluster_size=max(20,int(0.01*len(E))),min_samples=10,cluster_selection_method="eom").fit_predict(E),"hdbscan.HDBSCAN"
        except Exception as exc2:
            return None,f"UNAVAILABLE: {exc1}; {exc2}"


def stage_crossview(runroot: Path) -> None:
    out=runroot/"08_crossview"; out.mkdir(parents=True,exist_ok=True)
    cases=load_frame(runroot/"01_raw"/"cases_linkage"); base_ids=cases["case_id"].to_numpy()
    reg=enumerate_embeddings(runroot).dropna(subset=["base"])
    embeds={}; knns={}; meta_rows=[]
    for _,r in reg.iterrows():
        view=str(r["view"]); E,ids,meta=load_embedding(Path(r["base"])); E=align_by_case_ids(base_ids,ids,E)
        E=StandardScaler().fit_transform(np.asarray(E,dtype=float))
        embeds[view]=E; knns[view]=_knn_sets(E,20)
        meta_rows.append({"view":view,"dims":E.shape[1],"rows":E.shape[0]})
    write_csv(pd.DataFrame(meta_rows),out/"embedding_registry.csv")

    pair_rows=[]; views=sorted(embeds)
    for i,a in enumerate(views):
        for b in views[i+1:]:
            cka=_linear_cka(embeds[a],embeds[b])
            ovs=[len(knns[a][j]&knns[b][j])/max(1,len(knns[a][j]|knns[b][j])) for j in range(len(base_ids))]
            pair_rows.append({"view_a":a,"view_b":b,"linear_cka":cka,"median_knn_jaccard":float(np.median(ovs)),"mean_knn_jaccard":float(np.mean(ovs))})
    pairs=pd.DataFrame(pair_rows).sort_values("linear_cka",ascending=False) if pair_rows else pd.DataFrame()
    write_csv(pairs,out/"view_similarity.csv")

    # Automatic view redundancy pruning by very high representation agreement.
    selected=[]; pruned=[]
    for v in views:
        redundant=None
        for k in selected:
            row=pairs[((pairs.view_a==min(v,k))&(pairs.view_b==max(v,k))) | ((pairs.view_a==max(v,k))&(pairs.view_b==min(v,k)))] if not pairs.empty else pd.DataFrame()
            if not row.empty and float(row.iloc[0].linear_cka)>=0.95:
                redundant=k; break
        if redundant: pruned.append({"view":v,"representative":redundant,"reason":"linear_CKA_ge_0.95"})
        else: selected.append(v)
    write_csv(pd.DataFrame(pruned),out/"view_redundancy_pruning.csv")

    # Equal-weight multi-view fusion. Each view is row-normalized then divided by sqrt(dim).
    parts=[]
    for v in selected:
        E=embeds[v].copy(); norm=np.linalg.norm(E,axis=1,keepdims=True); norm[norm==0]=1
        E=E/norm/math.sqrt(max(1,E.shape[1])); parts.append(E)
    if parts:
        F=np.hstack(parts)
        dims=min(128,F.shape[0]-1,F.shape[1])
        pca=PCA(n_components=dims,random_state=SEED,svd_solver="randomized")
        Z=pca.fit_transform(F)
        save_embedding(out/"fused_embedding",Z,base_ids,{"selected_views":selected,"input_dims":F.shape[1],"pca_dims":dims,"explained_variance":float(pca.explained_variance_ratio_.sum())})
        model_rows=[]; best=None
        k_max = 6 if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1" else 20
        for k in range(2,k_max+1):
            lab=KMeans(n_clusters=k,random_state=SEED,n_init=30).fit_predict(Z)
            sil=float(silhouette_score(Z,lab,sample_size=min(2500,len(Z)),random_state=SEED))
            model_rows.append({"method":"kmeans","k":k,"silhouette":sil})
            if best is None or sil>best[0]: best=(sil,k,lab)
        h,impl=_hdbscan(Z)
        ass=pd.DataFrame({"case_id":base_ids,"fused_kmeans":best[2]})
        if h is not None: ass["fused_hdbscan"]=h
        write_csv(ass,out/"fused_assignments.csv")
        write_csv(pd.DataFrame(model_rows),out/"fused_model_selection.csv")
        iso=IsolationForest(n_estimators=700,random_state=SEED,n_jobs=-1).fit(Z); iscore=-iso.score_samples(Z)
        lof=LocalOutlierFactor(n_neighbors=35); lof.fit_predict(Z); lscore=-lof.negative_outlier_factor_
        write_csv(pd.DataFrame({"case_id":base_ids,"fused_isolation_score":iscore,"fused_lof_score":lscore}),out/"fused_anomalies.csv")

    # Cross-artifact lexical alignment in a shared char-ngram space.
    text=load_frame(runroot/"01_raw"/"case_text").set_index("case_id").reindex(base_ids)
    pdocs=load_frame(runroot/"03_views"/"patch"/"patch_documents").set_index("case_id").reindex(base_ids)
    files=load_frame(runroot/"01_raw"/"pr_files_with_patch")
    fcol=next((c for c in files.columns if c.lower()=="filename"),None)
    path_docs=files.groupby("case_id")[fcol].apply(lambda s:"\n".join(s.dropna().astype(str))).reindex(base_ids).fillna("") if fcol else pd.Series([""]*len(base_ids),index=base_ids)
    docs={}
    for c in text.columns:
        s=text[c].fillna("").astype(str)
        if (s.str.len()>0).sum()>=50: docs[f"text::{c}"]=s.tolist()
    for c in ["add_raw","del_raw"]:
        if c in pdocs.columns: docs[f"patch::{c}"]=pdocs[c].fillna("").astype(str).tolist()
    docs["paths::raw"]=path_docs.tolist()
    if len(docs)>=2:
        all_docs=list(itertools.chain.from_iterable(docs.values()))
        vec=TfidfVectorizer(analyzer="char_wb",ngram_range=(3,5),min_df=max(5,int(len(base_ids)*0.001)),max_df=0.99,max_features=100000,sublinear_tf=True)
        vec.fit(all_docs)
        mats={k:vec.transform(v) for k,v in docs.items()}
        align=pd.DataFrame({"case_id":base_ids}); summ=[]; rng=np.random.default_rng(SEED)
        repo_groups={r:np.flatnonzero(cases["repo_id"].to_numpy()==r) for r in cases["repo_id"].unique()}
        for i,a in enumerate(sorted(mats)):
            for b in sorted(mats)[i+1:]:
                same=np.asarray(mats[a].multiply(mats[b]).sum(axis=1)).ravel()
                name=re.sub(r"[^A-Za-z0-9]+","_",f"align__{a}__{b}")[:160]
                align[name]=same
                null_meds=[]
                null_iters = 3 if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1" else 50
                for q in range(null_iters):
                    perm=np.arange(len(base_ids))
                    for idx in repo_groups.values():
                        if len(idx)>1: perm[idx]=rng.permutation(idx)
                    null=np.asarray(mats[a].multiply(mats[b][perm]).sum(axis=1)).ravel()
                    null_meds.append(float(np.median(null)))
                nm=float(np.mean(null_meds)); ns=float(np.std(null_meds))
                summ.append({"artifact_a":a,"artifact_b":b,"median_same_case_cosine":float(np.median(same)),"mean_same_case_cosine":float(np.mean(same)),"null_median_mean":nm,"null_median_sd":ns,"median_null_z":(float(np.median(same))-nm)/ns if ns>0 else np.nan})
        write_csv(align,out/"artifact_alignment_scores.csv")
        write_csv(pd.DataFrame(summ),out/"artifact_alignment_summary.csv")
    write_json(out/"STATUS.json",{"status":"OK","embedding_views":len(views),"selected_fusion_views":selected,"artifact_doc_views":len(docs)})


def _cramers_v(a,b):
    tab=pd.crosstab(a,b)
    if tab.empty:return np.nan
    chi2=stats.chi2_contingency(tab,correction=False)[0]; n=tab.to_numpy().sum(); r,k=tab.shape
    if n<=1:return np.nan
    phi2=chi2/n; phi2corr=max(0,phi2-((k-1)*(r-1))/(n-1)); rcorr=r-((r-1)**2)/(n-1); kcorr=k-((k-1)**2)/(n-1)
    den=min(kcorr-1,rcorr-1); return math.sqrt(phi2corr/den) if den>0 else 0.0


def _phi(a,b):
    a=pd.Series(a).astype(int); b=pd.Series(b).astype(int)
    if a.nunique()<2 or b.nunique()<2:return np.nan
    return float(a.corr(b))


def _eta2(num,cat):
    x=pd.to_numeric(num,errors="coerce"); c=pd.Series(cat); m=x.notna()&c.notna(); x=x[m]; c=c[m]
    if len(x)<10 or c.nunique()<2:return np.nan
    gm=x.mean(); ss=sum(((g-gm)**2).sum() for _,g in x.groupby(c)); tot=((x-gm)**2).sum()
    return float(ss/tot) if tot>0 else 0.0


def _normalized_mi(a,b,bins=10):
    sa=pd.Series(a); sb=pd.Series(b); m=sa.notna()&sb.notna(); sa=sa[m]; sb=sb[m]
    if len(sa)<30:return np.nan
    def disc(s):
        if pd.api.types.is_numeric_dtype(s):
            try:return pd.qcut(pd.to_numeric(s),q=min(bins,max(2,s.nunique())),duplicates="drop").astype(str)
            except Exception:return s.astype(str)
        return s.astype(str)
    aa=disc(sa); bb=disc(sb); mi=mutual_info_score(aa,bb); ha=mutual_info_score(aa,aa); hb=mutual_info_score(bb,bb)
    den=math.sqrt(ha*hb); return float(mi/den) if den>0 else 0.0


def assemble_feature_table(runroot: Path) -> pd.DataFrame:
    base=load_frame(runroot/"01_raw"/"case_scalar_features")
    keep=["case_id","repo_id"]
    # Objective scalar values, excluding raw identifiers/text/timestamps. Low-cardinality strings remain categorical.
    data=base[keep].copy()
    for c in base.columns:
        if c in keep or c in {"issue_id","pr_id"}:continue
        if is_identifier_name(c) or is_text_name(c) or is_time_name(c):continue
        s=base[c]
        if pd.api.types.is_numeric_dtype(s) or s.nunique(dropna=True)<=50:
            data[c]=s
    # Generic metrics from raw representations.
    for p in [
        runroot/"03_views"/"paths"/"path_metrics",
        runroot/"03_views"/"patch"/"patch_morphology",
        runroot/"03_views"/"syntax"/"syntax_metrics",
    ]:
        try:
            x=load_frame(p); data=data.merge(x,on="case_id",how="left")
        except Exception:pass
    # Discovered cluster/topic/anomaly/alignment features.
    for p in [
        runroot/"04_view_models"/"assignments.csv",
        runroot/"04_view_models"/"view_anomalies.csv",
        runroot/"05_latent_topics"/"topic_assignments.csv",
        runroot/"08_crossview"/"fused_assignments.csv",
        runroot/"08_crossview"/"fused_anomalies.csv",
        runroot/"08_crossview"/"artifact_alignment_scores.csv",
    ]:
        if p.exists():
            try:data=data.merge(pd.read_csv(p),on="case_id",how="left")
            except Exception:pass
    # Template memberships become generic binary pattern variables; bound to 500 largest groups.
    tm=runroot/"06_templates"/"template_members.csv"; tg=runroot/"06_templates"/"template_groups.csv"
    if tm.exists() and tg.exists():
        mem=pd.read_csv(tm); groups=pd.read_csv(tg).sort_values(["case_count","repository_count"],ascending=False).head(500)["template_id"].tolist()
        mem=mem[mem["template_id"].isin(groups)]
        if not mem.empty:
            piv=pd.crosstab(mem["case_id"],mem["template_id"]).clip(upper=1).add_prefix("template__").reset_index()
            data=data.merge(piv,on="case_id",how="left")
    save_frame(data,runroot/"09_associations"/"discovery_feature_table")
    return data


def stage_associations(runroot: Path) -> None:
    out=runroot/"09_associations"; out.mkdir(parents=True,exist_ok=True)
    df=assemble_feature_table(runroot)
    cols=[c for c in df.columns if c not in {"case_id","repo_id"}]
    kinds={}; audit=[]
    for c in cols:
        s=df[c]; nun=int(s.nunique(dropna=True))
        if nun <= 1:
            kinds[c]="exclude_constant"
        elif pd.api.types.is_numeric_dtype(s):
            kinds[c]="binary" if nun==2 else "numeric"
        else:
            kinds[c]="categorical" if nun<=50 else "exclude_high_cardinality"
        audit.append({"feature":c,"kind":kinds[c],"nunique":nun,"missing_fraction":float(s.isna().mean())})
    write_csv(pd.DataFrame(audit),out/"feature_type_audit.csv")

    numcols=[c for c in cols if kinds[c] in {"numeric","binary"}]
    catcols=[c for c in cols if kinds[c]=="categorical"]
    rows=[]

    # Vectorized Spearman/phi scan for all numeric/binary pairs.
    if numcols:
        X=df[numcols].apply(pd.to_numeric,errors="coerce")
        R=X.rank(axis=0,method="average",na_option="keep").corr(method="pearson",min_periods=30)
        V=X.notna().astype(np.int32).to_numpy()
        N=V.T@V
        vals=R.to_numpy()
        for i,a in enumerate(numcols):
            for j in range(i+1,len(numcols)):
                e=vals[i,j]; n=int(N[i,j])
                if n<30 or pd.isna(e): continue
                b=numcols[j]
                metric="phi" if kinds[a]==kinds[b]=="binary" else "spearman"
                rows.append({"a":a,"b":b,"kind_a":kinds[a],"kind_b":kinds[b],"metric":metric,"effect":float(e),"abs_effect":abs(float(e)),"normalized_mi":np.nan,"n":n})

    # Categorical-categorical and numeric-categorical effects.
    for i,a in enumerate(catcols):
        for b in catcols[i+1:]:
            m=df[a].notna()&df[b].notna(); n=int(m.sum())
            if n>=30:
                e=_cramers_v(df.loc[m,a],df.loc[m,b])
                rows.append({"a":a,"b":b,"kind_a":"categorical","kind_b":"categorical","metric":"cramers_v","effect":e,"abs_effect":abs(e) if pd.notna(e) else np.nan,"normalized_mi":np.nan,"n":n})
    for a in numcols:
        for b in catcols:
            m=df[a].notna()&df[b].notna(); n=int(m.sum())
            if n>=30:
                e=_eta2(df.loc[m,a],df.loc[m,b])
                rows.append({"a":a,"b":b,"kind_a":kinds[a],"kind_b":"categorical","metric":"eta2","effect":e,"abs_effect":abs(e) if pd.notna(e) else np.nan,"normalized_mi":np.nan,"n":n})

    rel=pd.DataFrame(rows)
    if rel.empty:
        write_csv(rel,out/"all_relationships.csv")
        write_json(out/"STATUS.json",{"status":"OK","features":len(numcols)+len(catcols),"relationships":0})
        return
    rel["redundancy_candidate"]=(rel["metric"].isin(["spearman","phi"])) & (rel["abs_effect"]>=0.985)

    # Generic nonlinear check for the strongest effect candidates only; the full effect scan above remains exhaustive.
    top_idx=rel[~rel.redundancy_candidate].nlargest(min(5000,len(rel)),"abs_effect").index
    for idx in top_idx:
        r=rel.loc[idx]; m=df[r.a].notna()&df[r.b].notna()
        try: rel.at[idx,"normalized_mi"]=_normalized_mi(df.loc[m,r.a],df.loc[m,r.b])
        except Exception: pass

    # Within-repository centered Spearman for strongest numeric relationships.
    topnum=rel[(rel.metric=="spearman") & (~rel.redundancy_candidate)].nlargest(500,"abs_effect").copy()
    centered=[]
    for _,r in topnum.iterrows():
        a=pd.to_numeric(df[r.a],errors="coerce"); b=pd.to_numeric(df[r.b],errors="coerce")
        ac=a-a.groupby(df["repo_id"]).transform("mean")
        bc=b-b.groupby(df["repo_id"]).transform("mean")
        m=ac.notna()&bc.notna(); rho=float(stats.spearmanr(ac[m],bc[m]).statistic) if m.sum()>=30 and ac[m].nunique()>1 and bc[m].nunique()>1 else np.nan
        centered.append({"a":r.a,"b":r.b,"within_repo_centered_spearman":rho})
    if centered: rel=rel.merge(pd.DataFrame(centered),on=["a","b"],how="left")
    write_csv(rel.sort_values(["redundancy_candidate","abs_effect"],ascending=[True,False]),out/"all_relationships.csv")
    write_json(out/"STATUS.json",{"status":"OK","numeric_binary_features":len(numcols),"categorical_features":len(catcols),"relationships":len(rel),"nonlinear_mi_evaluated":len(top_idx),"redundancy_candidates":int(rel.redundancy_candidate.sum())})


def _find_time_columns(raw: pd.DataFrame):
    out=[]
    for c in raw.columns:
        if not is_time_name(c):continue
        t=pd.to_datetime(raw[c],errors="coerce",utc=True)
        if t.notna().sum()>=100 and t.dt.to_period("M").nunique()>=6: out.append((c,t))
    return out


def stage_temporal(runroot: Path) -> None:
    out=runroot/"10_temporal_exhaustive"; out.mkdir(parents=True,exist_ok=True)
    raw=load_frame(runroot/"01_raw"/"case_scalar_features")
    feat=load_frame(runroot/"09_associations"/"discovery_feature_table")
    if not np.array_equal(raw["case_id"].to_numpy(),feat["case_id"].to_numpy()): feat=raw[["case_id"]].merge(feat,on="case_id",how="left")
    time_cols=_find_time_columns(raw); trend_rows=[]; series_rows=[]
    numeric=[c for c in feat.columns if c not in {"case_id","repo_id"} and pd.api.types.is_numeric_dtype(feat[c]) and feat[c].nunique(dropna=True)>1]
    # Bound pathological generic schemas by variance/support, not domain selection.
    if len(numeric)>500:
        scores=[(c,float(pd.to_numeric(feat[c],errors="coerce").notna().mean()),float(pd.to_numeric(feat[c],errors="coerce").var(skipna=True) or 0)) for c in numeric]
        numeric=[x[0] for x in sorted(scores,key=lambda z:(z[1],z[2]),reverse=True)[:500]]
    for tc,t in time_cols:
        periods=t.dt.to_period("M").astype(str)
        counts=periods.value_counts(); valid_periods=set(counts[counts>=30].index)
        for c in numeric:
            x=pd.to_numeric(feat[c],errors="coerce")
            temp=pd.DataFrame({"period":periods,"x":x}).dropna(); temp=temp[temp.period.isin(valid_periods)]
            if temp.empty:continue
            agg=temp.groupby("period").agg(value=("x","median"),case_count=("x","size")).reset_index().sort_values("period")
            if len(agg)<6:continue
            idx=np.arange(len(agg)); rho=float(stats.spearmanr(idx,agg.value).statistic)
            try:slope=float(stats.theilslopes(agg.value.to_numpy(),idx)[0])
            except Exception:slope=np.nan
            trend_rows.append({"time_column":tc,"feature":c,"periods":len(agg),"cases":int(agg.case_count.sum()),"spearman_time":rho,"abs_spearman":abs(rho),"theil_sen_slope_per_period":slope,"first_period":agg.period.iloc[0],"last_period":agg.period.iloc[-1],"first_value":agg.value.iloc[0],"last_value":agg.value.iloc[-1],"peak_period":agg.loc[agg.value.abs().idxmax(),"period"]})
            if abs(rho)>=0.5:
                for _,r in agg.iterrows():series_rows.append({"time_column":tc,"feature":c,"period":r.period,"value":r.value,"case_count":r.case_count})
    trends=pd.DataFrame(trend_rows).sort_values("abs_spearman",ascending=False) if trend_rows else pd.DataFrame()
    write_csv(trends,out/"all_temporal_trends.csv"); write_csv(pd.DataFrame(series_rows),out/"strong_trend_series.csv")
    # Generic PELT for top 200 strongest series where library is available.
    cps=[]
    try:
        import ruptures as rpt
        for _,r in trends.head(200).iterrows():
            s=pd.DataFrame(series_rows); s=s[(s.time_column==r.time_column)&(s.feature==r.feature)].sort_values("period")
            if len(s)<8:continue
            y=s.value.to_numpy(float).reshape(-1,1)
            pen=max(1.0,float(np.nanstd(y))*math.log(len(y)+1))
            try:
                bkps=rpt.Pelt(model="rbf").fit(y).predict(pen=pen)
                for b in bkps[:-1]: cps.append({"time_column":r.time_column,"feature":r.feature,"index":b,"period":s.iloc[b-1].period,"pre_value":s.iloc[max(0,b-2)].value,"post_value":s.iloc[min(len(s)-1,b)].value})
            except Exception:pass
        write_json(out/"PELT_STATUS.json",{"status":"OK","change_points":len(cps)})
    except Exception as exc:
        write_json(out/"PELT_STATUS.json",{"status":"UNAVAILABLE","detail":repr(exc)})
    write_csv(pd.DataFrame(cps),out/"change_points.csv")
    write_json(out/"STATUS.json",{"status":"OK","time_columns":len(time_cols),"features":len(numeric),"trends":len(trends)})


def _pattern_indicators(runroot: Path, base_ids: np.ndarray) -> pd.DataFrame:
    out=pd.DataFrame({"case_id":base_ids})
    for p in [runroot/"04_view_models"/"assignments.csv",runroot/"05_latent_topics"/"topic_assignments.csv",runroot/"08_crossview"/"fused_assignments.csv"]:
        if not p.exists():continue
        x=pd.read_csv(p)
        for c in x.columns:
            if c=="case_id" or c.endswith("weight"):continue
            for val,n in x[c].value_counts(dropna=True).items():
                if n<10:continue
                key=re.sub(r"[^A-Za-z0-9_.-]+","_",f"pattern__{c}__{val}")[:180]
                tmp=x[["case_id",c]].copy(); tmp[key]=(tmp[c]==val).astype(int); out=out.merge(tmp[["case_id",key]],on="case_id",how="left")
    tm=runroot/"06_templates"/"template_members.csv"
    if tm.exists():
        x=pd.read_csv(tm); counts=x.template_id.value_counts(); groups=counts[counts>=3].index[:1000]
        x=x[x.template_id.isin(groups)]
        if not x.empty:
            piv=pd.crosstab(x.case_id,x.template_id).clip(upper=1); piv.columns=[re.sub(r"[^A-Za-z0-9_.-]+","_","pattern__template__"+str(c))[:180] for c in piv.columns]; piv=piv.reset_index(); out=out.merge(piv,on="case_id",how="left")
    for c in out.columns:
        if c!="case_id":out[c]=out[c].fillna(0).astype(int)
    return out


def stage_generalizability(runroot: Path) -> None:
    out=runroot/"11_generalizability"; out.mkdir(parents=True,exist_ok=True)
    cases=load_frame(runroot/"01_raw"/"cases_linkage"); raw=load_frame(runroot/"01_raw"/"case_scalar_features")
    ids=cases.case_id.to_numpy(); pat=_pattern_indicators(runroot,ids); df=cases.merge(pat,on="case_id",how="left")
    # Automatically discover language and a useful PR-created timestamp if present.
    lang_col=next((c for c in raw.columns if "language" in c.lower() and raw[c].nunique(dropna=True)<=100),None)
    time_col=next((c for c in raw.columns if re.search(r"pr.*created.*at",c.lower())),None)
    aux=raw[["case_id"]+([lang_col] if lang_col else [])+([time_col] if time_col else [])].copy(); df=df.merge(aux,on="case_id",how="left")
    if time_col: df["__quarter"]=pd.to_datetime(df[time_col],errors="coerce",utc=True).dt.to_period("Q").astype(str)
    rows=[]
    for c in pat.columns:
        if c=="case_id":continue
        sub=df[df[c]==1]; n=len(sub)
        support=n/len(df)
        if n<3 or support<0.005 or support>0.98:continue
        rc=sub.repo_id.value_counts(); row={"pattern":c,"pattern_family":"latent_or_template","case_count":n,"support":n/len(df),"repository_count":int(len(rc)),"repository_coverage":len(rc)/cases.repo_id.nunique(),"top_repository_share":float(rc.iloc[0]/n),"effective_repositories":effective_number_from_counts(rc.values),"repository_gini":gini_from_counts(rc.values)}
        if lang_col:
            vc=sub[lang_col].fillna("<missing>").value_counts(); row["language_count"]=len(vc); row["top_language_share"]=float(vc.iloc[0]/n) if len(vc) else np.nan
        if time_col:
            vc=sub["__quarter"].value_counts(); row["quarter_count"]=len(vc); row["top_quarter_share"]=float(vc.iloc[0]/n) if len(vc) else np.nan
        rows.append(row)

    # Also profile top automatically-discretized frequent itemsets without naming their semantics.
    fp=runroot/"09b_frequent_patterns"/"frequent_itemsets.csv"
    ci=runroot/"09b_frequent_patterns"/"case_items.csv"
    if fp.exists() and ci.exists():
        fpdf=pd.read_csv(fp)
        fpdf=fpdf[(fpdf.min_support_setting==0.01) & (fpdf.length>=2)].sort_values(["support","length"],ascending=[False,False]).head(500)
        cidf=pd.read_csv(ci)
        item_to_cases={item:set(g.case_id.tolist()) for item,g in cidf.groupby("item")}
        base_aux=df.set_index("case_id")
        for _,fr in fpdf.iterrows():
            items=[x.strip() for x in str(fr["items"]).split(" | ") if x.strip()]
            sets=[item_to_cases.get(x,set()) for x in items]
            cids=set.intersection(*sets) if sets else set()
            if len(cids)<3:continue
            sub=df[df.case_id.isin(cids)]; n=len(sub); rc=sub.repo_id.value_counts()
            row={"pattern":"itemset__"+str(fr["items"])[:300],"pattern_family":"frequent_itemset","case_count":n,"support":n/len(df),"repository_count":int(len(rc)),"repository_coverage":len(rc)/cases.repo_id.nunique(),"top_repository_share":float(rc.iloc[0]/n),"effective_repositories":effective_number_from_counts(rc.values),"repository_gini":gini_from_counts(rc.values)}
            if lang_col:
                vc=sub[lang_col].fillna("<missing>").value_counts(); row["language_count"]=len(vc); row["top_language_share"]=float(vc.iloc[0]/n) if len(vc) else np.nan
            if time_col:
                vc=sub["__quarter"].value_counts(); row["quarter_count"]=len(vc); row["top_quarter_share"]=float(vc.iloc[0]/n) if len(vc) else np.nan
            rows.append(row)

    write_csv(pd.DataFrame(rows).sort_values(["repository_coverage","case_count"],ascending=False),out/"pattern_generalizability.csv")
    write_json(out/"STATUS.json",{"status":"OK","patterns":len(rows),"language_column":lang_col,"time_column":time_col})


def _effect_for_pair(df,a,b,metric):
    sa,sb=df[a],df[b]; m=sa.notna()&sb.notna()
    if m.sum()<30:return np.nan
    if metric=="spearman":return float(stats.spearmanr(pd.to_numeric(sa[m]),pd.to_numeric(sb[m])).statistic)
    if metric=="phi":return _phi(sa[m],sb[m])
    if metric=="cramers_v":return _cramers_v(sa[m],sb[m])
    if metric=="eta2":
        if pd.api.types.is_numeric_dtype(sa):return _eta2(sa[m],sb[m])
        return _eta2(sb[m],sa[m])
    return np.nan


def stage_stability(runroot: Path) -> None:
    out=runroot/"12_stability_null"; out.mkdir(parents=True,exist_ok=True)
    feat=load_frame(runroot/"09_associations"/"discovery_feature_table"); rel=pd.read_csv(runroot/"09_associations"/"all_relationships.csv")
    rel=rel[~rel.redundancy_candidate.astype(bool)].dropna(subset=["abs_effect"]).nlargest(300,"abs_effect").copy()
    rng=np.random.default_rng(SEED); boot=[]
    boot_iters = 5 if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1" else 500
    for b in range(boot_iters):
        idx=repo_block_sample_indices(feat,rng,REPO_SAMPLE_FRAC); sub=feat.iloc[idx]
        for rid,r in rel.iterrows():
            e=_effect_for_pair(sub,r.a,r.b,r.metric); boot.append({"relationship_index":int(rid),"iteration":b,"effect":e,"n":len(sub)})
    bdf=pd.DataFrame(boot); write_csv(bdf,out/"relationship_bootstrap_iterations.csv")
    summ=[]
    for rid,g in bdf.groupby("relationship_index"):
        r=rel.loc[rid]; x=g.effect.dropna(); summ.append({"relationship_index":rid,"a":r.a,"b":r.b,"metric":r.metric,"full_effect":r.effect,"median_boot_effect":x.median(),"p025":x.quantile(.025),"p975":x.quantile(.975),"sign_stability":float(np.mean(np.sign(x)==np.sign(r.effect))) if len(x) else np.nan,"bootstrap_n":len(x)})
    srel=pd.DataFrame(summ); write_csv(srel,out/"relationship_stability.csv")

    # Within-repository permutation null for top 100 relationships.
    null=[]; top=rel.head(100); groups=[np.asarray(ix) for ix in feat.groupby("repo_id").indices.values()]
    for rid,r in top.iterrows():
        obs=float(r.effect); vals=[]
        null_iters = 5 if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1" else 200
        for q in range(null_iters):
            perm=np.arange(len(feat))
            for ix in groups:
                if len(ix)>1: perm[ix]=rng.permutation(ix)
            tmp=feat[[r.a,r.b]].copy(); tmp[r.b]=feat[r.b].iloc[perm].to_numpy(); e=_effect_for_pair(tmp,r.a,r.b,r.metric); vals.append(e)
        arr=np.asarray([x for x in vals if pd.notna(x)],dtype=float); p=float((1+np.sum(np.abs(arr)>=abs(obs)))/(1+len(arr))) if len(arr) else np.nan
        null.append({"relationship_index":rid,"a":r.a,"b":r.b,"metric":r.metric,"observed_effect":obs,"null_mean":float(np.mean(arr)) if len(arr) else np.nan,"null_sd":float(np.std(arr)) if len(arr) else np.nan,"empirical_two_sided_p":p,"permutations":len(arr)})
    write_csv(pd.DataFrame(null),out/"relationship_within_repo_null.csv")

    # Fused-cluster repository-blocked stability.
    femb=runroot/"08_crossview"/"fused_embedding.npy"; fass=runroot/"08_crossview"/"fused_assignments.csv"
    fc=[]
    if femb.exists() and fass.exists():
        Z=np.load(femb); ass=pd.read_csv(fass); base=ass.fused_kmeans.to_numpy(); k=len(np.unique(base))
        fused_iters = 5 if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1" else 300
        for b in range(fused_iters):
            idx=repo_block_sample_indices(feat,rng,REPO_SAMPLE_FRAC); lab=KMeans(n_clusters=k,random_state=SEED+b+1000,n_init=10).fit_predict(Z[idx]); fc.append({"iteration":b,"n":len(idx),"ari":adjusted_rand_score(base[idx],lab),"nmi":normalized_mutual_info_score(base[idx],lab)})
    write_csv(pd.DataFrame(fc),out/"fused_cluster_stability.csv")
    write_json(out/"STATUS.json",{"status":"OK","relationship_bootstrap_iterations":len(boot),"null_relationships":len(null),"fused_cluster_iterations":len(fc)})



def _read_csv_safe(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

def stage_catalog(runroot: Path) -> None:
    out=runroot/"13_catalog"; out.mkdir(parents=True,exist_ok=True)
    candidates=[]
    stab=runroot/"12_stability_null"/"relationship_stability.csv"
    gen=runroot/"11_generalizability"/"pattern_generalizability.csv"
    if stab.exists():
        x=_read_csv_safe(stab); nullp={}
        npth=runroot/"12_stability_null"/"relationship_within_repo_null.csv"
        if npth.exists():
            nx=_read_csv_safe(npth)
            if not nx.empty and "relationship_index" in nx.columns: nullp=nx.set_index("relationship_index").empirical_two_sided_p.to_dict()
        for _,r in x.iterrows():
            candidates.append({"type":"relationship","description":f"{r.a} <-> {r.b}","effect":abs(r.full_effect),"support":1.0,"repository_coverage":np.nan,"stability":r.sign_stability,"null_p":nullp.get(r.relationship_index,np.nan),"evidence_path":"12_stability_null/relationship_stability.csv"})
    tp=runroot/"06_templates"/"template_groups.csv"
    if tp.exists():
        x=_read_csv_safe(tp); n=load_frame(runroot/"01_raw"/"cases_linkage").shape[0]; nr=load_frame(runroot/"01_raw"/"cases_linkage").repo_id.nunique()
        for _,r in x.iterrows(): candidates.append({"type":"template","description":str(r.template_id),"effect":r.threshold,"support":r.case_count/n,"repository_coverage":r.repository_count/nr,"stability":np.nan,"null_p":np.nan,"evidence_path":"06_templates/template_groups.csv"})
    tr=runroot/"10_temporal_exhaustive"/"all_temporal_trends.csv"
    if tr.exists():
        x=_read_csv_safe(tr).head(500)
        for _,r in x.iterrows(): candidates.append({"type":"temporal","description":f"{r.time_column}: {r.feature}","effect":abs(r.spearman_time),"support":r.cases/load_frame(runroot/"01_raw"/"cases_linkage").shape[0],"repository_coverage":np.nan,"stability":np.nan,"null_p":np.nan,"evidence_path":"10_temporal_exhaustive/all_temporal_trends.csv"})
    gr=runroot/"07_cooccurrence_graphs"/"communities.csv"
    if gr.exists():
        x=_read_csv_safe(gr)
        for _,r in x.iterrows(): candidates.append({"type":"cooccurrence_community","description":f"{r.community_id}: {str(r['items'])[:400]}","effect":math.log1p(r.item_count),"support":np.nan,"repository_coverage":np.nan,"stability":np.nan,"null_p":np.nan,"evidence_path":"07_cooccurrence_graphs/communities.csv"})
    fp=runroot/"09b_frequent_patterns"/"association_rules.csv"
    if fp.exists():
        x=_read_csv_safe(fp).head(2000)
        for _,r in x.iterrows(): candidates.append({"type":"frequent_rule","description":f"{r.antecedent} => {r.consequent}","effect":r.lift,"support":r.support,"repository_coverage":np.nan,"stability":np.nan,"null_p":np.nan,"evidence_path":"09b_frequent_patterns/association_rules.csv"})
    if gen.exists():
        x=_read_csv_safe(gen)
        for _,r in x.iterrows(): candidates.append({"type":"discrete_pattern","description":str(r.pattern),"effect":r.support,"support":r.support,"repository_coverage":r.repository_coverage,"stability":1-r.top_repository_share,"null_p":np.nan,"evidence_path":"11_generalizability/pattern_generalizability.csv"})
    cat=pd.DataFrame(candidates)
    if cat.empty:
        write_csv(cat,out/"DISCOVERY_CATALOG.csv"); return
    # Type-local percentile ranking prevents one metric scale from dominating all discovery families.
    cat["effect_pct"]=cat.groupby("type")["effect"].rank(pct=True).fillna(0.5)
    cat["support_pct"]=cat.groupby("type")["support"].rank(pct=True).fillna(0.5)
    cat["repo_pct"]=cat.groupby("type")["repository_coverage"].rank(pct=True).fillna(0.5)
    cat["stability_pct"]=cat.groupby("type")["stability"].rank(pct=True).fillna(0.5)
    cat["rank_score"]=(cat.effect_pct+cat.support_pct+cat.repo_pct+cat.stability_pct)/4
    cat=cat.sort_values(["rank_score","effect"],ascending=False).reset_index(drop=True); cat.insert(0,"discovery_id",[f"D{i+1:05d}" for i in range(len(cat))])
    write_csv(cat,out/"DISCOVERY_CATALOG.csv")
    write_json(out/"STATUS.json",{"status":"OK","discoveries":len(cat),"types":cat.type.value_counts().to_dict()})
