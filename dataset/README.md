# Research dataset

The data interface uses neutral `study_*` table names and one case-index entry point. Genuine author credits and original evidence payloads are retained.

Status: schema and exporter prepared. Cluster execution and data upload are not yet verified.

The derived SQLite dataset contains research tables, embedded evidence and the core case/repository/issue/PR records. Operational mining logs remain in the preserved master. It does not overwrite that master.

Expected case-level checks: 3,809 cases, 192 annotated positives (122 initial + 70 later), 191 cases with mapped changes, 455 producing changes, 342 final roots, 190 matched pairs and 40 archived original replay runs. Later tests remain separate.

[Schema](SCHEMA.sql) · [Dataset builder](build_dataset.py) · [Parquet exporter](build_paper_dataset.py) · [Evidence extraction utility](artifact_reader.py)

The default Hugging Face configuration will be `paper_cases`; a direct positive-case configuration and supporting tables retain their distinct analysis units. Source-record text and binary archives are copied unchanged. Any remaining internal terms in original evidence are inventoried separately, rather than silently editing the evidence.

The exact historical source tree is retained on branch `preservation/20261111`. Older commits and that branch have not been rewritten.

[Core ERD](erd/OVERVIEW.svg) · [Complete ERD atlas](erd/FULL_DATABASE_ERD.svg)

The schema contains 111 tables (including the SQLite sequence table) and 18 navigation views. It describes a derivative research edition, not a rewrite of the original operational master.
