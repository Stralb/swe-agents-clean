#!/usr/bin/env python3
"""Document E126 with conservative, source-backed public-score claims."""
from pathlib import Path
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027/git_checkout')
def write(path,content):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content.strip()+'\n')
 print('DOCUMENT',path,p.stat().st_size,flush=True)
def append(path,marker,content):
 p=ROOT/path;s=p.read_text()
 if marker not in s:p.write_text(s.rstrip()+'\n\n'+content.strip()+'\n')
 print('DOCUMENT_UPDATE',path,flush=True)
write('experiments/E126/README.md',"""
# E126 — observation-conditioned click exploration for ARC-AGI-3

**Status: packaged, verified offline on public SDK, NOT submitted to Kaggle.**

E126 composes (1) a frozen N117 optimistic Bellman / PUCT agent, (2)
observation-conditioned click-contingency and rarity ranking from E124,
and (3) the teammate's frozen pretrained action-effect CNN from E125,
activated **only on Level 1** in sparse, click-only scenes with
>= 80% modal colour. The original Level 2+ strategy is untouched.

## Release files

- **src/e126_submission_agent.py** — self-contained native MyAgent
  interface and embedded pretrained effect CNN. Frozen N117 is its exact prefix.
- **notebooks/E126_Kaggle_Candidate.ipynb** — CPU/offline Kaggle notebook
  based on the supplied ARC-AGI-3-Kaggle-Starter.
- **assets/e126/effect_prior_s11.pt** — frozen peer checkpoint for regeneration.
- **experiments/E126/e126_template.py** — auditable hybrid extension source.
- **experiments/E126/build_candidate.py** — deterministic standalone generator.
- **experiments/E126/cluster_verify_reference.py** — historical verification
  against Wits public SDK traces (requires the original cluster research cache).
- **experiments/E126/results/** — E124/E125/E126 controls, per-game scores,
  ablations, predeclared robustness runs, and evidence provenance.
- **reports/E126_SUBMISSION_CANDIDATE.md** — scientific findings and caveats.

The original src/best_public_agent.py remains **unchanged**.

## Regenerate the notebook

From the repository root run:

    python experiments/E126/build_candidate.py

This writes experiments/E126/build/my_agent.py and
experiments/E126/build/E126_Kaggle_Candidate.ipynb.

Verify these **SHA-256** digests before using the candidate:

- Standalone agent: 84f27a2589575558ddb85dff2539f68d1937c6dc1a048cb3b133f6ae7005178c
- Candidate notebook: 6bbbbc5c4011d5c781e24065e70f8fea731250c07e994980c932fad41ee30b56
- Teammate checkpoint: c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9
- Frozen N117 source: 0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa

The built source is self-contained: pretrained weights are embedded in a
compressed base85 blob, validated by SHA-256 before first use. No download
or cluster path is required in Kaggle.

## Validation evidence

E128 verified that the submission agent reproduces all **75/75** stored
E126 native public episodes from 25 game families x 3 policy seeds
(76, 77, 78), with all **8,632** actions matching, including pre/post
frame hashes and rewards. The peer effect-model outputs match the
uploaded original and its weights passed strict equality checks.

E127 separately checked **1,125** native public game episodes and
**125,220** counted actions across E124, E125 and E126.
See results/integrated_audit.json and results/all_arms.csv.

Additional four predeclared policy/native seed pairs (79/48 through
82/51) improved mean SDK score in **4/4** and lost no previously
completed levels. Two had one extra public-game level; two had none.
No public initial frame changed under the different native seeds.

All 25 game families were *historically exposed to development*, and
the >=80% threshold is post hoc. These are **not hidden Kaggle results**.
A descriptive game-cluster bootstrap interval includes zero.
The 0.33 Kaggle result is from an earlier agent submission.

## Safety, ownership and submission status

At runtime the agent only receives official image observations, legal
action masks and within-session feedback. No game-name dispatch, hidden
engine state, external LLM, internet calls, unauthorized reset probes,
or other privileged access is used for action selection.

The teammate's pretrained checkpoint is included as a clearly
identified derived dependency, not represented as N117's own training.
Ensure team permission and applicable licensing before redistributing
the model in further publications or competitions.

The notebook uses the gateway rerun convention and CPU/offline wheels.
It has **not been tested in the official Kaggle rerun environment** and
has **not been submitted**. Check notebook compatibility and runtime
before spending the final competition submission. No hidden-score
improvement above 0.33 is guaranteed.

The full 8.75 MB E124/E125/E126 episode trace archive is retained on
the Wits cluster in:
~/research_artifacts/mcp_uploads/jobs/click_integrated_audit_e127_20261026/analysis/E124_E125_E126_FULL_NATIVE_EVIDENCE.zip
""")
write('reports/E126_SUBMISSION_CANDIDATE.md',"""
# E126: What changed when click selection learned from observation?

**Research-only development result — no official Kaggle submission.**

## Hypothesis

Can observation-conditioned local action-effect feedback and a
pretrained action-effect prior improve a frozen ARC-AGI-3 exploration
agent without adding task-specific solutions, an LLM or privileged state?

## Controlled comparison

The frozen N117 agent is the baseline. E124 tests background removal,
click-contingency / rarity bonuses and short action chaining. E125
transfers the teammate CNN only into sparse click-only scenes. E126
combines contingency ranking outside these scenes with the trained
prior inside them. Random-weight and visual-salience controls use the
same gating rule. A wider 70% gate was tested and rejected after
regressing a public-game completion.

| Policy seed | Frozen completed levels | E126 completed levels | Frozen SDK mean | E126 SDK mean |
|---|---:|---:|---:|---:|
| 76 | 15 | 16 | 2.093242 | 2.211518 |
| 77 | 14 | 16 | 2.054775 | 2.223942 |
| 78 | 15 | 16 | 2.096435 | 2.240737 |

Mean across three seeds: frozen N117 **2.081484**, E126 **2.225399**,
difference **+0.143915 SDK points**, about **+6.9% relative**.
These are on the **local public SDK** (0–100 scale), NOT the hidden
competition leaderboard score of 0.33.

The trained prior adds the public **s5i5** completion in every original
seed. Local action ranking recovers **lf52** for seed 77. No previously
completed family regressed in these runs.

The four predeclared additional policy/native seed pairs (79/48, 80/49,
81/50, 82/51) gave SDK deltas of **+0.134875, +0.037532, +0.033191,
+0.128988**; level deltas **+1, 0, 0, +1**. No lost completions.
Changing the native seed did not change any initial game image.

## Mechanistic limitations

The E124 rarity-only and local-effect-only ablations can reproduce
the first seed's score advantage independently. Hence that
advantage is **not attributable uniquely to causal learning**.
The effect prior was pretrained to predict action effects; it does
not establish that online RL received more reward information.
The advantage in aggregate is concentrated in a small number of
familiar public game families.

## Evidence quality and acceptance gate

E127 checked 1,125 native episodes and 125,220 charged actions.
The packaged E128 submission reproduced all 75 E126 reference
episodes and all 8,632 actions, frames, and rewards exactly.
Checksums confirm the original teammate pretrained model.
See experiments/E126/results and the original 8.75 MB trace archive.

These games and the sparse threshold informed development, so this
is **not an independent generalisation test**. A descriptive
game-cluster bootstrap interval for improvement includes zero.
A better public SDK score need not beat 0.33 on hidden Kaggle games.
The candidate should be retained **alongside**, not silently
replace, the previously submitted 0.33 baseline.

The notebook is a reproducible candidate for **later optional**
submission, not evidence of a completed new competition run.
""")
append('README.md','## E126 Kaggle submission candidate',"""
## E126 Kaggle submission candidate

The frozen N117 agent has a newly packaged hybrid extension, E126,
combining local click feedback with a selectively activated teammate
pretrained action-effect model. Full details:
[experiments/E126/README.md](experiments/E126/README.md).
The [candidate notebook](notebooks/E126_Kaggle_Candidate.ipynb)
is **not submitted**. No hidden-score improvement beyond 0.33 is verified.
""")
append('notebooks/README.md','E126_Kaggle_Candidate.ipynb',"""
E126_Kaggle_Candidate.ipynb packages the selectively transferred
pretrained-effect-prior and observation-based click ranking over the
frozen N117 agent. This is an **unsubmitted** Kaggle-ready-format
candidate; all improvements are measured on exposed public games.
See experiments/E126/README.md for rebuild and validity checks.
""")
append('reports/INDEX.md','E126_SUBMISSION_CANDIDATE.md',"""
- [E126 click-exploration candidate](E126_SUBMISSION_CANDIDATE.md):
  controlled ablations, local SDK robustness, verified release and caveats.
""")
print('E128_DOCS_STAGED',flush=True)
