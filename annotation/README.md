# Annotation

The prompts, blinding protocols and codebooks used to annotate the study cases. The annotated results are in the study dataset ([data/README.md](../data/README.md)).

## Prompts

Frozen prompt text given to the model.

| File | Stage |
| --- | --- |
| [implementation_description.txt](prompts/implementation_description.txt) | Blind description of what a patch changes (Stage 4B) |
| [root_grouping_coder.md](prompts/root_grouping_coder.md) | Grouping producing changes into implementation choices |
| [root_grouping_adjudicator.md](prompts/root_grouping_adjudicator.md) | Resolving grouping disagreements |
| [later_cases_nine_phase_request.txt](prompts/later_cases_nine_phase_request.txt) | Full request for the 70 later cases: issue coding, PR coding and alignment, blind implementation coding, context, finding verification, finding-to-change mapping, task-role attribution, synthesis and risk assessment |
| [mechanism_origin_pass_b_request.txt](prompts/mechanism_origin_pass_b_request.txt) | Full blind Pass-B request classifying the production route of all 342 implementation choices |

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
| [root_grouping.md](codebooks/root_grouping.md) | Rules for grouping the 455 producing changes into 342 implementation choices |
| [mechanism_origin.md](codebooks/mechanism_origin.md) | H/T/M/U production routes and T1 to T5 explanation strength |
| [control_coding.csv](codebooks/control_coding.csv) | Purpose, specificity, alignment and implementation codes for matched controls |

[classification_corrections.csv](classification_corrections.csv) records the one file-type correction made after the original annotation.

"Side-effect" in these files is the earlier label for what the paper calls Supporting.

## Scope

The prompts above are the original request text. References to later review feedback were removed from the protocols and shortened in the nine-phase request; no method wording changed, and line endings were normalised.

The other stages are documented by their protocols and codebooks. These full requests were not preserved: the mechanism-origin Pass-A, adjudication and final-coding requests, the matched-control coding requests, and the per-case requests for the original 122 cases.
