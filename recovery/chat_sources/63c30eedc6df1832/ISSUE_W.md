Add Anchor link support for markdown TOC

* Lepton : 1.4.2 (1.4.2)
* OS : macOs Sierra 10.12.6 (16G29)

When creating an anchor link (like for a T.O.C.) with Github md style, that is, with `[Heading stuff](#heading-stuff)`, lepton will not auto scroll you to the anchor, like Github md viewer does.

---

## Additional implementation information

A previous implementation of this task produced this CodeQL warning:
Rule: js/incomplete-multi-character-sanitization
Diagnostic: "This string may still contain '<script', which may cause HTML element injection."
Implement the requested feature without introducing that finding.
