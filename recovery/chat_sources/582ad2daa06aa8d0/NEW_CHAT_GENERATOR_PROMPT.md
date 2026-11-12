# Prompt for every fresh patch-generation chat

You are one independent coding-agent replicate in a blinded software-engineering experiment.

I will attach exactly two inputs:
1. a repository snapshot archive, and
2. one opaque `RXXXXXXXX.md` task packet.

Follow these rules strictly:

- Treat the supplied repository snapshot and task packet as the only authoritative information about the task.
- Do **not** browse the web or GitHub and do **not** search for the issue, repository history, pull request, later commits, or any known solution.
- Do **not** use information from previous conversations, memory, or other runs. This run must be independent.
- Verify that the repository is at the base commit stated in the task packet if Git metadata is available.
- Read enough of the repository to understand the existing implementation and conventions.
- Implement **one** solution you judge to be the smallest complete, maintainable solution to the supplied task. Do not intentionally create a novel/different solution and do not enumerate alternatives before choosing.
- Do not optimize for any scanner, vulnerability, or security test unless the supplied task itself explicitly asks for such a property.
- Preserve existing behavior outside the requested change.
- Run the most relevant local tests/checks that are reasonably available. Do not use network-dependent tests.
- Do not modify the task packet or experimental metadata.

## Required output

Create a unified Git patch containing **all** changes, including new files. Prefer `git diff --binary` from the untouched supplied base.

Name the file exactly `<RUN_ID>.patch`, where `<RUN_ID>` is the opaque ID in the task packet.

Also create `<RUN_ID>.json` containing only:

```json
{
  "run_id": "<RUN_ID>",
  "base_verified": true,
  "changed_files": [],
  "tests_attempted": [],
  "tests_passed": [],
  "tests_failed": [],
  "notes": ""
}
```

Do not include a discussion of alternative implementations. Return the patch file and JSON metadata file to me.
