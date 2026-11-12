# Why v2.1 is not the final scientific miner

The v2.1 run completed correctly as an outcome-blind computation, but inspection of the strict catalogue showed that its discovery unit was still too permissive.

Strict catalogue composition (1,950 rows):

- code_motif_asymmetry: 1,474
- relationship: 119
- path_cochange_motif: 100
- edit_transition_motif: 100
- interaction_pattern: 100
- call_shape_motif: 49
- adjusted_temporal: 8

Observed failure modes:

1. 45 generic relational/operational fields remained in the 107 included primary-observed features, including crawler query/string-length metadata and generic relational string summaries.
2. All 8 strict adjusted-temporal discoveries were crawler/retrieval metadata rather than software-development behavior.
3. Top relationships/interactions were dominated by alternate measurements of the same quantity (for example PR additions versus parsed patch additions).
4. Path motifs were heavily dominated by alternate decompositions of the same path (`namepart=tsx` + `ext=.tsx`, `.github` + `.github/workflows`, etc.).
5. 81/100 strict edit-transition motifs contained partial-hunk parser artifacts such as `ERROR` or `string_content`.
6. The 1,474 code-motif asymmetries were mostly global lexical composition differences such as common language tokens, not concrete before->after operations.
7. The cleanest call-shape results largely described expected test scaffolding (`beforeEach`, `describe`, assertions, mocks, temporary directories), useful descriptively but not a deep discovery on their own.

Therefore v2.2 does not attempt to rerank the v2.1 catalogue. It changes the discovery object from stable states/frequencies to concrete diff operations and repository-conditioned cross-file relationships.
