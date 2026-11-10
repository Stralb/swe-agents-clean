# 14-case O/W/P coding-agent runner

**Purpose.** Generate independent implementations for all 14 frozen cases under the three predeclared conditions: original issue **O**, retrospective historical scanner diagnostic **W**, and forward-specifiable security property **P**. This runner is a *generator*, not a validator. The frozen repository and relevant issue text for each condition are already inside `CASE_XXXXX_O.zip`, `CASE_XXXXX_W.zip`, and `CASE_XXXXX_P.zip`.

## Current study facts

- All **42 frozen packets** are already on the Wits cluster at `~/research_artifacts/prevention_pilot_phase2/owp14_allcases_packets_job71014/` (job 71014). Download them with `download_owp14.ps1`.
- Eight case IDs reproduced their specific historical CodeQL target rule in an earlier original-issue-only attempt: `668, 3429, 3581, 6104, 8152, 8461, 22223, 31207`. Six other scanner-positive cases (`12344, 15151, 16633, 20094, 21682, 32759`) are additional exploratory cases and **should not be described as historical-target prevention tests** unless the exact target recurs in a new O sample.
- Four packets use **filtered**, not complete, repository snapshots: `3429, 12344, 21682, 31207`. Keep them in a separate analysis stratum.
- Historical issue-body provenance has not been confirmed to the pre-PR date. The study is **exploratory** until this is resolved.
- The first manually generated case `668` trio produced 0 new CodeQL findings in O/W/P, with builds and focused HUD tests passing. The original P patch had malformed new-file diff headers; the CodeQL experiment used a separately identified header-only normalization. This trio is a *different generator cohort* if the remainder is generated with Codex CLI. **Do not pool its results blindly.**

## One-time local setup (Windows PowerShell)

1. Install Python 3.10+ and Git if not already available. Install Codex CLI using the current [official installation instructions](https://github.com/openai/codex#readme), then run `codex login` to authenticate. Codex may consume plan quota or bill API usage depending on authentication.
2. Download this runner bundle and extract it to a folder such as `Downloads\OWP14-runner`.
3. Run this inside PowerShell, from the extracted runner folder:

```powershell
.\download_owp14.ps1
```

The 42 ZIPs will be in `$HOME\Downloads\OWP14` and the frozen CSV index will be there too. No database, historical warning dossier, or earlier generated patches need be shown to Codex.

4. Choose a Codex model supported by your account, and keep it **identical for every run**. In PowerShell, set it once: `$Model = Read-Host "Codex model ID"`. Check the current CLI/model options before setting it; do not guess a model ID.

**Preflight only (no model calls):**

```powershell
py .\run_owp14_codex.py --packets "$HOME\Downloads\OWP14" --out "$HOME\Downloads\OWP14-codex-results" --model "$Model"
```

**Small operational smoke run (one matched 3-arm case):**

```powershell
py .\run_owp14_codex.py --packets "$HOME\Downloads\OWP14" --out "$HOME\Downloads\OWP14-codex-results" --model "$Model" --max-runs 3 --execute
```

**Finish the same 14-case cohort (39 remaining sessions, because the first 3 were this runner's own Codex sessions):**

```powershell
py .\run_owp14_codex.py --packets "$HOME\Downloads\OWP14" --out "$HOME\Downloads\OWP14-codex-results" --model "$Model" --execute
```

Existing runs are **never overwritten**; this command skips the initial three and completes the others. It also saves the raw Git diffs from each isolated workspace (including newly added files) and logs timeouts, malformed or empty patches, and model failures without concealing them.

**To perform a second independent replication later:** run the same command with `--start-rep 2`. Keep the model identical and clearly label any model change as a different cohort.

**For an exploratory five-case subset:** use `--cases 668,3581,6104,8152,22223`. However, don't discard any of the 14 from the predeclared cohort based on whether its O result was positive.

## Upload and evaluation

The runner prints a `PATCH EXPORT:` path for the ZIP containing its complete manifest, unmodified generated patches, and failure records. Upload the ZIP to this chat for a **standardized identical CodeQL evaluation** against the frozen pre-PR bases. Keep the event logs (`codex_events.jsonl` and `codex_stderr.log`) locally for audit; don't include API credentials or private authentication files. The cluster has not yet been connected to a standalone independent coding-agent runner; this local runner handles generation, and the cluster handles scanning and tests.

For each output, the evaluator must record: `git apply` outcome; compile/build status; issue-specific acceptance; baseline-to-generated differential scanner findings (matching the historical query/rule, plus other rules); mechanism/path/changed-line evidence; and failures. **A patch with no warnings but missing requested functionality is not a successful prevention.**

## Experiment controls and limitations

- All three conditions for a case use the **same frozen repository files**. Only `ISSUE.md` differs. The runner checks the full 42-packet SHA256 manifest before executing any agent.
- Every Codex call uses an independent working directory, `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `--sandbox workspace-write`, and the **same model**. The model can access only files it can reach in the sandbox; do not run it with sandbox bypass or full access. The operator must still protect credentials and use a suitable isolated account/VM when running untrusted source repositories.
- Existing local repositories, Git histories, and generated patches are not reused as agent context. The runner constructs a new local Git baseline in each extracted frozen repository to capture a valid unified diff even for new files.
- This script doesn't prevent a malicious repository from attempting actions through tools available within the chosen sandbox. Review the CodeQL and functional environment and avoid giving coding agents broad network, credentials or host privileges.
- **This is a new Codex CLI generator cohort.** Previously generated ChatGPT-web `668` patches should be analyzed separately, not combined as if identically sampled.
- No external historical PR or CodeQL warning files are provided to the O or P agent. W is a retrospective oracle, not a deployable predictor of future warnings. Security-property text P is a research intervention, not evidence that a real developer would have known the right property without assistance.

## Artifact layout

```text
OWP14-codex-results/
  RUNNER_MANIFEST.json
  PATCHES_r01-01_<timestamp>.zip
  runs/
    CASE_00668_O_r01/
      CASE_00668_O_r01.patch
      result.json
      codex_events.jsonl
      codex_stderr.log
    CASE_00668_W_r01/...
    CASE_00668_P_r01/...
    ...
```

**Do not edit or repair a model's generated patch before recording it.** If a repair is needed for scanner applicability, preserve both original and explicitly labelled normalized copies with hashes and reason, as done for `668` P.
