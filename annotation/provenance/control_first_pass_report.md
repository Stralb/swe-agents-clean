# Matched Control Study — C4 First-Pass Coding v1.0

**Status: C4 FIRST PASS COMPLETE; C5 QC REQUIRED BEFORE FREEZE.**

## What was coded

All **190 blinded matched controls** received the same frozen semantic layers that exist for the positive cohort where those concepts are defined:

- factual issue request summary;
- frozen issue-purpose category;
- instruction specificity;
- factual PR stated-goal summary;
- frozen PR-purpose category;
- issue↔PR goal alignment;
- blind implementation summary;
- frozen seven-category implementation pattern.

No scope/range label was added.

## Blinding safeguards

- scanner findings read: **No**
- scanner runs read: **No**
- locked positive↔control map read: **No**
- positive-case identities used: **No**
- context used to assign semantic labels: **No**
- positive-vs-control comparison performed: **No**

The context export is copied into the workbook only as a physically separate sheet for the later QC/context stage.

## First-pass counts

### Issue purpose
- Bug / regression / reliability fix: **102**
- Internal engineering / test / CI maintenance: **15**
- Feature / capability addition: **52**
- Compatibility / migration / platform adaptation: **4**
- Dependency / package/toolchain maintenance: **14**
- Security hardening / vulnerability remediation: **3**

### Instruction specificity
- Explicit instruction: **150**
- Problem only: **31**
- Suggests solution: **9**

### PR purpose
- Security hardening / vulnerability remediation: **3**
- Internal engineering / test / CI maintenance: **15**
- Bug / regression / reliability fix: **92**
- Feature / capability addition: **63**
- Compatibility / migration / platform adaptation: **5**
- Dependency / package/toolchain maintenance: **12**

### Issue↔PR alignment
- Aligned: **184**
- Expanded: **3**
- Diverged: **3**

### Implementation pattern
- Dependency / build / toolchain change: **18**
- Validation / access / boundary control: **17**
- Internal tooling / CI / refactor: **13**
- Behavior / reliability correction: **47**
- Capability / integration expansion: **54**
- Data / persistence / state management: **10**
- Runtime / infrastructure / configuration change: **31**

## Evidence/QC handoff

The C3 evidence index shows **15** case packets with overall truncation, **28** cases with at least one individually truncated file, and **17** cases with at least one missing inline patch. Full raw implementation evidence remains available in the C3 package for C5.

C5 queue priority:
- HIGH: **20**
- MEDIUM: **29**
- ROUTINE: **141**

Every one of the 190 rows is intentionally marked `c5_qc_required=YES`. C5 is the second blinded factual/category-boundary pass and is where corrections become the frozen control labels.

## Important interpretation rule

These are **not yet control-study results**. The first-pass counts must not be compared with the positive cohort until C5 is complete and the labels are frozen. C6 is the first permitted unblinding/comparison stage.
