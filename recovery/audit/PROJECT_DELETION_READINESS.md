# Project deletion-readiness audit — 10 November 2026

**Decision: NOT READY to delete the ChatGPT project.** Code preservation and complete results reproduction are different claims. This audit substantially improves the preserved code, but does not attest to a complete export of the project's chats and evidence.

## Code preservation verified

| Check | Evidence |
| --- | --- |
| Current cluster miner implementation | 224 previously archived miner files re-hashed at their original cluster paths; zero changed and zero missing |
| Historical recovery branches | All five non-main historical branch tips in Stralb/arno-research-reproducibility surveyed; 552 additional distinct file contents preserved |
| Chat-side source packages | 225 distinct archives, including nested archives, inspected without executing their contents; 595 additional source/protocol files preserved |
| Published historical/chat source bytes | 1,147 published file blob hashes checked against GitHub; zero mismatches |
| Original manuscript source archive | Complete Arno_A24_FINAL_FIGURES_SOURCE_2026-11-09.zip preserved, including figures and supplementary sources; 4,843,195 bytes, SHA-256 403ae9749ed085d7ad6bb456f9b3e8707fd39ff7b974a7554a1ec1ae6bf111fc |
| Additional miner build files and historical variants | All 525 candidate paths verified present in GitHub, including the original cluster Makefile, requirements and 24 paths initially ignored under logs |

The 552 historical additions and 595 chat-side additions required credential-pattern redactions in 3 and 9 files respectively. The earlier cluster recovery redacted 35 files. Original private GitHub/cluster files were retained. Redacted files are preservation copies, not assertions of executable equivalence.

The 525-file supplementary set includes duplicate historical versions. A file-count increase does not imply new functionality. The live miner had uncommitted/untracked changes; its working file bytes, rather than only its old Git commit, were preserved.

## Where the code is

- ../cluster/miner/ — original captured miner implementation.
- ../cluster/miner_supplement/ — build files, historical variants and scripts outside the first extension/directory filter.
- ../cluster/research_artifacts/ — cluster research drivers, evaluators, extraction scripts and launch jobs.
- ../history/MANIFEST.json — all five historical source refs and a file-to-preserved-path map; byte-identical files already in the recovery branch are referenced rather than repeated.
- ../chat_sources/MANIFEST.json — additional chat package sources and archive hashes.
- LIVE_CLUSTER_AUDIT.json — current live miner comparison and supplementary source records.
- ARCHIVE_COVERAGE.json — limited comparison with the master's 52-object archive-vault index.
- ../chat_sources/Arno_A24_FINAL_FIGURES_SOURCE_2026-11-09.zip — complete manuscript source archive. The later separately uploaded main (3).tex is also preserved among the indexed source files.

No historical research driver was executed during this source recovery. No missing research result or prompt was regenerated.

## Why deletion is not signed off

1. **Latest database backup is unfinished.** The latest observed state of job 84244 is the full integrity check of ARNO_RESEARCH_MASTER.sqlite. The 42.19 GB master and 4.39 GB evidence vault have not yet received a verified upload receipt in this audit. Job 84253 is intended to add database-backup.json and pinned restore instructions only after both uploads verify. Check the actual receipt before treating the backup as complete.

2. **Raw experimental inputs are not fully attested outside ChatGPT.** The archive inspection found many full frozen task repositories and input packets. These are experimental evidence, not the research implementation. Their hashes are inventoried, but their complete private backup has not been established by this audit. Comparison with one 52-object SQLite archive index is not a search of every possible embedded parent archive or table; an unmatched hash is not proof of loss.

3. **Complete chat history has not been exported or verified.** Indexed files and recovered packages do not prove preservation of every inline code block, exact prompt, decision, correction or run detail that may exist only in conversation messages. Keep a separate complete chat/project export before deletion. A handoff summary is not a verbatim history export.

4. **Exact historical reproduction remains unproven.** No full replay of the original 3,809 workflows, 192 positive workflows, 455 producing changes and 190 matched pairs was performed here. The latest recovered manuscript records incomplete exact model invocation/prompt coverage and incomplete historical scanner/runtime pinning. Current compute-node PATH probes do not establish which scanner binaries or advisory databases were used historically. Recovered source versions are not independently authenticated as the exact bytes used for every original scan.

## Deletion conditions

- [ ] Both database files have verified remote sizes/checksums, a final private manifest, and an accessible GitHub backup receipt.
- [ ] Required raw evidence/input archives have been copied outside ChatGPT and matched by checksums.
- [ ] A complete copy of project conversations is saved outside the project.
- [x] Final remote source inventory confirms all 525 supplemental paths, including the 24 ignored log-directory files.
- [ ] The source manifests, build instructions, environment observations and remaining scientific limitations are retained with the research handoff.

The verified conclusion is that the audited live mining implementation and additional recoverable source packages have been preserved. The stronger claim that nothing else in the entire project can be needed for reproduction is not established.


Final verified source commit: 22f9c57781d7a07fd41930f021d493042282e55b. Remote inventory was not truncated; all 525 supplemental paths were present, all 1,147 historical/chat-side blob hashes matched, and the manuscript ZIP blob matched the original Git hash. The latest database status observed during this audit was still the master integrity check.
