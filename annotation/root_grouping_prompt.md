# Root-decision grouping prompt

You are coding **only root-decision boundaries** within one blinded PR/workflow packet.

## Task
Group the producing changes in this packet into distinct root implementation decisions.

A root decision is the smallest underlying implementation strategy for one implementation subproblem that explains one or more producing changes.

Put two producing changes in the same root **only if all are true**:
1. they address the same concrete implementation subproblem;
2. they use/instantiate the same underlying strategy;
3. one conceptual implementation change would normally replace/remove both.

Keep them separate when this is not established. Do not merge merely because they occur in the same file/hunk, trigger similar conditions, concern the same broad feature, or are both dependency changes.

For dependency/toolchain material, merge only when one common dependency/resolution operation jointly accounts for the PCs. Separate independently editable package/version operations or distinct dependency subproblems.

## Forbidden inference
Do **not** judge or infer:
- security severity or vulnerability validity;
- whether a human requested the mechanism;
- repository provenance/copying;
- toolchain causality beyond what is needed to identify one indivisible implementation operation;
- maliciousness or intent;
- Direct/Side-effect;
- T1–T5 explanation tier;
- guard/check/validation labels;
- scanner-negative controls;
- membership in any earlier root study.

Use only the factual producing-change descriptions, changed locations, and patch excerpts in the packet.

When uncertain, **fail closed against over-merging**: keep PCs separate and set `boundary_uncertain=true` where appropriate.

## Output
Return exactly one JSON object for the workflow, with no prose outside the JSON:

{
  "workflow_alias": "<exact alias from packet>",
  "roots": [
    {
      "root_local_id": "R1",
      "pc_aliases": ["P01", "P02"],
      "root_summary": "Neutral factual description of the underlying implementation decision",
      "subproblem": "Concrete implementation subproblem",
      "shared_strategy": "Implementation strategy selected/realized in the patch",
      "merge_rationale": "Why these PCs are one root; for singleton root say 'singleton PC'",
      "evidence_refs": ["P01:path-or-hunk", "P02:path-or-hunk"],
      "boundary_uncertain": false,
      "confidence": "high"
    }
  ],
  "all_pc_aliases_accounted_for": true,
  "notes": ""
}

Allowed confidence values: `high`, `medium`, `low`.
Every PC alias in the packet must occur **exactly once** across the roots.
