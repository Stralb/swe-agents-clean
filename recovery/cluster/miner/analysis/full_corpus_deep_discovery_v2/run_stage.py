from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

stage=os.environ["STAGE"]
runroot=os.environ["RUNROOT"]
db=os.environ["DB"]
repo=os.environ["REPO"]
analysis_dir=Path(os.environ["ANALYSIS_DIR"])
python_bin=os.environ.get("PYTHON_BIN",sys.executable)
cmd=[python_bin,str(analysis_dir/"deep_discovery.py"),"--stage",stage,"--runroot",runroot,"--db",db,"--repo",repo]
print("RUNNING_STAGE="+stage,flush=True)
print("COMMAND="+" ".join(cmd),flush=True)
raise SystemExit(subprocess.call(cmd))
