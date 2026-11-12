# Arno research thinking archive - v1.0

**Purpose:** preserve the development of this coding-agent security research before writing the paper. This is an intellectual-history archive, **not the final scientific evidence register, not an empirical audit, and not a new human-annotation task**.

## Annotation firewall

**This archive contains earlier AI labels, case judgments and experimental condition identities. Do not use it to fill your independent review answers. Keep the prior-judgment material separate until your human annotations are frozen. You do not need to read or annotate this new archive now.**

## Start here

Open **ARNO_RESEARCH_IDEAS_AND_FINDINGS_HISTORY_v1_0.csv**. It contains **275 curated entries**. Each row records a substantive statement, finding, hypothesis, intuition, correction, rejected approach, methodological boundary, or author decision. The original source wording, source identity, line range, interpretation limit, and later related records are beside it.

The archive also contains **114 explicit idea-evolution links**. These prevent an attractive earlier interpretation from silently surviving a later correction. Links are archival judgments, not new scientific tests.

## Files

- `ARNO_RESEARCH_IDEAS_AND_FINDINGS_HISTORY_v1_0.csv`: the main filterable working CSV.
- `ARNO_IDEA_EVOLUTION_LINKS_v1_0.csv`: relations among old and later ideas, definitions, results and qualifications.
- `ARNO_HISTORY_SOURCE_REGISTER_v1_0.csv`: 113 sources, exact identities, dates where genuinely known, file digests and coverage.
- `ARNO_FULL_SOURCE_PASSAGES_v1_0.csv`: 1154 consecutive, non-overlapping source passages. These are raw source material, **not 1154 scientific findings**.
- `ARNO_EARLY_HISTORY_RETRIEVAL_LEADS_v1_0.csv`: seven June-July leads available only through secondary personal-context summaries. Not admitted as primary evidence.
- `ARNO_HISTORY_COVERAGE_GAPS_v1_0.csv`: explicit gaps and their consequences.
- `sources/`: exact supplied text for each source, addressed by source ID; contextual PDFs appear as page-labelled extracted text, with original PDF hashes in the register.
- `QA_REPORT.json`: structural checks and coverage counts.
- `MANIFEST.json`: checksums for delivered files.

## What was covered

**102 saved exchange files** (101 unique contents), **five semester presentations**, **four contextual documents** (original project brief, proposal, literature review, August handoff), **selected exact current-user messages**, and the **previous October fact-check report**. There are **113 source records and 112 unique text contents**.

The saved files are primarily earlier assistant responses, not complete original user/assistant transcripts. Some different messages have the same title; they were recovered by file identity rather than relying on the final mounted filename. C077 is an exact duplicate of C076 and is explicitly marked.

This is the available project history, **not a claim to have accessed every conversation in the ChatGPT account**. Full earliest June-July transcripts and some original meeting messages remain unavailable. Secondary recollections remain in a separate leads file. No missing transcript has been reconstructed as if it were verbatim.

## How to read the main CSV

Useful columns:

- `record_id` / `record_key`: stable identifiers for later notes and manuscript links.
- `research_stage`: logical grouping, **not a verified chronological sequence**.
- `category`: a small set of broad filters such as reported finding, hypothesis, correction, limitation, design, or future idea.
- `entry_type`: a more specific archival subtype, not a required new annotation taxonomy.
- `statement`: the archive editor's source-grounded summary, not a quotation or approved paper sentence.
- `historical_status`: status within the available research record.
- `claim_boundary`: an explicitly editorial caution or inference about how the source may be used; it is not a new empirical result. Where the source itself states the qualification, the original excerpt preserves it.
- `historical_status`: an archival classification, not current scientific approval.
- `verification_needed`: what would be needed before relying on the idea scientifically.
- `source_locator`: e.g. `sources/C099.txt#L354-L438`; open that file and use its original line numbers.
- `original_excerpt`: exact contiguous source text before CSV formula-escaping.
- `related_records` / `later_development`: pointers to developments that must be read together.

Every scientific entry is marked **NOT GRANTED BY THIS HISTORY EXTRACTION** for manuscript approval. A source saying 'complete', 'frozen', 'validated' or 'PASS' is retained as a historical statement, not independently certified here. The same caution applies to a previous assistant claiming it performed an audit. Repeated discussion of a result is not independent corroboration of that result.

Dates printed in documents are retained. Import dates are **not** used as original conversation dates. Source identifiers are locators, not timestamps. Reported supervisor feedback is marked as indirect unless it comes from the supplied supervisor brief.

## Critical preserved developments

1. **Original discovery question to mechanism-production question.** The original brief did not guarantee malicious cases would be found. Later work asked where security-relevant implementation mechanisms become observable.
2. **Requested functionality versus exact prescription.** The old Direct label is not the same as asking the human to prescribe the exact scanner-producing mechanism.
3. **Selected 55 roots versus complete census.** The history preserves why a complete 455-to-342 root accounting stage was added and why units/versions cannot be merged casually.
4. **Old T5 'unexplained' labels were revised.** A later report states the eleven old T5 roots changed to nine T4 and two incomplete. The older 20% must not silently become a final estimate.
5. **A flat experiment is not automatically a causal null.** The later C099 account says Context- often retained equivalent mechanism information. This qualifies earlier C096/C097 interpretations without changing their recorded counts. It also leaves a narrower marginal-snippet estimand distinct from 'all context is irrelevant'.
6. **Mechanism, scanner and task outcomes differ.** The archive preserves both M-with-no-warning cases and an archived syntax failure with zero claimed new warnings.
7. **Retrospective warning knowledge is an oracle.** W and warning-derived P conditions do not establish prospective retrieval of safety requirements.
8. **P1/P2/P3 duplication and targeted repairs are different issues.** Invalid treatment comparisons remain invalid; post-hoc repairability is not seven successful preventive interventions.
9. **Unexecuted ideas remain visible.** Non-agent-marker controls, multi-artifact attacks, regression models and footprint-control comparisons are retained with their actual stated status rather than quietly promoted to Methods.

## Separation from current work

Your review workbook, sampling record, frozen original research, and existing 47-claim evidence register were **not changed**. No cluster job was launched, no empirical result recomputed, and no human review assumed completed. This archive adds no new annotation workload for you.

No independent subagent audit was performed or claimed. The work here is source recovery, archival classification, and explicit linking of changes in interpretation.

## Later perspective PDFs

After the human annotations and numerical/evidence audits are integrated, these stable IDs support separate views:

- **Empirical evidence:** which recorded findings survive verification, with final units and cohorts.
- **Causal interpretation:** what was manipulated, what contrast was identified, and what remains confounded.
- **Security interpretation:** scanner conditions versus weaknesses, exploitability, intent, and functional acceptance.
- **Methodological validity:** selection, chronology, label reliability, retrieval completeness, measurement and reproducibility.
- **Contribution and narrative:** what question the study answers, how it differs from related work, and which dead ends motivate the final scope.

These are future synthesis views of one shared record, not independent evidence sources or simulated independent audits. No PDFs or manuscript prose were generated in this pass.

## CSV and archival safety

CSV files are UTF-8 with a BOM for spreadsheet compatibility. Text cells that begin with spreadsheet formula prefixes receive a leading apostrophe; exact unescaped text is preserved in `sources/`. Import numeric-looking identifiers as text where necessary. Legacy `filecite` tokens and sandbox links inside old messages are historical references, **not current accessible citations or proof of an artifact**. Follow the new source IDs and file hashes instead.

The source archive contains historical commands and code snippets as text. **They were not executed and should not be executed simply because they appear in an old exchange.** This is a private working archive; repository paths, case descriptions and manuscript planning may need review before any public release.
