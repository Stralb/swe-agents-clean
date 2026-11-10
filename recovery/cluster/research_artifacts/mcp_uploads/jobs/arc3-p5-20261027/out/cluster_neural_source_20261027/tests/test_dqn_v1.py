import random

import numpy as np
import torch

from src.adapter import NO_ACTION, Observation, Transition, build_mask
from src.dqn_v1 import DQNV1
from src.dqn_v1.exploration import StructuredExplorer
from src.dqn_v1.prior import load_prior, state_outputs


def _obs(avail=(1,2,3,4,6,7), seed=1):
    r=np.random.default_rng(seed)
    f=r.integers(0,13,(64,64),dtype=np.int8)
    return Observation(f,f.copy(),build_mask(avail),NO_ACTION,0,0,5)


def test_v1_checkpoint_loads_and_action_is_legal():
    d=DQNV1('ls20', {
        'gamma':0.99,'learning_rate':1e-4,'batch_size':8,'replay_capacity':4096,'warmup_actions':16,
        'train_every_actions':8,'target_update_actions':80,'gradient_clip_norm':10.0,'hidden_dim':128,
        'epsilon_start':1.0,'epsilon_end':0.1,'epsilon_decay_actions':400,'per_alpha':0.6,
        'per_beta_start':0.4,'per_beta_end':1.0,'per_eps':1e-4,'c51_atoms':51,'c51_vmin':0.0,'c51_vmax':5.0,
    })
    d.start_run(5209)
    for avail in ((6,), (1,2,3,4), (3,4,6,7), (5,6,7)):
        o=_obs(avail, 9)
        idx=d.act(o)
        assert o.mask[idx]
        d.pending=None


def test_v1_refuses_unknown_game_without_deployment_checkpoint():
    d=DQNV1('unknown_private_game', {})
    try:
        d.start_run(1)
    except ValueError as e:
        assert 'deployment checkpoint' in str(e)
    else:
        raise AssertionError('V1 must not silently select an arbitrary public fold checkpoint')
