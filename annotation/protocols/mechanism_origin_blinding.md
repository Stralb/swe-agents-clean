# D Complete Root Evidence Export v1.1

Purpose:
Deterministically export the public evidence required to classify the frozen
342 root implementation decisions.

This export performs NO D semantic classification.

It does not assign:
- H / T / M / U
- T1 / T2 / T3 / T4 / T5
- maliciousness
- intent
- model reasoning
- copying
- guard/control outcomes

PASS A:
Use D_PASS_A_EVIDENCE_342.jsonl for the first complete coding pass.

PASS B:
Use D_PASS_B_EVIDENCE_BLIND_342.jsonl only after Pass A is frozen, preferably
in a fresh conversation/context. Root IDs are opaque and evidence ordering is
randomized.

PRIVATE:
D_PRIVATE_B_ALIAS_CROSSWALK.csv must remain hidden from the Pass-B coder until
both passes are frozen.

Temporal rule:
Only items explicitly marked eligible_prechange=YES may support claims about
what explained original implementation choice. NO items may not. UNKNOWN items
require caution and cannot establish a chronology-safe driver.

T5:
No-public-explanation may only be assigned after all materially applicable
required evidence channels are complete. URLS_PRESENT_UNFETCHED is not
automatically T5-complete; relevance must first be assessed.
