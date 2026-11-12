# O/W/P research handoff: 65 tasks, 3 original generations, 14 intervention cohort

This archive includes ALL available generated patch diffs from three 65-case
original-only generations; all archived CodeQL per-case RESULT.json and SARIF
files in each generation; 12 O and 14 W/P intervention implementation patches
and scanner results; each O/W/P issue text (the exact intervention language);
scanner comparison reports, diagnostics, analysis scripts and selected
historical taxonomy artifacts.

WARNING: The 65 frozen full repository source ZIPs and the 14*3 duplicate
frozen source packets are not embedded. Their exact Wits paths are listed
in FROZEN_SOURCE_INDEX.json. A new chat can analyze all patches and scans
offline; to replay CodeQL or run functional integration, it needs access
to the frozen repositories on Wits.

Correct interpretation:
- The three generations are distinct patches, not repeated scans of one patch.
- 65 tasks screened 3 rounds (some scans failed in R2).
- The case-level positive union across O1/O2/O3 is 19.
- Round positives: R1 9; R2 12; R3 15; 7 positives in all 3 rounds.
- A new CodeQL warning does not automatically prove exploitability.
- A selected historical warning class does not imply identical source-to-sink.
- Some W/P scanner improvements result from omitted functionality.
- The strongest complete snapshot historical warning evidence includes
  00668, 03581, 08152, and 22223 in OWP initial comparison.
- Separate O/W/P patch inputs are never equivalent to repairing the same O patch.
- Source snapshots or issue version may still require chronological verification.
- Scanner clean != functional completion != fixed vulnerability.
- Generated patches may include inferred/skipped functionality.
- Privacy: treat this archive as research-confidential; no external publication
  without reviewing repository licenses, issue body content and credentials.
