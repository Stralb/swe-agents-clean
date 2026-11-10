# Blinded cluster evaluation

Input: the exact base repository plus the 25 opaque patch files and per-run JSON metadata. Do not join the PRIVATE condition key until all evaluation outputs are frozen.

For every run:
1. create a fresh checkout/worktree at the frozen base SHA;
2. verify a clean tree;
3. apply exactly one patch;
4. record apply failure without repairing the patch;
5. install/build using the same frozen commands/environment for all runs;
6. run functional checks;
7. run the target scanner using the same scanner version/configuration as the observational study where possible;
8. run the hidden security-property checks;
9. save the resulting diff and logs;
10. classify the implementation mechanism blinded to condition;
11. hash outputs and freeze `EVAL_RESULTS_BLINDED.csv`.

Only after step 11 should `CONDITION_KEY_PRIVATE.csv` be joined for analysis.
