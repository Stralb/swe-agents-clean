# Changelog: deep discovery v2.0 -> v2.1

v2.0 is preserved unchanged. v2.1 is an incremental outcome-blind correction layer.

## Fixed

- Corrected the numeric↔categorical eta/omega calculation.
- Prevented v2-generated model outputs (topics, clusters, anomaly scores, template membership) from re-entering primary generic discovery.
- Removed AI-marker provenance-text artifacts from primary discovery; retained them only for provenance/control use.
- Separated missingness from primary itemset mining.
- Removed binary zero/complement events from primary itemsets.
- Replaced capped brute-force frequent-itemset output with surprise-first pair mining plus clique-gated triples/quads and closed-pattern filtering.
- Marked near-deterministic/mechanical associations as audit-only before stability allocation.
- Reallocated repository bootstrap and within-repository null compute to corrected, nonmechanical candidates.
- Replaced naive add-vs-delete interpretation with a representation-wide add/delete exposure null.
- Added >=80% patch-coverage sensitivity for code motifs and call-shape motifs.
- Added generic callee-shape extraction without a semantic/API allowlist.
- Added code edit-transition mining (removed feature -> added feature).
- Added raw path co-change surprise mining.
- Added repository-blocked stability + within-repository permutation nulls for edit transitions and path co-change motifs.
- Decoded opaque near-duplicate template IDs into characteristic features and cosine-nearest representative cases.
- Corrected template representative selection to use cosine similarity rather than magnitude-biased dot products.
- Added repository/task/provenance-adjusted temporal effects and repository-blocked temporal stability.
- Split output into evidence grades so descriptive/expected grounding signals cannot outrank strict surprise-first findings.
- Added `STRICT_DISCOVERY_CATALOG_V21.csv`.
- Added a methodology self-test to cluster preflight.

## Not changed

- Frozen v2.0 run and hashes.
- Frozen 3,809-case corpus.
- Security/scanner outcome blinding.
- Raw v2.0 text/path/patch/syntax representations.
- Security/manual outcome tables remain inaccessible.
