# C0 — Complete Root-Decision Census Codebook v1.0

## Research question
How many distinct underlying implementation decisions are represented by the 455 mapped scanner-producing changes?

## Unit
A **root decision** is the smallest underlying implementation strategy for one implementation subproblem such that replacing or removing that strategy would jointly remove or alter all producing changes assigned to that root.

Two producing changes may be merged into one root only when **all** of the following hold:
1. They belong to the same issue→PR workflow.
2. They address the same concrete implementation subproblem.
3. They are manifestations of the same underlying implementation strategy.
4. They are jointly replaceable: one conceptual implementation change would normally replace/remove both.

## Conservative default
When the evidence does not establish a shared root, keep producing changes separate. Never merge merely because they:
- occur in the same file or hunk;
- trigger the same scanner rule/family;
- belong to the same broad feature;
- are both dependency/lockfile changes;
- look security-related in similar ways.

## Dependency/toolchain rule
Merge dependency PCs only when the packet supports one common dependency/resolution operation (for example, one package/version introduction or one indivisible resolver/lockfile regeneration operation) that jointly accounts for them. Separate independently editable direct package/version operations or distinct dependency subproblems.

## Multi-file rule
A root may span files only when the files jointly implement the same subproblem and strategy. File boundaries do not determine root boundaries.

## Neutrality
C does not classify security severity, correctness, human prescription, repository provenance, toolchain causality, model intent, Direct/Side-effect, T1–T5, guard/check presence, or control status.

## Required output per root
- local root id
- producing-change aliases
- neutral root summary
- implementation subproblem
- shared strategy
- merge rationale (mandatory for multi-PC roots)
- evidence references
- boundary uncertainty flag
- confidence
