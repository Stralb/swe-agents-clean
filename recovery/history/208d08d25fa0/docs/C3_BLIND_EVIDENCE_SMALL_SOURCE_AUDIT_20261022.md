# C3 blind-evidence integrity — 22 October 2026

**Result:** `PASS_SMALL_FROZEN_C3_LOCKED_MAPPING_AND_BLANK_TEMPLATE_ROSTERS_ONLY`

This audit was performed through approved read-only Wits artifact access. It does **not** reopen the C1 path whose access was denied.

## Directly checked historical inputs

The C3 locked pair map, blinded-control manifest, and all three annotation templates were fetched in full and their SHA-256 fingerprints checked against the original C3 `SHA256SUMS.txt`. The locked pair map was compared to the already-authenticated C2 frozen 190-pair CSV.

| Invariant | Observed |
| --- | ---: |
| Locked C3 control↔positive links | 190 / 190 |
| Unique blinded IDs | 190 |
| Unique C2 controls and positives | 190 each |
| Repository, positive/control case or tier disagreements | **0** |
| Blinded manifest rows and matching blind IDs | 190 |
| Issue, PR and implementation annotation-template blind IDs | 190 each |
| Populated fields beyond blind ID in those **frozen templates** | **0** |

The three frozen templates are completely blank beyond their blind IDs. **They are not a completed annotation dataset.** This does not prove no annotations exist elsewhere. A separately authenticated, completed source is required to regenerate claimed positive-versus-control semantic comparisons.

## Blinding boundary in the source manifest

The archived C3 QC report states scanner runs and scanner findings were **not read** for the control evidence packets, and that positive IDs are confined to the locked mapping. The issue and PR packets each declare 190 rows, and context was kept separate. Those declarations are not independent recreation of the full text-packet exports.

The original C3 hashes for the larger issue, PR and context CSVs are preserved in `provenance/c3_small_blind_readonly_audit_20261022.json`. Independent **full-byte** reconstruction of those three CSVs remains outstanding due to intermittent Wits SSH timeouts. Do not report their current byte identity or per-row roster as newly verified.

## Read-only verifier

A standalone local `analysis.frozen_c3_blind_gate` checker and **20 synthetic tests** were developed and passed offline. The verifier accepts approved source copies outside Git, checks fixed source hashes, source schema, 190-row blind rosters and C2 relationships, verifies all three templates remain blank, and tests implementation packet **filenames** only (not file bytes). Transfer of these files to the draft PR has been blocked by an expired file-transfer session; they must not be counted as committed or CI-verified until a GitHub commit actually includes them.

## Scientific limits

This pass certifies stored blinding and membership relations in a subset of C3, not annotation completion, implementation correctness, scanner validity, matching-optimiser optimality, statistical significance or causal effects. Preserve separate workflow boundaries for blind issue → blind PR → blind implementation → frozen labels → post-label context.
