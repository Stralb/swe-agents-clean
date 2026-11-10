from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, spearmanr

from v22_common import *


def _source(root: Path, name: str) -> pd.DataFrame:
    return load_frame(root / "01_raw" / name)


def _source_manifest(root: Path):
    p=root/"00_manifest"/"FINAL_STATUS_V2.json"
    if not p.exists():
        # final status is normally at source root after v2 report
        p=root/"00_manifest"/"FINAL_STATUS_V2.json"
    if p.exists():
        return json.loads(p.read_text())
    r=root/"00_manifest"/"RUN_MANIFEST.json"
    return json.loads(r.read_text()) if r.exists() else {}


def stage_audit(outroot: Path, source: Path):
    out=outroot/"00_audit"; out.mkdir(parents=True,exist_ok=True)
    man=_source_manifest(source)
    runman={}
    p=source/"00_manifest"/"RUN_MANIFEST.json"
    if p.exists(): runman=json.loads(p.read_text())
    dbsha=runman.get("db_sha256") or man.get("db_sha256")
    if dbsha and dbsha != EXPECTED_DB_SHA256:
        raise RuntimeError(f"SOURCE_DB_SHA_MISMATCH={dbsha}")
    if man.get("security_outcomes_read") is True or man.get("outcome_overlay_performed") is True:
        raise RuntimeError("SOURCE_RUN_NOT_OUTCOME_BLIND")
    required=[
        "01_raw/cases_linkage",
        "01_raw/pr_files_with_patch",
        "01_raw/case_text",
        "01_raw/repos_safe",
        "01_raw/issues_safe",
        "01_raw/pull_requests_safe",
    ]
    rows=[]
    for rel in required:
        base=source/rel
        exists=base.with_suffix(".parquet").exists() or base.with_suffix(".pkl").exists()
        rows.append({"artifact":rel,"exists":exists})
        if not exists: raise RuntimeError(f"MISSING_SOURCE_ARTIFACT={rel}")
    cases=_source(source,"cases_linkage")
    expected = len(cases) if os.environ.get("V22_TEST_MODE") == "1" else EXPECTED_CASES
    if len(cases)!=expected or cases.case_id.nunique()!=expected:
        raise RuntimeError(f"CASE_INVARIANT rows={len(cases)} unique={cases.case_id.nunique()} expected={expected}")
    cov=pd.read_csv(source/"01_raw"/"patch_coverage.csv")
    write_csv(pd.DataFrame(rows),out/"required_artifacts.csv")
    write_json(out/"SOURCE_STATUS.json",{
        "status":"PASS","source_runroot":str(source),"cases":len(cases),
        "security_outcomes_read":False,"outcome_overlay_performed":False,
        "patch_coverage_ge_0_8":int((cov.patch_line_coverage_ratio>=0.8).sum()),
        "principle":"Discover transformations and conditional surprise in real development artifacts; operational miner metadata is excluded by construction.",
    })
    write_json(out/"STATUS.json",{"status":"PASS","timestamp":now_iso()})


def _join_identity(source: Path):
    cases=_source(source,"cases_linkage")
    repos=_source(source,"repos_safe")
    issues=_source(source,"issues_safe")
    prs=_source(source,"pull_requests_safe")
    x=cases.copy()
    x=x.merge(repos,on="repo_id",how="left")
    x=x.merge(issues,on="issue_id",how="left")
    x=x.merge(prs,on="pr_id",how="left")
    cols=[c for c in x.columns if c in {"case_id","repo_id","issue_id","pr_id"} or c in {
        "repo__full_name","repo__language","issue__number","issue__created_at","pr__number","pr__created_at"
    }]
    return x[cols]


def stage_blocks(outroot: Path, source: Path):
    out=outroot/"01_blocks"; out.mkdir(parents=True,exist_ok=True)
    files=_source(source,"pr_files_with_patch")
    cov=pd.read_csv(source/"01_raw"/"patch_coverage.csv")[["case_id","patch_line_coverage_ratio"]]
    identity=_join_identity(source)
    filename=next(c for c in files.columns if c.lower()=="filename")
    patch=next(c for c in files.columns if c.lower()=="patch")
    rows=[]; casesummary=[]; block_id=0
    for cid,g in files.groupby("case_id",sort=False):
        c_blocks=0; code_blocks=0; generated_blocks=0; reps=adds=dels=0
        for _,r in g.iterrows():
            fn=str(r.get(filename) or "")
            p=r.get(patch)
            if pd.isna(p) or not str(p).strip(): continue
            ext=ext_of(fn); generated=is_generated_path(fn); code=is_code_path(fn)
            for hidx,h in enumerate(parse_unified_patch(str(p))):
                for bidx,b in enumerate(change_blocks_from_hunk(h)):
                    rem=b["removed"]; add=b["added"]
                    if not rem and not add: continue
                    block_id+=1; c_blocks+=1
                    if generated: generated_blocks+=1
                    if code: code_blocks+=1
                    kind="replace" if rem and add else ("add_only" if add else "delete_only")
                    if kind=="replace": reps+=1
                    elif kind=="add_only": adds+=1
                    else: dels+=1
                    rt="\n".join(rem); at="\n".join(add)
                    rc=sorted(set(calls_in_text(rt))) if code else []
                    ac=sorted(set(calls_in_text(at))) if code else []
                    ri=sorted(set(import_modules(rt))) if code else []
                    ai=sorted(set(import_modules(at))) if code else []
                    rk,ro=lexical_features(rt) if code else ([],[])
                    ak,ao=lexical_features(at) if code else ([],[])
                    rows.append({
                        "block_id":block_id,"case_id":cid,"filename":fn,"extension":ext,
                        "is_code":bool(code),"is_generated":bool(generated),"change_kind":kind,
                        "removed_lines":len(rem),"added_lines":len(add),
                        "removed_calls":" | ".join(rc),"added_calls":" | ".join(ac),
                        "removed_imports":" | ".join(ri),"added_imports":" | ".join(ai),
                        "removed_keywords":" | ".join(sorted(set(rk))),"added_keywords":" | ".join(sorted(set(ak))),
                        "removed_operators":" | ".join(sorted(set(ro))),"added_operators":" | ".join(sorted(set(ao))),
                        "removed_skeleton":normalized_block(rem)[:1200],"added_skeleton":normalized_block(add)[:1200],
                        "removed_text":rt[:8000],"added_text":at[:8000],
                        "removed_preview":rt[:800].replace("\n"," "),"added_preview":at[:800].replace("\n"," "),
                    })
        casesummary.append({"case_id":cid,"change_blocks":c_blocks,"code_blocks":code_blocks,"generated_blocks":generated_blocks,
                            "replace_blocks":reps,"add_only_blocks":adds,"delete_only_blocks":dels})
    blocks=pd.DataFrame(rows).merge(identity,on="case_id",how="left").merge(cov,on="case_id",how="left")
    summary=pd.DataFrame(casesummary).merge(identity,on="case_id",how="left").merge(cov,on="case_id",how="left")
    save_frame(blocks,out/"change_blocks")
    save_frame(summary,out/"case_change_summary")
    write_csv(summary,out/"case_change_summary.csv")
    write_json(out/"STATUS.json",{
        "status":"PASS","blocks":len(blocks),"cases":summary.case_id.nunique(),
        "code_blocks":int(blocks.is_code.sum()),"generated_blocks":int(blocks.is_generated.sum()),
        "replace_blocks":int((blocks.change_kind=="replace").sum()),
    })


def _explode_set(s):
    if pd.isna(s) or not str(s).strip(): return []
    return [x.strip() for x in str(s).split("|") if x.strip()]


def _pair_candidates(blocks, oldcol, newcol, family, min_cases=8, min_repos=5):
    counts=defaultdict(set); repos=defaultdict(set); extcounts=defaultdict(Counter)
    examples=defaultdict(list)
    old_case=defaultdict(set); new_case=defaultdict(set)
    for _,r in blocks.iterrows():
        cid=int(r.case_id); rid=int(r.repo_id) if pd.notna(r.repo_id) else -1; ext=str(r.extension)
        olds=set(_explode_set(r[oldcol])); news=set(_explode_set(r[newcol]))
        for a in olds: old_case[a].add(cid)
        for b in news: new_case[b].add(cid)
        for a in olds:
            for b in news:
                if a==b: continue
                key=(a,b); counts[key].add(cid); repos[key].add(rid); extcounts[key][ext]+=1
                if len(examples[key]) < 8:
                    examples[key].append((cid, str(r.filename), str(r.removed_preview)[:180], str(r.added_preview)[:180]))
    rows=[]; ncases=blocks.case_id.nunique()
    for (a,b),cids in counts.items():
        if len(cids)<min_cases or len(repos[(a,b)]-{ -1 })<min_repos: continue
        na=len(old_case[a]); nb=len(new_case[b]); obs=len(cids)
        exp=max(1e-9,na*nb/ncases); lift=obs/exp
        pxy=obs/ncases; pa=na/ncases; pb=nb/ncases
        if pxy <= 0:
            npmi=np.nan
        elif pxy >= 1.0:
            npmi=1.0
        else:
            npmi=math.log(max(pxy/(pa*pb),1e-12))/(-math.log(max(pxy,1e-12)))
        ex=examples[(a,b)]
        rows.append({"family":family,"removed":a,"added":b,"case_count":obs,"support":obs/ncases,
                     "repository_count":len(repos[(a,b)]-{ -1 }),"lift":lift,"npmi":npmi,
                     "top_extension":extcounts[(a,b)].most_common(1)[0][0] if extcounts[(a,b)] else "",
                     "example_case_ids":" | ".join(str(x[0]) for x in ex),
                     "example_files":" | ".join(x[1] for x in ex),
                     "example_block_previews":" || ".join(f"-{x[2]} => +{x[3]}" for x in ex)})
    return pd.DataFrame(rows)


def _dep_transitions(blocks):
    rows=[]
    for _,r in blocks[(blocks.change_kind=="replace") & (~blocks.is_generated)].iterrows():
        rem={}; add={}
        for line in str(r.removed_text).split("\n"):
            m=DEP_PAIR_RE.match(line)
            if m: rem[m.group(1)]=m.group(2)
        for line in str(r.added_text).split("\n"):
            m=DEP_PAIR_RE.match(line)
            if m: add[m.group(1)]=m.group(2)
        for pkg in set(rem)&set(add):
            if rem[pkg]!=add[pkg]:
                rows.append({"case_id":r.case_id,"repo_id":r.repo_id,"filename":r.filename,"package":pkg,
                             "old_value":rem[pkg],"new_value":add[pkg]})
    return pd.DataFrame(rows)


def stage_transformations(outroot: Path, source: Path):
    out=outroot/"02_transformations"; out.mkdir(parents=True,exist_ok=True)
    blocks=load_frame(outroot/"01_blocks"/"change_blocks")
    # High-quality code replacement blocks only. Generated/vendor/lock artifacts are a separate stratum.
    q=blocks[(blocks.is_code==True)&(blocks.is_generated==False)&(blocks.change_kind=="replace")&(blocks.patch_line_coverage_ratio>=0.8)].copy()
    families=[]
    for old,new,name,mc,mr in [
        ("removed_calls","added_calls","call_transition",6,4),
        ("removed_imports","added_imports","import_transition",5,3),
        ("removed_keywords","added_keywords","keyword_transition",10,6),
        ("removed_operators","added_operators","operator_transition",10,6),
    ]:
        x=_pair_candidates(q,old,new,name,mc,mr)
        if not x.empty: families.append(x)
    cand=pd.concat(families,ignore_index=True) if families else pd.DataFrame()
    if not cand.empty:
        # Remove pure structural opposite pairs that are too generic to interpret.
        cand["candidate_score"]=(cand.npmi.clip(lower=0)*np.log1p(cand.case_count)*np.log1p(cand.repository_count))
        cand=cand.sort_values("candidate_score",ascending=False)
    write_csv(cand,out/"transition_candidates.csv")
    deps=_dep_transitions(blocks)
    write_csv(deps,out/"dependency_value_transitions.csv")
    if not deps.empty:
        dsum=(deps.groupby(["package","old_value","new_value"],dropna=False)
              .agg(case_count=("case_id","nunique"),repository_count=("repo_id","nunique"),
                   example_case_ids=("case_id",lambda z:" | ".join(map(str,sorted(set(z))[:8]))),
                   example_files=("filename",lambda z:" | ".join(list(dict.fromkeys(map(str,z)))[:8])))
              .reset_index())
        dsum=dsum.sort_values(["repository_count","case_count"],ascending=False)
    else:
        dsum=pd.DataFrame(columns=["package","old_value","new_value","case_count","repository_count","example_case_ids","example_files"])
    write_csv(dsum,out/"dependency_transition_summary.csv")
    write_json(out/"STATUS.json",{"status":"PASS","quality_replace_blocks":len(q),"transition_candidates":len(cand),"dependency_value_transitions":len(deps),"dependency_transition_summaries":len(dsum)})


def _safe_text_col(df, candidates):
    for c in candidates:
        if c in df.columns: return c
    return None


def _case_patch_text(files):
    filename=next(c for c in files.columns if c.lower()=="filename")
    patch=next(c for c in files.columns if c.lower()=="patch")
    rows=[]
    for cid,g in files.groupby("case_id",sort=False):
        add=[]; rem=[]; paths=[]; added_calls=[]; removed_calls=[]; added_imports=[]; removed_imports=[]
        for _,r in g.iterrows():
            fn=str(r.get(filename) or ""); p=r.get(patch)
            paths.append(fn)
            if pd.isna(p) or not str(p).strip(): continue
            file_add=[]; file_rem=[]
            for h in parse_unified_patch(str(p)):
                for op,line in h:
                    if op=="+": add.append(line); file_add.append(line)
                    elif op=="-": rem.append(line); file_rem.append(line)
            if is_code_path(fn):
                at="\n".join(file_add); rt="\n".join(file_rem)
                added_calls.extend(calls_in_text(at)); removed_calls.extend(calls_in_text(rt))
                added_imports.extend(import_modules(at)); removed_imports.extend(import_modules(rt))
        rows.append({"case_id":cid,"added_text":"\n".join(add),"removed_text":"\n".join(rem),"path_text":"\n".join(paths),
                     "added_calls":" | ".join(sorted(set(added_calls))),"removed_calls":" | ".join(sorted(set(removed_calls))),
                     "added_imports":" | ".join(sorted(set(added_imports))),"removed_imports":" | ".join(sorted(set(removed_imports)))})
    return pd.DataFrame(rows)


def stage_flows(outroot: Path, source: Path):
    out=outroot/"03_flows"; out.mkdir(parents=True,exist_ok=True)
    text=_source(source,"case_text")
    files=_source(source,"pr_files_with_patch")
    cov=pd.read_csv(source/"01_raw"/"patch_coverage.csv")[["case_id","patch_line_coverage_ratio"]]
    identity=_join_identity(source)
    issue_title=_safe_text_col(text,["issue__title","issue_title"])
    issue_body=_safe_text_col(text,["issue__body","issue_body"])
    pr_title=_safe_text_col(text,["pr__title","pr_title"])
    pr_body=_safe_text_col(text,["pr__body","pr_body"])
    if not issue_body or not pr_body:
        raise RuntimeError(f"EXPECTED_TEXT_COLUMNS_MISSING columns={text.columns.tolist()}")
    patchdf=_case_patch_text(files)
    x=text[["case_id",issue_title,issue_body,pr_title,pr_body]].copy().merge(patchdf,on="case_id",how="left").merge(identity,on="case_id",how="left").merge(cov,on="case_id",how="left")
    rows=[]; transferred=Counter(); bridged=Counter(); transfer_repos=defaultdict(set); bridge_repos=defaultdict(set)
    for _,r in x.iterrows():
        issue=" ".join([str(r.get(issue_title) or ""),str(r.get(issue_body) or "")])
        pr=" ".join([str(r.get(pr_title) or ""),str(r.get(pr_body) or "")])
        add=str(r.get("added_text") or ""); rem=str(r.get("removed_text") or "")
        issue_t=set(word_tokens(issue)); pr_t=set(word_tokens(pr)); add_t=set(word_tokens(add)); rem_t=set(word_tokens(rem))
        add_calls=set(_explode_set(r.get("added_calls"))); rem_calls=set(_explode_set(r.get("removed_calls")))
        add_imp=set(_explode_set(r.get("added_imports"))); rem_imp=set(_explode_set(r.get("removed_imports")))
        issue_low=issue.lower(); pr_low=pr.lower(); rem_low=rem.lower()
        call_intro=add_calls-rem_calls
        import_intro=add_imp-rem_imp
        call_issue={c for c in call_intro if c.lower() in issue_low}
        call_pr={c for c in call_intro if c.lower() in pr_low}
        call_removed={c for c in call_intro if c.lower() in rem_low}
        imp_issue={m for m in import_intro if m.lower() in issue_low}
        imp_pr={m for m in import_intro if m.lower() in pr_low}
        direct=add_t & issue_t
        bridge=(add_t-issue_t)&pr_t
        novel=add_t-(issue_t|pr_t|rem_t)
        rid=int(r.repo_id) if pd.notna(r.repo_id) else -1
        for tok in direct:
            if len(tok)>=3: transferred[tok]+=1; transfer_repos[tok].add(rid)
        for tok in bridge:
            if len(tok)>=3: bridged[tok]+=1; bridge_repos[tok].add(rid)
        rows.append({
            "case_id":r.case_id,"repo_id":r.repo_id,"patch_line_coverage_ratio":r.patch_line_coverage_ratio,
            "issue_token_count":len(issue_t),"pr_token_count":len(pr_t),"added_token_count":len(add_t),"removed_token_count":len(rem_t),
            "issue_to_added_token_recall":safe_ratio(len(direct),len(issue_t)),
            "added_token_issue_anchored_fraction":safe_ratio(len(direct),len(add_t)),
            "added_token_pr_bridge_fraction":safe_ratio(len(bridge),len(add_t)),
            "added_token_novel_fraction":safe_ratio(len(novel),len(add_t)),
            "introduced_call_count":len(call_intro),
            "introduced_call_issue_anchored_fraction":safe_ratio(len(call_issue),len(call_intro)),
            "introduced_call_pr_anchored_fraction":safe_ratio(len(call_pr),len(call_intro)),
            "introduced_call_unanchored_fraction":safe_ratio(len(call_intro-(call_issue|call_pr|call_removed)),len(call_intro)),
            "introduced_import_count":len(import_intro),
            "introduced_import_issue_anchored_fraction":safe_ratio(len(imp_issue),len(import_intro)),
            "introduced_import_pr_anchored_fraction":safe_ratio(len(imp_pr),len(import_intro)),
        })
    metrics=pd.DataFrame(rows).merge(identity,on=[c for c in ["case_id","repo_id"] if c in identity.columns],how="left")
    write_csv(metrics,out/"artifact_flow_metrics.csv")
    # Repo-broad transferred and bridge vocabulary, for interpretation only.
    trows=[]
    for typ,counter,reps in [("issue_to_patch",transferred,transfer_repos),("pr_bridge_to_patch",bridged,bridge_repos)]:
        for tok,n in counter.items():
            if n<8 or len(reps[tok]-{-1})<4: continue
            trows.append({"flow_type":typ,"token":tok,"case_count":n,"repository_count":len(reps[tok]-{-1})})
    tv=pd.DataFrame(trows)
    if not tv.empty: tv=tv.sort_values(["repository_count","case_count"],ascending=False)
    write_csv(tv,out/"cross_artifact_vocabulary.csv")
    # Quantiles and robust extremes become a transparent inspection queue, not "findings".
    metric_cols=[c for c in metrics.columns if c.endswith("fraction") or c.endswith("recall")]
    extreme=[]
    for c in metric_cols:
        s=pd.to_numeric(metrics[c],errors="coerce")
        if s.notna().sum()<100: continue
        lo=s.quantile(.025); hi=s.quantile(.975)
        for side,mask in [("low",s<=lo),("high",s>=hi)]:
            for _,rr in metrics.loc[mask,["case_id","repo_id",c]].head(200).iterrows():
                extreme.append({"metric":c,"side":side,"case_id":rr.case_id,"repo_id":rr.repo_id,"value":rr[c],"threshold":lo if side=="low" else hi})
    write_csv(pd.DataFrame(extreme),out/"flow_extremes.csv")
    write_json(out/"STATUS.json",{"status":"PASS","cases":len(metrics),"flow_metrics":len(metric_cols),"vocabulary_rows":len(tv)})


def stage_cochange(outroot: Path, source: Path):
    out=outroot/"04_cochange"; out.mkdir(parents=True,exist_ok=True)
    files=_source(source,"pr_files_with_patch")
    identity=_join_identity(source)[["case_id","repo_id"]]
    filename=next(c for c in files.columns if c.lower()=="filename")
    case_items={}; item_files={}
    for cid,g in files.groupby("case_id",sort=False):
        mapping=defaultdict(set)
        for idx,fn in enumerate(g[filename].dropna().astype(str).tolist()):
            for item in path_items(fn): mapping[item].add(idx)
        case_items[int(cid)]=set(mapping)
        item_files[int(cid)]=mapping
    repo_of=dict(zip(identity.case_id.astype(int),identity.repo_id.astype(int)))
    # Marginals by repo and corpus.
    repo_cases=defaultdict(list)
    for cid in case_items: repo_cases[repo_of.get(cid,-1)].append(cid)
    marginal=Counter(); pair_obs=Counter(); pair_repos=defaultdict(set); pair_examples=defaultdict(list)
    for cid,items in case_items.items():
        for a in items: marginal[a]+=1
        ls=sorted(items)
        for i,a in enumerate(ls):
            for b in ls[i+1:]:
                # Must be realizable across two distinct changed files; filters path-token tautologies.
                fa=item_files[cid][a]; fb=item_files[cid][b]
                distinct=[(x,y) for x in fa for y in fb if x!=y]
                if not distinct: continue
                pair_obs[(a,b)]+=1; pair_repos[(a,b)].add(repo_of.get(cid,-1))
                if len(pair_examples[(a,b)]) < 8:
                    x,y=distinct[0]
                    pair_examples[(a,b)].append(cid)
    rows=[]
    for (a,b),obs in pair_obs.items():
        reps=pair_repos[(a,b)]-{-1}
        if obs<15 or len(reps)<8: continue
        expected=0.0
        for rid,cids in repo_cases.items():
            if rid==-1 or not cids: continue
            n=len(cids)
            pa=sum(a in case_items[c] for c in cids)/n
            pb=sum(b in case_items[c] for c in cids)/n
            expected += n*pa*pb
        ratio=obs/max(expected,1e-9)
        z=(obs-expected)/math.sqrt(max(expected,1e-9))
        rows.append({"item_a":a,"item_b":b,"case_count":obs,"repository_count":len(reps),
                     "repo_conditioned_expected":expected,"repo_conditioned_ratio":ratio,"repo_conditioned_z":z,
                     "support":obs/max(len(case_items),1),
                     "example_case_ids":" | ".join(map(str,pair_examples[(a,b)]))})
    df=pd.DataFrame(rows)
    if not df.empty:
        df["surprise_score"]=np.log2(df.repo_conditioned_ratio.clip(lower=1e-9)).clip(lower=0)*np.log1p(df.case_count)*np.log1p(df.repository_count)
        df=df.sort_values("surprise_score",ascending=False)
    write_csv(df,out/"cross_file_cochange_surprises.csv")
    write_json(out/"STATUS.json",{"status":"PASS","pairs":len(df),"cases":len(case_items)})


def stage_templates(outroot: Path, source: Path):
    out=outroot/"05_templates"; out.mkdir(parents=True,exist_ok=True)
    blocks=load_frame(outroot/"01_blocks"/"change_blocks")
    q=blocks[(blocks.is_code==True)&(blocks.is_generated==False)&(blocks.patch_line_coverage_ratio>=0.8)].copy()

    def collect(kind):
        groups=defaultdict(list)
        for _,r in q.iterrows():
            add=str(r.added_skeleton or "").strip(); rem=str(r.removed_skeleton or "").strip()
            if kind=="added":
                key_text=add; minlen=30
                if not key_text or len(key_text)<minlen or len(key_text)>1200: continue
                if key_text.count("ID") + len(calls_in_text(key_text)) < 2: continue
            else:
                if r.change_kind != "replace": continue
                if not add or not rem or len(add)<10 or len(rem)<10 or len(add)>1000 or len(rem)>1000: continue
                if add==rem: continue
                key_text=rem+" => "+add
                if len(key_text)<40: continue
            h=hashlib.sha1((kind+"\n"+key_text).encode("utf-8",errors="replace")).hexdigest()[:20]
            groups[h].append(r)
        rows=[]; members=[]
        for h,rs in groups.items():
            cids=sorted(set(int(r.case_id) for r in rs)); reps=sorted(set(int(r.repo_id) for r in rs if pd.notna(r.repo_id)))
            if len(cids)<3 or len(reps)<3: continue
            top=Counter(int(r.repo_id) for r in rs if pd.notna(r.repo_id)).most_common(1)[0][1]/len(rs)
            if top>0.5: continue
            exemplar=rs[0]
            rows.append({"template_id":f"V22-{kind[:1].upper()}T-"+h,"template_kind":kind,
                         "case_count":len(cids),"repository_count":len(reps),"top_repository_share":top,
                         "extension":exemplar.extension,"removed_skeleton":exemplar.removed_skeleton if kind=="replacement" else "",
                         "added_skeleton":exemplar.added_skeleton,"skeleton":key_text if False else (exemplar.added_skeleton if kind=="added" else str(exemplar.removed_skeleton)+" => "+str(exemplar.added_skeleton)),
                         "representative_removed_preview":exemplar.removed_preview,"representative_added_preview":exemplar.added_preview,
                         "representative_case_ids":" | ".join(map(str,cids[:10]))})
            for rr in rs:
                members.append({"template_id":f"V22-{kind[:1].upper()}T-"+h,"template_kind":kind,"case_id":rr.case_id,"repo_id":rr.repo_id,"filename":rr.filename})
        return rows,members

    rows=[]; members=[]
    for kind in ["added","replacement"]:
        rr,mm=collect(kind); rows.extend(rr); members.extend(mm)
    df=pd.DataFrame(rows)
    if not df.empty:
        df["template_score"]=np.log1p(df.case_count)*np.log1p(df.repository_count)*(1-df.top_repository_share)
        df=df.sort_values(["template_score","repository_count","case_count"],ascending=False)
    write_csv(df,out/"cross_repo_code_templates.csv")
    write_csv(pd.DataFrame(members),out/"cross_repo_code_template_members.csv")
    write_json(out/"STATUS.json",{"status":"PASS","templates":len(df),"members":len(members),
                                    "added_templates":int((df.template_kind=="added").sum()) if not df.empty else 0,
                                    "replacement_templates":int((df.template_kind=="replacement").sum()) if not df.empty else 0})


def _case_binary_sets(blocks, col):
    d=defaultdict(set)
    for _,r in blocks.iterrows():
        for x in _explode_set(r[col]): d[int(r.case_id)].add(x)
    return d


def _transition_null_and_bootstrap(blocks, candidates, permutations=500, bootstraps=500):
    """Validate removed->added pairs at the SAME replacement-block level.

    Null draws preserve, within every repository, the number of blocks containing
    the removed item and the number containing the added item. Repository bootstrap
    resamples repositories and recomputes the repository-conditioned block-level lift.
    """
    if candidates.empty:
        return candidates
    fam_cols={
        "call_transition":("removed_calls","added_calls"),
        "import_transition":("removed_imports","added_imports"),
        "keyword_transition":("removed_keywords","added_keywords"),
        "operator_transition":("removed_operators","added_operators"),
    }
    rng=np.random.default_rng(SEED)
    out=[]
    for fam,gcand in candidates.groupby("family"):
        oldcol,newcol=fam_cols[fam]
        nblocks=Counter(); oldcnt=Counter(); newcnt=Counter(); jointcnt=Counter()
        for _,br in blocks.iterrows():
            if pd.isna(br.repo_id):
                continue
            rid=int(br.repo_id); nblocks[rid]+=1
            olds=set(_explode_set(br[oldcol])); news=set(_explode_set(br[newcol]))
            for a in olds: oldcnt[(rid,a)]+=1
            for b in news: newcnt[(rid,b)]+=1
            for a in olds:
                for b in news:
                    if a!=b: jointcnt[(rid,a,b)]+=1
        repkeys=sorted(nblocks)
        top=gcand.sort_values("candidate_score",ascending=False).head(150)
        for _,r in top.iterrows():
            a,b=r.removed,r.added
            stats=[]
            for rid in repkeys:
                n=nblocks[rid]; aa=oldcnt[(rid,a)]; bb=newcnt[(rid,b)]; oo=jointcnt[(rid,a,b)]
                if aa or bb:
                    stats.append((n,aa,bb,oo))
            if not stats:
                continue
            arr=np.asarray(stats,dtype=int)
            nvec,avec,bvec,ovec=arr.T
            obs=int(ovec.sum())
            expected_by_repo=avec*bvec/np.maximum(nvec,1)
            expected=float(expected_by_repo.sum())
            full_lift=obs/max(expected,1e-9)
            try:
                draws=rng.hypergeometric(bvec,nvec-bvec,avec,size=(permutations,len(arr)))
                null_overlap=draws.sum(axis=1)
                p=(1+int((null_overlap>=obs).sum()))/(1+permutations)
                null_mean=float(null_overlap.mean())
            except Exception:
                p=np.nan; null_mean=np.nan
            pick=rng.integers(0,len(arr),size=(bootstraps,len(arr)))
            bo=ovec[pick].sum(axis=1)
            bexp=expected_by_repo[pick].sum(axis=1)
            lifts=bo/np.maximum(bexp,1e-9)
            out.append({**r.to_dict(),
                        "observed_same_block_joint_blocks":obs,
                        "repo_conditioned_expected_joint_blocks":expected,
                        "repo_conditioned_block_lift":full_lift,
                        "within_repo_null_mean_overlap":null_mean,
                        "within_repo_permutation_p":p,
                        "bootstrap_median_lift":float(np.median(lifts)),
                        "bootstrap_lift_gt1_fraction":float(np.mean(lifts>1)),
                        "permutations":permutations,"bootstraps":bootstraps})
    df=pd.DataFrame(out)
    if not df.empty:
        df["fdr_q"]=bh_fdr(df.within_repo_permutation_p)
    return df

def _cochange_bootstrap(cochange, files, identity, bootstraps=500):
    if cochange.empty: return cochange
    filename=next(c for c in files.columns if c.lower()=="filename")
    repo_of=dict(zip(identity.case_id.astype(int),identity.repo_id.astype(int)))
    case_items={}
    for cid,g in files.groupby("case_id",sort=False):
        mapping=defaultdict(set)
        for idx,fn in enumerate(g[filename].dropna().astype(str).tolist()):
            for item in path_items(fn): mapping[item].add(idx)
        case_items[int(cid)]=mapping
    repos=defaultdict(list)
    for cid in case_items: repos[repo_of.get(cid,-1)].append(cid)
    repkeys=[r for r in repos if r!=-1]
    rng=np.random.default_rng(SEED+1)
    out=[]
    for _,r in cochange.sort_values("surprise_score",ascending=False).head(300).iterrows():
        a,b=r.item_a,r.item_b
        stats=[]
        for rid in repkeys:
            cids=repos[rid]; n=len(cids)
            aa=bb=oo=0
            for c in cids:
                ma=case_items[c].get(a,set()); mb=case_items[c].get(b,set())
                pa=bool(ma); pb=bool(mb); joint=pa and pb and any(x!=y for x in ma for y in mb)
                aa+=pa; bb+=pb; oo+=joint
            if aa or bb: stats.append((n,aa,bb,oo))
        if not stats: continue
        arr=np.asarray(stats,dtype=float); nvec,avec,bvec,ovec=arr.T
        pick=rng.integers(0,len(arr),size=(bootstraps,len(arr)))
        bn=nvec[pick].sum(axis=1); ba=avec[pick].sum(axis=1); bb=bvec[pick].sum(axis=1); bo=ovec[pick].sum(axis=1)
        bexp=np.zeros(bootstraps,dtype=float)
        # Sum n_r p_a,r p_b,r for each sampled repo occurrence.
        exp_per_repo=nvec*(avec/np.maximum(nvec,1))*(bvec/np.maximum(nvec,1))
        bexp=exp_per_repo[pick].sum(axis=1)
        ratios=bo/np.maximum(bexp,1e-9)
        out.append({**r.to_dict(),"bootstrap_median_ratio":float(np.median(ratios)),
                    "bootstrap_ratio_gt1_fraction":float(np.mean(ratios>1)),"bootstraps":bootstraps})
    return pd.DataFrame(out)

def stage_validate(outroot: Path, source: Path):
    out=outroot/"06_validate"; out.mkdir(parents=True,exist_ok=True)
    blocks=load_frame(outroot/"01_blocks"/"change_blocks")
    q=blocks[(blocks.is_code==True)&(blocks.is_generated==False)&(blocks.change_kind=="replace")&(blocks.patch_line_coverage_ratio>=0.8)].copy()
    cand=pd.read_csv(outroot/"02_transformations"/"transition_candidates.csv")
    valid=_transition_null_and_bootstrap(q,cand)
    write_csv(valid,out/"validated_transitions.csv")
    co=pd.read_csv(outroot/"04_cochange"/"cross_file_cochange_surprises.csv")
    files=_source(source,"pr_files_with_patch")
    ident=_join_identity(source)[["case_id","repo_id"]]
    covalid=_cochange_bootstrap(co,files,ident)
    write_csv(covalid,out/"validated_cochanges.csv")
    write_json(out/"STATUS.json",{"status":"PASS","validated_transitions":len(valid),"validated_cochanges":len(covalid)})


def stage_catalog(outroot: Path, source: Path):
    out=outroot/"07_catalog"; out.mkdir(parents=True,exist_ok=True)
    rows=[]
    vt=pd.read_csv(outroot/"06_validate"/"validated_transitions.csv")
    if not vt.empty:
        good=vt[(vt.fdr_q<=0.05)&(vt.bootstrap_lift_gt1_fraction>=0.85)&(vt.repository_count>=5)&(vt.case_count>=6)].copy()
        for _,r in good.iterrows():
            score=max(0,math.log2(max(r.bootstrap_median_lift,1e-9)))*math.log1p(r.case_count)*math.log1p(r.repository_count)*r.bootstrap_lift_gt1_fraction
            rows.append({"family":r.family,"description":f"{r.family}: `{r.removed}` -> `{r.added}`",
                         "case_count":r.case_count,"repository_count":r.repository_count,"effect":r.bootstrap_median_lift,
                         "null_p":r.within_repo_permutation_p,"stability":r.bootstrap_lift_gt1_fraction,"score":score,
                         "evidence":"within-repository permutation + whole-repository bootstrap","detail":f"top_extension={r.top_extension}; raw_lift={r.lift:.3f}"})
    vc=pd.read_csv(outroot/"06_validate"/"validated_cochanges.csv")
    if not vc.empty:
        good=vc[(vc.bootstrap_ratio_gt1_fraction>=0.85)&(vc.repository_count>=8)&(vc.case_count>=15)&(vc.repo_conditioned_ratio>=1.25)].copy()
        for _,r in good.iterrows():
            score=max(0,math.log2(r.bootstrap_median_ratio))*math.log1p(r.case_count)*math.log1p(r.repository_count)*r.bootstrap_ratio_gt1_fraction
            rows.append({"family":"cross_file_cochange","description":f"cross-file `{r.item_a}` + `{r.item_b}`",
                         "case_count":r.case_count,"repository_count":r.repository_count,"effect":r.bootstrap_median_ratio,
                         "null_p":np.nan,"stability":r.bootstrap_ratio_gt1_fraction,"score":score,
                         "evidence":"repository-conditioned expectation + whole-repository bootstrap","detail":f"repo_conditioned_z={r.repo_conditioned_z:.2f}"})
    tm=pd.read_csv(outroot/"05_templates"/"cross_repo_code_templates.csv")
    if not tm.empty:
        for _,r in tm.head(120).iterrows():
            kind=str(r.template_kind)
            desc=(f"repeated added-code skeleton: {str(r.added_skeleton)[:220]}" if kind=="added"
                  else f"repeated replacement skeleton: {str(r.removed_skeleton)[:150]} => {str(r.added_skeleton)[:150]}")
            rows.append({"family":f"cross_repo_{kind}_template","description":desc,
                         "case_count":r.case_count,"repository_count":r.repository_count,"effect":np.nan,"null_p":np.nan,
                         "stability":np.nan,"score":float(r.template_score),"evidence":"exact API-preserving normalized change block repeated across repositories",
                         "detail":f"representative_cases={r.representative_case_ids}; removed={str(r.representative_removed_preview)[:180]}; added={str(r.representative_added_preview)[:180]}"})
    cat=pd.DataFrame(rows)
    if not cat.empty:
        # Family-normalized score prevents one representation from flooding the front page.
        cat["family_score_pct"]=cat.groupby("family")["score"].rank(pct=True)
        cat["global_score_pct"]=cat["score"].rank(pct=True)
        cat["final_score"]=0.65*cat.family_score_pct+0.35*cat.global_score_pct
        cat=cat.sort_values("final_score",ascending=False).reset_index(drop=True)
        cat.insert(0,"discovery_id",[f"V22-D{i:04d}" for i in range(1,len(cat)+1)])
    write_csv(cat,out/"DISCOVERY_CATALOG_V22.csv")
    # Small balanced shortlist: max 15 per family, max 60 total.
    short=[]
    if not cat.empty:
        for fam,g in cat.groupby("family",sort=False): short.append(g.head(15))
        short=pd.concat(short,ignore_index=True).sort_values("final_score",ascending=False).head(60)
    else: short=pd.DataFrame()
    write_csv(short,out/"SCIENTIFIC_SHORTLIST_V22.csv")
    write_json(out/"STATUS.json",{"status":"PASS","catalog":len(cat),"shortlist":len(short),"families":int(cat.family.nunique()) if not cat.empty else 0})


def stage_report(outroot: Path, source: Path):
    out=outroot/"08_report"; out.mkdir(parents=True,exist_ok=True)
    cat=pd.read_csv(outroot/"07_catalog"/"DISCOVERY_CATALOG_V22.csv")
    short=pd.read_csv(outroot/"07_catalog"/"SCIENTIFIC_SHORTLIST_V22.csv")
    flows=pd.read_csv(outroot/"03_flows"/"artifact_flow_metrics.csv")
    templates=pd.read_csv(outroot/"05_templates"/"cross_repo_code_templates.csv")
    blocks=load_frame(outroot/"01_blocks"/"case_change_summary")
    lines=[]
    lines.append("# Full-Corpus Outcome-Blind Change-Operation Discovery v2.2\n")
    lines.append("## Why this run exists\n")
    lines.append("v2.2 deliberately stops treating stable states, raw token frequency, path decomposition, parser errors, crawler metadata, or alternate measurements of patch size as scientific discoveries. The primary object is now an actual **change operation** or **cross-file relationship**.\n")
    lines.append("## Outcome blinding\n")
    lines.append("- Reads only the already outcome-blind v2 raw artifacts.\n- Does not query the SQLite database.\n- Does not read scanner findings, scanner status, manual labels, old/new positive cohorts, risk labels, or F1-F5.\n")
    lines.append("## Data quality\n")
    lines.append(f"- Cases: {blocks.case_id.nunique():,}\n- Cases with >=80% stored patch coverage: {(blocks.patch_line_coverage_ratio>=0.8).sum():,}\n- Change blocks: {blocks.change_blocks.sum():,.0f}\n- Source-code change blocks: {blocks.code_blocks.sum():,.0f}\n- Generated-artifact blocks kept separate: {blocks.generated_blocks.sum():,.0f}\n")
    lines.append("## Cross-artifact flow distributions\n")
    mcols=[c for c in flows.columns if c.endswith("fraction") or c.endswith("recall")]
    if mcols:
        d=flows[mcols].describe(percentiles=[.1,.25,.5,.75,.9]).T[["count","10%","25%","50%","75%","90%"]]
        lines.append(d.to_markdown()+"\n")
    lines.append("## Scientifically filtered discovery shortlist\n")
    if not short.empty:
        cols=[c for c in ["discovery_id","family","description","case_count","repository_count","effect","stability","null_p","final_score"] if c in short]
        lines.append(short[cols].to_markdown(index=False)+"\n")
    else:
        lines.append("No candidate passed the strict generic gates. This is a valid outcome.\n")
    lines.append("## Repeated cross-repository code templates\n")
    if not templates.empty:
        tcols=[c for c in ["template_id","template_kind","case_count","repository_count","extension","removed_skeleton","added_skeleton","representative_case_ids"] if c in templates.columns]
        lines.append(templates.head(30)[tcols].to_markdown(index=False)+"\n")
    lines.append("## Interpretation discipline\n")
    lines.append("A v2.2 candidate is evidence that a concrete edit transformation or cross-file pattern recurs more often than expected after repository conditioning and/or remains stable when whole repositories are resampled. It is not evidence of security, quality, maliciousness, or causation. The shortlist is intentionally small and family-balanced; if it contains only expected development practices, the correct conclusion is that the outcome-blind corpus does not reveal a stronger general pattern.\n")
    lines.append("**V2_2_CHANGE_OPERATION_DISCOVERY_COMPLETE — OUTCOME_OVERLAY_NOT_PERFORMED**\n")
    report="\n".join(lines)
    (outroot/"V2_2_DISCOVERY_REPORT.md").write_text(report,encoding="utf-8")
    write_json(outroot/"00_audit"/"FINAL_STATUS_V22.json",{
        "status":"PASS","completed_at":now_iso(),"source_runroot":str(source),"security_outcomes_read":False,
        "outcome_overlay_performed":False,"catalog_entries":len(cat),"shortlist_entries":len(short),"report":"V2_2_DISCOVERY_REPORT.md"
    })
    write_json(out/"STATUS.json",{"status":"PASS"})


STAGES={
    "audit":stage_audit,
    "blocks":stage_blocks,
    "transformations":stage_transformations,
    "flows":stage_flows,
    "cochange":stage_cochange,
    "templates":stage_templates,
    "validate":stage_validate,
    "catalog":stage_catalog,
    "report":stage_report,
}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage",required=True,choices=STAGES)
    ap.add_argument("--outroot",required=True,type=Path)
    ap.add_argument("--source",required=True,type=Path)
    a=ap.parse_args()
    a.outroot.mkdir(parents=True,exist_ok=True)
    cp=a.outroot/"checkpoints"; cp.mkdir(parents=True,exist_ok=True)
    try:
        STAGES[a.stage](a.outroot.resolve(),a.source.resolve())
        write_json(cp/f"{a.stage}.json",{"stage":a.stage,"status":"PASS","timestamp":now_iso(),"detail":""})
        print(f"STAGE_STATUS={a.stage}=PASS",flush=True)
    except Exception as exc:
        write_json(cp/f"{a.stage}.json",{"stage":a.stage,"status":"FAIL","timestamp":now_iso(),"detail":repr(exc)})
        print(f"STAGE_STATUS={a.stage}=FAIL {type(exc).__name__}: {exc}",flush=True)
        raise

if __name__=="__main__": main()
