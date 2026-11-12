# Full-Corpus Deep Discovery v2.1

This package runs the **corrective outcome-blind discovery layer** over the already-completed deep v2.0 artifact tree.

It does **not** rerun raw extraction, TF-IDF construction, syntax parsing, patch representation generation, NMF grids, or v2.0 view-model fitting.

## Source

Expected source symlink:

```text
$HOME/research_artifacts/full_corpus_deep_discovery_v2_LATEST
```

The source must have a PASS final status with:

```text
deep_discovery_complete = true
outcome_overlay_performed = false
security_outcomes_read = false
```

## Output

A new immutable run directory is created:

```text
$HOME/research_artifacts/full_corpus_deep_discovery_v2_1_<UTC timestamp>
```

and linked as:

```text
$HOME/research_artifacts/full_corpus_deep_discovery_v2_1_LATEST
```

The v2.0 run is never modified.

## Run

```bash
cd /home-mscluster/astrauss/full_corpus_deep_discovery_v2_1 || true
bash setup_and_submit.sh
```

The setup performs:

1. v2.0 outcome-blind final-status precheck;
2. Python syntax precheck;
3. statistical/methodology self-test;
4. coordinator submission only if all prechecks pass.

## DAG

```text
audit
  ↓
redundancy / feature-role gate
  ↓
├── corrected associations
├── code/path/edit motifs
├── template decoding
└── composition-adjusted temporal analysis
       ↓
associations → surprise-first patterns
       ↓
associations + patterns + temporal → stability/null validation
       ↓
motifs + templates + stability → evidence-graded catalogue
       ↓
report
```

Scheduler fallbacks are included. No GPU GRES is requested; `biggpu` is used only as a CPU/RAM node class when available.

## Status

```bash
bash status.sh
```

Success ends with:

```text
status = PASS
outcome_overlay_performed = false
security_outcomes_read = false
```

and creates:

```text
V2_1_DISCOVERY_REPORT.md
08_catalog/STRICT_DISCOVERY_CATALOG_V21.csv
08_catalog/DISCOVERY_CATALOG_V21.csv
```

## Main methodological principle

**Frequency is not treated as discovery.**

The primary catalogue favors patterns that are surprising relative to an explicit null, stable when whole repositories are resampled, distributed across repositories, non-redundant, and interpretable. Expected/descriptive structures are retained separately rather than being discarded.

See `V2_1_SPEC.md` for the full frozen specification and `CHANGELOG_FROM_V2.md` for exact corrections.
