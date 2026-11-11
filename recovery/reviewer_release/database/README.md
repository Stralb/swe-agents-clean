# Database relationship diagrams

Start with a subject section below. Each SVG is independent, so it can be opened at a readable size. The complete atlas stacks all 11 sections vertically instead of squeezing 135 tables into one horizontal line.

[Complete ERD atlas](erd/FULL_DATABASE_ERD.svg)

| Section | Diagram |
|---|---|
| sqlite internal | [Open SVG](erd/sqlite_internal.svg) |
| coding lineage | [Open SVG](erd/coding_lineage.svg) |
| embedded archive | [Open SVG](erd/embedded_archive.svg) |
| rq1 new70 | [Open SVG](erd/rq1_new70.svg) |
| provenance audit | [Open SVG](erd/provenance_audit.svg) |
| mining baseline | [Open SVG](erd/mining_baseline.svg) |
| rq2 controls statistics | [Open SVG](erd/rq2_controls_statistics.svg) |
| artifact provenance | [Open SVG](erd/artifact_provenance.svg) |
| review layer | [Open SVG](erd/review_layer.svg) |
| rq3 experiments | [Open SVG](erd/rq3_experiments.svg) |
| rq1 original122 | [Open SVG](erd/rq1_original122.svg) |

All 135 tables and 162 declared foreign-key constraints are retained. Grey tables provide parent context from another section. Arrows point child → parent; only PK/FK columns are shown. Repeated grey context tables are not additional tables. No JSON/prose relationships or historical constraint enforcement are inferred.
