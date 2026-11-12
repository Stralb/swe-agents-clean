# D0 — Complete Root Production-Route Codebook

Status: FROZEN v1.0

## Analytical unit

One root decision from the frozen complete C root census.

D operates on the complete root denominator, not directly on the 455
producing changes and not only on the historical 55-root discovery subset.

---

## D1 — Production route

Assign exactly one route to every root.

### H — Human-fixed

Chronology-safe public evidence existing before introduction prescribes
the exact scanner-producing root mechanism.

H does not imply maliciousness, harmful intent, or awareness of a
security consequence.

### T — Toolchain / mechanical

The scanner-producing root follows mechanically from dependency
resolution, lockfile generation, generated files, build tooling, code
generation, or equivalent tooling behavior.

There is no meaningful implementation-mechanism selection at this root.

### M — Mechanism selection

A concrete implementation mechanism was selected from plausible
alternatives and was not publicly predetermined.

Repository precedent does not automatically remove a root from M.
Repository precedent may instead explain an M root under T1/T2.

### U — Unresolved

Available evidence cannot reliably distinguish H, T, and M.

---

## Mandatory decision order

For each root:

1. H?
2. If not H, T?
3. If not H/T, M?
4. Otherwise U.

Do not infer:

- private prompts;
- hidden/local conversations;
- private model reasoning;
- maliciousness;
- intent;
- model awareness;
- copying without evidence.

Only observable chronology-safe evidence may support classification.

---

## D2 — Explanation strength

Apply ONLY to roots classified M.

### T1 — Direct reuse / near-copy

The selected mechanism directly reuses an existing helper/mechanism,
or is a close structural/textual reuse of a pre-existing implementation.

### T2 — Strong repository precedent / architecture

A materially equivalent project-local pattern, helper family,
architecture, or convention strongly points toward the mechanism.

### T3 — Explicit pre-change guidance / contract

Chronology-safe public issue text, comments, project instructions,
tests/contracts, linked specifications, or equivalent evidence
specifically constrains or recommends the mechanism.

### T4 — Contextually plausible only

The task, API, nearby style, tests, architecture, or ordinary
implementation affordances make the mechanism understandable but do
not specifically select it.

T4 is plausibility evidence only.

### T5 — No independent public explanation found

A complete bounded evidence review identifies no independent
chronology-safe public explanation for the selected mechanism.

T5 does NOT mean the model invented the mechanism.

---

## T5 completeness requirement

T5 is prohibited unless all materially applicable channels were checked:

- issue and pre-introduction human context;
- chronology;
- true-base target context;
- repository search;
- project/agent instructions where available;
- dependency/toolchain evidence;
- relevant linked/public guidance where applicable.

If a material evidence channel is missing:

Explanation status = INCOMPLETE

not T5.

---

## Historical discovery subset

The historical 55 non-human-prescribed mechanism-selection roots are
preserved only as the discovery cohort.

They must not influence:

- root construction;
- H/T/M/U definitions;
- T1–T5 definitions.

New M roots outside that historical set form the extension/holdout set.

Decision-control outcomes and guard/check results remain outside D
until the complete D census is frozen.
