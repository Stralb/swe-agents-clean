# Annotation

The prompts, blinding protocols and codebooks used to annotate the study cases. The annotated results are in the study dataset ([data/README.md](../data/README.md)).

## Prompts

Frozen prompt text given to the model.

| File | Stage |
| --- | --- |
| [implementation_description.txt](prompts/implementation_description.txt) | Blind description of what a patch changes (Stage 4B) |
| [root_grouping_coder.md](prompts/root_grouping_coder.md) | Grouping responsible changes into implementation choices |
| [root_grouping_adjudicator.md](prompts/root_grouping_adjudicator.md) | Resolving grouping disagreements |
| [later_cases_nine_phase_request.txt](prompts/later_cases_nine_phase_request.txt) | Full request for the 70 later cases: issue coding, PR coding and alignment, blind implementation coding, context, finding verification, finding-to-change mapping, task-role attribution, synthesis and risk assessment |
| [mechanism_origin_pass_b_request.txt](prompts/mechanism_origin_pass_b_request.txt) | Full blind Pass-B request classifying the production route of all 342 implementation choices |
| [generation/master_prompt.txt](prompts/generation/master_prompt.txt) | Shared implementation prompt for the five-chat, 30-packet experiment |
| [generation/between_task_reset.txt](prompts/generation/between_task_reset.txt) | Reset instruction between generation tasks in the same chat |
| [generation/screening_wave14.txt](prompts/generation/screening_wave14.txt) | Wave-14 screening generation request |
| [review_phase2_audit_request.txt](prompts/review_phase2_audit_request.txt) | Post-freeze Phase-2 reliability and root-scope audit request |

The Phase-2 audit file preserves the verbatim request from the handoff's “WHAT TO ASK” section; upload instructions and historical classifications are excluded. Generation prompts are separate from the annotation passes. These instructions document the requested procedure and do not establish runtime compliance or independent human review.

## Not recovered

The original request text was not recovered for four stages: the Pass-A classification of the 342 implementation choices, the adjudication of Pass-A and Pass-B disagreements, the coding of the 190 matched controls and the quality check of those control labels. Their codebooks, blinding protocols and outputs are included and define what each stage did. The prompts above are the requests that were recovered.

## Protocols

What each coder could see, and in what order. These are the instructions followed at each stage, not literal model requests.

| File | Stage |
| --- | --- |
| [issue_blind.txt](protocols/issue_blind.txt) | Issue summary from title and body only |
| [pr_blind.txt](protocols/pr_blind.txt) | PR goal summary from title and body only |
| [implementation_blind.txt](protocols/implementation_blind.txt) | Implementation description from the diff only |
| [original_122_method.txt](protocols/original_122_method.txt) | Full method for the original 122 annotated cases, including finding-to-change evidence rules and Direct/Side-effect/Unclear task roles |
| [mechanism_origin_blinding.md](protocols/mechanism_origin_blinding.md) | Evidence packets for the mechanism-origin passes |
| [control_blinding.md](protocols/control_blinding.md) | Order of blinding for matched-control coding |

## Codebooks

| File | Contents |
| --- | --- |
| [root_grouping.md](codebooks/root_grouping.md) | Rules for grouping the 455 responsible changes into 342 implementation choices |
| [mechanism_origin.md](codebooks/mechanism_origin.md) | H/T/M/U production routes and T1 to T5 explanation strength |
| [control_coding.csv](codebooks/control_coding.csv) | Purpose, specificity, alignment and implementation codes for matched controls |

## Provenance

Records saved when the later stages ran.

| File | Contents |
| --- | --- |
| [control_first_pass_report.md](provenance/control_first_pass_report.md) | First-pass coding of the 190 matched controls: what was coded, blinding safeguards, first-pass counts |
| [control_qc_report.md](provenance/control_qc_report.md) | Second blinded pass over the controls, with pass-to-pass stability and the frozen control counts |
| [mechanism_origin_pass_a.json](provenance/mechanism_origin_pass_a.json) | Pass-A metadata: model, inputs revealed and withheld, route and tier counts |
| [mechanism_origin_final.json](provenance/mechanism_origin_final.json) | Final adjudicated census metadata, including Pass-A/Pass-B agreement |
| [discovery_holdout_results.json](provenance/discovery_holdout_results.json) | Comparison of the final census with the earlier discovery cohort, run after the labels were frozen |

The recorded annotation model was GPT-5.6 Sol. The two mechanism-origin passes used the same model family with different root identities and ordering, so their agreement is within-pipeline stability and not independent human reliability.

[classification_corrections.csv](classification_corrections.csv) records the one file-type correction made after the original annotation.

"Side-effect" in these files is the earlier label for what the paper calls Supporting.

## Scope

The prompts above are the original request text. References to later review feedback were removed from the protocols and shortened in the nine-phase request; no method wording changed, and line endings were normalised.

The other stages are documented by their protocols, codebooks and provenance records. These requests were not preserved: the mechanism-origin Pass-A and adjudication requests, the matched-control coding requests, and the per-case requests for the original 122 cases. The discovery/holdout comparison was an analysis run after the labels were frozen, not an annotation pass.
