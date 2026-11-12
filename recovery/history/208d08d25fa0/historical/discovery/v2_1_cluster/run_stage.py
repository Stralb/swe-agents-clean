from __future__ import annotations
import os, subprocess, sys
from pathlib import Path
stage=os.environ["STAGE"]
source=os.environ["SOURCE_RUNROOT"]
outroot=os.environ["V21_RUNROOT"]
analysis_dir=Path(os.environ["ANALYSIS_DIR"])
python_bin=os.environ.get("PYTHON_BIN",sys.executable)
cmd=[python_bin,str(analysis_dir/"v21_runner.py"),"--stage",stage,"--source-runroot",source,"--outroot",outroot]
print("RUNNING_V21_STAGE="+stage,flush=True)
print("COMMAND="+" ".join(cmd),flush=True)
raise SystemExit(subprocess.call(cmd))
