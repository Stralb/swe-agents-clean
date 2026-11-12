#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(
    "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
)

DB = (
    ROOT
    / "data"
    / "miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db"
)

REVALIDATION_ROOT = (
    ROOT
    / "data"
    / "scanner_revalidation_17"
)

OUT = (
    ROOT
    / "data"
    / "step1_canonical_findings_134"
)

ZIP_OUT = (
    ROOT
    / "data"
    / "step1_canonical_findings_134_bundle.zip"
)

RAW_JSONL = (
    OUT
    / "step1_corrected_raw_findings_134.jsonl"
)

EVENT_JSONL = (
    OUT
    / "step1_canonical_events_134.jsonl"
)

EVENT_CSV = (
    OUT
    / "step1_canonical_events_134.csv"
)

CASE_CSV = (
    OUT
    / "step1_case_summary_134.csv"
)

QC_JSON = (
    OUT
    / "step1_qc_summary.json"
)

MANIFEST_JSON = (
    OUT
    / "step1_manifest.json"
)

EXCLUDED = {
    59,
    8038,
    8162,
    10825,
}

CODEQL_REVALIDATED = {
    290,
    291,
    299,
    649,
    3882,
    4621,
    5355,
    8461,
    9992,
    10361,
    15151,
    15739,
    16203,
}

EXPECTED_CASE_COUNT = 134

CVE_RE = re.compile(
    r"CVE-\d{4}-\d+",
    re.IGNORECASE,
)

GHSA_RE = re.compile(
    r"GHSA-[0-9A-Za-z-]+",
    re.IGNORECASE,
)

SEVERITY_ORDER = {
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

DEPENDENCY_MANIFEST_NAMES = {
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

LOCKFILE_NAMES = {
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

OUT.mkdir(
    parents=True,
    exist_ok=True,
)


def text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(
        value
    ).strip()


def norm_path(
    value: Any,
) -> str:
    value = (
        text(value)
        .replace("\\", "/")
    )

    while value.startswith("./"):
        value = value[2:]

    return value.lstrip("/")


def parse_json_object(
    value: Any,
) -> dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    if not value:
        return {}

    try:
        parsed = json.loads(
            str(value)
        )
    except Exception:
        return {}

    if isinstance(
        parsed,
        dict,
    ):
        return parsed

    return {}


def first_nonempty(
    values,
) -> str:
    for value in values:
        value = text(
            value
        )

        if value:
            return value

    return ""


def unique_text(
    values,
) -> list[str]:
    output = []

    for value in values:
        value = text(
            value
        )

        if (
            value
            and value not in output
        ):
            output.append(
                value
            )

    return output


def path_context(
    path: Any,
    category: Any = None,
) -> str:
    normalized = norm_path(
        path
    )

    lower = normalized.lower()

    name = (
        lower.rsplit(
            "/",
            1,
        )[-1]
    )

    category_text = (
        text(
            category
        ).lower()
    )

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

    if any(
        token
        in f"/{lower}"
        for token
        in test_tokens
    ):
        return "test / fixture / mock"

    if category_text == "test":
        return "test / fixture / mock"

    if (
        name in LOCKFILE_NAMES
        or name.endswith(
            ".lock"
        )
    ):
        return "dependency lockfile"

    if name in DEPENDENCY_MANIFEST_NAMES:
        return "dependency manifest"

    if (
        lower.startswith(
            ".github/workflows/"
        )
        or "/.github/workflows/"
        in f"/{lower}"
    ):
        return "CI / workflow"

    if any(
        token
        in f"/{lower}/"
        for token
        in (
            "/vendor/",
            "/generated/",
            "/dist/",
            "/build/",
            "/minified/",
        )
    ):
        return "generated / vendor"

    if category_text in {
        "dependency",
        "dependency_config",
    }:
        return "dependency metadata"

    return "production source"


def dependency_values(
    finding: dict[str, Any],
) -> dict[str, str]:
    evidence = parse_json_object(
        finding.get(
            "evidence"
        )
    )

    raw = parse_json_object(
        finding.get(
            "raw_json"
        )
    )

    package = text(
        evidence.get(
            "package"
        )
        or raw.get(
            "PkgName"
        )
    )

    version = text(
        evidence.get(
            "version"
        )
        or raw.get(
            "InstalledVersion"
        )
    )

    old_version = text(
        evidence.get(
            "old_version"
        )
        or raw.get(
            "old_version"
        )
    )

    new_version = text(
        evidence.get(
            "new_version"
        )
        or raw.get(
            "new_version"
        )
    )

    fixed_version = text(
        evidence.get(
            "fixed_version"
        )
        or raw.get(
            "FixedVersion"
        )
    )

    change_type = text(
        evidence.get(
            "change_type"
        )
        or raw.get(
            "change_type"
        )
    )

    ids = []

    for candidate in (
        finding.get(
            "rule_id"
        ),
        evidence.get(
            "vulnerability"
        ),
        evidence.get(
            "vuln_id"
        ),
        raw.get(
            "VulnerabilityID"
        ),
        raw.get(
            "id"
        ),
        raw.get(
            "PrimaryURL"
        ),
    ):
        candidate = text(
            candidate
        )

        if candidate:
            ids.append(
                candidate
            )

    aliases = (
        raw.get(
            "aliases"
        )
        or []
    )

    if isinstance(
        aliases,
        str,
    ):
        aliases = [
            aliases
        ]

    if isinstance(
        aliases,
        list,
    ):
        for candidate in aliases:
            candidate = text(
                candidate
            )

            if candidate:
                ids.append(
                    candidate
                )

    joined = " ".join(
        ids
    )

    cves = sorted(
        {
            match.upper()
            for match
            in CVE_RE.findall(
                joined
            )
        }
    )

    ghsas = sorted(
        {
            match.upper()
            for match
            in GHSA_RE.findall(
                joined
            )
        }
    )

    canonical_vuln = ""

    if cves:
        canonical_vuln = cves[0]

    elif ghsas:
        canonical_vuln = ghsas[0]

    else:
        canonical_vuln = text(
            finding.get(
                "rule_id"
            )
        )

    return {
        "package":
            package,
        "version":
            version,
        "old_version":
            old_version,
        "new_version":
            new_version,
        "fixed_version":
            fixed_version,
        "change_type":
            change_type,
        "canonical_vuln_id":
            canonical_vuln,
    }


def effective_severity(
    finding: dict[str, Any],
) -> str:
    severity = text(
        finding.get(
            "severity"
        )
    ).lower()

    if severity:
        return severity

    raw = parse_json_object(
        finding.get(
            "raw_json"
        )
    )

    database_specific = (
        raw.get(
            "database_specific"
        )
        or {}
    )

    if isinstance(
        database_specific,
        dict,
    ):
        severity = text(
            database_specific.get(
                "severity"
            )
        ).lower()

        if severity:
            return severity

    severity = text(
        raw.get(
            "Severity"
        )
    ).lower()

    return (
        severity
        or "unknown"
    )


def event_family(
    scanner: str,
    finding_type: str,
    change_type: str,
) -> str:
    scanner = (
        scanner.lower()
    )

    finding_type = (
        finding_type.lower()
    )

    change_type = (
        change_type.lower()
    )

    if (
        scanner == "gitleaks"
        or finding_type
        == "secret"
    ):
        return "Secret exposure"

    if scanner == "dependency-diff":
        if "downgrade" in change_type:
            return "Dependency downgrade"

        return "Dependency change"

    if (
        finding_type == "dependency"
        or scanner
        in {
            "osv-scanner",
            "trivy-scanner",
        }
    ):
        return "Dependency vulnerability"

    return "Code vulnerability"


def event_key(
    row: dict[str, Any],
) -> str:
    family = row[
        "event_family"
    ]

    if family == "Dependency vulnerability":
        return "|".join(
            [
                str(
                    row[
                        "case_id"
                    ]
                ),
                family,
                text(
                    row.get(
                        "package"
                    )
                ).lower(),
                text(
                    row.get(
                        "version"
                    )
                ),
                text(
                    row.get(
                        "canonical_vuln_id"
                    )
                ).upper(),
            ]
        )

    if family in {
        "Dependency downgrade",
        "Dependency change",
    }:
        return "|".join(
            [
                str(
                    row[
                        "case_id"
                    ]
                ),
                family,
                text(
                    row.get(
                        "package"
                    )
                ).lower(),
                text(
                    row.get(
                        "old_version"
                    )
                ),
                text(
                    row.get(
                        "new_version"
                    )
                ),
                norm_path(
                    row.get(
                        "file_path"
                    )
                ),
            ]
        )

    return "|".join(
        [
            str(
                row[
                    "case_id"
                ]
            ),
            family,
            text(
                row.get(
                    "rule_id"
                )
            ),
            norm_path(
                row.get(
                    "file_path"
                )
            ),
            str(
                int(
                    row.get(
                        "line"
                    )
                    or 0
                )
            ),
            text(
                row.get(
                    "description"
                )
            )[:160],
        ]
    )


def canonical_description(
    event: dict[str, Any],
) -> str:
    family = event[
        "event_family"
    ]

    package = text(
        event.get(
            "package"
        )
    )

    version = text(
        event.get(
            "version"
        )
    )

    old_version = text(
        event.get(
            "old_version"
        )
    )

    new_version = text(
        event.get(
            "new_version"
        )
    )

    vuln = text(
        event.get(
            "canonical_vuln_id"
        )
    )

    rule = text(
        event.get(
            "rule_id"
        )
    )

    file_path = text(
        event.get(
            "primary_files"
        )
    )

    line = text(
        event.get(
            "primary_line"
        )
    )

    title = " ".join(
        text(
            event.get(
                "scanner_description"
            )
        ).split()
    )

    if family == "Dependency vulnerability":
        subject = (
            f"`{package}`"
            if package
            else "The dependency"
        )

        if version:
            subject += (
                f" version `{version}`"
            )

        if vuln:
            return (
                f"{subject} is reported by the dependency scanners "
                f"as affected by `{vuln}`."
            )

        if title:
            return (
                f"{subject} is reported by the dependency scanners "
                f"with this vulnerability condition: {title}"
            )

        return (
            f"{subject} is reported by the dependency scanners "
            "as vulnerable."
        )

    if family == "Dependency downgrade":
        subject = (
            f"`{package}`"
            if package
            else "A dependency"
        )

        if (
            old_version
            and new_version
        ):
            return (
                f"{subject} is recorded as being downgraded "
                f"from `{old_version}` to `{new_version}`."
            )

        if title:
            return (
                f"The dependency scanner records a downgrade: "
                f"{title}"
            )

        return (
            "The dependency scanner records a dependency downgrade."
        )

    if family == "Dependency change":
        subject = (
            f"`{package}`"
            if package
            else "A dependency"
        )

        if (
            old_version
            and new_version
        ):
            return (
                f"{subject} is recorded as changing "
                f"from `{old_version}` to `{new_version}`."
            )

        if title:
            return (
                f"The dependency scanner records a version change: "
                f"{title}"
            )

        return (
            "The dependency scanner records a dependency version change."
        )

    if family == "Secret exposure":
        location = ""

        if file_path:
            location = (
                f" in `{file_path}`"
            )

            if line:
                location += (
                    f" at line {line}"
                )

        if rule:
            return (
                f"Gitleaks reports a `{rule}` secret-like pattern"
                f"{location}."
            )

        return (
            f"Gitleaks reports a secret-like pattern"
            f"{location}."
        )

    location = ""

    if file_path:
        location = (
            f" at `{file_path}`"
        )

        if line:
            location += (
                f":{line}"
            )

    if rule and title:
        return (
            f"The scanner reports rule `{rule}`{location}: "
            f"{title}"
        )

    if rule:
        return (
            f"The scanner reports rule `{rule}`{location}."
        )

    if title:
        return (
            f"The scanner reports this code condition{location}: "
            f"{title}"
        )

    return (
        f"The scanner reports a code vulnerability condition"
        f"{location}."
    )


def load_rows(
    connection: sqlite3.Connection,
    query: str,
    params=(),
) -> list[dict[str, Any]]:
    connection.row_factory = (
        sqlite3.Row
    )

    return [
        dict(
            row
        )
        for row
        in connection.execute(
            query,
            params,
        )
    ]


if not DB.exists():
    raise FileNotFoundError(
        f"Snapshot DB not found: {DB}"
    )


source = sqlite3.connect(
    f"file:{DB.resolve()}?mode=ro",
    uri=True,
)

source.row_factory = (
    sqlite3.Row
)


cases = load_rows(
    source,
    """
    SELECT
        c.id AS case_id,
        c.pr_id AS pr_id,
        r.full_name AS repo_full_name,
        p.number AS pr_number

    FROM cases c

    JOIN repos r
      ON r.id = c.repo_id

    JOIN pull_requests p
      ON p.id = c.pr_id

    WHERE EXISTS (
        SELECT 1
        FROM scanner_findings sf
        WHERE sf.case_id = c.id
          AND COALESCE(sf.introduced, 0) = 1
    )

      AND c.id NOT IN (
          59,
          8038,
          8162,
          10825
      )

    ORDER BY c.id
    """,
)


if len(
    cases
) != EXPECTED_CASE_COUNT:
    raise RuntimeError(
        f"Expected {EXPECTED_CASE_COUNT} corrected cases, "
        f"found {len(cases)}"
    )


case_ids = [
    int(
        row[
            "case_id"
        ]
    )
    for row in cases
]

case_meta = {
    int(
        row[
            "case_id"
        ]
    ): row
    for row in cases
}

placeholders = ",".join(
    "?"
    for _ in case_ids
)


snapshot_findings = load_rows(
    source,
    f"""
    SELECT
        id,
        case_id,
        pr_id,
        scanner,
        finding_type,
        severity,
        rule_id,
        cwe,
        file_path,
        line,
        description,
        evidence,
        raw_json,
        introduced,
        created_at

    FROM scanner_findings

    WHERE COALESCE(introduced, 0) = 1

      AND case_id IN (
          {placeholders}
      )

    ORDER BY
        case_id,
        id
    """,
    case_ids,
)


file_rows = load_rows(
    source,
    f"""
    SELECT
        pf.pr_id,
        pf.filename,
        pf.category

    FROM pr_files pf

    WHERE pf.pr_id IN (
        SELECT c.pr_id
        FROM cases c
        WHERE c.id IN (
            {placeholders}
        )
    )
    """,
    case_ids,
)


source.close()


file_category = {
    (
        int(
            row[
                "pr_id"
            ]
        ),
        norm_path(
            row[
                "filename"
            ]
        ),
    ):
        text(
            row[
                "category"
            ]
        )

    for row
    in file_rows
}


corrected_raw = []


for row in snapshot_findings:
    case_id = int(
        row[
            "case_id"
        ]
    )

    scanner = text(
        row[
            "scanner"
        ]
    ).lower()

    if (
        case_id
        in CODEQL_REVALIDATED
        and scanner
        == "codeql"
    ):
        continue

    row[
        "source"
    ] = "snapshot"

    row[
        "source_finding_id"
    ] = (
        f"snapshot:{row['id']}"
    )

    corrected_raw.append(
        row
    )


revalidation_counts = {}


for case_id in sorted(
    CODEQL_REVALIDATED
):
    validation_db = (
        REVALIDATION_ROOT
        / "work"
        / f"case_{case_id}.db"
    )

    result_json = (
        REVALIDATION_ROOT
        / "results"
        / f"case_{case_id}.json"
    )

    if not validation_db.exists():
        raise FileNotFoundError(
            f"Missing revalidation DB for case {case_id}: "
            f"{validation_db}"
        )

    validation = sqlite3.connect(
        f"file:{validation_db.resolve()}?mode=ro",
        uri=True,
    )

    rows = load_rows(
        validation,
        """
        SELECT
            id,
            case_id,
            pr_id,
            scanner,
            finding_type,
            severity,
            rule_id,
            cwe,
            file_path,
            line,
            description,
            evidence,
            raw_json,
            introduced,
            created_at

        FROM scanner_findings

        WHERE COALESCE(introduced, 0) = 1
          AND LOWER(scanner) = 'codeql'

        ORDER BY id
        """,
    )

    validation.close()

    expected_count = None

    if result_json.exists():
        result = json.loads(
            result_json.read_text(
                encoding="utf-8"
            )
        )

        expected_count = int(
            result.get(
                "new_finding_count"
            )
            or 0
        )

        if len(
            rows
        ) != expected_count:
            raise RuntimeError(
                f"Case {case_id}: validation DB has "
                f"{len(rows)} CodeQL rows but result JSON "
                f"expects {expected_count}"
            )

    revalidation_counts[
        str(case_id)
    ] = {
        "loaded_codeql_findings":
            len(rows),
        "expected_from_result_json":
            expected_count,
    }

    for row in rows:
        row[
            "source"
        ] = "revalidated_merge_base"

        row[
            "source_finding_id"
        ] = (
            f"revalidated:{case_id}:{row['id']}"
        )

        corrected_raw.append(
            row
        )


corrected_raw.sort(
    key=lambda row: (
        int(
            row[
                "case_id"
            ]
        ),
        text(
            row[
                "scanner"
            ]
        ),
        text(
            row[
                "rule_id"
            ]
        ),
        norm_path(
            row[
                "file_path"
            ]
        ),
        int(
            row[
                "line"
            ]
            or 0
        ),
        text(
            row[
                "source_finding_id"
            ]
        ),
    )
)


prepared = []


for finding in corrected_raw:
    finding = dict(
        finding
    )

    finding[
        "case_id"
    ] = int(
        finding[
            "case_id"
        ]
    )

    finding[
        "pr_id"
    ] = int(
        finding[
            "pr_id"
        ]
    )

    finding[
        "file_path"
    ] = norm_path(
        finding.get(
            "file_path"
        )
    )

    dependency = dependency_values(
        finding
    )

    finding.update(
        dependency
    )

    finding[
        "event_family"
    ] = event_family(
        text(
            finding.get(
                "scanner"
            )
        ),
        text(
            finding.get(
                "finding_type"
            )
        ),
        text(
            finding.get(
                "change_type"
            )
        ),
    )

    finding[
        "effective_severity"
    ] = effective_severity(
        finding
    )

    category = file_category.get(
        (
            int(
                finding[
                    "pr_id"
                ]
            ),
            norm_path(
                finding.get(
                    "file_path"
                )
            ),
        ),
        "",
    )

    finding[
        "primary_context"
    ] = path_context(
        finding.get(
            "file_path"
        ),
        category,
    )

    finding[
        "event_key"
    ] = event_key(
        finding
    )

    prepared.append(
        finding
    )


groups = defaultdict(
    list
)


for row in prepared:
    groups[
        row[
            "event_key"
        ]
    ].append(
        row
    )


events = []


for key, rows in groups.items():
    rows = sorted(
        rows,
        key=lambda row: (
            -SEVERITY_ORDER.get(
                text(
                    row.get(
                        "effective_severity"
                    )
                ).lower(),
                0,
            ),
            text(
                row.get(
                    "scanner"
                )
            ),
            text(
                row.get(
                    "source_finding_id"
                )
            ),
        ),
    )

    first = rows[0]

    event_id = hashlib.sha1(
        key.encode(
            "utf-8"
        )
    ).hexdigest()[:16]

    severity = max(
        (
            text(
                row.get(
                    "effective_severity"
                )
            ).lower()
            or "unknown"
        )
        for row in rows
    )

    severity = max(
        [
            text(
                row.get(
                    "effective_severity"
                )
            ).lower()
            or "unknown"
            for row in rows
        ],
        key=lambda value:
            SEVERITY_ORDER.get(
                value,
                0,
            ),
    )

    scanners = unique_text(
        row.get(
            "scanner"
        )
        for row in rows
    )

    rule_ids = unique_text(
        row.get(
            "rule_id"
        )
        for row in rows
    )

    files = unique_text(
        row.get(
            "file_path"
        )
        for row in rows
    )

    lines = [
        int(
            row[
                "line"
            ]
        )
        for row in rows
        if row.get(
            "line"
        )
        is not None
    ]

    descriptions = unique_text(
        row.get(
            "description"
        )
        for row in rows
    )

    package = first_nonempty(
        row.get(
            "package"
        )
        for row in rows
    )

    version = first_nonempty(
        row.get(
            "version"
        )
        for row in rows
    )

    old_version = first_nonempty(
        row.get(
            "old_version"
        )
        for row in rows
    )

    new_version = first_nonempty(
        row.get(
            "new_version"
        )
        for row in rows
    )

    fixed_version = first_nonempty(
        row.get(
            "fixed_version"
        )
        for row in rows
    )

    canonical_vuln = first_nonempty(
        row.get(
            "canonical_vuln_id"
        )
        for row in rows
    )

    contexts = unique_text(
        row.get(
            "primary_context"
        )
        for row in rows
    )

    meta = case_meta[
        int(
            first[
                "case_id"
            ]
        )
    ]

    event = {
        "Event ID":
            event_id,

        "Case ID":
            int(
                first[
                    "case_id"
                ]
            ),

        "Repository":
            meta[
                "repo_full_name"
            ],

        "PR #":
            int(
                meta[
                    "pr_number"
                ]
            ),

        "Event Family":
            first[
                "event_family"
            ],

        "Canonical Vulnerability ID":
            canonical_vuln,

        "Package":
            package,

        "Version":
            version,

        "Old Version":
            old_version,

        "New Version":
            new_version,

        "Fixed Version":
            fixed_version,

        "Severity":
            severity,

        "Rule ID":
            ", ".join(
                rule_ids
            ),

        "Primary File(s)":
            ", ".join(
                files
            ),

        "Primary Line":
            (
                min(
                    lines
                )
                if lines
                else ""
            ),

        "Primary Context":
            ", ".join(
                contexts
            ),

        "Scanner(s)":
            ", ".join(
                scanners
            ),

        "Raw Scanner Row Count":
            len(
                rows
            ),

        "Raw Finding IDs":
            ", ".join(
                text(
                    row.get(
                        "source_finding_id"
                    )
                )
                for row in rows
            ),

        "Scanner Description":
            (
                descriptions[0]
                if descriptions
                else ""
            ),

        "Canonical Finding":
            "",
    }

    event[
        "Canonical Finding"
    ] = canonical_description(
        {
            "event_family":
                event[
                    "Event Family"
                ],
            "package":
                event[
                    "Package"
                ],
            "version":
                event[
                    "Version"
                ],
            "old_version":
                event[
                    "Old Version"
                ],
            "new_version":
                event[
                    "New Version"
                ],
            "canonical_vuln_id":
                event[
                    "Canonical Vulnerability ID"
                ],
            "rule_id":
                event[
                    "Rule ID"
                ],
            "primary_files":
                event[
                    "Primary File(s)"
                ],
            "primary_line":
                event[
                    "Primary Line"
                ],
            "scanner_description":
                event[
                    "Scanner Description"
                ],
        }
    )

    event[
        "_event_key"
    ] = key

    event[
        "_raw_members"
    ] = [
        {
            "source_finding_id":
                row[
                    "source_finding_id"
                ],
            "source":
                row[
                    "source"
                ],
            "scanner":
                row[
                    "scanner"
                ],
            "finding_type":
                row[
                    "finding_type"
                ],
            "severity":
                row[
                    "severity"
                ],
            "rule_id":
                row[
                    "rule_id"
                ],
            "cwe":
                row[
                    "cwe"
                ],
            "file_path":
                row[
                    "file_path"
                ],
            "line":
                row[
                    "line"
                ],
            "description":
                row[
                    "description"
                ],
            "evidence":
                row[
                    "evidence"
                ],
            "raw_json":
                row[
                    "raw_json"
                ],
        }

        for row
        in rows
    ]

    events.append(
        event
    )


events.sort(
    key=lambda event: (
        int(
            event[
                "Case ID"
            ]
        ),
        event[
            "Event Family"
        ],
        event[
            "Event ID"
        ],
    )
)


with RAW_JSONL.open(
    "w",
    encoding="utf-8",
) as handle:
    for row in prepared:
        export_row = dict(
            row
        )

        export_row[
            "repo_full_name"
        ] = case_meta[
            int(
                row[
                    "case_id"
                ]
            )
        ][
            "repo_full_name"
        ]

        export_row[
            "pr_number"
        ] = case_meta[
            int(
                row[
                    "case_id"
                ]
            )
        ][
            "pr_number"
        ]

        handle.write(
            json.dumps(
                export_row,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


with EVENT_JSONL.open(
    "w",
    encoding="utf-8",
) as handle:
    for event in events:
        handle.write(
            json.dumps(
                event,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


csv_fields = [
    key
    for key
    in events[0].keys()
    if not key.startswith(
        "_"
    )
]


with EVENT_CSV.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=csv_fields,
    )

    writer.writeheader()

    for event in events:
        writer.writerow(
            {
                key:
                    event.get(
                        key,
                        "",
                    )
                for key
                in csv_fields
            }
        )


events_by_case = defaultdict(
    list
)

raw_by_case = Counter()


for row in prepared:
    raw_by_case[
        int(
            row[
                "case_id"
            ]
        )
    ] += 1


for event in events:
    events_by_case[
        int(
            event[
                "Case ID"
            ]
        )
    ].append(
        event
    )


case_summary = []


for case_id in case_ids:
    case_events = events_by_case[
        case_id
    ]

    families = Counter(
        event[
            "Event Family"
        ]
        for event
        in case_events
    )

    case_summary.append(
        {
            "Case ID":
                case_id,

            "Repository":
                case_meta[
                    case_id
                ][
                    "repo_full_name"
                ],

            "PR #":
                case_meta[
                    case_id
                ][
                    "pr_number"
                ],

            "Corrected Raw Finding Count":
                raw_by_case[
                    case_id
                ],

            "Canonical Finding Count":
                len(
                    case_events
                ),

            "Collapsed Duplicate Rows":
                raw_by_case[
                    case_id
                ]
                - len(
                    case_events
                ),

            "Finding Families":
                "; ".join(
                    f"{family}: {count}"
                    for family, count
                    in sorted(
                        families.items()
                    )
                ),
        }
    )


with CASE_CSV.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=list(
            case_summary[
                0
            ].keys()
        ),
    )

    writer.writeheader()

    writer.writerows(
        case_summary
    )


family_counts = Counter(
    event[
        "Event Family"
    ]
    for event
    in events
)

scanner_counts = Counter(
    text(
        row[
            "scanner"
        ]
    )
    for row
    in prepared
)

cases_with_multiple_events = [
    case_id
    for case_id
    in case_ids
    if len(
        events_by_case[
            case_id
        ]
    ) > 1
]


qc = {
    "corrected_case_count":
        len(
            case_ids
        ),

    "unique_case_count":
        len(
            set(
                case_ids
            )
        ),

    "excluded_case_ids":
        sorted(
            EXCLUDED
        ),

    "codeql_revalidated_case_ids":
        sorted(
            CODEQL_REVALIDATED
        ),

    "revalidation_counts":
        revalidation_counts,

    "corrected_raw_finding_count":
        len(
            prepared
        ),

    "canonical_finding_count":
        len(
            events
        ),

    "collapsed_raw_rows":
        len(
            prepared
        )
        - len(
            events
        ),

    "canonicalization_reduction_percent":
        round(
            (
                (
                    len(
                        prepared
                    )
                    - len(
                        events
                    )
                )
                / len(
                    prepared
                )
                * 100
            ),
            2,
        )
        if prepared
        else 0.0,

    "event_family_counts":
        dict(
            family_counts
        ),

    "raw_scanner_counts":
        dict(
            scanner_counts
        ),

    "cases_with_multiple_canonical_findings":
        len(
            cases_with_multiple_events
        ),

    "maximum_canonical_findings_in_one_case":
        max(
            (
                len(
                    events_by_case[
                        case_id
                    ]
                )
                for case_id
                in case_ids
            ),
            default=0,
        ),

    "cases_with_zero_canonical_findings":
        [
            case_id
            for case_id
            in case_ids
            if not events_by_case[
                case_id
            ]
        ],
}


QC_JSON.write_text(
    json.dumps(
        qc,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


manifest = {
    "stage":
        "Unblinding Pass 1 - Step 1",

    "purpose":
        (
            "Convert corrected introduced scanner rows into "
            "distinct canonical findings without using issue intent, "
            "PR stated intent, actor context, or maliciousness labels."
        ),

    "corrected_positive_cases":
        134,

    "excluded_false_positive_cases":
        sorted(
            EXCLUDED
        ),

    "corrected_codeql_source":
        (
            "For the 13 revalidated CodeQL cases, snapshot CodeQL rows "
            "are replaced by findings from the merge-base revalidation DB."
        ),

    "canonicalization_rules": {
        "dependency_vulnerability":
            (
                "same case + package + installed version + canonical "
                "CVE/GHSA identifier"
            ),

        "dependency_change":
            (
                "same case + change family + package + old version + "
                "new version + dependency file"
            ),

        "code_or_secret":
            (
                "same case + event family + rule + file + line + "
                "scanner description preview"
            ),
    },

    "canonical_finding_description_rule":
        (
            "Neutral deterministic template based only on scanner "
            "evidence. It does not claim exploitability or malicious intent."
        ),

    "step_1_does_not_use": [
        "issue title/body",
        "issue coding",
        "PR title/body",
        "goal alignment",
        "actual implementation summary",
        "actor context",
        "timeline context",
        "agent-steering risk labels",
        "maliciousness labels",
    ],
}


MANIFEST_JSON.write_text(
    json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


with zipfile.ZipFile(
    ZIP_OUT,
    "w",
    compression=zipfile.ZIP_DEFLATED,
    compresslevel=6,
) as archive:
    for path in (
        RAW_JSONL,
        EVENT_JSONL,
        EVENT_CSV,
        CASE_CSV,
        QC_JSON,
        MANIFEST_JSON,
    ):
        archive.write(
            path,
            path.name,
        )


print()
print("=" * 80)
print("STEP 1 CANONICAL FINDING EXPORT COMPLETE")
print("=" * 80)

print(
    f"Cases:                   {len(case_ids)}"
)

print(
    f"Corrected raw findings:  {len(prepared)}"
)

print(
    f"Canonical findings:      {len(events)}"
)

print(
    f"Collapsed duplicate rows:{len(prepared) - len(events)}"
)

print(
    "Reduction:               "
    f"{qc['canonicalization_reduction_percent']}%"
)

print()
print("Canonical event families:")

for family, count in sorted(
    family_counts.items(),
    key=lambda item: (
        -item[1],
        item[0],
    ),
):
    print(
        f"  {count:4}  {family}"
    )

print()
print(
    "Cases with zero canonical findings: "
    f"{qc['cases_with_zero_canonical_findings']}"
)

print()
print(
    f"Bundle: {ZIP_OUT}"
)
