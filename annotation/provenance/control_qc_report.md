# Matched Control Study — C5 Blinded QC / Reliability / Freeze v1.0

**Status: PASS — 190 matched scanner-negative controls are frozen for C6.**

## C5 scope and safeguards

C5 performed the required second blinded QC pass over all 190 C4 controls. HIGH and MEDIUM queue items were reviewed against full issue text, full PR text, and the full raw implementation evidence; routine rows were checked against full issue/PR text and the frozen implementation evidence, with full raw patch evidence used when a correction was required.

Hard safeguards remained intact:
- scanner findings read: **No**
- scanner runs read: **No**
- locked positive↔control map read: **No**
- positive-case identities used: **No**
- positive-vs-control comparison performed: **No**
- C3 context used to assign semantic labels: **No**

The C4 codebooks were not changed. Scope/range remains omitted from the current control analysis.

## QC outcome

- controls QC'd: **190/190**
- cases confirmed unchanged: **148**
- cases with at least one C5 correction: **42**
- unresolved final semantic labels: **0**
- C5 priority queue processed: **20 HIGH + 29 MEDIUM + 141 ROUTINE**

Evidence limitations were handled conservatively using C3 full raw evidence where available: 15 case packets were truncated in the bounded packet representation, 28 had at least one truncated file, and 17 had at least one missing inline patch. These are preserved as evidence-completeness fields rather than silently discarded.

## C4 → C5 pass-to-pass stability

- **Issue purpose**: 179/190 unchanged (94.2%); 11 corrected; κ=0.909
- **Instruction specificity**: 178/190 unchanged (93.7%); 12 corrected; κ=0.822
- **PR purpose**: 172/190 unchanged (90.5%); 18 corrected; κ=0.856
- **Goal alignment**: 189/190 unchanged (99.5%); 1 corrected; κ=0.921
- **Implementation pattern**: 164/190 unchanged (86.3%); 26 corrected; κ=0.830

These κ values measure **within-pipeline C4→C5 stability**, not independent human inter-rater reliability. The fixed 38-case repeat-QC sample is included for auditability, but it was reviewed by the same model/system. An independent human/second-coder subset therefore remains a publication-level validation task and is not falsely claimed here.

## Frozen C5 counts

### Issue purpose
- Bug / regression / reliability fix: **97** (51.1%)
- Feature / capability addition: **53** (27.9%)
- Internal engineering / test / CI maintenance: **16** (8.4%)
- Dependency / package/toolchain maintenance: **14** (7.4%)
- Security hardening / vulnerability remediation: **6** (3.2%)
- Compatibility / migration / platform adaptation: **4** (2.1%)

### Instruction specificity
- Explicit instruction: **148** (77.9%)
- Problem only: **33** (17.4%)
- Suggests solution: **9** (4.7%)

### PR purpose
- Bug / regression / reliability fix: **89** (46.8%)
- Feature / capability addition: **59** (31.1%)
- Internal engineering / test / CI maintenance: **16** (8.4%)
- Dependency / package/toolchain maintenance: **15** (7.9%)
- Security hardening / vulnerability remediation: **6** (3.2%)
- Compatibility / migration / platform adaptation: **5** (2.6%)

### Goal alignment
- Aligned: **183** (96.3%)
- Expanded: **4** (2.1%)
- Diverged: **3** (1.6%)

### Implementation pattern
- Capability / integration expansion: **56** (29.5%)
- Behavior / reliability correction: **47** (24.7%)
- Runtime / infrastructure / configuration change: **29** (15.3%)
- Dependency / build / toolchain change: **20** (10.5%)
- Internal tooling / CI / refactor: **19** (10.0%)
- Validation / access / boundary control: **10** (5.3%)
- Data / persistence / state management: **9** (4.7%)

## Context freeze

The separate C3 factual context table was QC'd and frozen without using it to change semantic labels. Available fields include signed issue→PR delay, PR merge time, author identity/association, same issue/PR author, PR size, review-row availability, and agent-marker evidence. A deterministic agent-tool normalization is included while retaining the raw marker JSON.

The C3 context export did **not** contain account-age-at-issue or prior-repository-interaction counts. C5 does not invent them. If those fields are required in C6, they must come from the already-existing positive/control factual enrichment source or a bounded factual export.

## Freeze boundary

C5 is now frozen. **No C6 comparison was performed.** The locked positive↔control mapping remains unopened in this phase. C6 is the first permitted unblinding/comparison stage.
