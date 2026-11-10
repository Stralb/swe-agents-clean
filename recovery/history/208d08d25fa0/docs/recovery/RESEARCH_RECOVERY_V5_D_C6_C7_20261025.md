# Historical research evidence v5 — original frozen D/C6/C7 recovery

Created solely from original user-uploaded historical source bytes, independently hashed and preserved intact. **No experiments, LLM codings, scanner runs or new scientific interpretations have been performed.**

## Verified new evidence

- Four original tar.gz archives have their `SHA256SUMS.txt` entries cryptographically checked against their actual members. All 57 referenced payload digests match; no missing entries.
- 3 original standalone frozen D/D7 files preserved; the 198 D4 and 342 D5 standalone files hash-identically match their originals in the D-final archive.
- 4,953 source-row snapshots indexed from 25 specific original CSV/JSONL sources, with original SHA-256 and archive paths.
- 190 C6 matched pairs cross-linked one-to-one to original C7 records (115 matched within the same repository).
- D5 original 342 roots (M234/T103/H5); D7 original 342 roots (M233/T103/H6); exactly 43 D5-vs-D7 source label differences, with one M-to-H route change at CROOT-00649-01, are preserved as **unresolved source-version differences**.
- 342 source Pass A input packets and 342 separately blinded Pass B input packets retained. The private alias crosswalk stays distinct from the blinded inputs.
- 198 original D4 adjudications agree exactly with the D5 frozen adjudicated-root subset.
- Original earlier 122-case workbook and O/W/P generated patches plus SARIF reports are retained from v4 unchanged.

## Reviewer commands

Run the supplied `v5_root_controls_cli.py` using Python 3.11 or later:
```bash
python v5_root_controls_cli.py --database arno_research_v5_PORTABLE_PRIVATE.sqlite verify --deep
python v5_root_controls_cli.py --database arno_research_v5_PORTABLE_PRIVATE.sqlite root CROOT-00154-01
python v5_root_controls_cli.py --database arno_research_v5_PORTABLE_PRIVATE.sqlite root CROOT-00649-01
python v5_root_controls_cli.py --database arno_research_v5_PORTABLE_PRIVATE.sqlite pair 1
python v5_root_controls_cli.py --database arno_research_v5_PORTABLE_PRIVATE.sqlite case 154
python v5_root_controls_cli.py --database arno_research_v5_PORTABLE_PRIVATE.sqlite differences --limit 50
```
Private unblinding requires explicit `--unblind` in the root query and must never be provided to blind coders before their pass is frozen.

## Strict limitations

All 16 historical research stages remain registered, but many original prior-chat archives are metadata-only in ChatGPT Library; raw-byte materialization failed in this current Project session. This database does not claim full study completion or valid counterfactual causality, and no data has been uploaded to Hugging Face.
The private archive contains unpublished original source code and research data. Do not make public without privacy, intellectual-property and blinding review.

## Stage coverage

| Study | Verified named recovery targets | Still metadata-only |
|---|---:|---:|
| P00_SUPERVISOR_CONCEPT | 2 | 0 |
| P01_MINER_AND_WORKFLOWS | 0 | 2 |
| P02_122_FIRST_AUDIT | 0 | 1 |
| P03_FOOTPRINTS_AND_SWEXPLOIT | 0 | 3 |
| P04_SCAN_COHORT | 0 | 2 |
| P05_PRODUCING_CHANGES | 0 | 3 |
| P06_D_DOUBLE_CODING | 4 | 1 |
| P07_MATCHED_CONTROLS | 3 | 0 |
| P08_NEW70 | 0 | 2 |
| P09_T1_CONTEXT | 0 | 3 |
| P10_T2_TRANSFER | 0 | 2 |
| P11_S5PAIR | 0 | 3 |
| P12_PREVENTION_65 | 0 | 0 |
| P13_COUNTERFACTUAL_14 | 0 | 0 |
| P14_PAPER_CLAIMS | 0 | 3 |
| P15_RELEASE_REPRODUCIBILITY | 0 | 2 |

Source-level manifest: `arno_research_v5_recovery_report.json`. The original bytes—not this README—are authoritative.