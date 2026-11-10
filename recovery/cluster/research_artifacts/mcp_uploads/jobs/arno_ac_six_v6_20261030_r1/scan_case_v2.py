#!/usr/bin/env python3
from pathlib import Path
import os,importlib.util,sys
ROOT=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_ac_six_v6_20261030_r1"
NODE=Path.home()/"tools/node/bin"
assert (NODE/"node").exists()
os.environ["PATH"]=str(NODE)+os.pathsep+os.environ.get("PATH","")
spec=importlib.util.spec_from_file_location("scan_case_original",ROOT/"scan_case.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.DEST=ROOT/"retry_v2"
module.EVIDENCE=ROOT/"evidence"
module.main(sys.argv[1],sys.argv[2])
