from __future__ import annotations

import argparse
import traceback
from pathlib import Path

from v21_common import checkpoint
from v21_analysis import (
    stage_audit, stage_redundancy, stage_associations, stage_patterns,
    stage_motifs, stage_templates, stage_temporal, stage_stability,
    stage_catalog, stage_report,
)

STAGES = {
    "audit": stage_audit,
    "redundancy": stage_redundancy,
    "associations": stage_associations,
    "patterns": stage_patterns,
    "motifs": stage_motifs,
    "templates": stage_templates,
    "temporal": stage_temporal,
    "stability": stage_stability,
    "catalog": stage_catalog,
    "report": stage_report,
}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage",required=True,choices=list(STAGES))
    ap.add_argument("--source-runroot",required=True)
    ap.add_argument("--outroot",required=True)
    args=ap.parse_args()
    source=Path(args.source_runroot).resolve();outroot=Path(args.outroot).resolve();outroot.mkdir(parents=True,exist_ok=True)
    stage=args.stage
    try:
        STAGES[stage](source,outroot)
        checkpoint(outroot,stage,"PASS")
    except Exception as exc:
        checkpoint(outroot,stage,"FAIL",detail=f"{type(exc).__name__}: {exc}")
        (outroot/"logs").mkdir(parents=True,exist_ok=True)
        (outroot/"logs"/f"{stage}.exception.txt").write_text(traceback.format_exc(),encoding="utf-8")
        raise

if __name__=="__main__":main()
