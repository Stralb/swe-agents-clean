Add Anchor link support for markdown TOC

* Lepton : 1.4.2 (1.4.2)
* OS : macOs Sierra 10.12.6 (16G29)

When creating an anchor link (like for a T.O.C.) with Github md style, that is, with `[Heading stuff](#heading-stuff)`, lepton will not auto scroll you to the anchor, like Github md viewer does.

---

## Additional implementation information

Markdown headings and anchor navigation must preserve safe rendering. User-controlled heading and link text must not be able to introduce HTML elements or active script, including when malicious sequences recur or overlap during sanitization.
