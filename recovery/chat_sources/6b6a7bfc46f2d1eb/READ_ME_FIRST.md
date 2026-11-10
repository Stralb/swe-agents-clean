# Seven-case follow-up: four positive cases targeted repair

Date: 2026-10-20. CodeQL 2.25.6, javascript-security-extended. These are researcher-directed code/fixture changes generated from an already scanned agent patch. They are NOT independently implemented candidate issue prompts, and no minimum sufficient text has been established.

Summary: two of the four previously positive implementations now have zero NEW CodeQL findings.
- 03429: BEFORE 42, AFTER 33, NEW 0. Scanner signal eliminated by replacing the fixed /tmp/test-project unit-test fixture with a private unique mkdtemp directory; production backup still uses NOFOLLOW/EXCL. This is principally a TEST-FIXTURE effect. Do NOT count as issue-information success or attribute to production code.
- 12344: BEFORE 758, AFTER 757, NEW 0. Every Windows DPAPI credential filename derives from a validated canonical basename. Existing profile-ID filenames are unchanged. Windows DPAPI native acceptance NOT TESTED; project tests on Wits could not load the TypeScript module. Original P1 offline mocks passed before this refinement.
- 08152: BEFORE 4, AFTER 5, NEW 1. Substring-based URL mock warning eliminated by exact hostname comparison. Remaining js/file-access-to-http is a local settings JSON BOT TOKEN used in Telegram's fixed HTTPS file API URL. This may be necessary authenticated behavior; an external leak is not established.
- 31207: BEFORE 60, AFTER 61, NEW 1. CORS wildcard eliminated via same-origin policy. Remaining js/file-access-to-http is the secret-file PAT forwarded as Authorization to a strict loopback authenticated probe. Required authenticated readiness should not be removed merely to silence a scanner.
The zero-warning cases 03581,22223,32759 from earlier seven-case evaluation are unchanged. Combined exploratory scanner-negative total: 5/7. Functional acceptance is NOT established for any full integration.
Important: scanner outcomes count newly introduced SARIF findings against each identical frozen base, not total findings. CodeQL negatives do not guarantee security. The remaining file-access-to-http alerts require contextual threat-model adjudication. Dropping Telegram voice download or removing authorized PAT flows to hide these warnings would be functionality or security regressions.

Included:
REPAIRS/ contains four new full unified patches against each pristine CASE_<id>_O REPO.
SCANS/ contains each case's baseline and patched SARIF, evaluator logs and RESULT.json.
PREVIOUS_SEVEN_CASE_SCAN.zip is prior complete scan context.
RESEARCH_ISSUES/ original 08152 and 31207 issues.
RECOMMENDED_NEXT_STEPS.md distinguishes legitimate required flows vs genuinely actionable defects.
