# O/W/P — selected finding adjudication (19 October 2026)

## Scope and decision rule

This audit uses the 12 uploaded O patches, 14 W patches, and 14 P patches, plus the archived CodeQL 2.25.6 security-extended SARIF and a direct source review of the uploaded patch diffs. The comparison is *counterfactual*: W and P independently implement the same original issue, rather than editing the O patch. A same-rule alert is not necessarily the same vulnerable source-to-sink path. An absent alert is not necessarily the absence of risky behavior.

For the six cases where this particular O implementation newly triggered the selected historical rule, classify (1) same unsafe operation remains; (2) original unsafe mechanism replaced or materially guarded; (3) finding disappeared because implicated operation was omitted; or (4) unresolved. Maintain distinct scanner and mechanism outcomes.

| Case | O selected-rule | W selected-rule | P selected-rule | Source-level adjudication |
|---|---:|---:|---:|---|
| 00668 | 1 | 1 | 1 | **Not prevented** in either arm. `readHudConfig` reads `settings.json` and W/P still use a check-before-read (`existsSync` before `readFileSync`) in `src/hud/state.ts`. The same CodeQL race category remains in the same function. |
| 03429 | 1 | 1 | 0 | **P materially mitigates the flagged file-writing operation; W does not.** O/W add a new call into an existing `writeGeneratedFile` that uses `fs.writeFile`; the warning lands at an unchanged line in `FileSystemUtils.ts`, but the newly introduced call path triggers the finding. P changes that helper to create a random, exclusive temporary file (`O_CREAT|O_EXCL|O_NOFOLLOW`, mode `0600`) and rename. This supports mechanism mitigation of insecure direct creation, **not proof of fully atomic symlink-safe destination replacement**. Filtered source provisional. |
| 03581 | 1 | 0 | 0 | **Both replace the particular check-then-open file-race mechanism.** O does `stat(file)` and later `open(file)` separately. W uses `openSync` and `fstatSync` on the same descriptor; P uses `open` and `file.stat()` on the same descriptor and checks inode identity. Both address that specific TOCTOU pattern. Existing watcher black-box fixtures separately show W drops tool-result records and P handles file replacement. Not full feature validation. |
| 08152 | 2 | 1 | 2 | **Partial scanner reduction in W, not an established security fix.** O CodeQL dataflows are the Telegram bot token loaded from local settings into the Telegram file download URL and a separate stored API key into the transcription Authorization header. W removes the stored-key flow by using `OPENAI_API_KEY` but retains the bot-token flow. P retains both stored-credential flows. W/P also validate returned Telegram file paths (P explicitly disallows redirects), but those checks do **not** address the CodeQL-reported credential-origin sources. Whether these intentional credential flows are exploitable is unresolved. |
| 22223 | 1 | 1 | 1 | **Neither prevents the selected CodeQL dataflow.** All three independently fetch browser-mediated data and persist the resulting bytes; the selected `js/http-to-file-access` source/sink pattern persists. W/P constrain origins and filenames and use exclusive local output (`wx`); these are useful additional mitigations but do not eliminate the selected flow. W uses a presumed ChatGPT backend endpoint; functional compatibility unverified. |
| 31207 | 1 | 0 | 1 | **W eliminates the alert by omitting the implicated health-check operation, not by securing it.** O/P add `fleetHealthcheck.mjs`, read a token from a file and send it to a local `/fleet/probe` endpoint; the selected dataflow remains in P. W adds only `fleetPlaneHttp.mjs`, `fleetPlaneHttp.test.mjs`, and `configBase.mjs`, with no health-check, Compose service or ingress integration. W is an *operation omission*, not prevention evidence. Filtered source provisional. |

### Critical caveats

- **O target absent in this new cohort**: 06104, 12344, 16633, 20094, 21682, 32759. These cannot contribute to a denominator of *introduced target findings prevented*. 08461 and 15151 have no uploaded O patch at all.
- **The historical eight-case eligibility cohort is different**: recurrence in one of two *earlier* O pilot generations does not imply recurrence in these *new* O patches. Keep both cohorts separate.
- **Scanner-level counts are not confirmed vulnerability counts**: the six cases above have O selected-rule counts totaling seven, and W/P differ, but each result must be linked to its actual source/sink and root behavior.
- **No causal claim yet**: generation controls, frozen historical issue-body provenance, and filtered source limitations remain; this is a mechanistic adjudication rather than a randomized treatment estimate.

## Priority conclusion

1. **Strongest evidence of removal of the introduced risky pattern**: 03581 (W and P), supported by the same-file-descriptor source change and the disappearance of the selected CodeQL alert.
2. **Additional promising prevention by changed write mechanism**: 03429 P, provisional and narrower than comprehensive symlink safety.
3. **Nonprevention / residual finding**: 00668 W/P and 22223 W/P.
4. **Not a valid warning-prevention success**: 31207 W, because the implicated health-check path is omitted.
5. **Changed scanner path but underlying risk uncertain**: 08152 W/P, including potentially intentional use of credentials in HTTPS requests.

The next step is a **minimal mechanism-specific reproduction** only for genuine ambiguities (e.g., 03429 destination-symlink replacement and 08152 actual credential-leak control). No broad acceptance-suite requirement is necessary to answer the narrower question, although omitted operations must be identified to avoid false successes.
