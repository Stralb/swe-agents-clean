# A24 final argument and evidence revision — 9 November 2026

**Starting point:** `Arno_A24_PLAIN_LANGUAGE_REVISED_2026-11-09.pdf` and its exact source ZIP. All revisions were made to `main.tex` and `supplement.tex` within that project, not to a superseded draft.

## Evidence confirmed independently

- Spotify pre-PR code: `ZHANGTIANYAO1/teamspeak-music-bot`, commit `f8743a904f50a065c9fcf5139e46005b5fff2e46`, `src/data/sessions.ts:56` uses `randomBytes(32).toString("base64url")`. This is a repository-local *example*, not a tested drop-in fix for the Spotify verifier. A pinned source link is embedded in the case card.
- Historical O/W/P archive: `Stralb/arno-research-reproducibility/provenance/owp14_case_arm_counts_20261020.csv` records OpenAgents case `16633` with `O_new_claimed=0` and `O_syntax_JSX=SYNTAX_FAIL`; W and P pass their recorded syntax checks. The identification is added to Results and S6.
- The original workbook's Stage4C taxonomy sheet has 134 data rows. The S2 record now distinguishes 133 unchanged descriptions and one correction from the later 122 active cases.

## Main manuscript

1. Reframed the introduction and contributions around the scientific finding: implementing a requested feature and its security consequences require distinct evidence.
2. Replaced jargon-heavy RQ1 with the question of how PR warnings relate to linked issue requirements.
3. Corrected matching language: finding status defines the groups; issue-wording labels and review variables were not additional matching criteria.
4. Reworded the replay protocol to distinguish archived outputs from verified independent model sessions. Corrected the hindsight interpretation.
5. Shortened P1-P5 pilot narrative to a supplementary reference while keeping the completed O/W/P experiment as an actual reported result.
6. Added case 16633-O's failed syntax check next to zero-alert replay results.
7. Replaced case-card `Better option` with `Alternative`; added the verified Spotify pre-PR source link and removed the false 'repository not checked' statement.
8. Moved the detailed 342-choice classification discussion to S4 (which already contains the census), leaving a short guide in the main RQ1 results.
9. Removed an unsupported promise of an S3 four-case trace-index table. S3 case evidence remains; the previously removed index is not restored.
10. Removed unnecessary quantitative discussion of Direct versus Supporting roles in the Discussion; retained method/table definitions.
11. Rewrote the conclusion around interpretation rather than inferred patch correctness or causal prevention.
12. Replaced some 'one generation' statements with 'one retained output' where independent session provenance is not established.

## Supplement

- S1 scanner note now points to the version and configuration observations in S7 while maintaining their evidential boundary.
- S2 records 133 unchanged and one corrected description, without conflating 134 reviewed records with the final 122 active instances.
- S6 identifies OpenAgents case 16633-O and its syntax failure.
- Table S8's former non-existent 'item 4' reference had already been corrected in the input source, so no new edit was required.
- P1-P5 pilot and separate targeted repair results remain fully in S6.

## Not changed or newly claimed

- No scanner reruns, new implementation tests, new independent coding or reanalysis of matched outcomes were carried out in this editorial revision.
- No reported alert totals, matched-pair counts, stage proportions, or P1-P5 cell values were changed.
- Code availability wording was not altered; the examiner's access is an established part of the submission context.
- The old 'finding-free' comparison wording and the overbroad static-analysis-warning claim had already been corrected in the starting draft.

## Build and layout QA

- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` succeeded.
- Result is 33 pages. All pages were rendered for inspection. Main revisions on pp. 2, 10–11, 14–19 and supplementary revisions on pp. 23 and 30–31 were visually checked.
- No LaTeX overfull text boxes or undefined references were detected.
- The Spotify case card's pinned source link was checked in the compiled PDF and retains `#L56`.
