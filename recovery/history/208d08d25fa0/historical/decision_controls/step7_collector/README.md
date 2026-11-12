# Decision-Level Controls Step 7 Symmetric Evidence Collector v1.0

Purpose: collect the *same kinds of public evidence* for both members of each of the 51 frozen decision-level pairs, enabling Step 7B–7E without giving the positive side richer context than controls.

For each side it collects:
- PR base/head metadata and exact target-file diff;
- pre-change and post-change target file;
- bounded pre-change `git grep` hits using frozen decision anchors;
- repository agent/project instruction files at the PR base;
- changed test/spec hunks;
- issue comments, PR conversation, reviews, and file-level review comments;
- PR commit chronology;
- 30/90-day target-file persistence using normalized added-line retention;
- SHA256 manifest and collection QC.

It does **not** automatically call a repository pattern “precedent” or a different implementation “safer.” Those are semantic judgments to be made only after the symmetric evidence has been frozen.

Expected output: 102 side directories (51 pairs x 2), then one tarball `~/DECISION_LEVEL_STEP7_EVIDENCE_<timestamp>.tar.gz`.
