# E-PILOT653 blinded generation bundle

Purpose: generate 25 independent patches for one historical task without exposing the historical PR, scanner finding, root mechanism, or condition labels to the generator.

## Inputs required for each fresh chat

- exact repository snapshot of `pingcap/ossinsight` at `32934c7e9169f214bf65e214e45104b9a1d678b8`
- exactly one task file from `tasks/`
- the text in `NEW_CHAT_GENERATOR_PROMPT.md`

## Critical blindness rule

Never upload any file from the separate PRIVATE bundle to a generation chat.

## Session rule

Use a fresh **Temporary Chat / otherwise isolated new chat outside the research project** for every run. Do not reuse a conversation. Keep the same model/mode for all 25 runs in a model block.

## Execution order

Follow `RUN_MANIFEST_BLINDED.csv` from order 1 to 25. The order was frozen with seed `20260905` before generation.

## Collection

For each run, save `<RUN_ID>.patch` and `<RUN_ID>.json` unchanged. Do not repair patches manually. Record the generation metadata in `GENERATION_LOG_TEMPLATE.csv`.
