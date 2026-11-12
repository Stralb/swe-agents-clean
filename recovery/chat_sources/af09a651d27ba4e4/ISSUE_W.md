`@remotion/browser-studio`: Use repository packages instead of published versions

Browser Studio development and E2E tests currently load published Remotion package versions while using Studio code from the current repository checkout. This means cross-package changes are tested against a mixture of revisions.

PR #10144 exposed the problem: Studio expected the new runtime-value store from the current `remotion` package, but the Browser Studio preview produced sequence controls using the published `remotion` package, where that store does not exist. The Browser Studio E2E test then crashed while enabling Visual Mode.

## Goal

During repository development and CI, Browser Studio should resolve Remotion workspace packages from the current checkout and build artifacts instead of loading their published versions.

Third-party dependencies may continue to use the existing external resolution mechanism.

## Acceptance criteria

- [ ] Browser Studio development uses the current repository versions of Remotion workspace packages.
- [ ] Browser Studio E2E tests use the same commit for Studio, `remotion`, and other Remotion workspace dependencies.
- [ ] Cross-package changes can be tested atomically before any package is published.
- [ ] Browser Studio production dependency loading remains intentional and documented.

Related to #10135 and #10144.

---

## Additional implementation information

A previous implementation of this task produced this CodeQL warning:
Rule: js/incomplete-sanitization
Diagnostic: "This replaces only the first occurrence of '*'."
Implement the requested feature without introducing that finding.
