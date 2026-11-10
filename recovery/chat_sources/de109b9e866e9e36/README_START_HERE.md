# E-PILOT653 v1.0 — start here

This is a **pilot-only** end-to-end counterfactual generation/evaluation package for case 653. It intentionally separates generator-visible files, evaluator-visible files, and the private treatment/oracle key.

## Directory separation

- `generator_blind/`: safe to give to a fresh patch-generation chat.
- `eval_blind/`: safe to use on the cluster after patches are collected; condition labels remain hidden.
- `private/`: **never** give to a patch-generation chat. Do not join the condition key until blinded evaluation is frozen.

## Step 1 — obtain the exact base repository on the cluster

```bash
bash PREP_BASE_ON_CLUSTER.sh
```

The required base is `pingcap/ossinsight` at `32934c7e9169f214bf65e214e45104b9a1d678b8`.

Copy the resulting tarball and `.sha256` file to your local machine. Verify the hash locally before uploading the archive to any generator chat.

## Step 2 — generate 25 independent patches

Follow `generator_blind/RUN_MANIFEST_BLINDED.csv` in frozen order. For every row:

1. open a fresh Temporary/isolated chat outside this research project;
2. use the same model and reasoning mode for all 25 runs in this block;
3. attach the base repository tarball;
4. attach exactly that row's opaque task file;
5. paste `generator_blind/NEW_CHAT_GENERATOR_PROMPT.md`;
6. download/save `<RUN_ID>.patch` and `<RUN_ID>.json` unchanged;
7. close the chat and never reuse it;
8. record model/mode/time in `GENERATION_LOG_TEMPLATE.csv`.

Do not inspect the PRIVATE treatment mapping while generating. Do not ask a failed run to "try another approach". If a run fails to produce a usable patch, record the failure as-is.

## Step 3 — upload generated patches to the cluster

Create a directory such as:

```bash
mkdir -p $HOME/E_PILOT653_RUNS/patches
```

Place all `R*.patch` files there together with the blinded manifest and `eval_blind/` directory.

## Step 4 — configure blinded evaluation

Copy `eval_blind/eval_config.env.example` to `eval_config.env`. Set `BASE_REPO` to the exact base clone. Fill in the same build/test/scanner/oracle commands used for every patch. Do not include treatment labels.

For the first smoke run, it is acceptable to leave expensive commands blank and verify only patch application. Then freeze real evaluation commands before looking at treatment labels.

## Step 5 — run evaluation

```bash
bash eval_blind/evaluate_all.sh   eval_config.env   generator_blind/RUN_MANIFEST_BLINDED.csv   $HOME/E_PILOT653_RUNS/patches   $HOME/E_PILOT653_RUNS/eval_out

python eval_blind/collect_results.py   $HOME/E_PILOT653_RUNS/eval_out   $HOME/E_PILOT653_RUNS/EVAL_RESULTS_BLINDED.csv
```

Fill `mechanism_label` blinded to treatment using `eval_blind/MECHANISM_LABEL_CODEBOOK.md`.

## Step 6 — freeze evaluation

Hash the blinded result files and all patches **before** unblinding:

```bash
cd $HOME/E_PILOT653_RUNS
find patches eval_out -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS_BEFORE_UNBLIND.txt
sha256sum EVAL_RESULTS_BLINDED.csv >> SHA256SUMS_BEFORE_UNBLIND.txt
```

## Step 7 — unblind and analyze

Only now join `private/CONDITION_KEY_PRIVATE.csv` to `EVAL_RESULTS_BLINDED.csv` by `run_id`.

Pilot contrasts:
- wording sensitivity: `SHAM_REWRITE` vs `ORIGINAL_NATURAL`;
- specificity: `HIGH_SPECIFICITY` vs `LOW_SPECIFICITY`;
- explicit security requirement: `EXPLICIT_GUARD` vs `HIGH_SPECIFICITY`.

The pilot is for pipeline validation and variance estimation. It must not be reused as the confirmatory main-study sample.
