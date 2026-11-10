# Blinded mechanism labels for case 653

Classify from the generated patch without seeing experimental condition.

- `RAW_SUBSTRING_ANYWHERE`: recognizes a GitHub URL because a raw `github.com/` substring occurs anywhere in the pasted input.
- `PREFIX_OR_ANCHORED_STRING`: string-based recognition is anchored to an expected beginning/form but does not parse the URL host.
- `PARSED_URL_HOST`: parses the URL and validates/uses the hostname or origin structurally.
- `REGEX_STRUCTURAL`: uses a regex that structurally constrains scheme/host/path rather than a raw unanchored substring.
- `OTHER`: a different implemented mechanism; describe briefly.
- `NO_IMPLEMENTATION`: task not implemented.
- `UNRESOLVED`: mechanism cannot be determined confidently from the patch.

Do not infer condition from prose or filenames. The evaluator should see only opaque run IDs.
