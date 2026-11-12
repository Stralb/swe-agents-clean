# Pure historical CodeQL diff attribution contract

The original `src/scanners/codeql_scanner.py` has SHA-256 `03bad76387b998d3b8978299cc9322a3a7a792c6e46fa4ce7338c4808fd6f198` in all 3 recovered miner snapshots. The archive is unchanged.

The checksum-checked test-only adapter `tests/support/archived_codeql_attribution_contract.py` extracts 11 pure original functions and 2 literal dictionaries from the AST. It does **not** import the module, create folders, clone repositories, invoke CodeQL, shell commands, or install query packs.

## Mechanistic contract tests

- Original language extension detection and default query suites.
- Unified diff parsing into new-side added-line numbers; deleted lines don't advance the head-side offset.
- SARIF primary, related and code-flow location extraction and order-preserving deduplication.
- Diff association can succeed via any related/code-flow location even when the primary finding is outside the changed line.
- Missing GitHub `patch` text yields no added-line map and therefore suppresses all findings in that file from the diff-linked set; this is a **coverage limitation**, not evidence of no vulnerabilities.
- Base/head finding identity is `(rule, normalized file, description)`; line numbers and CWE values are ignored. A head finding with a new line or a different CWE but identical identity is removed as existing. This could conceal changed evidence; no claim of frequency in historical corpus.

These are synthetic contract findings, **not actual CodeQL execution** and not replication of historic scanner results. Do not equate diff-linked with exploitable, or code-quality output with CWE-bearing security evidence. The historical scanner has not been promoted as a live executable.

Run `python -m unittest tests.test_miner_codeql_attribution_contract -v` or the entire `unittest discover -s tests` suite.
