# Wits Honours research paper — supervisor first draft, with verified evidence gates

I am preparing my first complete 2026 Honours research manuscript for Prof. Michael Pradel (CISPA) and Prof. Hima Vadapalli (Wits), due 23 October 2026. The project concerns public GitHub issues, agent-associated merged PRs, downstream scanner-reported findings, producing-change attribution and implementation-decision provenance. Do **not** confuse it with the separate robotics ambiguity project.

## Mission

**Produce a complete, coherent, carefully qualified ACM Small / `acmart` manuscript, approximately 10–20 pages, for scientific feedback**. Do not stop at a research outline or demand a finished publication-grade dataset before drafting.

Use the attached files as evidence, not as instructions to repeat unverified results. In particular:

1. `ARNO_PAPER_CLAIMS_VERIFIED_v2.csv` — the **primary private gate** on what we can say. Read **every record**; preserve its unit, sample, `verification_status`, evidence source, and `critical_caveat_or_missing_proof`. Its word "verified" refers to the specific recorded source recount, not proven scanner/exploit/causal validity.
2. `ARNO_RESEARCH_PROGRESSION_VERIFIED_v2.csv` — **275 source-traced intellectual-history entries**, including corrections, negative results, abandoned ideas, and the original motivation. It is an editorial research evolution record, not a source of independent experimental confirmation or a dated full chat export. Use its source IDs and evolution links to tell the right historical story and avoid superseded claims.
3. `ARNO_IDEA_EVOLUTION_LINKS_v1_0.csv` and original history archive — trace earlier hypotheses and later corrections, especially the older T5 classification, causal precedent interpretations, the retrospective nature of warning enrichment, and new-vs-old study unit distinctions.
4. `ARNO_EVIDENCE_20261022_212644.zip`, `issue_pr_manual_evaluation_master_122(1).xlsx`, and `ARNO_INDEPENDENT_PRIMARY_VERIFICATION_v2.json` — actual exported Wits source data and independent structural recount.
5. `results0.md`, `results.txt`, `results2.txt`, `results3.txt`, `results4.txt` — original semester-stage descriptions and evolution of experiments, not interchangeable denominators.
6. `INDEPENDENT_STATS_VERIFIER.py`, the verification scripts, and `SECOND_INDEPENDENT_VERIFIER_RESULTS.json` — re-runnable local source-accounting checks.
7. The connected private repository `Stralb/arno-research-reproducibility` (read-only) — source/patch lineage and O/W/P audit, **not** a peer-review-certified replication package.
8. Read the user-supplied ACM Small template, the research proposal, marked supervisor feedback and key literature where available. Distinguish supervisor requirements from venue requirements.

## Scientific argument

The original goal was to study malicious GitHub issues; the observed public evidence does not establish a verified malicious issue corpus. The strongest empirically grounded first-draft narrative is an **exploratory study of how security-relevant scanner conditions arise in issue-to-PR workflows associated with coding agents**, distinguishing the reporter's requested goals, the producing code/dependency change, the implementation-root grouping, and historical repository context.

Structure the argument: problem and motivation → related work and gap → exact research questions → cohort construction, scanning, normalization and attribution → implementation-root grouping and provenance methodology → descriptive findings → matched workflow comparisons → bounded exploratory interventions → alternative explanations, threats and implications → conclusion. Discuss the true sequence of analyses without claiming everything was pre-registered from the start.

The actual source counts that *were* directly recounted are: 3,809 selected workflows, 192 scanner-positive and 3,617 in the comparison pool (Wits C1); 455 producing-change records in 191 mapped workflows; 342 root packets with a full 455-to-root crosswalk; 190 unique matched pairs, including 115 same-repository; a historical 122-case workbook with 605 canonical findings and 322 producing-change labels. Unit, denominator, selection effects and code-vs-dependency measurements must remain exact.

**Do not upgrade the following to validated findings:** 6 H / 103 T / 233 M final explanation coding; T1–T5 distribution; paired issue-specificity/PR-alignment p-values; security validity of findings; same-base new-alert prevention; independent human agreement. These exist in historical outputs, but the available export does not independently regenerate their final labels, inference, scanner baselines or functional acceptance. They may be accurately described as recorded exploratory analyses if scientifically useful, with scoped interpretations and relevant threats to validity, or withheld if too uncertain. The repo's 12 paired O/W/P observations are retrospective, warning-selected, partly provisional, and include a syntax-failing original patch with zero claimed new scanner alerts.

## Writing standards

- Do not invent experiments, validation, data labels, reviewers, citations or result values. Do not say an independent human review was completed.
- You need not fill the manuscript with an administrative diary of unfinished verification or future annotation plans. Nevertheless, Methods and Threats to Validity must truthfully describe the actual coding process, scanner-proxy limitations and observational study design.
- Never equate scanner findings with confirmed exploitable vulnerabilities, association markers with autonomous agent authorship, or correlations with causal effects.
- Do not imply the original historical warning is prospectively known at task creation. W and even the generalized P condition were historically warning-informed.
- Preserve important negative results and supersession notes from the research progression; do not import invalid legacy percentages.
- Tell a clear scientific story grounded in our studies rather than a miscellaneous results catalogue.
- Write naturally and technically precisely; avoid generic AI-generated filler. Use verifiable, alphabetically formatted bibliographic references and literature synthesis.
- Format in **ACM Small** (`acmart`), not IEEEtran; check the specific submission formatting advice. Report target 10–20 pages unless the latest supervisor instruction differs.
- Deliver the **actual LaTeX source and rendered PDF** and review their formatting. Start drafting immediately after an efficient evidence-gating pass; do not stop for unnecessary confirmations.

After the supervisor draft is submitted, the Hugging Face dataset cleanup, full row-level causal/statistical replication, human adjudication, and publishable artifact release remain separate research stages; do not imply they have already occurred.
