# Case-evidence editorial corrections (9 November 2026)

**Base version:** `Arno_A24_S2_S7_MERGED_SOURCE_2026-11-09.zip`.
**Deliverable:** corrected ACM manuscript and its editable LaTeX source.
**Scope:** case-level factual wording and replay-evidence boundaries only. The 3,809-instance population, numerical tables, alert totals, research questions, figure assets, and S2/S7 consolidation were not altered.

## Corrections applied

- **Spotify (main paper):** replaced the unsupported judgement that the modulo bias was *small* with a statement of non-uniformity and an explicit absence of exploitability assessment. The pre-PR `randomBytes(32).toString("base64url")` repository precedent was already accurately documented and remains intact.
- **GSD (main paper):** distinguished supplying temporary paths to tested code from creating temporary paths; scoped the bullet-list parse/regex/streaming fallback description to the final tool-call arguments instead of claiming a universal parser sequence. The two mapped test operations still account for the archived 86 reported findings.
- **Chaibuilder (main and S3):** described the manifest's actual dependency range `^4` to `^3.4.19` in `frameworks/nextjs/package.json:32` rather than an exact version pin; avoided claiming that the downgrade necessarily caused six associated advisory-bearing entries.
- **cc-wf-studio (main paper):** described pathname `stat` followed by a separate `open` and descriptor-based read, rather than incorrectly calling this a `reopen`.
- **dot-ai (S3):** repaired the broken quotation, restored the full `examples/gateway-api/README.md` path, and explained that the stored production-source label conflicts with the documented file location.
- **Telegram voice input (S6):** corrected Unix mode `0600` to apply to the written audio file, not the temporary directory. Separated O/W/P alert counts (2/1/2) from the distinct P1-P5 pilot (P5: 3).
- **Open Design (S6):** added the historical PR's BYOK rollback context; limited the historical-rule non-reproduction statement specifically to the three O/W/P outputs.
- **Oracle (S6):** removed an unsupported guarantee of confinement under the session directory, and stopped treating missing P4/P5 results as evidence of zero alerts.
- **Extended provenance (S3 and S6):** replaced statements that could imply absent mappings with a description of archived mappings that were not independently revalidated for the case card.
- **Replay method (S6):** replaced the broad claim of missing task-acceptance tests with the narrower fact that the reported checks do not establish functional task completion. The archived OpenAgents case 16633-O syntax failure was already accurately identified and remains unchanged.

## Source-evidence checks in this revision

The following specific source files were inspected at their pinned commits through GitHub: Oracle's `src/browser/artifacts.ts` (sanitiser and pathname construction), Telegram's `src/telegram/audio-input.ts` (`mkdtemp`, `writeFile(..., { mode: 0o600 })`, `rm`), Chaibuilder's `frameworks/nextjs/package.json` (version range), and Open Design's `apps/daemon/src/routes/runs.ts` (BYOK completeness check). The pasted reviewer checklist supplied the remaining targeted code/context findings. No new static-analysis scan or functional replay was performed.

The complete P1-P5 model-session provenance remains unverified; no conclusion has been inferred from missing P4/P5 cells. The pre-existing O/W/P numerical tables are unchanged.

## Build and visual checks

- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` succeeded.
- PDF remains 33 pages.
- No undefined references or overfull boxes reported by the final TeX build.
- The altered pages (main 14/17; supplement 24/26/32/33) were rendered and inspected.
