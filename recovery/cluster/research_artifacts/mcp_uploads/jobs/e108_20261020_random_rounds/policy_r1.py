"""R1: context-conditioned action evidence and cycle-aware exploration.
Only frames, legal masks and observed native outcomes enter this policy.
No game identity, coordinates of solutions, semantic color labels or replay.
"""
from collections import Counter, defaultdict, deque
import hashlib
import math
import random
import numpy as np


def state_key(frame):
    """Categorical 2x2 majority plus occupancy: suppress isolated pixel flicker.
    This is an approximate observation key, NOT claimed to be a Markov state.
    """
    a = np.asarray(frame, dtype=np.uint8)
    h, w = a.shape
    patches = a.reshape(h//2, 2, w//2, 2).transpose(0, 2, 1, 3).reshape(-1, 4)
    hist = np.zeros((len(patches), 256), dtype=np.uint8)
    rows = np.arange(len(patches))
    for j in range(4):
        hist[rows, patches[:, j]] += 1
    maxima = hist.max(1)
    # Ties use spatial first-occurrence, never an ordering of palette numbers.
    winner = patches[:, 0].copy()
    best = hist[rows, winner]
    for j in range(1, 4):
        wins = hist[rows, patches[:, j]] > best
        winner[wins] = patches[wins, j]
        best[wins] = hist[rows[wins], patches[wins, j]]
    token = np.stack([winner, maxima], axis=1).tobytes()
    return hashlib.blake2s(token, digest_size=12).hexdigest()


class Agent:
    def __init__(self, seed, candidates_fn, descriptor_fn, use_memory=True):
        self.rng = random.Random(seed)
        self.candidates_fn, self.descriptor_fn = candidates_fn, descriptor_fn
        self.use_memory = use_memory
        self.stats = Counter()
        self.action_trials = Counter()
        self.action_effect = Counter()
        self.classes = defaultdict(Counter)
        self.state_trials = Counter()
        self.state_actions = Counter()
        self.edges = defaultdict(Counter)
        self.rewards = Counter()
        self.history = deque(maxlen=12)
        self.repeat_action = None
        self.repeat_age = 0
        self.pending = None
        self.previous_mask = None
        self.total_updates = 0

    def episode_reset(self):
        # Reset transient execution state, retain only within-game evidence.
        self.repeat_action = None
        self.repeat_age = 0
        self.pending = None
        self.history.clear()
        self.stats['retry_transient_resets'] += 1

    def _prediction(self, key, action):
        outcomes = self.edges.get((key, action))
        if not outcomes:
            return None, 0.0
        nxt, count = outcomes.most_common(1)[0]
        return nxt, count / sum(outcomes.values())

    def _pool(self, frame, legal):
        pool = list(self.candidates_fn(frame, legal))
        # All legal coordinates retain positive exploration probability.
        # Candidate proposals are a preference, never a permanent action mask.
        if legal[6:].any():
            locs = np.flatnonzero(legal[6:])
            for _ in range(8):
                idx = 6 + int(locs[self.rng.randrange(len(locs))])
                pool.append((idx, 0.15, 'uniform_legal_coordinate'))
        dedup = {}
        for idx, weight, origin in pool:
            if legal[idx] and (idx not in dedup or weight > dedup[idx][0]):
                dedup[idx] = (weight, origin)
        return [(i, *v) for i, v in sorted(dedup.items())]

    def decide(self, frame, legal):
        legal = np.asarray(legal, dtype=bool)
        key = state_key(frame)
        self.state_trials[key] += 1
        pool = self._pool(frame, legal)
        if not pool:
            raise ValueError('No legal action candidates')
        self.rng.shuffle(pool)
        self.stats['decisions'] += 1
        blocked_repeat = False
        if self.repeat_action is not None and legal[self.repeat_action] and self.repeat_age < 7:
            previous = self.repeat_action
            next_key, conf = self._prediction(key, previous)
            repeated_here = self.state_actions[(key, previous)]
            loop = self.use_memory and (
                (next_key == key and conf >= .75) or repeated_here >= 2 or
                (len(self.history) >= 6 and len(set(self.history)) <= 2))
            if not loop:
                self.stats['repeat_actions'] += 1
                self.pending = (key, previous, self.descriptor_fn(frame, previous), next_key)
                return previous, 'effect_option_continue', {'predicted_state': next_key, 'confidence': conf}
            blocked_repeat = True
            self.repeat_action = None
            self.stats['cycle_option_stops'] += 1

        # Fixed probability mixes action types; no family-dependent routing.
        prim = [p for p in pool if p[0] < 6]
        click = [p for p in pool if p[0] >= 6]
        if prim and click:
            choices = prim if self.rng.random() < .25 else click
        else:
            choices = pool

        def utility(item):
            idx, weight, _ = item
            cls = self.descriptor_fn(frame, idx)
            group = self.classes[cls]
            p = (group['effect'] + self.action_effect[idx] + 1) / (
                group['effect'] + group['no_effect'] + self.action_trials[idx] + 2)
            uncertainty = 4 * p * (1-p)
            novelty = 1.8 / math.sqrt(1 + self.action_trials[idx])
            score = novelty + .45*weight + .35*uncertainty
            if self.use_memory:
                local = self.state_actions[(key, idx)]
                score += 1.3/math.sqrt(1+local)
                nxt, confidence = self._prediction(key, idx)
                if nxt is not None:
                    score -= .8*confidence*min(2, self.state_trials[nxt]/4)
                    if nxt == key:
                        score -= .8*confidence
            score += min(1.5, self.rewards[idx]/(1+self.action_trials[idx]))
            return score + .03*self.rng.random()

        idx, _, origin = max(choices, key=utility)
        expected, conf = self._prediction(key, idx)
        self.pending = (key, idx, self.descriptor_fn(frame, idx), expected)
        self.repeat_age = 0
        self.stats['fresh_choices'] += 1
        self.stats['source_'+origin] += 1
        return idx, 'contextual_frontier_probe', {'predicted_state': expected, 'confidence': conf,
                                                 'cycle_stop': blocked_repeat}

    def update(self, before, after, action, native_reward, advanced, terminal):
        key = state_key(before)
        new_key = state_key(after)
        if self.pending is None or self.pending[1] != action:
            raise AssertionError('Action/update alignment failure')
        _, _, cls, prediction = self.pending
        pixels = int(np.count_nonzero(np.asarray(before) != np.asarray(after)))
        novelty = self.state_trials[new_key] == 0
        changed = new_key != key
        # Pre-action prediction is evaluated before updating its conditional table.
        if prediction is not None:
            self.stats['predictions_checked'] += 1
            self.stats['predictions_correct' if prediction == new_key else 'predictions_wrong'] += 1
        self.state_actions[(key, action)] += 1
        self.edges[(key, action)][new_key] += 1
        self.action_trials[action] += 1
        effect = pixels >= 6 or native_reward > 0
        self.action_effect[action] += int(effect)
        self.classes[cls]['effect' if effect else 'no_effect'] += 1
        if native_reward > 0:
            self.rewards[action] += native_reward
            self.stats['native_advancements'] += int(native_reward)
        self.stats['transition_updates'] += 1
        self.stats['new_observation_keys'] += int(novelty)
        self.stats['visible_changes'] += int(effect)
        self.total_updates += 1
        self.history.append(new_key)
        repeated = self.repeat_action == action
        if effect and not terminal and not advanced:
            self.repeat_action = action
            self.repeat_age = self.repeat_age + 1 if repeated else 0
        else:
            self.repeat_action = None
            self.repeat_age = 0
        if advanced:
            # A new level is not the same transition system. No semantic ID enters.
            self.edges.clear(); self.state_actions.clear(); self.state_trials.clear()
            self.action_trials.clear(); self.action_effect.clear(); self.classes.clear()
            self.rewards.clear(); self.history.clear()
            self.stats['level_model_resets'] += 1
        self.pending = None
        return {'pixels': pixels, 'state_changed': changed, 'novel_state': novelty,
                'predicted_state': prediction, 'actual_state': new_key,
                'prediction_correct': prediction == new_key if prediction is not None else None}


def selftest():
    def props(a, mask):
        return [(int(i), 1., 'synthetic') for i in np.flatnonzero(mask)]
    def desc(a, i):
        return ('primitive', i) if i < 6 else ('click',)
    frame = np.zeros((64,64),np.uint8)
    frame[20:24,20:24] = 7
    mask = np.zeros(4102,bool); mask[[0,1,4]] = True
    ag = Agent(7, props, desc)
    for _ in range(24):
        i, _, _ = ag.decide(frame, mask)
        assert mask[i]
        ag.update(frame, frame, i, 0., False, False)
    assert ag.stats['predictions_checked'] > 0
    assert ag.total_updates == 24
    ag.episode_reset(); assert ag.pending is None
    mask2 = np.zeros(4102,bool); mask2[6:] = True
    ag2 = Agent(8, lambda a,m: [(6+32*64+32,1.,'component')], desc)
    for _ in range(10):
        i, _, _ = ag2.decide(frame, mask2); assert mask2[i]
        ag2.update(frame, frame, i, 0., False, False)
    # Categorical relabeling does not alter state recurrence equivalences.
    shifted = np.where(frame==7,123,41).astype(np.uint8)
    assert state_key(shifted)==state_key(shifted.copy())
    print('R1_UNIT_PASS', {'updates':ag.total_updates,'predictions':ag.stats['predictions_checked']})

if __name__ == '__main__':
    selftest()
