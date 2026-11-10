#!/bin/bash
#SBATCH --job-name=E108_random5_round1
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:35:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds
printf '%s  %s\n' fa2fc448aadd255d76fe469341485d904db85f854164e1dbbaa8d87125b5fb62 "$D/random_round_runner.py" | sha256sum -c -
"$PY" -B - <<'PY'
from pathlib import Path
import hashlib
D=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds')
p=D/'policy_r1.py'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='a9f6ff52aae54abecb5f8f43092f9435850466f8b227655c5abf15ced8071883'
s=p.read_text()
old='        blocked_repeat = False\n'
new="""        # Nonzero support for every legal action, including visually unmarked clicks.
        if self.rng.random() < .05:
            types = list(map(int, np.flatnonzero(legal[:6])))
            if legal[6:].any():
                types.append(6)
            typ = self.rng.choice(types)
            if typ == 6:
                coords = np.flatnonzero(legal[6:])
                idx = 6 + int(coords[self.rng.randrange(len(coords))])
            else:
                idx = typ
            expected, conf = self._prediction(key, idx)
            self.repeat_action = None; self.repeat_age = 0
            self.pending = (key, idx, self.descriptor_fn(frame, idx), expected)
            self.stats['unrestricted_legal_probes'] += 1
            return idx, 'unrestricted_legal_probe', {'predicted_state': expected, 'confidence': conf}
        blocked_repeat = False
"""
assert s.count(old)==1
s=s.replace(old,new)
s=s.replace('    maxima = hist.max(1)','    maxima = np.minimum(hist.max(1), 3)')
s=s.replace('    mask = np.zeros(4102,bool); mask[[0,1,4]] = True',"    micro = frame.copy(); micro[2,2] = 11\n    assert state_key(micro) == state_key(frame), 'isolated animation not suppressed'\n    mask = np.zeros(4102,bool); mask[[0,1,4]] = True")
b=s.encode()
expected='fa64f8ac36680154ba65f44694d7428e4214ffbdb0c6a4e88b19d8f7a57a116d'
assert hashlib.sha256(b).hexdigest()==expected
out=D/'policy_r1_v1.py'
if out.exists():
 assert out.read_bytes()==b,'Existing version cannot be overwritten'
else:
 with out.open('xb') as f:f.write(b)
print('R1_FROZEN_SOURCE',expected,flush=True)
PY
"$PY" -B "$D/policy_r1_v1.py"
"$PY" -B "$D/random_round_runner.py" --round 1 --candidate policy_r1_v1.py --candidate-sha fa64f8ac36680154ba65f44694d7428e4214ffbdb0c6a4e88b19d8f7a57a116d --budget 512 --seeds 28901 28902 28903 --workers 2
echo E108_RANDOM_ROUND1_DONE