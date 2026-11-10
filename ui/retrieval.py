from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

LOOKBACK_START_DATE = '2025-01-01'
BASE_QUERY = f'repo:OWNER/REPO is:pr is:merged linked:issue draft:false merged:YYYY-MM-01..YYYY-MM+1-01 -maintenance-bots'
ISSUE_LINK_TERMS = ('same-repo linked issue',)


@dataclass(frozen=True)
class QueryStream:
    key: str
    name: str
    color: str
    terms: tuple[str, ...]


STREAMS: tuple[QueryStream, ...] = (
    QueryStream("issue_links", "Issue link", "#2563eb", ('same-repo linked issue',)),
    QueryStream("ai_agents", "AI agents", "#7c3aed", ('"Claude Code"', '"Co-Authored-By: Claude"', '"Codex"', '"OpenAI Codex"', '"GitHub Copilot"', '"Copilot"', '"Devin"', '"Cursor"', '"OpenHands"', '"Aider"', '"AI-generated"', '"agent-generated"')),
    QueryStream("dependency", "Dependency", "#ea580c", ('"requirements.txt"', '"pyproject.toml"', '"poetry.lock"', '"Pipfile.lock"', '"setup.py"', '"setup.cfg"', '"downgrade"', '"relax constraint"', '"version conflict"', '"dependency conflict"', '"pin version"', '"unpin"')),
    QueryStream("ci_cd_secrets", "CI/CD secrets", "#dc2626", ('".github/workflows"', '"pull_request_target"', '"permissions:"', '"GITHUB_TOKEN"', '"ACTIONS_ID_TOKEN_REQUEST_TOKEN"', '"id-token"', '"secrets."', '"workflow_dispatch"', '"actions/github-script"', '"printenv"', '"echo $"')),
    QueryStream("source_security", "Source / CodeQL indicators", "#0f766e", ('"shell=True"', '"os.system"', '"subprocess"', '"eval("', '"exec("', '"pickle.load"', '"yaml.load"', '"deserialize"', '"SQL injection"', '"path traversal"', '"SSRF"', '"verify=False"', '"disable validation"', '"bypass validation"', '"skip verification"')),
    QueryStream("issue_steering", "Issue steering", "#ca8a04", ('"steps to reproduce"', '"minimal repro"', '"stack trace"', '"traceback"', '"expected behavior"', '"actual behavior"', '"failing test"', '"regression test"')),
    QueryStream("security_regression", "Security regression", "#92400e", ('"CVE"', '"security fix"', '"security regression"', '"revert security"', '"disable check"', '"bypass"', '"too strict"', '"false positive"')),
)

STREAM_BY_KEY = {s.key: s for s in STREAMS}
TERM_TO_STREAM: dict[str, QueryStream] = {term: stream for stream in STREAMS for term in stream.terms}


SIGNAL_LABELS = {
    "vulnerability": "CodeQL",
    "secret": "Secret/CI",
    "dependency": "Dependency",
    "clean": "Clean",
    "none": "Pending",
}

LABELS = [
    "Unreviewed",
    "Auto-clean",
    "Benign",
    "Tool false positive",
    "Benign security fix",
    "Security regression candidate",
    "Suspicious issue-linked regression",
    "High-confidence suspicious",
    "Unclear",
]

STAGES = ["All", "Validated", "Scanning", "Scan blocked", "Clean", "Needs review", "Reviewed"]


def unquote_term(term: str) -> str:
    return term.strip().strip('"')


def is_issue_link_term(term: str) -> bool:
    return term in ISSUE_LINK_TERMS


def generated_queries(term: str) -> list[str]:
    """Return the structural query frame, not keyword bucket queries.

    The colored chips in the UI are post-inclusion indicators/features. They are
    intentionally not used as main retrieval filters.
    """
    return [BASE_QUERY]


def generated_query(term: str) -> str:
    return generated_queries(term)[0]


def term_color(term: str) -> str:
    stream = TERM_TO_STREAM.get(term)
    return stream.color if stream else "#64748b"


def term_stream_name(term: str) -> str:
    stream = TERM_TO_STREAM.get(term)
    return stream.name if stream else "Unknown"


def render_query_html(term: str | None = None) -> str:
    base = html.escape(BASE_QUERY)
    if not term:
        return f'<span class="query-base">{base}</span>'
    color = term_color(term)
    return f'<span class="query-base">{base}</span> <span class="query-term" style="color:{color}; border-color:{color}; background:{color}1a;">{html.escape(term)}</span>'


def render_term_chip(term: str, count: int | None = None) -> str:
    color = term_color(term)
    suffix = f" <span class='term-count'>{int(count)}</span>" if count is not None else ""
    return f'<span class="query-term" title="{html.escape(term_stream_name(term))}" style="color:{color}; border-color:{color}; background:{color}1a;">{html.escape(term)}{suffix}</span>'


def _text_blob(row: dict, keys: Sequence[str]) -> str:
    return "\n".join(str(row.get(k) or "") for k in keys).lower()


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _has_phrase(text: str, phrase: str) -> bool:
    clean = unquote_term(phrase).lower()
    if not clean:
        return False
    # Single-word security terms use boundaries to avoid widevine/devin-style false positives.
    if re.fullmatch(r"[a-zA-Z0-9_+-]+", clean):
        return re.search(rf"(?<![A-Za-z0-9_]){re.escape(clean)}(?![A-Za-z0-9_])", text, re.I) is not None
    return clean in text


def _file_blob(row: dict) -> str:
    return "\n".join(_split_csv(row.get("file_names"))).lower()


def _marker_blob(row: dict) -> str:
    return "\n".join(_split_csv(row.get("ai_marker_terms"))).lower()


def derive_query_terms(row: dict) -> list[str]:
    """Infer matched retrieval terms for already-collected cases.

    New targeted runs can store exact retrieval terms. For older DBs, this function
    derives display/filter terms from PR text, linked files, scanner context, and
    AI marker rows so the upgraded UI remains useful on existing data.
    """
    explicit = _split_csv(row.get("retrieval_terms"))
    if explicit:
        return [t for t in explicit if t in TERM_TO_STREAM]

    text = _text_blob(row, ("issue_title", "issue_body", "pr_title", "pr_body", "link_methods"))
    files = _file_blob(row)
    markers = _marker_blob(row)
    out: list[str] = []

    for stream in STREAMS:
        for term in stream.terms:
            raw = unquote_term(term).lower()
            matched = False
            if stream.key == "ai_agents":
                matched = _has_phrase(markers, term) or _has_phrase(text, term)
            elif stream.key == "dependency":
                matched = _has_phrase(files, term) or _has_phrase(text, term)
            elif stream.key == "ci_cd_secrets":
                matched = _has_phrase(files, term) or _has_phrase(text, term)
            elif stream.key == "source_security":
                matched = _has_phrase(files, term) or _has_phrase(text, term)
            else:
                matched = _has_phrase(text, term)
            if matched:
                out.append(term)
    return dedupe_terms(out)


def dedupe_terms(terms: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        if term not in seen:
            seen.add(term)
            out.append(term)
    return out


def ai_marker_label(row: dict) -> str:
    terms = []
    for item in _split_csv(row.get("ai_marker_terms")):
        clean = item.strip()
        if clean and clean not in terms:
            terms.append(clean)
    if terms:
        return ", ".join(terms[:3]) + (" +" if len(terms) > 3 else "")
    cohort = str(row.get("ai_cohort") or "")
    if cohort.startswith("AI-explicit"):
        return cohort.replace("AI-explicit-", "AI marker: ")
    return "No AI"


def signal_label(signal: str | None, status: str | None = None) -> str:
    """Return the visible downstream signal label.

    Empty downstream_signal means different things depending on case stage:
    - scanned_clean: scanners finished and found no promoted signal -> Clean
    - needs_review should normally have a signal, but keep Pending if absent
    - validated/scanner_running: scanners are not finished -> Pending
    """
    if not signal:
        if str(status or "").lower() == "scanned_clean":
            return "Clean"
        return "Pending"
    labels = []
    for part in str(signal).split(","):
        key = part.strip().lower()
        if key:
            labels.append(SIGNAL_LABELS.get(key, key.replace("_", " ").title()))
    return " + ".join(dedupe_terms(labels)) if labels else "Pending"


def derive_stage(row: dict) -> str:
    status = str(row.get("status") or "").lower()
    label = str(row.get("final_label") or "").strip()
    scanner_statuses = (str(row.get("scanner_statuses") or "") + "," + str(row.get("scanner_job_statuses") or "")).lower()
    if status == "reviewed" or (label and label not in {"Unclear", "Unreviewed", "Auto-clean"}):
        return "Reviewed"
    if status == "needs_review":
        return "Needs review"
    if status == "scanned_clean":
        return "Clean"
    if status in {"scanner_blocked", "scan_blocked", "error"}:
        return "Scan blocked"
    if "running" in scanner_statuses or "pending" in scanner_statuses or "partial" in scanner_statuses:
        return "Scanning"
    return "Validated"


def display_label(row: dict) -> str:
    stage = derive_stage(row)
    label = row.get("final_label") or "Unreviewed"
    if stage == "Clean":
        return "Auto-clean"
    if stage != "Reviewed":
        return "Unreviewed"
    return str(label)


def row_signal_label(row: dict) -> str:
    return signal_label(row.get("downstream_signal"), row.get("status"))


def priority_score(row: dict) -> int:
    """UI review-order value only; never used for candidate inclusion."""
    terms = derive_query_terms(row)
    streams = {TERM_TO_STREAM[t].key for t in terms if t in TERM_TO_STREAM}
    signal = row_signal_label(row)
    score = 0
    if derive_stage(row) == "Needs review":
        score += 5
    if "+" in signal:
        score += 4
    if ai_marker_label(row) != "No AI":
        score += 3
    if len(streams) > 1:
        score += 3
    if "issue_steering" in streams:
        score += 2
    if "security_regression" in streams:
        score += 3
    if "Secret/CI" in signal:
        score += 2
    if "Dependency" in signal:
        score += 2
    if "CodeQL" in signal:
        score += 2
    text = _text_blob(row, ("issue_title", "issue_body", "pr_title", "pr_body"))
    if any(x in text for x in ("steps to reproduce", "traceback", "stack trace", "minimal repro", "failing test")):
        score += 1
    return score


def filter_by_terms(row_terms: Sequence[str], selected_terms: Sequence[str], mode: str = "any") -> bool:
    if not selected_terms:
        return True
    row_set = set(row_terms)
    selected = set(selected_terms)
    if mode == "all":
        return selected.issubset(row_set)
    return bool(row_set & selected)


def methodology_snapshot() -> dict:
    return {
        "base_query": BASE_QUERY,
        "lookback_start_date": LOOKBACK_START_DATE,
        "candidate_frame": "repo universe -> repo/month merged linked PR search -> same-repo issue -> downstream worker routing",
        "streams": [
            {"key": s.key, "name": s.name, "color": s.color, "terms": list(s.terms), "generated_queries": {t: generated_queries(t) for t in s.terms}}
            for s in STREAMS
        ],
        "note": "Colored terms are post-inclusion indicators/features only. The main retrieval query is structural and does not use issue/content keyword buckets.",
    }
