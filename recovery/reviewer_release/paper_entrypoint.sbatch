#!/bin/bash
#SBATCH --job-name=arno-paper-entry
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
/home-mscluster/astrauss/.venvs/huggingface/bin/python -u - <<'PY'
import subprocess,os
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts')
deps=root/'mcp_uploads/jobs/paper_entrypoint_20261111_v2/dependencies'
python='/home-mscluster/astrauss/.venvs/huggingface/bin/python'
subprocess.run([python,'-m','pip','install','--disable-pip-version-check','--target',str(deps),'pyarrow==19.0.1','PyYAML==6.0.2'],check=True)
env=dict(os.environ);env['PYTHONPATH']=str(deps)
subprocess.run([python,'-u',str(root/'mcp_uploads/jobs/paper_entrypoint_20261111_v1/build_paper_dataset.py'),'--database',str(root/'ARNO_REVIEW_RELEASE_20261111_v1/ARNO_RESEARCH_MASTER_REVIEW.sqlite'),'--output',str(root/'ARNO_PAPER_CASES_20261111_v1'),'--publish'],env=env,check=True)
PY
