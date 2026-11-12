#!/bin/bash
#SBATCH --job-name=E074_native_mode_test
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:06:00
set -euo pipefail
umask 077
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
"$PY" - <<'PY'
import arc_agi, json
from arc_agi import OperationMode
from arcengine import GameAction
print('E074_ONLY_SOURCE_FIVE_S5I5_DEV_MODE_TEST_BEGIN',flush=True)
arc=arc_agi.Arcade(operation_mode=OperationMode.NORMAL)
env=arc.make('s5i5')
if env is None:raise RuntimeError('NORMAL mode cannot instantiate s5i5 source-five development game')
f=env.reset()
print('E074_MODE_TEST',json.dumps({
 'mode':'NORMAL','family':'s5i5','state':str(f.state.value),
 'level_completed':int(f.levels_completed),'win_levels':int(f.win_levels),
 'legal_actions':list(map(int,f.available_actions)),
 'frames':len(f.frame),'last_frame_shape':list(f.frame[-1].shape) if f.frame else [],
 'game_over':str(f.state.value)=='GAME_OVER'
}),flush=True)
print('E074_MODE_TEST_SUCCESS',flush=True)
PY