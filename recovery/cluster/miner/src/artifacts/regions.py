from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import PurePosixPath
from typing import Any, Iterable

SOURCE_EXTS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue",
    ".go", ".java", ".kt", ".kts", ".rb", ".cs", ".c", ".cc", ".cpp", ".cxx",
    ".h", ".hpp", ".hh", ".hxx", ".rs", ".php", ".swift", ".scala",
}
SCRIPT_EXTS = {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd"}
MACHINE_READABLE_EXTS = {
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg", ".conf",
    ".properties", ".hcl", ".tf", ".tfvars", ".lock", ".env", ".service",
}
PROSE_EXTS = {".md", ".rst", ".txt", ".adoc"}
ASSET_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".pdf", ".mp4", ".mov",
    ".woff", ".woff2", ".ttf", ".eot", ".map",
}
DEPENDENCY_NAMES = {
    "requirements.txt", "requirements-dev.txt", "requirements-test.txt", "dev-requirements.txt",
    "pyproject.toml", "setup.py", "setup.cfg", "pipfile", "pipfile.lock", "poetry.lock",
    "uv.lock", "pdm.lock", "environment.yml", "environment.yaml", "tox.ini",
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lockb", "bun.lock", "gemfile", "gemfile.lock", "go.mod", "go.sum", "pom.xml",
    "build.gradle", "build.gradle.kts", "gradle.lockfile", "packages.config", "packages.lock.json",
    "cargo.toml", "cargo.lock", "composer.json", "composer.lock",
}
CI_PREFIXES = (
    ".github/workflows/", ".github/actions/", ".gitlab/ci/", ".circleci/", ".azure-pipelines/",
)
CI_NAMES = {"jenkinsfile", ".gitlab-ci.yml", "circle.yml", "azure-pipelines.yml", "azure-pipelines.yaml"}
DEPLOYMENT_NAMES = {
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    "kubernetes.yml", "kubernetes.yaml", "kustomization.yaml", "helmfile.yaml", "chart.yaml",
    "serverless.yml", "serverless.yaml", "terraform.tf", "main.tf", "variables.tf", "outputs.tf",
}
SECRET_NAMES = {".env", ".env.local", ".env.production", "secrets.yml", "secrets.yaml", "credentials.yml", "credentials.yaml"}
AGENTIC_TERMS = (
    "mcp", "agent", "agents", "tool", "tools", "tool_call", "function_call", "openai", "anthropic",
    "claude", "codex", "prompt", "prompts", "aider", "cursor", "devin", "llm",
)
VENDOR_PARTS = {"vendor", "vendors", "third_party", "third-party", "node_modules", "dist", "build", "coverage"}
GENERATED_TERMS = ("generated", "autogen", "auto-generated", "mock", "mocks", "pb.go", ".pb.", "swagger", "openapi")

REGION_ROUTES = {
    "source_code": ["semgrep_source", "codeql"],
    "dependency_config": ["dependency_downgrade", "osv_dependency", "trivy_vuln"],
    "ci_workflow": ["workflow_risk", "secret_ci", "trivy_misconfig"],
    "secret_config": ["secret_ci", "trivy_secret"],
    "deployment_iac": ["trivy_misconfig", "checkov_iac"],
    "script_execution": ["semgrep_script", "secret_ci"],
    "agentic_tooling": ["agentic_tooling", "semgrep_source", "codeql"],
    "unknown_machine_readable": ["trivy", "secret_ci", "manual_sample"],
    "generated_vendor": ["low_priority_sample"],
    "non_behavioral": [],
}

@dataclass(frozen=True)
class ArtifactClassification:
    path: str
    region: str
    language: str | None
    generated: bool
    vendor: bool
    scanner_routes: list[str]
    confidence: str
    evidence: str


def _norm(path: str) -> str:
    return (path or "").replace("\\", "/").lstrip("/")


def _parts(path: str) -> list[str]:
    return [p.lower() for p in _norm(path).split("/") if p]


def _name(path: str) -> str:
    return PurePosixPath(_norm(path)).name.lower()


def _suffix(path: str) -> str:
    return PurePosixPath(_norm(path)).suffix.lower()


def _language(path: str) -> str | None:
    ext = _suffix(path)
    return {
        ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
        ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".java": "Java",
        ".kt": "Kotlin", ".kts": "Kotlin", ".rb": "Ruby", ".cs": "C#", ".c": "C/C++",
        ".cc": "C/C++", ".cpp": "C/C++", ".cxx": "C/C++", ".h": "C/C++", ".hpp": "C/C++",
        ".rs": "Rust", ".php": "PHP", ".sh": "Shell", ".ps1": "PowerShell",
        ".yaml": "YAML", ".yml": "YAML", ".json": "JSON", ".toml": "TOML", ".xml": "XML",
        ".tf": "HCL", ".hcl": "HCL",
    }.get(ext)


def is_vendor_or_generated(path: str) -> tuple[bool, bool]:
    npath = _norm(path).lower()
    parts = set(_parts(path))
    vendor = bool(parts & VENDOR_PARTS)
    generated = any(term in npath for term in GENERATED_TERMS)
    return vendor, generated


def classify_file(file: dict[str, Any] | str) -> ArtifactClassification:
    path = _norm(str(file.get("filename") or file.get("path") or "") if isinstance(file, dict) else str(file))
    lower = path.lower()
    name = _name(path)
    ext = _suffix(path)
    vendor, generated = is_vendor_or_generated(path)
    lang = _language(path)

    if vendor or generated:
        region = "generated_vendor"
        evidence = "path matched generated/vendor heuristic"
    elif lower.startswith(CI_PREFIXES) or name in CI_NAMES:
        region = "ci_workflow"
        evidence = "CI/workflow path"
    elif name in SECRET_NAMES or "/secrets/" in f"/{lower}/" or "credential" in lower:
        region = "secret_config"
        evidence = "secret/credential config path"
    elif name in DEPENDENCY_NAMES or (lower.startswith("requirements/") and ext == ".txt"):
        region = "dependency_config"
        evidence = "dependency manifest or lockfile"
    elif name in DEPLOYMENT_NAMES or ext in {".tf", ".tfvars"} or "/helm/" in f"/{lower}/" or "/k8s/" in f"/{lower}/" or "/kubernetes/" in f"/{lower}/":
        region = "deployment_iac"
        evidence = "deployment/IaC artifact"
    elif ext in SCRIPT_EXTS or name in {"makefile", "rakefile", "justfile"}:
        region = "script_execution"
        evidence = "script/execution artifact"
    elif any(re.search(rf"(^|[/_.-]){re.escape(term)}($|[/_.-])", lower) for term in AGENTIC_TERMS) and ext in SOURCE_EXTS | MACHINE_READABLE_EXTS:
        region = "agentic_tooling"
        evidence = "agentic/tooling path term"
    elif ext in SOURCE_EXTS:
        region = "source_code"
        evidence = "source code extension"
    elif ext in MACHINE_READABLE_EXTS:
        region = "unknown_machine_readable"
        evidence = "machine-readable artifact not matched to known region"
    elif ext in PROSE_EXTS or ext in ASSET_EXTS or lower.startswith(("docs/", "doc/", "examples/")):
        region = "non_behavioral"
        evidence = "prose/documentation/asset artifact"
    else:
        region = "unknown_machine_readable" if ext else "non_behavioral"
        evidence = "unknown extension; conservatively retained" if ext else "no extension / likely non-behavioral"

    return ArtifactClassification(
        path=path,
        region=region,
        language=lang,
        generated=generated,
        vendor=vendor,
        scanner_routes=list(REGION_ROUTES[region]),
        confidence="high" if region not in {"unknown_machine_readable", "generated_vendor"} else "medium",
        evidence=evidence,
    )


def classify_files(files: Iterable[dict[str, Any] | str]) -> list[ArtifactClassification]:
    return [classify_file(f) for f in files]


def profile_summary(classifications: Iterable[ArtifactClassification]) -> dict[str, Any]:
    classes = list(classifications)
    counts: dict[str, int] = {}
    routes: set[str] = set()
    languages: set[str] = set()
    for c in classes:
        counts[c.region] = counts.get(c.region, 0) + 1
        routes.update(c.scanner_routes)
        if c.language:
            languages.add(c.language)
    primary_region = "non_behavioral"
    if counts:
        primary_region = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return {
        "primary_region": primary_region,
        "region_counts": counts,
        "scanner_routes": sorted(routes),
        "languages": sorted(languages),
        "file_count": len(classes),
    }


def profile_json(files: Iterable[dict[str, Any] | str]) -> str:
    classes = classify_files(files)
    return json.dumps({
        "summary": profile_summary(classes),
        "files": [asdict(c) for c in classes],
    }, sort_keys=True)
