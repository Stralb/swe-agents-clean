# T1 Pilot Harness v1

Generic, anonymized harness for the P-/P+/N-/N+ repository-context experiment.

## Core invariants
- Historical repository bases are never edited to manufacture context conditions.
- P-/P+ differ only in whether optional context X is shown.
- N-/N+ differ only in whether optional context X is shown.
- Each LLM run is isolated.
- Generated edits are materialized exactly as emitted; no manual repair.
- Functional failure is not treated as scanner-negative evidence.

## LLM output contract
Each generation must return a JSON file of the form:

{
  "files": [
    {"path": "relative/path.ext", "op": "write", "content": "complete file contents"}
  ]
}

`op` may be `write` or `delete`. Absolute paths and `..` traversal are rejected.

## Workflow
1. `freeze_pilot.py` freezes randomized run order.
2. `build_packets.py` builds P-/P+/N-/N+ packets and checks invariants.
3. Run one isolated LLM session per row of `RUN_SCHEDULE.csv`.
4. `materialize_generation.py` applies exact generated files to a detached worktree at the historical base.
5. `run_evaluation.py` runs functional and scanner commands and records machine-readable results.

The scanner command adapter convention is:
- exit 0 = target finding absent
- exit 42 = target finding present
- any other exit = scanner/evaluation failure

Pair-specific scanner wrappers can therefore hide tool/rule details from the main harness.
