# Frozen source notes for case 653

Derived from the frozen Stage C/D evidence export already present in the project.

- Case: 653
- Repository: `pingcap/ossinsight`
- Issue: #1879, title `Remove "https://github.com/" when pasted to search box`
- Issue created: 2025-12-06T13:46:02Z
- Pre-introduction human comment: `@pantheon-bot please take a look and complete this request, keep linus KISS principle`
- Root: `CROOT-00653-01`
- Base SHA: `32934c7e9169f214bf65e214e45104b9a1d678b8`
- Historical PR: #1881
- Historical root strategy: `pastedText.includes("github.com/")` in two repository-search entry points
- Target scanner rule: `js/incomplete-url-substring-sanitization`

This file is PRIVATE and must never be attached to a patch-generation chat.
