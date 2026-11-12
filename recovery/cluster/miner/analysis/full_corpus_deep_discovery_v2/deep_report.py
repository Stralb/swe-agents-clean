from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from deep_common import file_sha256s, load_frame, now_iso, write_csv, write_json

EXPECTED_STAGES = [
    "extract","quality","structured","text_views","path_views","patch_views","syntax_views",
    "view_models","topics","templates","graphs","crossview","associations","frequent_patterns","temporal",
    "generalizability","stability","catalog",
]


def _read_json(path: Path):
    try:return json.loads(path.read_text())
    except Exception:return None



def _read_csv_safe(path: Path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

def stage_report(runroot: Path) -> None:
    out=runroot/"14_report"; out.mkdir(parents=True,exist_ok=True)
    checkpoint_rows=[]; failures=[]
    for s in EXPECTED_STAGES:
        p=runroot/"checkpoints"/f"{s}.json"; x=_read_json(p)
        status=x.get("status") if x else "MISSING"
        checkpoint_rows.append({"stage":s,"status":status,"timestamp":x.get("timestamp") if x else None,"detail":x.get("detail") if x else None})
        if status!="PASS":failures.append(f"{s}:{status}")
    write_csv(pd.DataFrame(checkpoint_rows),out/"stage_status.csv")
    if failures:
        raise RuntimeError("REPORT_BLOCKED_INCOMPLETE_STAGES="+",".join(failures))

    inv=_read_json(runroot/"02_quality"/"invariants.json") or {}
    extract=_read_json(runroot/"00_manifest"/"EXTRACT_SUMMARY.json") or {}
    patch=_read_json(runroot/"02_quality"/"patch_coverage_summary.json") or {}
    catalog_path=runroot/"13_catalog"/"DISCOVERY_CATALOG.csv"
    catalog=_read_csv_safe(catalog_path) if catalog_path.exists() else pd.DataFrame()
    model_path=runroot/"04_view_models"/"model_selection.csv"
    models=_read_csv_safe(model_path) if model_path.exists() else pd.DataFrame()
    sim_path=runroot/"08_crossview"/"view_similarity.csv"
    sim=_read_csv_safe(sim_path) if sim_path.exists() else pd.DataFrame()
    trend_path=runroot/"10_temporal_exhaustive"/"all_temporal_trends.csv"
    trends=_read_csv_safe(trend_path) if trend_path.exists() else pd.DataFrame()
    gen_path=runroot/"11_generalizability"/"pattern_generalizability.csv"
    gen=_read_csv_safe(gen_path) if gen_path.exists() else pd.DataFrame()

    lines=[]
    lines.append("# Full-Corpus Schema-Driven Multi-View Discovery v2.0")
    lines.append("")
    lines.append("## Scope and interpretation boundary")
    lines.append("This run is outcome-blind. It searches for stable structure across safely accessible objective database representations without optimizing for any predetermined software-development or security hypothesis. Scanner/security outcomes and manual security/risk annotations were not read. Discovered structures are unnamed analytical findings until later human interpretation.")
    lines.append("")
    lines.append("## Corpus")
    lines.append(f"- Cases: {inv.get('rows')}")
    lines.append(f"- Repositories: {inv.get('repositories')}")
    lines.append(f"- Case scalar features extracted: {extract.get('scalar_features')}")
    lines.append(f"- PR-file rows: {extract.get('pr_file_rows')}")
    lines.append(f"- Cases with stored patch content: {patch.get('any_patch')}")
    lines.append(f"- Cases with patch-line coverage >= 0.80: {patch.get('coverage_ge_0_80')}")
    lines.append("")
    lines.append("## Discovery operators executed")
    lines.append("- Automatic relational schema aggregation over every safely case-linkable objective table.")
    lines.append("- Structured scalar representation with automatic typing, missingness indicators, high-cardinality frequency encoding, and redundancy pruning.")
    lines.append("- Independent issue/PR text word and character n-gram views.")
    lines.append("- Raw path-token, path-character, and binary co-change representations.")
    lines.append("- Raw added/removed patch lexical views, normalized code-token n-grams, unified-diff operation-shape views, and patch morphology.")
    lines.append("- Tree-sitter node-type representations where parsers were available, with generic lexer-type fallback otherwise.")
    lines.append("- Per-view K-means/HDBSCAN model search, anomaly detection, and 200 repository-blocked stability resamples.")
    lines.append("- Multi-resolution NMF latent pattern discovery across nonnegative sparse views.")
    lines.append("- Mutual-kNN near-duplicate/template discovery and co-occurrence graph/community mining.")
    lines.append("- Cross-view CKA, nearest-neighbor agreement, equal-weight multi-view fusion, and shared-space cross-artifact alignment with within-repository null pairings.")
    lines.append("- Exhaustive mixed-type relationship discovery over the assembled objective/latent feature table.")
    lines.append("- Automatic quantile/category itemization with multi-support Eclat frequent-itemset and association-rule mining.")
    lines.append("- Exhaustive supported temporal trend/change-point scan across available timestamps and discovered features.")
    lines.append("- Repository/language/time generalizability profiling of emergent discrete patterns.")
    lines.append("- 500 repository-blocked relationship bootstrap iterations plus within-repository permutation nulls for top relationships.")
    lines.append("")

    lines.append("## Computational scale")
    lines.append(f"- Per-view model-selection rows: {len(models)}")
    if not models.empty:
        lines.append(f"- Distinct embedding views modeled: {models['view'].nunique() if 'view' in models else 'unknown'}")
    lines.append(f"- Cross-view comparisons: {len(sim)}")
    lines.append(f"- Temporal feature/time-column trends retained: {len(trends)}")
    lines.append(f"- Generalizability patterns profiled: {len(gen)}")
    lines.append(f"- Discovery-catalog entries: {len(catalog)}")
    lines.append("")

    if not catalog.empty:
        lines.append("## Highest-ranked unnamed discoveries")
        top=catalog.head(100)
        keep=[c for c in ["discovery_id","type","description","effect","support","repository_coverage","stability","null_p","rank_score","evidence_path"] if c in top.columns]
        lines.append("| "+" | ".join(keep)+" |")
        lines.append("| "+" | ".join(["---"]*len(keep))+" |")
        for _,r in top.iterrows():
            vals=[]
            for c in keep:
                v=r[c]
                txt="" if pd.isna(v) else str(v).replace("|","\\|").replace("\n"," ")
                if len(txt)>240:txt=txt[:237]+"..."
                vals.append(txt)
            lines.append("| "+" | ".join(vals)+" |")
        lines.append("")

    if not sim.empty:
        lines.append("## Strongest cross-view representation agreements")
        top=sim.sort_values("linear_cka",ascending=False).head(30)
        lines.append(top[[c for c in ["view_a","view_b","linear_cka","median_knn_jaccard"] if c in top.columns]].to_markdown(index=False))
        lines.append("")

    lines.append("## Required interpretation discipline")
    lines.append("A high-ranked discovery is evidence of a stable statistical/structural regularity in this corpus, not evidence of causation, quality, security, maliciousness, or a universal property of AI coding. Repository concentration, temporal support, patch coverage, and representation provenance must be checked before naming any discovery.")
    lines.append("")
    lines.append("**DEEP_DISCOVERY_COMPLETE — OUTCOME_OVERLAY_NOT_PERFORMED**")
    (runroot/"DEEP_DISCOVERY_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

    # Reproducibility checksums are generated last. Exclude the checksum file itself inside helper.
    sums=file_sha256s(runroot); write_csv(sums,runroot/"00_manifest"/"SHA256SUMS_V2.tsv")
    write_json(runroot/"00_manifest"/"FINAL_STATUS_V2.json",{
        "status":"PASS","completed_at":now_iso(),"deep_discovery_complete":True,
        "outcome_overlay_performed":False,"security_outcomes_read":False,
        "catalog_entries":int(len(catalog)),"report":"DEEP_DISCOVERY_REPORT.md",
    })
