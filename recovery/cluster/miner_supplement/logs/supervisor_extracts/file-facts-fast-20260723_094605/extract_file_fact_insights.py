from __future__ import annotations

import csv
import os
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


db_path = Path(os.environ["WORK_DB"])
out_dir = Path(os.environ["OUT_DIR"])

report_path = (
    out_dir
    / "file-facts-insights.md"
)

detail_csv = (
    out_dir
    / "finding-file-attribution.csv"
)

region_csv = (
    out_dir
    / "region-summary.csv"
)

out_dir.mkdir(
    parents=True,
    exist_ok=True,
)

connection = sqlite3.connect(
    f"file:{db_path}?mode=ro",
    uri=True,
    timeout=60,
)

connection.row_factory = sqlite3.Row


def scalar(
    query: str,
    parameters: tuple[Any, ...] = (),
) -> int:
    row = connection.execute(
        query,
        parameters,
    ).fetchone()

    return int(
        (row[0] if row else 0)
        or 0
    )


def percentage(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(
        100.0 * numerator / denominator,
        1,
    )


def normalise_path(
    value: Any,
) -> str:
    return (
        str(value or "")
        .strip()
        .replace("\\", "/")
        .lstrip("./")
        .lower()
    )


def canonical_scanner(
    value: Any,
) -> str:
    name = str(
        value or ""
    ).lower()

    if "dependency-diff" in name:
        return "dependency-diff"

    if "gitleaks" in name:
        return "Gitleaks"

    if "semgrep" in name:
        return "Semgrep"

    if "codeql" in name:
        return "CodeQL"

    if "trivy" in name:
        return "Trivy"

    if "osv" in name:
        return "OSV"

    return name or "Unknown"


LOCKFILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "pnpm-lock.yml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "cargo.lock",
    "poetry.lock",
    "pipfile.lock",
    "composer.lock",
    "gemfile.lock",
    "go.sum",
}


def is_lockfile(
    path: Any,
) -> bool:
    return (
        Path(
            normalise_path(path)
        ).name
        in LOCKFILES
    )


quick_check = connection.execute(
    "PRAGMA quick_check"
).fetchone()[0]

if quick_check != "ok":
    raise RuntimeError(
        "quick_check failed: "
        + str(quick_check)
    )


repositories = scalar(
    """
    SELECT COUNT(DISTINCT repo_id)
    FROM cases
    WHERE repo_id IS NOT NULL
    """
)

cases = scalar(
    "SELECT COUNT(*) FROM cases"
)

changed_files = scalar(
    """
    SELECT COUNT(*)
    FROM (
        SELECT DISTINCT
            c.id AS case_id,
            pf.filename
        FROM cases c
        JOIN pr_files pf
          ON pf.pr_id=c.pr_id
    )
    """
)

artifact_rows = scalar(
    """
    SELECT COUNT(*)
    FROM artifact_regions
    """
)

profiled_files = scalar(
    """
    SELECT COUNT(*)
    FROM (
        SELECT DISTINCT
            case_id,
            path
        FROM artifact_regions
    )
    """
)

profiled_cases = scalar(
    """
    SELECT COUNT(DISTINCT case_id)
    FROM artifact_regions
    """
)

profile_rows = scalar(
    """
    SELECT COUNT(*)
    FROM pr_region_profiles
    """
)

if (
    artifact_rows == 0
    or profile_rows == 0
):
    raise RuntimeError(
        "The file-fact backfill is empty."
    )


primary_regions = list(
    connection.execute(
        """
        SELECT
            primary_region,
            COUNT(*) AS cases
        FROM pr_region_profiles
        GROUP BY primary_region
        ORDER BY
            cases DESC,
            primary_region
        """
    )
)


file_rows = connection.execute(
    """
    SELECT
        ar.case_id,
        ar.path,
        ar.region,
        ar.language,
        ar.generated,
        ar.vendor,
        ar.confidence,
        pf.status,
        pf.additions,
        pf.deletions
    FROM artifact_regions ar
    LEFT JOIN pr_files pf
      ON pf.id=ar.pr_file_id
    """
).fetchall()


file_facts: dict[
    tuple[int, str],
    dict[str, Any],
] = {}

region_files: dict[
    str,
    set[tuple[int, str]],
] = defaultdict(set)

region_cases: dict[
    str,
    set[int],
] = defaultdict(set)

language_files: dict[
    str,
    set[tuple[int, str]],
] = defaultdict(set)

status_files: dict[
    str,
    set[tuple[int, str]],
] = defaultdict(set)

confidence_files: dict[
    str,
    set[tuple[int, str]],
] = defaultdict(set)


for row in file_rows:
    case_id = int(
        row["case_id"]
    )

    path = str(
        row["path"]
        or ""
    )

    key = (
        case_id,
        normalise_path(path),
    )

    fact = file_facts.setdefault(
        key,
        {
            "case_id": case_id,
            "path": path,
            "status": str(
                row["status"]
                or "unknown"
            ).lower(),
            "regions": set(),
            "languages": set(),
            "generated": False,
            "vendor": False,
        },
    )

    region = str(
        row["region"]
        or "unknown"
    )

    language = str(
        row["language"]
        or "<unknown>"
    )

    confidence = str(
        row["confidence"]
        or "<unknown>"
    )

    status = str(
        row["status"]
        or "unknown"
    ).lower()

    fact["regions"].add(
        region
    )

    fact["languages"].add(
        language
    )

    fact["generated"] = (
        fact["generated"]
        or bool(row["generated"])
    )

    fact["vendor"] = (
        fact["vendor"]
        or bool(row["vendor"])
    )

    region_files[
        region
    ].add(key)

    region_cases[
        region
    ].add(case_id)

    language_files[
        language
    ].add(key)

    status_files[
        status
    ].add(key)

    confidence_files[
        confidence
    ].add(key)


generated_files = sum(
    1
    for fact in file_facts.values()
    if fact["generated"]
)

vendor_files = sum(
    1
    for fact in file_facts.values()
    if fact["vendor"]
)

unknown_files = {
    key
    for region, keys
    in region_files.items()
    if "unknown" in region.lower()
    for key in keys
}

lockfiles = {
    key
    for key, fact
    in file_facts.items()
    if is_lockfile(
        fact["path"]
    )
}

added_lockfiles = {
    key
    for key in lockfiles
    if file_facts[key]["status"]
    == "added"
}

modified_lockfiles = {
    key
    for key in lockfiles
    if file_facts[key]["status"]
    == "modified"
}


finding_rows = connection.execute(
    """
    SELECT
        id,
        case_id,
        scanner,
        rule_id,
        finding_type,
        severity,
        file_path,
        line,
        description
    FROM scanner_findings
    WHERE COALESCE(
        introduced,
        0
    )=1
    ORDER BY
        scanner,
        case_id,
        id
    """
).fetchall()


scanner_totals: Counter[str] = Counter()
scanner_exact: Counter[str] = Counter()
scanner_missing_target: Counter[str] = Counter()
scanner_unmatched: Counter[str] = Counter()

scanner_added_lock: Counter[str] = Counter()
scanner_modified_lock: Counter[str] = Counter()
scanner_added_other: Counter[str] = Counter()
scanner_modified_other: Counter[str] = Counter()
scanner_removed: Counter[str] = Counter()

region_findings: Counter[str] = Counter()

region_positive_cases: dict[
    str,
    set[int],
] = defaultdict(set)

details: list[
    dict[str, Any]
] = []


for row in finding_rows:
    scanner = canonical_scanner(
        row["scanner"]
    )

    case_id = int(
        row["case_id"]
    )

    raw_path = row[
        "file_path"
    ]

    finding_path = normalise_path(
        raw_path
    )

    scanner_totals[
        scanner
    ] += 1

    relationship = ""
    regions = ""
    languages = ""
    status = ""
    lockfile = 0

    if not finding_path:
        relationship = (
            "missing_target_path"
        )

        scanner_missing_target[
            scanner
        ] += 1

    else:
        fact = file_facts.get(
            (
                case_id,
                finding_path,
            )
        )

        if fact is None:
            relationship = (
                "unmatched_target"
            )

            scanner_unmatched[
                scanner
            ] += 1

        else:
            scanner_exact[
                scanner
            ] += 1

            status = str(
                fact["status"]
                or "unknown"
            )

            lockfile = int(
                is_lockfile(
                    fact["path"]
                )
            )

            regions = ",".join(
                sorted(
                    fact["regions"]
                )
            )

            languages = ",".join(
                sorted(
                    fact["languages"]
                )
            )

            if (
                lockfile
                and status == "added"
            ):
                relationship = (
                    "added_lockfile_"
                    "newly_observable_candidate"
                )

                scanner_added_lock[
                    scanner
                ] += 1

            elif (
                lockfile
                and status == "modified"
            ):
                relationship = (
                    "modified_lockfile"
                )

                scanner_modified_lock[
                    scanner
                ] += 1

            elif status == "added":
                relationship = (
                    "added_changed_file"
                )

                scanner_added_other[
                    scanner
                ] += 1

            elif status == "modified":
                relationship = (
                    "modified_changed_file"
                )

                scanner_modified_other[
                    scanner
                ] += 1

            elif status in {
                "removed",
                "deleted",
            }:
                relationship = (
                    "removed_changed_file"
                )

                scanner_removed[
                    scanner
                ] += 1

            else:
                relationship = (
                    "changed_target_"
                    + status
                )

            for region in fact[
                "regions"
            ]:
                region_findings[
                    region
                ] += 1

                region_positive_cases[
                    region
                ].add(case_id)

    details.append({
        "finding_id":
            int(row["id"]),
        "case_id":
            case_id,
        "scanner":
            scanner,
        "rule_id":
            row["rule_id"],
        "finding_type":
            row["finding_type"],
        "severity":
            row["severity"],
        "file_path":
            raw_path,
        "line":
            row["line"],
        "file_status":
            status,
        "is_lockfile":
            lockfile,
        "relationship":
            relationship,
        "regions":
            regions,
        "languages":
            languages,
    })


fieldnames = [
    "finding_id",
    "case_id",
    "scanner",
    "rule_id",
    "finding_type",
    "severity",
    "file_path",
    "line",
    "file_status",
    "is_lockfile",
    "relationship",
    "regions",
    "languages",
]

with detail_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=fieldnames,
    )

    writer.writeheader()
    writer.writerows(
        details
    )


with region_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:
    writer = csv.writer(
        handle
    )

    writer.writerow([
        "region",
        "files",
        "file_share_percent",
        "cases",
        "case_share_percent",
        "exact_linked_findings",
        "positive_cases",
    ])

    for region in sorted(
        region_files,
        key=lambda value: (
            -len(
                region_files[value]
            ),
            value,
        ),
    ):
        writer.writerow([
            region,
            len(
                region_files[region]
            ),
            percentage(
                len(region_files[region]),
                profiled_files,
            ),
            len(
                region_cases[region]
            ),
            percentage(
                len(region_cases[region]),
                cases,
            ),
            region_findings[
                region
            ],
            len(
                region_positive_cases[
                    region
                ]
            ),
        ])


scanner_order = [
    "dependency-diff",
    "OSV",
    "Trivy",
    "Gitleaks",
    "Semgrep",
    "CodeQL",
]

all_findings = sum(
    scanner_totals.values()
)

exact_findings = sum(
    scanner_exact.values()
)

unmatched_findings = sum(
    scanner_unmatched.values()
)

missing_target_findings = sum(
    scanner_missing_target.values()
)

added_lock_findings = sum(
    scanner_added_lock.values()
)

modified_lock_findings = sum(
    scanner_modified_lock.values()
)


lines: list[str] = [
    "# File-Fact Defence Snapshot",
    "",
    "## Coverage",
    "",
    (
        f"- Repositories: "
        f"**{repositories:,}**"
    ),
    (
        f"- Cases: "
        f"**{cases:,}**"
    ),
    (
        f"- Changed files: "
        f"**{changed_files:,}**"
    ),
    (
        f"- Cases with file facts: "
        f"**{profiled_cases:,}/"
        f"{cases:,} "
        f"({percentage(profiled_cases, cases)}%)**"
    ),
    (
        f"- Changed files with file facts: "
        f"**{profiled_files:,}/"
        f"{changed_files:,} "
        f"({percentage(profiled_files, changed_files)}%)**"
    ),
    (
        f"- Artifact-region rows: "
        f"**{artifact_rows:,}**"
    ),
    "",
    "## Primary region per case",
    "",
    "| Primary region | Cases | Share |",
    "|---|---:|---:|",
]


for row in primary_regions:
    region = str(
        row["primary_region"]
        or "unknown"
    )

    count = int(
        row["cases"]
    )

    lines.append(
        f"| {region} | "
        f"{count:,} | "
        f"{percentage(count, cases)}% |"
    )


lines.extend([
    "",
    "## Important file facts",
    "",
    (
        f"- Added files: "
        f"**{len(status_files['added']):,}**"
    ),
    (
        f"- Modified files: "
        f"**{len(status_files['modified']):,}**"
    ),
    (
        f"- Deleted/removed files: "
        f"**{len(status_files['deleted'] | status_files['removed']):,}**"
    ),
    (
        f"- Changed lockfiles: "
        f"**{len(lockfiles):,}**"
    ),
    (
        f"- Newly added lockfiles: "
        f"**{len(added_lockfiles):,}**"
    ),
    (
        f"- Modified lockfiles: "
        f"**{len(modified_lockfiles):,}**"
    ),
    (
        f"- Generated files: "
        f"**{generated_files:,} "
        f"({percentage(generated_files, profiled_files)}%)**"
    ),
    (
        f"- Vendor/minified files: "
        f"**{vendor_files:,} "
        f"({percentage(vendor_files, profiled_files)}%)**"
    ),
    (
        f"- Unknown-region files: "
        f"**{len(unknown_files):,} "
        f"({percentage(len(unknown_files), profiled_files)}%)**"
    ),
    "",
    "## Main languages",
    "",
    "| Language | Files | Share |",
    "|---|---:|---:|",
])


for language in sorted(
    language_files,
    key=lambda value: (
        -len(
            language_files[value]
        ),
        value,
    ),
)[:10]:
    count = len(
        language_files[language]
    )

    lines.append(
        f"| {language} | "
        f"{count:,} | "
        f"{percentage(count, profiled_files)}% |"
    )


lines.extend([
    "",
    "## Introduced findings linked to file facts",
    "",
    (
        "| Scanner | Findings | "
        "Exact changed-file match | "
        "Missing target path | "
        "Unmatched target | "
        "Added lockfile | "
        "Modified lockfile | "
        "Other added file | "
        "Other modified file |"
    ),
    (
        "|---|---:|---:|---:|---:|"
        "---:|---:|---:|---:|"
    ),
])


for scanner in scanner_order:
    if scanner_totals[
        scanner
    ] == 0:
        continue

    lines.append(
        f"| {scanner} | "
        f"{scanner_totals[scanner]:,} | "
        f"{scanner_exact[scanner]:,} | "
        f"{scanner_missing_target[scanner]:,} | "
        f"{scanner_unmatched[scanner]:,} | "
        f"{scanner_added_lock[scanner]:,} | "
        f"{scanner_modified_lock[scanner]:,} | "
        f"{scanner_added_other[scanner]:,} | "
        f"{scanner_modified_other[scanner]:,} |"
    )


lines.extend([
    "",
    "## Exact-linked findings by region",
    "",
    (
        "| Region | Files | "
        "Cases containing region | "
        "Exact-linked findings | "
        "Positive cases |"
    ),
    "|---|---:|---:|---:|---:|",
])


for region in sorted(
    region_files,
    key=lambda value: (
        -len(
            region_files[value]
        ),
        value,
    ),
)[:12]:
    lines.append(
        f"| {region} | "
        f"{len(region_files[region]):,} | "
        f"{len(region_cases[region]):,} | "
        f"{region_findings[region]:,} | "
        f"{len(region_positive_cases[region]):,} |"
    )


lines.extend([
    "",
    "## Defence interpretation",
    "",
    (
        f"- Stored introduced findings: "
        f"**{all_findings:,}**."
    ),
    (
        f"- Exact changed-file matches: "
        f"**{exact_findings:,} "
        f"({percentage(exact_findings, all_findings)}%)**."
    ),
    (
        f"- Missing target paths: "
        f"**{missing_target_findings:,} "
        f"({percentage(missing_target_findings, all_findings)}%)**."
    ),
    (
        f"- Unmatched target paths: "
        f"**{unmatched_findings:,} "
        f"({percentage(unmatched_findings, all_findings)}%)**."
    ),
    (
        f"- Findings in newly added lockfiles: "
        f"**{added_lock_findings:,}**. "
        "Treat these as potentially newly observable "
        "until the exact package delta is checked."
    ),
    (
        f"- Findings in modified lockfiles: "
        f"**{modified_lock_findings:,}**. "
        "These are stronger candidates, but still "
        "require package/version delta confirmation."
    ),
    (
        "- Exact file matching is an attribution "
        "filter, not final causal proof. Source and "
        "secret findings still need changed-line or "
        "changed-hunk validation."
    ),
    "",
    (
        f"- Detailed finding attribution: "
        f"`{detail_csv}`"
    ),
    (
        f"- Region summary: "
        f"`{region_csv}`"
    ),
])


report_text = "\n".join(
    lines
)

report_path.write_text(
    report_text,
    encoding="utf-8",
)

print(report_text)

print()
print(
    "report="
    + str(report_path)
)

print(
    "attribution_csv="
    + str(detail_csv)
)

print(
    "region_csv="
    + str(region_csv)
)


try:
    import matplotlib.pyplot as plt

    chart_regions = [
        str(
            row["primary_region"]
            or "unknown"
        )
        for row in primary_regions
    ]

    chart_counts = [
        int(row["cases"])
        for row in primary_regions
    ]

    plt.figure(
        figsize=(11, 6)
    )

    plt.bar(
        chart_regions,
        chart_counts,
    )

    plt.title(
        "Primary artifact region across mined cases"
    )

    plt.xlabel(
        "Primary artifact region"
    )

    plt.ylabel(
        "Cases"
    )

    plt.xticks(
        rotation=35,
        ha="right",
    )

    plt.tight_layout()

    region_chart = (
        out_dir
        / "primary-region-cases.png"
    )

    plt.savefig(
        region_chart,
        dpi=180,
    )

    plt.close()

    scanners = [
        scanner
        for scanner in scanner_order
        if scanner_totals[
            scanner
        ] > 0
    ]

    added = [
        scanner_added_lock[
            scanner
        ]
        for scanner in scanners
    ]

    modified = [
        scanner_modified_lock[
            scanner
        ]
        for scanner in scanners
    ]

    other_exact = [
        (
            scanner_exact[scanner]
            - scanner_added_lock[scanner]
            - scanner_modified_lock[scanner]
        )
        for scanner in scanners
    ]

    unmatched = [
        (
            scanner_unmatched[scanner]
            + scanner_missing_target[scanner]
        )
        for scanner in scanners
    ]

    plt.figure(
        figsize=(10, 6)
    )

    plt.bar(
        scanners,
        added,
        label="Added lockfile",
    )

    plt.bar(
        scanners,
        modified,
        bottom=added,
        label="Modified lockfile",
    )

    bottom_two = [
        first + second
        for first, second
        in zip(
            added,
            modified,
        )
    ]

    plt.bar(
        scanners,
        other_exact,
        bottom=bottom_two,
        label="Other exact changed file",
    )

    bottom_three = [
        first + second + third
        for first, second, third
        in zip(
            added,
            modified,
            other_exact,
        )
    ]

    plt.bar(
        scanners,
        unmatched,
        bottom=bottom_three,
        label="Missing/unmatched target",
    )

    plt.title(
        "Introduced findings by changed-file relationship"
    )

    plt.xlabel(
        "Scanner"
    )

    plt.ylabel(
        "Findings"
    )

    plt.legend()
    plt.tight_layout()

    attribution_chart = (
        out_dir
        / "finding-file-relationship.png"
    )

    plt.savefig(
        attribution_chart,
        dpi=180,
    )

    plt.close()

    print(
        "region_chart="
        + str(region_chart)
    )

    print(
        "attribution_chart="
        + str(attribution_chart)
    )

except Exception as error:
    print(
        "chart_generation_skipped="
        + repr(error)
    )


connection.close()

print(
    "FILE_FACT_INSIGHTS_READY"
)
