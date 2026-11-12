from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from deep_common import checkpoint
from deep_extract import stage_extract, stage_quality
from deep_repr import stage_structured, stage_text_views, stage_path_views, stage_patch_views, stage_syntax_views
from deep_models import stage_view_models, stage_topics, stage_templates, stage_graphs
from deep_cross import stage_crossview, stage_associations, stage_temporal, stage_generalizability, stage_stability, stage_catalog
from deep_patterns import stage_frequent_patterns
from deep_report import stage_report

STAGES = {
    "extract": lambda r, db, repo: stage_extract(r, db, repo),
    "quality": lambda r, db, repo: stage_quality(r),
    "structured": lambda r, db, repo: stage_structured(r),
    "text_views": lambda r, db, repo: stage_text_views(r),
    "path_views": lambda r, db, repo: stage_path_views(r),
    "patch_views": lambda r, db, repo: stage_patch_views(r),
    "syntax_views": lambda r, db, repo: stage_syntax_views(r),
    "view_models": lambda r, db, repo: stage_view_models(r),
    "topics": lambda r, db, repo: stage_topics(r),
    "templates": lambda r, db, repo: stage_templates(r),
    "graphs": lambda r, db, repo: stage_graphs(r),
    "crossview": lambda r, db, repo: stage_crossview(r),
    "associations": lambda r, db, repo: stage_associations(r),
    "frequent_patterns": lambda r, db, repo: stage_frequent_patterns(r),
    "temporal": lambda r, db, repo: stage_temporal(r),
    "generalizability": lambda r, db, repo: stage_generalizability(r),
    "stability": lambda r, db, repo: stage_stability(r),
    "catalog": lambda r, db, repo: stage_catalog(r),
    "report": lambda r, db, repo: stage_report(r),
}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=sorted(STAGES))
    ap.add_argument("--runroot", required=True)
    ap.add_argument("--db")
    ap.add_argument("--repo")
    args=ap.parse_args()
    runroot=Path(args.runroot).resolve(); db=Path(args.db).resolve() if args.db else None; repo=Path(args.repo).resolve() if args.repo else None
    stage=args.stage
    checkpoint(runroot,stage,"RUNNING")
    try:
        STAGES[stage](runroot,db,repo)
        checkpoint(runroot,stage,"PASS")
        print(f"STAGE_STATUS={stage}=PASS",flush=True)
    except Exception as exc:
        detail=f"{type(exc).__name__}: {exc}"
        checkpoint(runroot,stage,"FAIL",detail)
        err=runroot/"logs"/f"{stage}.exception.txt"; err.parent.mkdir(parents=True,exist_ok=True); err.write_text(traceback.format_exc(),encoding="utf-8")
        print(f"STAGE_STATUS={stage}=FAIL {detail}",file=sys.stderr,flush=True)
        traceback.print_exc()
        raise

if __name__=="__main__":
    main()
