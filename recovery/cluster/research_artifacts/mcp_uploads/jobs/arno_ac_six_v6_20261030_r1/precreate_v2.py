#!/usr/bin/env python3
from pathlib import Path
ROOT=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_ac_six_v6_20261030_r1"/"retry_v2"/"results"
for case in ("03429","03581","08152","12344","31207","32759"):
 p=ROOT/("CASE_"+case)
 p.mkdir(parents=True,exist_ok=True)
 print("READY",p,flush=True)
