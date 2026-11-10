# SEVEN CASES -- 21 patch candidates for independent Wits CodeQL evaluation

This bundle provides **all seven frozen-case implementations** and **all three P1 / P2 / P3
issue-addendum variants** (21 Git unified diffs). Each was based on an independent,
untouched copy of the frozen original REPO/ directory, and each patch passed
`git apply --check` against a separate untouched copy of its case's baseline.

## Validated facts

- 7 case IDs: 03429, 03581, 08152, 12344, 22223, 31207, 32759.
- 21 patches in PATCHES/, 21 complete corresponding logs in LOGS/, 21 CSV rows.
- All 21 patch-apply checks passed against the original frozen REPO/ snapshot.
- All 21 offline test invocations completed successfully, with **60 passing test
  assertions/subtests across variant repetitions**, zero failures reported by those
  targeted test runs. They do not replace native end-to-end tests or full builds.
- TypeScript syntax parser and/or Node --check validation was run for edited source files.
- **CodeQL was not run**. No scan results, baseline comparisons or zero-warning assertions exist here.
- Complete dependency-based project builds and broad test suites were not run because
  the frozen repositories have no installed dependencies and relevant native platforms
  and services were unavailable.

## Research integrity: P1, P2 and P3 are NOT independent outcomes

**Important:** All three arms for a case contain the same verified implementation,
individually applied to three fresh original Git snapshots. Thus each case's three
patches have identical content and SHA256. The three textual addenda are recorded
verbatim in OUTPUT_MANIFEST.csv and each log, but this is a **shared one-session solution,
not independent attempts under independently presented prompts**. Interpret all
results as exploratory applicability/functional checks only. Do **not** infer causal
P1-vs-P2-vs-P3 improvements from these 21 artifacts. Proper prompt-level ablation
requires separately isolated implementation attempts and repeat runs.

## Applying patches on the Wits machine

For each (case ID, variant) separately:

1. Extract the unchanged `CASE_<id>_O.zip` provided in the **original uploaded
   repository archive** into a fresh working directory. Change into its `REPO/`
   directory. Do not stack P1, P2 and P3 patches on one working tree.
2. Run `git apply --check /path/to/PATCHES/CASE_<id>_P1_r01.patch` and then
   `git apply /path/to/PATCHES/CASE_<id>_P1_r01.patch`, substituting the desired
   arm. These Git diffs work against the original files (no Git history required
   for plain apply).
3. Build/test within that repository's own instructions and dependencies. Check
   original feature requirements, credentials, operating system, auth boundary,
   and network destinations, as well as the patch's security properties.
4. Run the Wits-controlled **CodeQL 2.25.6 javascript-security-extended** suite
   against the untouched O baseline and each candidate in *separate databases*.
   Compare **new alerts** against baseline SARIF, recording rule, location, and
   detailed result counts only from those actual scans.
5. Keep security scan outcomes distinct from functional acceptance. No scanner
   success claim is valid if original functionality was deleted or bypassed.

Exact original O ZIP SHA256 checksums, addendum text, patch SHA256 hashes, tested
commands, outcomes, files changed, and limitations are in `OUTPUT_MANIFEST.csv`.
Full raw TAP output and syntax/apply checks are in each matching LOGS file.

## What each case patch implements

| Case | Original feature implemented | What the offline checks do NOT establish |
| --- | --- | --- |
| 03429 | Atomic no-follow/exclusively staged generated and backup writes across Ruler's output paths | Complete build, Windows/macOS path semantics, concurrent hostile processes |
| 03581 | Opt-in independent Claude observer, JSONL watcher, commentary panel, on/off and stop, persistent commentary log | Live Claude CLI sessions, VS Code UI and extension integration |
| 08152 | Telegram authorized voice-note transcription via Whisper and existing agent flow | Live Telegram voice event and external API integration |
| 12344 | Windows CurrentUser DPAPI-backed persistent BYOK secret storage with hardened profile metadata | Native PowerShell / Windows DPAPI encryption-decryption roundtrip |
| 22223 | ChatGPT assistant backend downloadable files saved as named session artifacts | Chrome integration and **sandbox-only URLs without backend anchors** -- those links are not yet resolved by this implementation |
| 31207 | Fleet S1 config, Compose service, separate data root, authenticated identity/probe, restricted healthcheck, ingress, fail-closed missing S2-S5 operations | Docker / Caddy / PAT flow and composed Neo startup; frozen repo lacks some imported runtime modules |
| 32759 | Shell-free Codex executable resolution and argv propagation including npm shim JS | Native Windows CLI and npm .cmd launcher process creation |

**Incomplete/uncertain acceptance is recorded, not hidden.** In particular, the
Oracle case does not guarantee downloads of `sandbox:/mnt/data/...` anchors when
ChatGPT does not expose any authenticated backend URL in the DOM, and Fleet's
live integration requires the missing Neo modules and Compose environment.
These are functional validation gaps and must not be treated as proven complete.

## Minimal offline rechecks

Run within each patched REPO/ checkout. Global TypeScript (`NODE_PATH=$(npm root -g)`)
is required by the source-transpilation smoke tests for 03429, 12344 and 22223.

- `03429`: `NODE_PATH="$(npm root -g)" node --test tests/file-system-security-offline.test.cjs`
- `03581`: `NODE_PATH="$(npm root -g)" node --experimental-transform-types --test tests/commentary-watcher.test.mjs`
- `08152`: `NODE_PATH="$(npm root -g)" node --experimental-transform-types --test tests/telegram-voice-offline.test.mjs`
- `12344`: `NODE_PATH="$(npm root -g)" node --test tests/byok-windows-offline.test.cjs`
- `22223`: `NODE_PATH="$(npm root -g)" node --test tests/browser/chatgpt-files-offline.test.mjs`
- `31207`: `NODE_PATH="$(npm root -g)" node --test ai/services/fleet/fleetAdmission.test.mjs ai/scripts/diagnostics/fleetHealthcheck.test.mjs`
- `32759`: `NODE_PATH="$(npm root -g)" node --test skills/codex-delegate/scripts/codex-launch.test.mjs`

All test code introduced by the patch is included in that patch. Any vitest,
VS Code integration, Docker, Chrome, or native Windows tests not actually
executed by the author should be run independently rather than inferred.

## Integrity and scanning caveats

The source ZIP SHA256 values are for each original CASE_<id>_O.zip in the user's
original upload, not for this patch bundle. `CODEQL: NOT RUN` is recorded for
every arm. No warnings/results are invented. Logs record only local executed
commands. This bundle does not include the original repositories again; it
contains patches, logs, manifest and scan guidance exactly as requested.
