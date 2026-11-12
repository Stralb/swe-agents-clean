from __future__ import annotations

import itertools
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from sklearn.cluster import KMeans
from sklearn.decomposition import NMF
from sklearn.ensemble import IsolationForest
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from sklearn.neighbors import LocalOutlierFactor, NearestNeighbors
from sklearn.preprocessing import StandardScaler

from deep_common import (
    REPO_SAMPLE_FRAC, SEED, align_by_case_ids, load_embedding, load_frame, load_sparse,
    repo_block_sample_indices, save_embedding, save_frame, stage_passed, write_csv, write_json,
)


def enumerate_embeddings(runroot: Path) -> pd.DataFrame:
    rows=[]
    root=runroot/"03_views"
    for p in sorted(root.rglob("*_svd.npy")):
        base=p.with_suffix("")
        ids=base.with_name(base.name+"_case_ids.npy")
        if not ids.exists(): continue
        try:
            E=np.load(p,mmap_mode="r")
            rows.append({"view":str(p.relative_to(root)).replace("/","__").replace("_svd.npy",""),"base":str(base),"rows":E.shape[0],"dims":E.shape[1]})
        except Exception as exc:
            rows.append({"view":str(p),"base":str(base),"error":repr(exc)})
    return pd.DataFrame(rows)


def enumerate_sparse_views(runroot: Path) -> pd.DataFrame:
    rows=[]; root=runroot/"03_views"
    for p in sorted(root.rglob("*.npz")):
        base=p.with_suffix("")
        if not base.with_name(base.name+"_case_ids.npy").exists(): continue
        try:
            X=sparse.load_npz(p)
            rows.append({"view":str(p.relative_to(root)).replace("/","__").replace(".npz",""),"base":str(base),"rows":X.shape[0],"features":X.shape[1]})
        except Exception as exc:
            rows.append({"view":str(p),"base":str(base),"error":repr(exc)})
    return pd.DataFrame(rows)


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


def _sil(E, labels):
    labs=np.asarray(labels); valid=labs>=0; u=np.unique(labs[valid])
    if len(u)<2 or valid.sum()<=len(u): return np.nan
    try: return float(silhouette_score(E[valid],labs[valid],sample_size=min(2500,valid.sum()),random_state=SEED))
    except Exception: return np.nan


def stage_view_models(runroot: Path) -> None:
    out=runroot/"04_view_models"; out.mkdir(parents=True,exist_ok=True)
    reg=enumerate_embeddings(runroot); write_csv(reg,out/"embedding_registry.csv")
    cases=load_frame(runroot/"01_raw"/"cases_linkage")
    base_ids=cases["case_id"].to_numpy(); rng=np.random.default_rng(SEED)
    model_rows=[]; stability_rows=[]; assignment_frames=[]; anomaly_frames=[]

    for _,rr in reg.dropna(subset=["base"]).iterrows():
        view=str(rr["view"]); E,ids,meta=load_embedding(Path(rr["base"])); E=align_by_case_ids(base_ids,ids,E)
        E=np.asarray(E,dtype=float)
        # Standardization lets each latent dimension contribute comparably.
        E=StandardScaler().fit_transform(E)
        # Candidate k is generic, not tied to software semantics.
        best=None
        k_max = 6 if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1" else 20
        for k in range(2,k_max+1):
            km=KMeans(n_clusters=k,random_state=SEED,n_init=20,max_iter=500)
            lab=km.fit_predict(E); sil=_sil(E,lab)
            model_rows.append({"view":view,"method":"kmeans","param":f"k={k}","clusters":k,"noise_fraction":0.0,"silhouette":sil,"inertia":float(km.inertia_)})
            if best is None or (pd.notna(sil) and sil>best[0]): best=(sil,k,lab)
        if best is None: continue
        best_sil,best_k,best_lab=best
        hlabels,himpl=_hdbscan(E)
        hsil=_sil(E,hlabels) if hlabels is not None else np.nan
        if hlabels is not None:
            model_rows.append({"view":view,"method":"hdbscan","param":himpl,"clusters":len(set(hlabels[hlabels>=0])),"noise_fraction":float(np.mean(hlabels<0)),"silhouette":hsil,"inertia":np.nan})
        adf=pd.DataFrame({"case_id":base_ids,f"{view}__kmeans":best_lab})
        if hlabels is not None: adf[f"{view}__hdbscan"]=hlabels
        assignment_frames.append(adf)

        # Generic anomaly detectors on each view embedding.
        iso=IsolationForest(n_estimators=500,random_state=SEED,n_jobs=-1,contamination="auto").fit(E)
        iso_score=-iso.score_samples(E)
        nnb=max(5,min(35,len(E)-1))
        lof=LocalOutlierFactor(n_neighbors=nnb,novelty=False)
        lof.fit_predict(E); lof_score=-lof.negative_outlier_factor_
        anomaly_frames.append(pd.DataFrame({"case_id":base_ids,f"{view}__iso":iso_score,f"{view}__lof":lof_score}))

        # Repository-blocked stability for the selected KMeans and HDBSCAN solution.
        stability_iters = 5 if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1" else 200
        for b in range(stability_iters):
            idx=repo_block_sample_indices(cases,rng,REPO_SAMPLE_FRAC)
            if len(idx)<max(100,best_k*5): continue
            km=KMeans(n_clusters=best_k,random_state=SEED+b+1,n_init=10,max_iter=400)
            sub=km.fit_predict(E[idx])
            ari=adjusted_rand_score(best_lab[idx],sub); nmi=normalized_mutual_info_score(best_lab[idx],sub)
            row={"view":view,"iteration":b,"n":len(idx),"kmeans_ari":ari,"kmeans_nmi":nmi}
            if hlabels is not None:
                hs,_=_hdbscan(E[idx])
                if hs is not None:
                    row["hdbscan_ari"]=adjusted_rand_score(hlabels[idx],hs)
                    row["hdbscan_nmi"]=normalized_mutual_info_score(hlabels[idx],hs)
            stability_rows.append(row)

    write_csv(pd.DataFrame(model_rows),out/"model_selection.csv")
    write_csv(pd.DataFrame(stability_rows),out/"stability_iterations.csv")
    if assignment_frames:
        ass=assignment_frames[0]
        for x in assignment_frames[1:]: ass=ass.merge(x,on="case_id",how="outer")
        write_csv(ass,out/"assignments.csv")
    if anomaly_frames:
        an=anomaly_frames[0]
        for x in anomaly_frames[1:]: an=an.merge(x,on="case_id",how="outer")
        write_csv(an,out/"view_anomalies.csv")
    write_json(out/"STATUS.json",{"status":"OK","views":int(len(reg)),"model_rows":len(model_rows),"stability_rows":len(stability_rows)})


def stage_topics(runroot: Path) -> None:
    out=runroot/"05_latent_topics"; out.mkdir(parents=True,exist_ok=True)
    reg=enumerate_sparse_views(runroot); write_csv(reg,out/"sparse_registry.csv")
    model_rows=[]; topic_rows=[]; assignment_frames=[]
    for _,rr in reg.dropna(subset=["base"]).iterrows():
        view=str(rr["view"]); X,ids,feats,meta=load_sparse(Path(rr["base"]))
        # NMF only makes sense for nonnegative tf/count views with sufficient vocabulary.
        if X.shape[1]<50 or X.shape[0]<100 or X.min()<0: continue
        # Binary item views are handled by graph/frequent-pattern mining instead.
        if "binary" in view.lower() or "structured_matrix" in view.lower(): continue
        maxk=min(60,X.shape[0]-1,X.shape[1]-1)
        ks=[k for k in [5,10,20,30,40,60] if k<=maxk]
        if not ks: continue
        best=None
        for k in ks:
            errs=[]; divs=[]
            seeds = [SEED] if os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1" else [SEED,SEED+1,SEED+2]
            for seed in seeds:
                try:
                    m=NMF(n_components=k,init="nndsvda",random_state=seed,max_iter=400,tol=1e-4)
                    W=m.fit_transform(X); err=float(m.reconstruction_err_)
                    names=np.asarray(feats if feats is not None else [f"f{i}" for i in range(X.shape[1])],dtype=object)
                    top=[tuple(names[np.argsort(comp)[-15:][::-1]]) for comp in m.components_]
                    div=len(set(itertools.chain.from_iterable(top)))/(k*15)
                    errs.append(err); divs.append(div)
                    model_rows.append({"view":view,"k":k,"seed":seed,"reconstruction_error":err,"top_term_diversity":div})
                except Exception as exc:
                    model_rows.append({"view":view,"k":k,"seed":seed,"error":repr(exc)})
            if errs:
                mederr=float(np.median(errs)); meddiv=float(np.median(divs)); score=meddiv/(1+mederr/max(1,X.shape[0]))
                if best is None or score>best[0]: best=(score,k)
        if best is None: continue
        k=best[1]
        m=NMF(n_components=k,init="nndsvda",random_state=SEED,max_iter=700,tol=1e-4)
        W=m.fit_transform(X); names=np.asarray(feats if feats is not None else [f"f{i}" for i in range(X.shape[1])],dtype=object)
        for j,comp in enumerate(m.components_):
            topidx=np.argsort(comp)[-30:][::-1]
            topic_rows.append({"view":view,"topic_id":j,"top_features":" | ".join(str(names[i]) for i in topidx),"component_l1":float(np.sum(comp))})
        lab=np.argmax(W,axis=1); weight=W.max(axis=1)
        assignment_frames.append(pd.DataFrame({"case_id":ids,f"{view}__topic":lab,f"{view}__topic_weight":weight}))
    write_csv(pd.DataFrame(model_rows),out/"nmf_model_selection.csv")
    write_csv(pd.DataFrame(topic_rows),out/"topics.csv")
    if assignment_frames:
        ass=assignment_frames[0]
        for x in assignment_frames[1:]: ass=ass.merge(x,on="case_id",how="outer")
        write_csv(ass,out/"topic_assignments.csv")
    write_json(out/"STATUS.json",{"status":"OK","models":len(model_rows),"topics":len(topic_rows),"views_with_topics":len(assignment_frames)})


def _mutual_knn_edges(X, k=20):
    n=X.shape[0]
    k=min(k,n-1)
    nn=NearestNeighbors(n_neighbors=k+1,metric="cosine",n_jobs=-1).fit(X)
    dist,ind=nn.kneighbors(X)
    neigh=[set(row[1:]) for row in ind]
    sims=[]
    for i in range(n):
        for pos,j in enumerate(ind[i,1:],start=1):
            if i<j and i in neigh[j]: sims.append((i,j,1-float(dist[i,pos])))
    return sims


def stage_templates(runroot: Path) -> None:
    out=runroot/"06_templates"; out.mkdir(parents=True,exist_ok=True)
    reg=enumerate_sparse_views(runroot)
    cases=load_frame(runroot/"01_raw"/"cases_linkage"); base_ids=cases["case_id"].to_numpy(); repo_map=dict(zip(cases["case_id"],cases["repo_id"]))
    edge_rows=[]; comp_rows=[]; member_rows=[]
    for _,rr in reg.dropna(subset=["base"]).iterrows():
        view=str(rr["view"]); X,ids,feats,meta=load_sparse(Path(rr["base"]))
        # Very wide sparse lexical views are exactly where near-duplicate/template search is useful.
        if X.shape[1]<20: continue
        edges=_mutual_knn_edges(X,20)
        if not edges: continue
        sims=np.asarray([x[2] for x in edges]); threshold=float(np.quantile(sims,0.99))
        kept=[x for x in edges if x[2]>=threshold]
        for i,j,s in kept:
            edge_rows.append({"view":view,"case_a":ids[i],"case_b":ids[j],"cosine_similarity":s,"empirical_threshold":threshold})
        if not kept: continue
        row=[]; col=[]
        for i,j,s in kept: row.extend([i,j]); col.extend([j,i])
        A=sparse.csr_matrix((np.ones(len(row)),(row,col)),shape=(len(ids),len(ids)))
        ncomp,labels=connected_components(A,directed=False)
        for comp in range(ncomp):
            members=np.flatnonzero(labels==comp)
            if len(members)<3: continue
            cids=[ids[i] for i in members]; repos={repo_map.get(x) for x in cids}
            comp_id=f"{view}__T{comp:05d}"
            comp_rows.append({"template_id":comp_id,"view":view,"case_count":len(cids),"repository_count":len(repos),"cross_repository":int(len(repos)>1),"threshold":threshold})
            for cid in cids: member_rows.append({"template_id":comp_id,"view":view,"case_id":cid})
    write_csv(pd.DataFrame(edge_rows),out/"near_duplicate_edges.csv")
    write_csv(pd.DataFrame(comp_rows),out/"template_groups.csv")
    write_csv(pd.DataFrame(member_rows),out/"template_members.csv")
    write_json(out/"STATUS.json",{"status":"OK","edges":len(edge_rows),"groups":len(comp_rows)})


def stage_graphs(runroot: Path) -> None:
    out=runroot/"07_cooccurrence_graphs"; out.mkdir(parents=True,exist_ok=True)
    reg=enumerate_sparse_views(runroot)
    edge_rows=[]; comm_rows=[]; summary_rows=[]
    try:
        import networkx as nx
        have_nx=True
    except Exception:
        nx=None; have_nx=False

    for _,rr in reg.dropna(subset=["base"]).iterrows():
        view=str(rr["view"]); X,ids,feats,meta=load_sparse(Path(rr["base"]))
        if feats is None or X.shape[1]<2: continue
        B=X.copy().tocsr(); B.data=np.ones_like(B.data)
        df=np.asarray(B.sum(axis=0)).ravel(); n=B.shape[0]
        eligible=np.flatnonzero((df>=max(5,0.005*n)) & (df<=0.80*n))
        if len(eligible)>600:
            # Automatically keep most prevalent eligible items to bound quadratic cooccurrence.
            eligible=eligible[np.argsort(df[eligible])[-600:]]
        if len(eligible)<2: continue
        S=(B[:,eligible].T @ B[:,eligible]).tocoo()
        local_edges=[]
        for i,j,co in zip(S.row,S.col,S.data):
            if i>=j: continue
            co=float(co); di=float(df[eligible[i]]); dj=float(df[eligible[j]])
            support=co/n; lift=(co*n)/(di*dj) if di*dj else np.nan
            pxy=co/n; px=di/n; py=dj/n
            npmi=(math.log(pxy/(px*py)) / -math.log(pxy)) if pxy>0 and px>0 and py>0 and pxy<1 else np.nan
            if co>=max(5,0.005*n) and pd.notna(lift) and lift>1:
                local_edges.append((i,j,co,support,lift,npmi))
        local_edges=sorted(local_edges,key=lambda x:(np.nan_to_num(x[5],nan=-9),x[3]),reverse=True)[:10000]
        for i,j,co,sup,lift,npmi in local_edges:
            edge_rows.append({"view":view,"item_a":str(feats[eligible[i]]),"item_b":str(feats[eligible[j]]),"cooccurrence":co,"support":sup,"lift":lift,"npmi":npmi})
        communities=[]
        if have_nx and local_edges:
            G=nx.Graph()
            for i,j,co,sup,lift,npmi in local_edges:
                G.add_edge(str(feats[eligible[i]]),str(feats[eligible[j]]),weight=max(0.0,float(npmi) if pd.notna(npmi) else 0.0),support=sup,lift=lift)
            try:
                communities=list(nx.algorithms.community.greedy_modularity_communities(G,weight="weight"))
            except Exception:
                communities=[set(c) for c in nx.connected_components(G)]
            for ci,c in enumerate(communities):
                if len(c)<2: continue
                comm_rows.append({"view":view,"community_id":f"{view}__C{ci:04d}","item_count":len(c),"items":" | ".join(sorted(c)[:100])})
        summary_rows.append({"view":view,"eligible_items":len(eligible),"retained_edges":len(local_edges),"communities":len(communities),"networkx":have_nx})
    write_csv(pd.DataFrame(edge_rows),out/"cooccurrence_edges.csv")
    write_csv(pd.DataFrame(comm_rows),out/"communities.csv")
    write_csv(pd.DataFrame(summary_rows),out/"graph_summary.csv")
    write_json(out/"STATUS.json",{"status":"OK","views":len(summary_rows),"edges":len(edge_rows),"communities":len(comm_rows),"networkx":have_nx})
