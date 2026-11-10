# Full-Corpus Outcome-Blind Change-Operation Discovery v2.2

## Status

This is a corrective extension of the completed outcome-blind v2.0 run. It does **not** reopen the SQLite database and does **not** recompute the expensive text/path/patch embedding models. It reads only the already-frozen, outcome-blind raw artifacts from:

`/home-mscluster/astrauss/research_artifacts/full_corpus_deep_discovery_v2_20260829T181912Z`

Expected corpus: 3,809 agent-associated issue -> merged-PR workflows.

Expected source DB SHA-256 recorded by v2:

`126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`

## Why v2.2 exists

v2.0/v2.1 showed that generic state/frequency mining can produce thousands of statistically stable but scientifically weak regularities. Examples include alternate measurements of edit size, absence+absence itemsets, crawler/query metadata, path decompositions of the same filename, and syntax artifacts produced by parsing partial diff hunks as complete programs.

v2.2 therefore changes the primary unit from **state/frequency** to **observed change operation**.

It asks no predetermined security or software-quality question. The generic discovery objects are:

1. concrete before -> after transformations inside replacement blocks;
2. cross-file co-change relationships that truly involve distinct files;
3. repeated API-preserving code-change templates across independent repositories;
4. generic information flow from issue -> PR -> changed code;
5. dependency value transitions, kept as a separate factual stratum.

## Hard outcome-blinding rule

v2.2 never queries SQLite.

It reads only these v2 raw artifacts:

- cases linkage;
- safe repository metadata;
- safe issue metadata/text;
- safe PR metadata/text;
- PR files and stored unified patches;
- patch-coverage audit.

It does not read:

- scanner findings/runs/jobs/status;
- validated positive/negative cohort membership;
- canonical findings;
- finding-producing changes;
- Direct/Side-effect attribution;
- risk/maliciousness labels;
- F1-F5;
- manual annotations.

The audit stage refuses to continue if the source v2 final status says that security outcomes were read or an outcome overlay was performed.

## Patch-quality rule

Primary code-operation discovery requires per-case stored-patch line coverage >= 0.80. Lower-coverage cases remain represented in transparent case-level quality outputs but do not drive primary transformation discovery.

Generated/vendor/build artifacts are separated from primary source-code transformations rather than silently dropped from the corpus.

## Stage 1: change blocks

Unified diffs are parsed as diffs, not as source files.

Each hunk is split into maximal replacement/addition/deletion blocks separated by context. A block records:

- removed lines;
- added lines;
- file/path/extension;
- source-code vs generated-artifact stratum;
- calls in removed and added lines;
- imported modules;
- language keywords;
- operators;
- API-preserving normalized before/after skeletons.

No Tree-sitter/AST claim is made from partial hunks.

## Stage 2: concrete transformations

Within actual replacement blocks, v2.2 automatically mines recurring:

- call/API transitions;
- import/module transitions;
- language-keyword transitions;
- operator transitions.

A candidate `A -> B` exists only when `A` is removed and `B` is added in the **same concrete replacement block**.

The miner records support, repository breadth, lift, normalized PMI, dominant extension, and representative real case/file/block examples.

Dependency key/value replacements are extracted separately and summarized; lockfiles/generated artifacts are not allowed to dominate primary source-code transformations.

## Stage 3: generic artifact flow

For every case, v2.2 measures without semantic labels:

- issue-token recall into added patch tokens;
- fraction of added tokens directly anchored in issue text;
- PR-bridge fraction: added tokens absent from issue but present in PR text;
- patch novelty fraction relative to issue + PR + removed code;
- introduced-call count;
- introduced calls anchored in issue text;
- introduced calls anchored in PR text;
- introduced calls unanchored in issue/PR/removed code;
- analogous introduced-import measures.

Extreme cases are exported as an **inspection queue**, not automatically called discoveries.

## Stage 4: true cross-file co-change surprise

Path items are mined only when the two items can be realized in **two distinct changed files in the same case**. This removes tautologies such as `.tsx + namepart=tsx` that came from one filename.

Expected co-occurrence is computed within repository and aggregated. The output therefore asks whether two path properties occur together more often than expected given that repository's own marginals.

## Stage 5: repeated cross-repository code templates

v2.2 uses API-preserving normalized diff blocks and discovers exact recurring templates across at least three repositories.

Two template types are kept separate:

- **added templates**: repeated normalized code additions;
- **replacement templates**: repeated normalized `before -> after` transformations.

Literals and local identifiers are normalized while callable/property names and language structure are retained. This is intended to expose recurring implementation/migration idioms rather than boilerplate spelling differences.

## Stage 6: nulls and stability

Top transformation candidates use:

- 500 within-repository hypergeometric null draws preserving per-repository marginals;
- Benjamini-Hochberg FDR correction;
- 500 whole-repository bootstrap resamples.

Top cross-file co-change candidates use:

- repository-conditioned expected counts;
- 500 whole-repository bootstrap resamples of the conditioned effect.

## Scientific catalogue gates

A transformation enters the catalogue only when it satisfies all of:

- FDR q <= .05;
- bootstrap effect > 1 in at least 85% of repository resamples;
- >= 5 repositories;
- >= 6 cases.

A cross-file co-change enters only when it satisfies all of:

- repository-conditioned ratio >= 1.25;
- bootstrap ratio > 1 in at least 85% of resamples;
- >= 8 repositories;
- >= 15 cases.

Cross-repository code templates require >= 3 cases and >= 3 repositories, with no single repository contributing >50% of members.

The final shortlist is family-balanced and capped at 60 rows. It is deliberately acceptable for the shortlist to be empty or contain only ordinary development practices.

## Interpretation boundary

A v2.2 result means:

> a concrete edit operation, repeated edit template, or true cross-file relationship recurs in this corpus beyond the stated repository-conditioned/null/stability criteria.

It does not mean:

- AI causes the pattern;
- the pattern is better/worse than human development;
- the pattern is secure/insecure;
- the pattern is malicious;
- the pattern predicts a scanner outcome.

Those require later comparison/overlay stages.
