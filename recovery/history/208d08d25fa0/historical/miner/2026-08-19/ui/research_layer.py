#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from ui.parquet_store import ParquetStore, get_parquet_store

_CVE_RE = re.compile(r"CVE-\d{4}-\d+", re.IGNORECASE)
_GHSA_RE = re.compile(r"GHSA-[0-9A-Za-z-]+", re.IGNORECASE)

_SEVERITY_ORDER = {
    "critical": 7,
    "high": 6,
    "error": 5,
    "medium": 4,
    "warning": 3,
    "low": 2,
    "info": 1,
    "unknown": 0,
    "": 0,
}

_ATTRIBUTION_ORDER = {
    "strong": 3,
    "moderate": 2,
    "weak": 1,
    "none": 0,
}

_DEPENDENCY_MANIFEST_NAMES = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "pipfile",
    "pipfile.lock",
    "setup.py",
    "setup.cfg",
    "cargo.toml",
    "go.mod",
    "composer.json",
}

_LOCKFILE_NAMES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "pnpm-lock.yml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "cargo.lock",
    "poetry.lock",
    "pipfile.lock",
    "composer.lock",
}

_UPSTREAM_CUE_GROUPS: dict[str, tuple[str, ...]] = {
    "dependency/version": (
        "dependency", "dependencies", "package", "version", "lockfile",
        "package-lock", "pnpm", "npm", "yarn", "upgrade", "downgrade", "pin",
    ),
    "security": (
        "security", "vulnerability", "vulnerable", "cve", "authentication",
        "authorization", "validation", "sanitize", "sanitise", "injection",
        "secret", "credential", "token", "password", "unsafe",
    ),
    "CI/workflow": (
        "github actions", "workflow", "ci/cd", "pipeline", "deployment", "deploy",
    ),
}

_REVIEW_CUE_PHRASES = (
    "disable", "bypass", "skip check", "skip validation", "ignore validation",
    "remove validation", "turn off", "hardcode", "downgrade", "pin to",
    "older version", "allow all", "no validation", "no verification",
)

_FRAMING_CUES = (
    "bug", "fix", "compatibility", "feature", "security", "performance",
    "refactor", "test", "reliability", "maintenance", "dependency", "update",
)


@dataclass(frozen=True)
class ResearchStats:
    total_cases: int
    positive_cases: int
    introduced_findings: int
    unique_events: int


def _clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def _text(value: Any) -> str:
    value = _clean(value)
    return "" if value is None else str(value)


def _int(value: Any) -> int | None:
    value = _clean(value)
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _json(value: Any) -> dict[str, Any]:
    value = _clean(value)
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _norm_path(value: Any) -> str:
    path = _text(value).replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/")


def _contains_entity(text: str, entity: Any) -> bool:
    candidate = _text(entity).strip().lower()
    if len(candidate) < 3:
        return False
    source = text.lower()
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(candidate)}(?![A-Za-z0-9_])"
    return re.search(pattern, source) is not None


def _matched_phrases(text: str, phrases: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in phrases if phrase in lowered]


def _hours_between(start: Any, end: Any) -> float | None:
    if not _text(start) or not _text(end):
        return None
    try:
        start_ts = pd.to_datetime(start, utc=True)
        end_ts = pd.to_datetime(end, utc=True)
        return round((end_ts - start_ts).total_seconds() / 3600.0, 1)
    except Exception:
        return None


def _path_context(path: Any, category: Any = None) -> str:
    normalized = _norm_path(path)
    lower = normalized.lower()
    category_text = _text(category).lower()
    if not normalized:
        return "unknown"
    name = lower.rsplit("/", 1)[-1]

    test_tokens = (
        "/tests/",
        "/test/",
        "__tests__",
        "/fixtures/",
        "/fixture/",
        "/mocks/",
        "/mock/",
        ".test.",
        ".spec.",
        ".snapshot",
    )
    if any(token in f"/{lower}" for token in test_tokens) or category_text == "test":
        return "test / fixture / mock"

    if name in _LOCKFILE_NAMES or name.endswith(".lock"):
        return "dependency lockfile"

    if name in _DEPENDENCY_MANIFEST_NAMES:
        return "dependency manifest"

    if lower.startswith(".github/workflows/") or "/.github/workflows/" in f"/{lower}":
        return "CI / workflow"

    if any(token in f"/{lower}/" for token in ("/vendor/", "/generated/", "/dist/", "/build/", "/minified/")):
        return "generated / vendor"

    if category_text in {"dependency", "dependency_config"}:
        return "dependency metadata"
    if category_text in {"script", "source"}:
        return "production source"
    if category_text in {"ci", "workflow"}:
        return "CI / workflow"

    return "production source"


def _codeflow_paths(raw: dict[str, Any]) -> set[str]:
    paths: set[str] = set()

    def add_location(location: Any) -> None:
        if not isinstance(location, dict):
            return
        physical = location.get("physicalLocation") or {}
        artifact = physical.get("artifactLocation") or {}
        uri = _norm_path(artifact.get("uri"))
        if uri:
            paths.add(uri)

    for location in raw.get("locations") or []:
        add_location(location)

    for flow in raw.get("codeFlows") or []:
        if not isinstance(flow, dict):
            continue
        for thread in flow.get("threadFlows") or []:
            if not isinstance(thread, dict):
                continue
            for item in thread.get("locations") or []:
                if not isinstance(item, dict):
                    continue
                add_location(item.get("location"))

    for item in raw.get("relatedLocations") or []:
        add_location(item)

    return paths


def _dependency_values(
    finding: dict[str, Any],
    evidence: dict[str, Any],
    raw: dict[str, Any],
) -> dict[str, str]:
    package = _text(evidence.get("package") or raw.get("PkgName"))
    version = _text(evidence.get("version") or raw.get("InstalledVersion"))
    old_version = _text(evidence.get("old_version") or raw.get("old_version"))
    new_version = _text(evidence.get("new_version") or raw.get("new_version"))
    fixed_version = _text(evidence.get("fixed_version") or raw.get("FixedVersion"))
    change_type = _text(evidence.get("change_type") or raw.get("change_type"))

    ids: list[str] = []
    for candidate in (
        finding.get("rule_id"),
        evidence.get("vulnerability"),
        evidence.get("vuln_id"),
        raw.get("VulnerabilityID"),
        raw.get("id"),
        raw.get("PrimaryURL"),
    ):
        value = _text(candidate)
        if value:
            ids.append(value)

    for candidate in raw.get("aliases") or []:
        value = _text(candidate)
        if value:
            ids.append(value)

    joined = " ".join(ids)
    cves = sorted({match.upper() for match in _CVE_RE.findall(joined)})
    ghsas = sorted({match.upper() for match in _GHSA_RE.findall(joined)})
    canonical_vuln = cves[0] if cves else (ghsas[0] if ghsas else _text(finding.get("rule_id")))

    return {
        "package": package,
        "version": version,
        "old_version": old_version,
        "new_version": new_version,
        "fixed_version": fixed_version,
        "change_type": change_type,
        "canonical_vuln_id": canonical_vuln,
    }


def _effective_severity(
    finding: dict[str, Any],
    raw: dict[str, Any],
) -> str:
    severity = _text(finding.get("severity")).strip().lower()
    if severity:
        return severity

    database_specific = raw.get("database_specific") or {}
    if isinstance(database_specific, dict):
        severity = _text(database_specific.get("severity")).strip().lower()
        if severity:
            return severity

    severity = _text(raw.get("Severity")).strip().lower()
    return severity or "unknown"


def _event_family(
    scanner: str,
    finding_type: str,
    change_type: str,
) -> str:
    scanner = scanner.lower()
    finding_type = finding_type.lower()
    change_type = change_type.lower()

    if scanner == "gitleaks" or finding_type == "secret":
        return "Secret exposure"

    if scanner == "dependency-diff":
        if "downgrade" in change_type:
            return "Dependency downgrade"
        return "Dependency change"

    if finding_type == "dependency" or scanner in {"osv-scanner", "trivy-scanner"}:
        return "Dependency vulnerability"

    return "Code vulnerability"


def _attribution(
    scanner: str,
    family: str,
    primary_changed: bool,
    codeflow_changed_paths: set[str],
    evidence: dict[str, Any],
    pr_dependency_paths: set[str],
) -> tuple[str, str]:
    scanner = scanner.lower()

    if primary_changed:
        return "strong", "The scanner's primary finding file was changed by the PR."

    if scanner == "codeql" and codeflow_changed_paths:
        return (
            "strong",
            "The reported sink is not the changed file, but CodeQL's flow passes through PR-changed code.",
        )

    if family.startswith("Dependency"):
        evidence_paths = {
            _norm_path(path)
            for path in (evidence.get("changed_dependency_paths") or [])
            if _norm_path(path)
        }
        if bool(evidence.get("pr_attributable")) or evidence_paths:
            return "strong", "Dependency scanner metadata explicitly attributes the target to the PR."
        if pr_dependency_paths:
            return (
                "moderate",
                "The finding target was not directly changed, but the PR changed dependency metadata.",
            )
        return "weak", "No changed dependency target could be linked to this finding."

    if scanner in {"semgrep", "gitleaks"}:
        return "weak", "The scanner finding could not be mapped directly to a changed file."

    return "weak", "No direct PR-change attribution was found."


def _severity_max(values: list[str]) -> str:
    cleaned = [(_text(value).lower() or "unknown") for value in values]
    if not cleaned:
        return "unknown"
    return max(cleaned, key=lambda value: _SEVERITY_ORDER.get(value, 0))


def _attribution_max(values: list[str]) -> str:
    cleaned = [(_text(value).lower() or "none") for value in values]
    if not cleaned:
        return "none"
    return max(cleaned, key=lambda value: _ATTRIBUTION_ORDER.get(value, 0))


def _join_unique(values: list[Any], limit: int | None = None) -> str:
    output: list[str] = []
    for value in values:
        text = _text(value).strip()
        if text and text not in output:
            output.append(text)
    if limit is not None and len(output) > limit:
        return ", ".join(output[:limit]) + f" +{len(output) - limit} more"
    return ", ".join(output)


def _event_key(row: dict[str, Any]) -> str:
    family = row["event_family"]
    if family == "Dependency vulnerability":
        return "|".join(
            [
                str(row["case_id"]),
                family,
                _text(row.get("package")).lower(),
                _text(row.get("version")),
                _text(row.get("canonical_vuln_id")).upper(),
            ]
        )

    if family in {"Dependency downgrade", "Dependency change"}:
        return "|".join(
            [
                str(row["case_id"]),
                family,
                _text(row.get("package")).lower(),
                _text(row.get("old_version")),
                _text(row.get("new_version")),
                _norm_path(row.get("file_path")),
            ]
        )

    return "|".join(
        [
            str(row["case_id"]),
            family,
            _text(row.get("rule_id")),
            _norm_path(row.get("file_path")),
            str(_int(row.get("line")) or 0),
            _text(row.get("description_preview"))[:160],
        ]
    )


def _priority_reason(events: pd.DataFrame) -> tuple[str, str]:
    if events.empty:
        return "Low", "No canonical introduced events were available."

    contexts = set(events["primary_context"].dropna().astype(str))
    families = set(events["event_family"].dropna().astype(str))
    strong = events[events["attribution_strength"] == "strong"]

    if contexts and contexts.issubset({"test / fixture / mock", "generated / vendor"}):
        return "Low", "All introduced evidence is in test/fixture/mock or generated/vendor context."

    if (
        families.issubset({"Dependency vulnerability", "Dependency change"})
        and len(events) >= 20
        and contexts.issubset({"dependency lockfile", "dependency metadata", "dependency manifest"})
    ):
        return "Low", "Bulk dependency/lockfile signal; prioritize attribution quality over raw finding count."

    production_strong = strong[
        strong["primary_context"].isin({"production source", "CI / workflow"})
    ]
    if not production_strong.empty:
        return "High", "Strong PR attribution in production source or CI/workflow code."

    if not strong[strong["event_family"] == "Dependency downgrade"].empty:
        return "High", "Strongly attributed dependency downgrade."

    if not strong.empty and len(events) <= 10:
        return "High", "Small, focused set of strongly attributed introduced events."

    if not strong.empty:
        return "Medium", "At least one event is strongly attributable to the PR."

    return "Low", "Evidence is weakly or indirectly attributable to the PR."


def _archetype(events: pd.DataFrame) -> str:
    families = set(events["event_family"].dropna().astype(str))
    contexts = set(events["primary_context"].dropna().astype(str))
    scanners = set(
        scanner
        for value in events["scanners"].dropna().astype(str)
        for scanner in value.split(", ")
    )

    if families == {"Code vulnerability"}:
        if scanners == {"semgrep"}:
            return "Semgrep code finding"
        return "Code vulnerability"
    if families == {"Secret exposure"}:
        return "Secret exposure"
    if families.issubset({"Dependency vulnerability", "Dependency change", "Dependency downgrade"}):
        if "dependency lockfile" in contexts:
            return "Dependency / lockfile"
        return "Dependency / manifest"
    return "Mixed security signals"


class ResearchLayer:
    """Small derived research layer built from the HF-cached Parquet snapshot.

    The source snapshot remains immutable. This layer canonicalises duplicate scanner
    reports, derives PR-attribution evidence, and produces a 138-case review queue.
    """

    def __init__(self, store: ParquetStore) -> None:
        self.store = store
        self.cases = store.query_df(
            """
            SELECT *
            FROM pq_cases
            WHERE introduced_finding_count > 0
            ORDER BY case_id
            """
        )
        self.findings = store.query_df(
            """
            SELECT
                f.*,
                d.description,
                d.evidence,
                d.raw_json
            FROM pq_findings f
            LEFT JOIN pq_finding_detail d USING (finding_id)
            WHERE f.introduced = TRUE
            ORDER BY f.case_id, f.finding_id
            """
        )
        self.files = store.query_df(
            """
            SELECT *
            FROM pq_files
            ORDER BY pr_id, file_id
            """
        )
        self.case_details = store.query_df(
            """
            SELECT c.case_id, d.issue_body, d.pr_body, d.review_notes
            FROM pq_cases c
            LEFT JOIN pq_case_detail d USING (case_id)
            WHERE c.introduced_finding_count > 0
            ORDER BY c.case_id
            """
        )

        self.attribution = self._build_attribution()
        self.events = self._build_events()
        self.upstream = self._build_upstream()
        self.case_summary = self._build_case_summary()

    @property
    def stats(self) -> ResearchStats:
        total_row = self.store.one("SELECT COUNT(*) AS n FROM pq_cases") or {"n": 0}
        return ResearchStats(
            total_cases=int(total_row.get("n") or 0),
            positive_cases=len(self.cases),
            introduced_findings=len(self.attribution),
            unique_events=len(self.events),
        )

    def case(self, case_id: int) -> dict[str, Any] | None:
        rows = self.cases[self.cases["case_id"] == int(case_id)]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def case_events(self, case_id: int) -> pd.DataFrame:
        rows = self.events[self.events["case_id"] == int(case_id)].copy()
        if rows.empty:
            return rows
        rows["_severity_rank"] = rows["severity"].map(
            lambda value: _SEVERITY_ORDER.get(_text(value).lower(), 0)
        )
        rows["_attr_rank"] = rows["attribution_strength"].map(
            lambda value: _ATTRIBUTION_ORDER.get(_text(value).lower(), 0)
        )
        return rows.sort_values(
            ["_attr_rank", "_severity_rank", "raw_finding_count"],
            ascending=[False, False, False],
        ).drop(columns=["_severity_rank", "_attr_rank"])

    def case_attribution(self, case_id: int) -> pd.DataFrame:
        return self.attribution[self.attribution["case_id"] == int(case_id)].copy()

    def case_upstream(self, case_id: int) -> dict[str, Any]:
        rows = self.upstream[self.upstream["case_id"] == int(case_id)]
        if rows.empty:
            return {}
        return rows.iloc[0].to_dict()

    def upstream_export(self) -> pd.DataFrame:
        columns = [
            "case_id", "repo_full_name", "issue_number", "issue_title", "issue_url",
            "pr_number", "pr_url", "issue_author", "pr_author", "same_issue_pr_author",
            "issue_change_alignment", "upstream_summary",
            "matched_packages", "matched_versions", "matched_files",
            "matched_vulnerability_ids", "review_cues", "technical_cues",
            "framing_cues", "issue_word_count", "issue_comments_count",
            "issue_to_pr_hours", "pr_additions", "pr_deletions",
            "changed_files_count", "commits_count", "pr_merged",
            "archetype", "unique_event_count", "raw_finding_count",
            "strongest_severity", "strongest_family", "strongest_attribution",
            "review_priority", "why_flagged",
        ]
        available = [column for column in columns if column in self.case_summary.columns]
        frame = self.case_summary[available].copy()
        if "issue_body" in self.upstream.columns:
            frame = frame.merge(
                self.upstream[["case_id", "issue_body"]],
                how="left",
                on="case_id",
            )
        return frame

    def _build_attribution(self) -> pd.DataFrame:
        changed_paths_by_pr: dict[int, set[str]] = {}
        dependency_paths_by_pr: dict[int, set[str]] = {}
        file_meta: dict[tuple[int, str], dict[str, Any]] = {}

        for record in self.files.to_dict("records"):
            pr_id = _int(record.get("pr_id"))
            path = _norm_path(record.get("filename"))
            if pr_id is None or not path:
                continue
            changed_paths_by_pr.setdefault(pr_id, set()).add(path)
            context = _path_context(path, record.get("category"))
            if context.startswith("dependency"):
                dependency_paths_by_pr.setdefault(pr_id, set()).add(path)
            file_meta[(pr_id, path)] = record

        rows: list[dict[str, Any]] = []
        for finding in self.findings.to_dict("records"):
            case_id = int(finding["case_id"])
            pr_id = _int(finding.get("pr_id")) or 0
            scanner = _text(finding.get("scanner"))
            finding_type = _text(finding.get("finding_type"))
            file_path = _norm_path(finding.get("file_path"))
            evidence = _json(finding.get("evidence"))
            raw = _json(finding.get("raw_json"))
            dependency = _dependency_values(finding, evidence, raw)
            family = _event_family(scanner, finding_type, dependency["change_type"])

            changed_paths = changed_paths_by_pr.get(pr_id, set())
            primary_changed = bool(file_path and file_path in changed_paths)
            codeflow_paths = _codeflow_paths(raw) if scanner.lower() == "codeql" else set()
            codeflow_changed = codeflow_paths.intersection(changed_paths)
            meta = file_meta.get((pr_id, file_path), {})
            context = _path_context(file_path, meta.get("category"))

            strength, reason = _attribution(
                scanner=scanner,
                family=family,
                primary_changed=primary_changed,
                codeflow_changed_paths=codeflow_changed,
                evidence=evidence,
                pr_dependency_paths=dependency_paths_by_pr.get(pr_id, set()),
            )

            severity = _effective_severity(finding, raw)
            row = dict(finding)
            row.update(dependency)
            row.update(
                {
                    "case_id": case_id,
                    "pr_id": pr_id,
                    "file_path": file_path,
                    "event_family": family,
                    "effective_severity": severity,
                    "primary_file_changed": primary_changed,
                    "changed_file_status": _text(meta.get("status")),
                    "changed_file_category": _text(meta.get("category")),
                    "primary_context": context,
                    "codeflow_paths": ", ".join(sorted(codeflow_paths)),
                    "codeflow_changed_paths": ", ".join(sorted(codeflow_changed)),
                    "codeflow_hits_changed_file": bool(codeflow_changed),
                    "attribution_strength": strength,
                    "attribution_reason": reason,
                    "event_key": "",
                }
            )
            row["event_key"] = _event_key(row)
            rows.append(row)

        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        return frame.sort_values(["case_id", "finding_id"]).reset_index(drop=True)

    def _build_events(self) -> pd.DataFrame:
        if self.attribution.empty:
            return pd.DataFrame()

        events: list[dict[str, Any]] = []
        for event_key, group in self.attribution.groupby("event_key", sort=False):
            records = group.to_dict("records")
            first = records[0]
            severity = _severity_max([record.get("effective_severity") for record in records])
            attribution_strength = _attribution_max(
                [record.get("attribution_strength") for record in records]
            )
            canonical_id = _text(first.get("canonical_vuln_id"))
            event_id = hashlib.sha1(event_key.encode("utf-8")).hexdigest()[:16]

            strongest = max(
                records,
                key=lambda record: (
                    _ATTRIBUTION_ORDER.get(_text(record.get("attribution_strength")).lower(), 0),
                    _SEVERITY_ORDER.get(_text(record.get("effective_severity")).lower(), 0),
                ),
            )

            events.append(
                {
                    "event_id": event_id,
                    "case_id": int(first["case_id"]),
                    "pr_id": int(first.get("pr_id") or 0),
                    "event_family": first["event_family"],
                    "canonical_vuln_id": canonical_id,
                    "package": _text(first.get("package")),
                    "version": _text(first.get("version")),
                    "old_version": _text(first.get("old_version")),
                    "new_version": _text(first.get("new_version")),
                    "fixed_version": _text(first.get("fixed_version")),
                    "severity": severity,
                    "rule_id": _join_unique([record.get("rule_id") for record in records], limit=3),
                    "title": _text(strongest.get("description_preview") or strongest.get("description")),
                    "primary_files": _join_unique([record.get("file_path") for record in records], limit=5),
                    "primary_context": _text(strongest.get("primary_context")),
                    "raw_finding_count": len(records),
                    "raw_finding_ids": ",".join(str(int(record["finding_id"])) for record in records),
                    "scanners": _join_unique([record.get("scanner") for record in records]),
                    "scanner_count": len({_text(record.get("scanner")) for record in records if _text(record.get("scanner"))}),
                    "duplicate_scanner_reports": max(0, len(records) - 1),
                    "attribution_strength": attribution_strength,
                    "attribution_reason": _join_unique([record.get("attribution_reason") for record in records], limit=3),
                    "primary_file_changed": any(bool(record.get("primary_file_changed")) for record in records),
                    "codeflow_hits_changed_file": any(bool(record.get("codeflow_hits_changed_file")) for record in records),
                    "codeflow_changed_paths": _join_unique([record.get("codeflow_changed_paths") for record in records], limit=5),
                }
            )

        frame = pd.DataFrame(events)
        return frame.sort_values(["case_id", "event_family", "event_id"]).reset_index(drop=True)

    def _build_upstream(self) -> pd.DataFrame:
        detail_map = {
            int(record["case_id"]): record
            for record in self.case_details.to_dict("records")
        }
        files_by_pr: dict[int, list[str]] = {}
        for record in self.files.to_dict("records"):
            pr_id = _int(record.get("pr_id"))
            path = _norm_path(record.get("filename"))
            if pr_id is not None and path:
                files_by_pr.setdefault(pr_id, []).append(path)

        rows: list[dict[str, Any]] = []
        for case in self.cases.to_dict("records"):
            case_id = int(case["case_id"])
            pr_id = _int(case.get("pr_id")) or 0
            detail = detail_map.get(case_id, {})
            issue_body = _text(detail.get("issue_body"))
            issue_title = _text(case.get("issue_title"))
            issue_text = f"{issue_title}\n{issue_body}".strip()
            events = self.events[self.events["case_id"] == case_id]

            packages = sorted({
                _text(value).strip()
                for value in events.get("package", pd.Series(dtype=str)).tolist()
                if _text(value).strip()
            })
            versions = sorted({
                _text(value).strip()
                for column in ("version", "old_version", "new_version")
                if column in events.columns
                for value in events[column].tolist()
                if _text(value).strip()
            })
            vuln_ids = sorted({
                _text(value).strip()
                for value in events.get("canonical_vuln_id", pd.Series(dtype=str)).tolist()
                if _text(value).strip()
            })

            downstream_paths: set[str] = set()
            for event in events.to_dict("records"):
                for field in ("primary_files", "codeflow_changed_paths"):
                    for path in _text(event.get(field)).split(","):
                        normalized = _norm_path(path)
                        if normalized and not normalized.startswith("+"):
                            downstream_paths.add(normalized)

            changed_paths = files_by_pr.get(pr_id, [])
            mentioned_packages = [value for value in packages if _contains_entity(issue_text, value)]
            mentioned_versions = [value for value in versions if _contains_entity(issue_text, value)]
            mentioned_vulns = [value for value in vuln_ids if _contains_entity(issue_text, value)]

            mentioned_files: list[str] = []
            for path in sorted(set(changed_paths).union(downstream_paths)):
                basename = path.rsplit("/", 1)[-1]
                if _contains_entity(issue_text, path) or (len(basename) >= 5 and _contains_entity(issue_text, basename)):
                    mentioned_files.append(path)

            technical_cues: list[str] = []
            for label, terms in _UPSTREAM_CUE_GROUPS.items():
                matches = _matched_phrases(issue_text, terms)
                if matches:
                    technical_cues.append(f"{label}: {', '.join(matches[:5])}")

            review_cues = _matched_phrases(issue_text, _REVIEW_CUE_PHRASES)
            framing = _matched_phrases(issue_text, _FRAMING_CUES)

            families = set(events["event_family"].dropna().astype(str))
            family_alignment = False
            lower = issue_text.lower()
            if any(family.startswith("Dependency") for family in families):
                family_alignment = any(term in lower for term in _UPSTREAM_CUE_GROUPS["dependency/version"])
            elif "Secret exposure" in families:
                family_alignment = any(term in lower for term in ("secret", "credential", "token", "password", "key"))
            elif "Code vulnerability" in families:
                family_alignment = any(term in lower for term in _UPSTREAM_CUE_GROUPS["security"])

            score = 0
            if mentioned_vulns:
                score += 4
            if mentioned_packages:
                score += 3
            if mentioned_versions:
                score += 2
            if mentioned_files:
                score += 2
            if family_alignment:
                score += 1

            if score >= 4:
                alignment = "High"
            elif score >= 2:
                alignment = "Medium"
            elif score >= 1:
                alignment = "Low"
            else:
                alignment = "None"

            reasons: list[str] = []
            if mentioned_packages:
                reasons.append("issue names affected package(s): " + ", ".join(mentioned_packages[:3]))
            if mentioned_versions:
                reasons.append("issue names affected version(s): " + ", ".join(mentioned_versions[:3]))
            if mentioned_files:
                reasons.append("issue names changed/finding file(s): " + ", ".join(mentioned_files[:3]))
            if mentioned_vulns:
                reasons.append("issue names vulnerability ID(s): " + ", ".join(mentioned_vulns[:3]))
            if family_alignment and not reasons:
                reasons.append("issue language matches the downstream security-change family")
            if not reasons:
                reasons.append("no exact downstream package, version, vulnerability ID, or changed file is named in the issue")

            issue_author = _text(case.get("issue_author"))
            pr_author = _text(case.get("pr_author"))
            same_author = bool(issue_author and pr_author and issue_author.lower() == pr_author.lower())
            issue_to_pr_hours = _hours_between(case.get("issue_created_at"), case.get("pr_created_at"))

            rows.append(
                {
                    "case_id": case_id,
                    "issue_body": issue_body,
                    "pr_body": _text(detail.get("pr_body")),
                    "issue_change_alignment": alignment,
                    "issue_change_alignment_score": score,
                    "upstream_summary": "; ".join(reasons) + ".",
                    "matched_packages": ", ".join(mentioned_packages),
                    "matched_versions": ", ".join(mentioned_versions),
                    "matched_files": ", ".join(mentioned_files[:8]),
                    "matched_vulnerability_ids": ", ".join(mentioned_vulns),
                    "review_cues": ", ".join(review_cues),
                    "technical_cues": " | ".join(technical_cues),
                    "framing_cues": ", ".join(framing),
                    "issue_word_count": _int(case.get("issue_word_count")) or len(issue_body.split()),
                    "issue_comments_count": _int(case.get("issue_comments_count")) or 0,
                    "issue_author": issue_author,
                    "pr_author": pr_author,
                    "same_issue_pr_author": same_author,
                    "issue_to_pr_hours": issue_to_pr_hours,
                    "issue_state": _text(case.get("issue_state")),
                    "pr_state": _text(case.get("pr_state")),
                    "pr_merged": bool(case.get("pr_merged")),
                }
            )

        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        return frame.sort_values("case_id").reset_index(drop=True)

    def _build_case_summary(self) -> pd.DataFrame:
        case_records: list[dict[str, Any]] = []
        case_map = {
            int(record["case_id"]): record
            for record in self.cases.to_dict("records")
        }

        for case_id, case in case_map.items():
            events = self.events[self.events["case_id"] == case_id].copy()
            raw = self.attribution[self.attribution["case_id"] == case_id]
            if events.empty:
                continue

            priority, priority_reason = _priority_reason(events)
            archetype = _archetype(events)
            strongest = events.copy()
            strongest["_severity_rank"] = strongest["severity"].map(
                lambda value: _SEVERITY_ORDER.get(_text(value).lower(), 0)
            )
            strongest["_attr_rank"] = strongest["attribution_strength"].map(
                lambda value: _ATTRIBUTION_ORDER.get(_text(value).lower(), 0)
            )
            strongest = strongest.sort_values(
                ["_attr_rank", "_severity_rank", "raw_finding_count"],
                ascending=[False, False, False],
            ).iloc[0].to_dict()

            strong_count = int((events["attribution_strength"] == "strong").sum())
            test_count = int((events["primary_context"] == "test / fixture / mock").sum())
            lockfile_count = int((events["primary_context"] == "dependency lockfile").sum())
            raw_count = len(raw)
            unique_count = len(events)

            family_counts = (
                events.groupby("event_family").size().sort_values(ascending=False).to_dict()
            )
            family_summary = ", ".join(
                f"{family}: {count}"
                for family, count in family_counts.items()
            )

            why = (
                f"{unique_count} unique introduced security event{'s' if unique_count != 1 else ''} "
                f"from {raw_count} raw scanner finding{'s' if raw_count != 1 else ''}. "
                f"Strongest signal: {strongest.get('event_family')}"
            )
            if strongest.get("canonical_vuln_id"):
                why += f" ({strongest.get('canonical_vuln_id')})"
            elif strongest.get("rule_id"):
                why += f" ({strongest.get('rule_id')})"
            why += f". Attribution: {strongest.get('attribution_strength')}."

            upstream_rows = self.upstream[self.upstream["case_id"] == case_id]
            upstream = upstream_rows.iloc[0].to_dict() if not upstream_rows.empty else {}

            case_records.append(
                {
                    "case_id": case_id,
                    "repo_full_name": _text(case.get("repo_full_name")),
                    "repo_stars": _int(case.get("repo_stars")) or 0,
                    "repo_language": _text(case.get("repo_language")),
                    "issue_number": _int(case.get("issue_number")),
                    "issue_title": _text(case.get("issue_title")),
                    "issue_url": _text(case.get("issue_url")),
                    "issue_author": _text(case.get("issue_author")),
                    "issue_state": _text(case.get("issue_state")),
                    "issue_comments_count": _int(case.get("issue_comments_count")) or 0,
                    "issue_word_count": _int(case.get("issue_word_count")) or 0,
                    "pr_number": _int(case.get("pr_number")),
                    "pr_url": _text(case.get("pr_url")),
                    "pr_author": _text(case.get("pr_author")),
                    "pr_state": _text(case.get("pr_state")),
                    "pr_merged": bool(case.get("pr_merged")),
                    "pr_additions": _int(case.get("pr_additions")) or 0,
                    "pr_deletions": _int(case.get("pr_deletions")) or 0,
                    "changed_files_count": _int(case.get("changed_files_count")) or 0,
                    "commits_count": _int(case.get("commits_count")) or 0,
                    "same_issue_pr_author": bool(upstream.get("same_issue_pr_author")),
                    "issue_to_pr_hours": upstream.get("issue_to_pr_hours"),
                    "issue_change_alignment": _text(upstream.get("issue_change_alignment")) or "None",
                    "issue_change_alignment_score": _int(upstream.get("issue_change_alignment_score")) or 0,
                    "upstream_summary": _text(upstream.get("upstream_summary")),
                    "matched_packages": _text(upstream.get("matched_packages")),
                    "matched_versions": _text(upstream.get("matched_versions")),
                    "matched_files": _text(upstream.get("matched_files")),
                    "matched_vulnerability_ids": _text(upstream.get("matched_vulnerability_ids")),
                    "review_cues": _text(upstream.get("review_cues")),
                    "technical_cues": _text(upstream.get("technical_cues")),
                    "framing_cues": _text(upstream.get("framing_cues")),
                    "archetype": archetype,
                    "review_priority": priority,
                    "review_priority_reason": priority_reason,
                    "raw_finding_count": raw_count,
                    "unique_event_count": unique_count,
                    "duplicate_report_count": max(0, raw_count - unique_count),
                    "strong_attribution_events": strong_count,
                    "test_context_events": test_count,
                    "lockfile_events": lockfile_count,
                    "strongest_severity": _text(strongest.get("severity")),
                    "strongest_family": _text(strongest.get("event_family")),
                    "strongest_event_title": _text(strongest.get("title")),
                    "strongest_event_id": _text(strongest.get("event_id")),
                    "strongest_attribution": _text(strongest.get("attribution_strength")),
                    "family_summary": family_summary,
                    "why_flagged": why,
                }
            )

        frame = pd.DataFrame(case_records)
        if frame.empty:
            return frame
        priority_rank = {"High": 0, "Medium": 1, "Low": 2}
        frame["_priority"] = frame["review_priority"].map(priority_rank).fillna(3)
        frame = frame.sort_values(
            ["_priority", "unique_event_count", "repo_stars", "case_id"],
            ascending=[True, True, False, True],
        ).drop(columns=["_priority"])
        return frame.reset_index(drop=True)


@st.cache_resource(show_spinner=False)
def get_research_layer() -> ResearchLayer:
    return ResearchLayer(get_parquet_store())


def clear_research_layer() -> None:
    get_research_layer.clear()
