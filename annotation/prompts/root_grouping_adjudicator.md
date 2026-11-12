# Frozen Adjudicator Prompt — C Root Census v1.0

You are adjudicating a disagreement between two isolated root-boundary coding passes.

Use the frozen root definition only. Resolve the **partition**, not provenance, security meaning, or intent.

A root is the smallest underlying implementation strategy for one implementation subproblem such that replacing/removing that strategy would jointly remove or alter every PC assigned to it.

Rules:
- Same workflow is mandatory.
- Same concrete subproblem is mandatory.
- Same underlying strategy is mandatory.
- Joint replaceability is mandatory.
- File proximity, scanner similarity, broad feature similarity, or both being dependencies is insufficient.
- When evidence cannot establish a shared root, keep PCs separate.
- Do not infer human prescription, copying, model reasoning, maliciousness, Direct/Side-effect, T1–T5, guard/check, or control status.

Return exactly one JSON object:
{
  "workflow_alias": "...",
  "roots": [...same root fields as coder prompt...],
  "adjudication_reason": "Why this final partition follows the frozen rule",
  "all_pc_aliases_accounted_for": true
}
