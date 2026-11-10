# CodeQL source-fingerprint multiplicity and non-equivalent SARIF recovery

**Audit date:** 22 October 2026  
**Status:** `READONLY_CANDIDATE_DB_LOCUS_ANALYSIS_NOT_FINAL_SOURCE_REPLAY`  
[Aggregate-only observation record](../provenance/codeql_candidate_fingerprint_overlap_20261022.json)

## Distinguish four different CodeQL units

An archived CodeQL **scanner_findings row** is not necessarily an independent CodeQL source location, an independent taint-flow path, a unique security weakness, or a distinct **implementation root decision**. These concepts have different equivalence criteria. In the source study, one root can map to several warning-producing changes/findings.

Read-only SQL against the **later Wits continuation SQLite**, not the hash-authenticated final 29 August DB, found:

| Counting rule for `scanner='codeql' AND introduced=1` | Count |
| --- | ---: |
| Scanner rows | **392** |
| Distinct workflow cases with at least one such row | **131** |
| Completely distinct `raw_json` values | **392** |
| Groups by case + rule + file + primary *line* hash | **385** |
| Groups by case + rule + file + line hash + start-column fingerprint + message | **388** |
| Groups with more than one row after the refined grouping | **1** |

All 392 rows have a primary line hash, start-column fingerprint, message, case ID, rule ID and file path. Three cases (649, 10779, 11286) create overlapping *line-hash-only* groups, with seven additional rows beyond the first per group. However, cases 10779 and 11286 **do not** retain repeated groups when both start-column fingerprint and message are added. Different message/start columns on the same source line can represent distinct findings. A simplistic `case + rule + file + line hash` deduplicator would over-collapse those.

### Source-confirmed case 649: five subranges at one sanitizer chain

Case 649 has **five distinct raw head JSON findings**, all rule `js/incomplete-sanitization` in `src/shared/format-terminal-path.ts`, beginning at line 74. They all share:

- primary line hash `d9ac97afaab7de15:1`;
- start-column fingerprint `12`;
- message indicating backslashes remain unescaped.

Their SARIF regions end at lines **75, 76, 77, 78, 79** respectively. Thus they are distinct scanner records with partially overlapping locations, not literally duplicated `raw_json` rows. Before declaring five separate defects or collapsing them into one vulnerability, inspect original base/head SARIF and full dataflow locations. In particular, five records do not imply five separate H/T/M mechanism choices.

The [case-649 inherited-code root audit](D7_CROOT_00649_RELOCATION_ROUTE_AUDIT_20261022.md) independently found that the old and relocated Windows escaping chains are textually identical; it remains an **introduced-warning vs introduced-vulnerability** validity concern, not a proven false positive.

### Read-only SQL used

The two relevant diagnostic queries below can be run against a **trusted locally staged** historic SQLite copy. Use read-only SQLite; do not mutate historical tables:

~~~sql
SELECT scanner, COUNT(*) AS n_rows, COUNT(DISTINCT case_id) AS n_cases
FROM scanner_findings
WHERE introduced = 1
GROUP BY scanner
ORDER BY n_rows DESC;

WITH keyed AS (
 SELECT
   case_id, rule_id, file_path,
   json_extract(raw_json,'$.partialFingerprints.primaryLocationLineHash') AS line_hash,
   json_extract(raw_json,'$.partialFingerprints.primaryLocationStartColumnFingerprint') AS col_hash,
   json_extract(raw_json,'$.message.text') AS message_text,
   COUNT(*) AS n
 FROM scanner_findings
 WHERE scanner='codeql' AND introduced=1
 GROUP BY case_id,rule_id,file_path,line_hash,col_hash,message_text
)
SELECT COUNT(*) AS refined_groups, SUM(n) AS head_rows,
       SUM(CASE WHEN n>1 THEN 1 ELSE 0 END) AS repeated_groups,
       SUM(CASE WHEN n>1 THEN n-1 ELSE 0 END) AS rows_above_one
FROM keyed;
~~~

The observed answers for the continuation DB are `refined_groups=388`, `head_rows=392`, `repeated_groups=1`, `rows_above_one=4`. An exact match for these counts in another database does not authenticate its file bytes or identical source snapshots.

## SARIF recovery: one visually plausible filename conclusively excluded

The Wits artifact tree also contains an old experimental CodeQL SARIF at

`counterfactual_replay_r1/calibration_medium/historical_validation/results/S5PAIR-025.base.sarif`.

The original PR/base identity for this older calibration case overlaps the October O/W/P case **03581** (same `breaking-brake/cc-wf-studio` and base `68d4f9c0ac43e54266205b80fea328da4dd535a2`). This made it a plausible **false candidate** for the missing original O/W/P before-SARIF.

I retrieved the complete **101,211 original bytes** in read-only base64 chunks, reassembled them, and computed SHA-256 with an implementation first checked against the standard SHA-256 digest of `abc`. The result:

`080f79fd01a52d22ed9d86ec5dbdd9518f059d279bc4d6f8b907ab1f686c6808`

**does not match** the O/W/P-14 original baseline expectation for 03581:

`406d53383bc7c6b133114ab623bfe63a2f43da6d1450b404d105f1e6d853cc9b`.

The candidate SARIF contains **zero result entries**, whereas the original O/W/P catalog reports **82 before results** for that case. Therefore the old calibration *targeted-rule* SARIF is **not** the original O/W/P baseline; it must never be used to close the O/W/P 14-file provenance gate. The same historical base commit and CodeQL product/version are insufficient to establish identical rule-suite and result scope.

## Release gates remain open

- Reinspect original frozen full-study CodeQL before/head SARIF, including exact source snapshots, query suite/pack digests and warning matcher semantics. Only then distinguish repeated source-locus records from independent findings and determine whether alerts were introduced.
- Audit baseline/head warning matching under file relocation and changed reachability; location hash alone is insufficient for semantic equivalence.
- Reproduce **final** 3,809-case scanner-positive membership from authenticated final SQLite, rather than transferring the observed 392/385/388 numbers from a separate continuation database.
- Recover and SHA-authenticate **all 14** original October O/W/P before-SARIF files, rather than substituting old experimental SARIF whose path/commit happens to overlap.

No original scanner rows were modified, no findings were deduplicated, no Slurm job or code execution was submitted on Wits, and no private SARIF data was committed to Git.
