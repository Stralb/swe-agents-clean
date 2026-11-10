# Reproducing the analysis

## Included inputs

The `data/` folder contains the aggregate C6 paired comparisons, C1/C2 cohort metadata, indexed C6/C7 pathway summaries, and a bootstrap consistency reference. The original per-case CSV files and the frozen SQLite database are not included.

The miner source was recovered from the 20 October 2026 source snapshot. Original miner modules are retained, with one review-interface import updated after a directory cleanup. Some later analysis scripts have updated paths to the included aggregate files.

## Available commands

Recalculate eight matched tests from the included aggregates and compare all nine recorded p-values:

```bash
python3 -m analysis.reproduce_matched --check
```

Check the recorded population accounting:

```bash
python3 -m analysis.cluster_stage_lineage audit-recorded
```

With an authorized original C6 paired master CSV staged outside the checkout, recalculate all nine tests:

```bash
python3 -m analysis.c6_full_original_190_pair_nine_tests --original-pair-master /path/to/C6_MATCHED_PAIR_MASTER_190.csv
```

Run the included regression tests:

```bash
python3 -m unittest discover -s tests -p 'test_reproduce_matched.py' -v
```

## Historical routing limitations

Two existing miner helper functions have known applicability errors. `has_any_applicable_downstream_worker` counts the `artifact_profile` metadata field as if it were a scanner route. `has_primary_applicable_downstream_worker` treats a missing `ci_security` route as applicable. The matching tests document these as expected failures. The recovered miner logic is unchanged so the original study code can be inspected. Any new collection should fix these predicates and separately measure their effect on sample selection.

## Limits

The aggregate test computes five Stuart-Maxwell and three exact McNemar statistics. The ninth, the Wilcoxon comparison, is checked against its historical result because the signed per-pair delays are not in the included aggregate tables.

Original scanner binaries, query packs, SARIF baselines, per-case labels, and the frozen database are still required for end-to-end replication. The miner's dependency file contains version ranges rather than a locked historical environment. Cluster-specific paths may remain in historical execution code. Use a separate database and working directory for new experiments.
