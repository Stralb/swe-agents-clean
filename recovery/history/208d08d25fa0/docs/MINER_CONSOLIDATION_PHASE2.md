# Miner consolidation phase 2A — Pure GitHub collection helpers

**Software reconstruction only: no new study or empirical claims.**

Five modules are promoted with their **original source bytes unchanged**. The GitHub objects are reused directly from the verified October historical snapshot and their SHA-256 identities agree across August 17, August 19 and October 20.

| Module | Responsibility | Side effects when imported |
| --- | --- | --- |
| `src/pipeline/repo_universe.py` | Search qualifiers, month windows, PR windows and deterministic sharding | None identified |
| `src/pipeline/agentic_discovery.py` | AI agent search terms and hydrated PR marker checks | None identified |
| `src/filters/bot_filter.py` | Historical substring-based bot exclusion | None identified |
| `src/filters/issue_filters.py` | Original body-word and optional language gate | None identified beyond imported text utility |
| `src/utils/text.py` | Word/substring/short-text helpers and English heuristics | Tries optional `langdetect` import |

### Reproducibility boundaries

- These pure helpers do not call GitHub or the Wits database. Query-generation tests only verify original string semantics.
- The original bot text check is substring-based. It may be overinclusive; altering it would change historical cohort construction.
- `langdetect` changes English-filter behavior when installed. Test the ASCII fallback separately and pin this dependency in future full pipeline execution.
- Adjacent date-window boundaries are preserved as authored. Their interpretation in live GitHub Search is not validated here.
- Stateful `src/settings.py`, `src/github/client.py`, `src/github/rate_limit.py` and `src/pipeline/collect_pipeline.py` remain in `historical/`, not active source.

The regression tests use only synthetic examples and verify that all five source files still match their three historical snapshots byte-for-byte.

Run: `python -m unittest discover -s tests -v`.
