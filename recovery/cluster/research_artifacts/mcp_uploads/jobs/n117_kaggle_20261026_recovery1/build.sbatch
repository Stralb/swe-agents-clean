#!/bin/bash
#SBATCH --job-name=arc3n117rebuild
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
python3 - <<'PY'
import ast
import hashlib
import json
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
old=root/'n117_kaggle_20261026_v2/kernel'
output=root/'n117_kaggle_20261026_recovery1/kernel'
output.mkdir(parents=True,exist_ok=True)
original=(old/'submission.ipynb').read_bytes()
assert hashlib.sha256(original).hexdigest()=='fa080512b18936a8f9156b22530dbb4cad08e8594759a91fc103b2606767f48b'
notebook=json.loads(original)
assert len(notebook['cells'])==5
agent=root/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'
assert hashlib.sha256(agent.read_bytes()).hexdigest()=='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
ast.parse(agent.read_text())
assert all('my_agent.py' in ''.join(notebook['cells'][2]['source']) for _ in [0])
run='''import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

if os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
    print("N117_PHASE_B_ENTERED", flush=True)
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    comp = Path("/kaggle/input/competitions/arc-prize-2026-arc-agi-3")
    wheels = comp / "arc_agi_3_wheels"
    if not wheels.is_dir():
        raise RuntimeError("ARC competition wheelhouse missing in Phase B")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--no-index",
        "--find-links", str(wheels), "arc-agi", "python-dotenv",
    ], check=True)
    print("N117_OFFLINE_DEPENDENCIES_OK", flush=True)
    src=Path("/tmp/my_agent.py")
    assert hashlib.sha256(src.read_bytes()).hexdigest()=="0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa"
    print("N117_FROZEN_AGENT_OK", flush=True)
    framework_source=comp / "ARC-AGI-3-Agents"
    if not framework_source.is_dir():
        raise RuntimeError("ARC competition framework directory missing")
    framework=Path("/kaggle/working/ARC-AGI-3-Agents")
    shutil.copytree(framework_source,framework)
    shutil.copy2(src,framework/"agents/templates/my_agent.py")
    init_source = """from typing import Type
from threading import BoundedSemaphore, Thread as _Thread
from dotenv import load_dotenv
from .agent import Agent, Playback
from .swarm import Swarm
from .templates.random_agent import Random
from .templates.my_agent import MyAgent
from . import swarm as _swarm_module

class _BoundedThread(_Thread):
    _slots = BoundedSemaphore(12)
    def run(self):
        with self._slots:
            return super().run()

_swarm_module.Thread = _BoundedThread
load_dotenv()
AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
    "random": Random,
    "myagent": MyAgent,
}
"""
    (framework/"agents/__init__.py").write_text(init_source)
    swarm_path=framework/"agents/swarm.py"
    swarm_text=swarm_path.read_text()
    if swarm_text.count("record=True,")!=1:
        raise RuntimeError("Unexpected upstream Swarm recording contract")
    swarm_path.write_text(swarm_text.replace("record=True,","record=False,",1))
    (framework/".env").write_text("""SCHEME=http
HOST=gateway
PORT=8001
ARC_API_KEY=REDACTED_CREDENTIAL
ARC_BASE_URL=http://gateway:8001/
OPERATION_MODE=online
ENVIRONMENTS_DIR=
RECORDINGS_DIR=/kaggle/working/server_recording
""")
    print("N117_FRAMEWORK_READY",flush=True)
    deadline=time.monotonic()+600
    gateway_url="http://gateway:8001/api/games"
    retries=0
    while True:
        try:
            req=Request(gateway_url,headers={"X-API-Key":"test-key-123"})
            with urlopen(req,timeout=8) as response:
                if response.status==200:
                    print("N117_GATEWAY_READY",flush=True)
                    break
        except (URLError,HTTPError,OSError) as exc:
            retries+=1
            if retries==1 or retries%12==0:
                print("N117_GATEWAY_WAIT",type(exc).__name__,retries,flush=True)
        if time.monotonic()>=deadline:
            raise RuntimeError("Gateway did not become available within 600 seconds")
        time.sleep(5)
    print("N117_AGENT_LAUNCH",flush=True)
    subprocess.run(
        [sys.executable,"main.py","--agent","myagent"],
        cwd=framework,
        env=os.environ.copy(),
        check=True,
    )
    print("N117_AGENT_FINISHED",flush=True)
else:
    print("N117_PHASE_A_COMMIT_ONLY",flush=True)
'''
compile(run,'n117_rerun_cell.py','exec')
notebook['cells'][3]['source']=run.splitlines(keepends=True)
notebook['cells'][3]['outputs']=[]
notebook['cells'][3]['execution_count']=None
notebook['cells'][0]['source']=['# N117 Recovery: Frozen Local-Effect Agent\n','Fresh Kaggle kernel with guarded offline gateway startup, bounded workers, and disabled redundant recordings.\n']
metadata=json.loads((old/'kernel-metadata.json').read_text())
assert metadata['dataset_sources']==['arnostrauss/arc-agi-3-n117-agent-source-20261026']
assert metadata['competition_sources']==['arc-prize-2026-arc-agi-3']
metadata['id']='arnostrauss/arc-agi-3-n117-recovery-20261026'
metadata['title']='ARC AGI 3 N117 Recovery 20261026'
metadata['keywords']=['reinforcement-learning']
(output/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2))
(output/'submission.ipynb').write_text(json.dumps(notebook,ensure_ascii=False,separators=(',',':')))
nbbytes=(output/'submission.ipynb').read_bytes()
assert len(nbbytes)<500000
assert all(json.loads(original)['cells'][i]==notebook['cells'][i] for i in (1,2,4))
assert hashlib.sha256(agent.read_bytes()).hexdigest()=='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
print("REBUILD_READY",len(nbbytes),hashlib.sha256(nbbytes).hexdigest())
print("FROZEN_SOURCE_INTACT")
print("NOTEBOOK_SLUG",metadata['id'])
print("ONLY_WRAPPER_CHANGED")
PY