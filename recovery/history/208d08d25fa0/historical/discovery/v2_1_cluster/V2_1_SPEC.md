# Full-Corpus Outcome-Blind Deep Discovery v2.1

## Status

Corrective, outcome-blind extension of the completed deep-discovery v2.0 run.

v2.1 **does not rerun raw extraction or expensive text/path/patch/syntax representation generation**. It reuses the frozen v2.0 artifacts and recomputes only the discovery, statistical validation, decoding, ranking, and report layers that were found to be weak during interpretation.

The v2.0 run remains unchanged.

## Scientific objective

> Discover stable, non-redundant, cross-repository and statistically surprising structure in the objective 3,809-case corpus without conditioning on any scanner/security outcome and without supplying a software-development hypothesis taxonomy.

The miner is generic. It does not ask prewritten questions such as whether tests, dependencies, CI, or validation matter. It operates on objective measurements and raw/derived representations already produced by v2.0.

## Outcome-blinding invariant

v2.1 reads **only artifacts from the completed outcome-blind v2.0 runroot**.

Before any stage executes, `audit` requires:

- v2.0 final status = PASS;
- `deep_discovery_complete = true`;
- `outcome_overlay_performed = false`;
- `security_outcomes_read = false`;
- v2.0 table-access audit confirms forbidden scanner/security/manual tables remained blocked.

v2.1 does not open the SQLite database and has no scanner/security outcome loader.

Final v2.1 status must again state:

- `outcome_overlay_performed = false`;
- `security_outcomes_read = false`.

## Why v2.0 required correction

Interpretation of the 4,607-entry v2.0 catalogue exposed methodological problems:

1. Frequency/stability alone promoted many expected or scientifically weak regularities.
2. Frequent-item mining included binary zero/complement states and missingness, producing many `absence + absence` patterns.
3. The v2.0 mixed numeric/categorical eta-squared implementation used total rather than between-group variation, often producing eta-squared near 1 even under unrelated categorical splits.
4. Generated model outputs (cluster assignments, topic assignments/weights, anomaly scores, template memberships) were recycled into generic association/pattern discovery, making circular model-derived relationships possible.
5. The original frequent-pattern stage hit a 500,000-result cap, so it was neither complete nor surprise-first.
6. Relationship stability/null compute was allocated before trivial/mechanical relationships were removed.
7. Add-versus-delete code motifs require comparison with the corpus-wide add/delete exposure, not a naive 50/50 null.
8. Repeated patch/path/syntax templates were represented by opaque IDs rather than decoded features and representative cases.
9. Temporal trends were not adjusted for repository, agent/provenance mix, and task/topic composition.
10. Several code-level candidate families lacked repository-blocked stability and within-repository null validation.

v2.1 fixes these issues before any outcome reveal.

## Feature provenance gate

Every feature receives a provenance role.

### `primary_observed`

Objective/raw or deterministic factual measurements eligible for generic relationship, interaction, and temporal discovery.

### `generated_model`

Model-produced assignments or scores, including:

- `template__*` memberships;
- `fused_*` assignments/anomaly scores;
- `__kmeans`;
- `__hdbscan`;
- `__iso` / `__lof`;
- `__topic`;
- `__topic_weight`.

These are preserved for decoding/controls but **excluded from the primary discovery matrix**.

### provenance-only features

AI-marker text/model features and generic AI-marker relational aggregates are preserved as provenance/context but excluded from the primary discovery matrix. Provenance/task topic assignments may be used as temporal adjustment factors only.

This prevents findings such as “cluster assignment X is associated with topic assignment Y” from being promoted as corpus discoveries.

## Stage 1 — outcome-blind source audit

Checks v2.0 status, table-access audit, required artifacts, and the 3,809-case invariant.

Outputs:

- `00_audit/SOURCE_STATUS.json`
- `00_audit/V21_MANIFEST.json`
- `00_audit/required_artifacts.csv`

## Stage 2 — redundancy and feature-role pruning

1. Inventory every v2.0 discovery feature.
2. Assign analytical provenance role.
3. Remove generated/provenance features from the primary matrix.
4. Hash objective columns and remove exact duplicates.
5. Detect near-identical rank relationships:
   - absolute rho >= 0.995 globally; or
   - absolute rho >= 0.975 only within a common provenance/root family.
6. Retain one representative from each redundancy group.

Moderate cross-view agreement is intentionally preserved.

Outputs:

- `01_redundancy/feature_table_pruned.*`
- `01_redundancy/feature_audit.csv`
- `01_redundancy/excluded_generated_or_provenance_features.csv`
- `01_redundancy/redundancy_groups.csv`
- `01_redundancy/redundancy_edges.csv`

## Stage 3 — corrected exhaustive associations

Uses only retained primary-objective features.

Measures:

- numeric↔numeric: Spearman rho;
- binary↔binary: phi;
- categorical↔categorical: bias-corrected Cramer's V;
- numeric↔categorical: correctly calculated omega-squared, with eta-squared retained as an audit value;
- normalized mutual information for strong nonmechanical candidates;
- within-repository centered effect for top numeric pairs.

Correct numeric/categorical calculation:

- between-group SS = sum(n_g * (mean_g - grand_mean)^2)
- total SS = sum((x - grand_mean)^2)
- eta-squared = SS_between / SS_total
- omega-squared uses within-group mean-square correction.

Relationships with effect strength >= 0.95 or the same normalized feature root are retained in audit outputs but marked mechanical/near-deterministic and excluded from the strict scientific catalogue.

Outputs:

- `02_associations/relationships_v21.csv`
- `02_associations/feature_types_v21.csv`

## Stage 4 — surprise-first event/interaction mining

Primary itemization intentionally excludes absence and missingness.

- binary: only `PRESENT = 1` is itemized;
- categorical: nonmissing levels;
- numeric: empirical quartile bins;
- missingness is written to a separate analysis table.

Initial eligibility:

- support >= 1%;
- >=5 repositories;
- top-repository share <=80%.

Pairwise surprise uses:

- support;
- lift;
- leverage;
- normalized PMI;
- independence z residual;
- repository spread.

Higher-order triples/quads are only enumerated when **every constituent pair already shows positive surprise**:

- lift >=1.25;
- leverage >=0.003;
- NPMI >=0.10;
- >=5 repositories;
- top repository <=80%.

Triples require >=1% corpus support; quads >=2%.

Closed-pattern filtering removes subsets with identical support to a strict superset.

No fixed 500,000 result cap is used.

Outputs:

- `03_patterns/itemization_v21.csv`
- `03_patterns/missingness_events_separate.csv`
- `03_patterns/pair_patterns_v21.csv`
- `03_patterns/higher_order_patterns_v21.csv`
- `03_patterns/closed_patterns_v21.csv`

## Stage 5 — code/path/edit motif discovery

This stage operates directly on existing raw v2.0 sparse representations and stored patch documents.

### A. Add/delete motif asymmetry

Views:

- raw added/deleted code-word n-grams;
- normalized added/deleted code-token n-grams;
- syntax added/deleted node patterns.

For each feature, v2.1 compares its add/delete prevalence against the **representation-wide add/delete exposure baseline**, not 50/50.

Statistics:

- relative log2 add/delete odds;
- binomial null against global exposure;
- BH-FDR;
- repository coverage/concentration.

Patch-derived effects are rerun on cases with stored patch coverage >=80%; strict candidates must keep the same direction when that sensitivity result is available.

### B. Generic call-shape asymmetry

No API allowlist is provided.

The miner extracts generic callee shapes such as `foo(...)`, `a.b(...)`, `a.b.c(...)` from added/deleted patch text and tests each callee's add/delete balance against the corpus-wide call exposure baseline.

Call motifs receive BH-FDR, repository spread, and >=80%-patch-coverage direction sensitivity.

### C. Cross-artifact token transfer

Shared tokens are measured across:

- issue body → added patch;
- PR body → added patch;
- issue title/body → changed paths;
- PR body → changed paths.

These are retained as **supporting grounding evidence**, not automatically promoted as surprising discoveries.

### D. Edit-transition motifs

Generic removed-feature → added-feature pairs are mined from:

- raw code words;
- normalized code tokens;
- syntax patterns.

Candidate transitions require broad support, lift/NPMI surprise, and cross-repository spread. Strong transitions are later validated by repository-blocked bootstraps and within-repository permutation nulls.

### E. Raw path co-change motifs

Changed path items are mined directly, with lift/NPMI and repository spread. Strong path pairs are later validated by the same repository-blocked/bootstrap and within-repository null procedure.

Outputs include:

- `04_motifs/add_delete_motif_asymmetry.csv`
- `04_motifs/call_shape_asymmetry.csv`
- `04_motifs/cross_artifact_token_transfer.csv`
- `04_motifs/edit_transition_motifs.csv`
- `04_motifs/path_cochange_surprises.csv`
- `04_motifs/interpretable_motif_prevalence.csv`

## Stage 6 — repeated-template decoding

Uses v2.0 near-duplicate template groups but decodes each group into:

- contrastive characteristic features versus corpus background;
- case count;
- repository count;
- repository concentration;
- high-patch-coverage fraction;
- cosine-nearest representative cases.

AI-marker provenance-text templates and character-ngram templates are not promoted into the strict catalogue.

Outputs:

- `05_template_decoding/decoded_templates_v21.csv`
- `05_template_decoding/TEMPLATE_DECODING.md`

## Stage 7 — composition-adjusted temporal discovery

For every eligible primary numeric/binary feature, v2.1 computes:

- raw case-level time Spearman;
- monthly-median trend using months with >=30 cases;
- repository fixed-effect rank correlation;
- repository + agent/provenance-topic + issue-body-task-topic adjusted rank correlation;
- per-repository trend direction consistency.

Strong adjusted trends later receive repository-blocked bootstrap stability.

The adjustment is intended to distinguish temporal change from changing repository/tool/task composition.

Outputs:

- `06_temporal_adjusted/temporal_adjusted_v21.csv`
- `06_temporal_adjusted/strong_adjusted_series.csv`

## Stage 8 — stability and null validation

### Relationships

- up to 300 top corrected nonmechanical relationships;
- default 500 repository-blocked 80%-repository resamples;
- up to 200 receive default 200 within-repository permutations.

Strict relationship discoveries require an actual within-repository null result.

### Interaction patterns

- up to 200 top closed surprise patterns;
- default 200 repository-blocked resamples;
- top 100 receive default 100 within-repository permutations.

Strict interaction discoveries require significant within-repository null evidence and >=80% support retention.

### Edit transitions and path co-change motifs

- up to 100 of each family;
- default 120 repository-blocked resamples;
- default 100 within-repository permutations;
- repo-specific marginals are preserved while pair coupling is destroyed.

### Temporal effects

- up to 80 strongest composition-adjusted effects;
- default 150 repository-blocked resamples.

Environment knobs:

- `V21_REL_BOOTSTRAPS` (500)
- `V21_REL_NULLS` (200)
- `V21_PATTERN_BOOTSTRAPS` (200)
- `V21_PATTERN_NULLS` (100)
- `V21_MOTIF_BOOTSTRAPS` (120)
- `V21_MOTIF_NULLS` (100)
- `V21_TEMP_BOOTSTRAPS` (150)

## Stage 9 — evidence-graded discovery catalogue

v2.1 outputs two catalogues.

### Strict Grade-A catalogue

`08_catalog/STRICT_DISCOVERY_CATALOG_V21.csv`

Contains only candidates with the strongest generic validation available for their family, such as:

- within-repository null + repository bootstrap for relationships/interactions;
- add/delete exposure null + FDR + patch-coverage sensitivity for code/call motifs;
- within-repository null + repository bootstrap for edit/path motifs;
- composition adjustment + repository bootstrap for temporal effects.

### Full catalogue

`08_catalog/DISCOVERY_CATALOG_V21.csv`

Also retains:

- Grade B decoded cross-repository templates awaiting case interpretation;
- Grade C descriptive cross-artifact token-transfer results.

This prevents expected descriptive behavior from displacing the surprise-first results while preserving it for context.

## Stage 10 — deterministic report

`V2_1_DISCOVERY_REPORT.md` reports:

1. exact corrections made;
2. strict Grade-A discoveries first;
3. broader decoded/exploratory results separately;
4. candidate counts by evidence family;
5. interpretation boundary.

Final marker:

`V2_1_QC_COMPLETE — OUTCOME_OVERLAY_NOT_PERFORMED`

## Preflight tests

`self_test.py` verifies at minimum:

- unrelated categorical groups do not produce eta-squared near 1;
- a true group effect does produce high eta/omega;
- exact duplicate pruning works;
- generated model/topic/template features are excluded from the primary matrix;
- binary zero complements are not itemized;
- binary presence is itemized.

`integration_test.py` creates a synthetic 3,809-case v2-like artifact tree and executes the complete v2.1 pipeline end-to-end.

The cluster setup runs the methodology self-test before submitting the real DAG.

## Interpretation rule

A Grade-A discovery is a statistically stable/surprising regularity in this corpus. It is **not** automatically causal, novel relative to all prior literature, security-relevant, malicious, beneficial, or harmful.

Human interpretation of the top decoded code/path/edit patterns still occurs **before** any scanner/security outcome overlay.
