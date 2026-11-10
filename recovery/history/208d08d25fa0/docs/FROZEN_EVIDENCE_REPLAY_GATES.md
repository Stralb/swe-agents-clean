# Frozen empirical-evidence gates: O/W/P-14 and D versus D7

**Status:** reproducible **recorded-summary arithmetic**; the original before/after
CodeQL alert deltas, full issue acceptance, causal prevention, historical miner
cohort, and conflicting semantic labels remain **unreproduced / unresolved**.

This gate is independent of the scanner smoke tests. It does not invoke the
original scanner, any coding agent, a cluster process, or statistical model.
It reads only **existing committed provenance ledgers**, without writing files.

## Recompute the available recorded evidence

From a checkout of this private repository:

~~~bash
python -m analysis.frozen_evidence_gate audit-recorded
python -m unittest tests.test_frozen_evidence_gate -v
~~~

The audit cross-checks three separately committed October O/W/P intake records:
\`provenance/owp14_case_arm_counts_20261020.csv\`,
\`provenance/owp14_missing_baseline_sha256.csv\`, and
\`provenance/owp14_intake_verified_20261020.json\`. It enforces one-to-one
five-digit case IDs, strict integer/sentinel fields, aggregate equality,
source-mode flags, and the distinction between missing arm and numeric zero.

| Unit | Exact independently recalculated **recorded** value |
| --- | --- |
| O/W/P case IDs | 14 |
| O present | 12 (missing O for 08461 and 15151) |
| W present / P present | 14 / 14 |
| Fully paired O/W/P comparisons | 12 |
| Fully paired and full-source snapshots | 8 |
| Source modes | 10 full frozen, 4 filtered provisional |
| Source-recorded **new CodeQL alerts** | O=21; W=10; P=15 |
| Source-recorded **new historical-rule alerts** | O=7; W=4; P=5 |
| Historical target previously reproduced | 8 cases (different unit from target warnings in current O scans) |
| JSX-aware patch syntax checks | 39 pass / 40 checks; 16633-O fails |
| Paired W versus O | 7 lower, 5 equal, 0 higher (among 12 paired) |
| Paired P versus O | 4 lower, 8 equal, 0 higher (among 12 paired) |
| Original before-SARIF files in supplied October export | **0 / 14** |
| Original per-case source-tree content equivalence | **not independently verified** |

These values are **derived from already-recorded claims** with independent
arithmetical consistency checks. They are **not** fresh scanner findings,
repeat-model experimental outcomes or causal estimates. In particular, 8/14
previous historical-rule reproductions is not equal to O's seven current
\`target_new_claimed\` alerts. The 39 syntax passes do not prove 39 functioning
patches. The initial non-JSX-aware 37/40 syntax figure is source-reported in
the intake JSON, **not** regenerated from the JSX-aware CSV.

## Semantic-label conflict

The audit separately checks
\`provenance/d_vs_d7_label_differences.csv\`:

- 43 unique disputed root labels, all \`UNRESOLVED\`.
- 42 changes confined to the explanation tier; one root changes route.
- \`CROOT-00649-01\`: D-final \`M/T1\`, D7 \`H/NA\`.

The audit intentionally does not merge or adjudicate the two frozen studies.
Full D-final (5 H/103 T/234 M) and D7 (6 H/103 T/233 M) label counts are
**reported** in \`docs/RESEARCH_MAP.md\`, not independently regenerated from
the 43-row differences ledger alone.

## The missing baseline SARIF gate

The exported October package included 40 **after**-scan SARIF files, but
**none of the 14 distinct before**-scan SARIF files. Without the original
baseline SARIF, one cannot establish which candidate warnings are newly
introduced by a patch or reproduce the recorded intervention warning deltas.

Once a separate, approved, read-only local copy of each original baseline is
available, place them in a **secure private staging directory outside Git**.
The gate's *local staging convention* (not an asserted original archive
filename) is:

\`CASE_00668_before.sarif\`, ..., \`CASE_32759_before.sarif\`.

Run from a new, ordinary local terminal; do not use a Wits shell:

~~~bash
python -m analysis.frozen_evidence_gate verify-baselines /path/to/secure/local/baselines
~~~

Each of the 14 case IDs is mapped to its **already recorded exact expected
SHA-256** and before-SARIF result count. The checker rejects symbolic links,
oversized files (>128 MiB), mismatched content bytes, malformed JSON/SARIF,
wrong before-result counts, and missing files. It only reads the input:
no file copies, moving, extraction, writes, subprocesses or network.

- Exit **0** = 14/14 exact SHA-and-result-count matches; still **not** alert
  introduction or full study replication.
- Exit **2** = any missing, mismatched, malformed or over-limit file.
- Exit **1** = structurally invalid provenance or unsafe staging root.

With the data currently committed to Git, all 14 baselines remain absent,
and the scientific provenance gate is **blocked**, even while
\`audit-recorded\` returns zero for correct bookkeeping. The normal CI job
runs only the first, recorded-arithmetic gate and synthetic negative tests.
This avoids manufacturing private SARIF files or producing a false-green
historical reproduction result.

## Further independent reproduction gates

1. Find original raw O/W/P after-scan SARIF, original full baseline SARIF,
   before/head Git tree identities and SHA-verified patch data in private
   frozen artifact storage; ensure originals are not uploaded into Git.
2. Reconstruct matching rules including path/line fingerprints and failure
   statuses; quantify differences from the archived \`new\` labels without
   overwriting them.
3. Verify full-source versus filtered-source comparability per arm.
4. Independently test issue acceptance (the syntax and four isolated
   subcomponent checks cannot stand in for functional correctness).
5. For D/D7, trace 43 disputed roots through D4 adjudication and chronology;
   do not infer the correct tier from the later export.
6. Recover the original 3,809-workflow SQLite and scanner version/rule
   digests, and regenerate cohort/root/control/intervention outputs.

**Safety:** code and synthetic fixtures only go into the draft private PR;
the original Wits cluster and other repositories remain untouched.
