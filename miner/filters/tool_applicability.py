from __future__ import annotations

from pathlib import PurePosixPath
import os
from typing import Any, Iterable

from miner.artifacts.regions import classify_files, profile_summary

PYTHON_EXTENSIONS = (".py", ".pyi")
JAVASCRIPT_TYPESCRIPT_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue")
RUBY_EXTENSIONS = (".rb",)
GO_EXTENSIONS = (".go",)
CSHARP_EXTENSIONS = (".cs",)
JAVA_KOTLIN_EXTENSIONS = (".java", ".kt", ".kts")
C_CPP_EXTENSIONS = (".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh", ".hxx")

CODEQL_LANGUAGE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "python": PYTHON_EXTENSIONS,
    "javascript-typescript": JAVASCRIPT_TYPESCRIPT_EXTENSIONS,
    "ruby": RUBY_EXTENSIONS,
    "go": GO_EXTENSIONS,
    "csharp": CSHARP_EXTENSIONS,
    "java-kotlin": JAVA_KOTLIN_EXTENSIONS,
    "c-cpp": C_CPP_EXTENSIONS,
}

CODEQL_SOURCE_EXTENSIONS = tuple(ext for exts in CODEQL_LANGUAGE_EXTENSIONS.values() for ext in exts)

DEPENDENCY_FILENAMES = {
    # Python
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "dev-requirements.txt",
    "test-requirements.txt",
    "requirements.in",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
    "uv.lock",
    "pdm.lock",
    "environment.yml",
    "environment.yaml",
    "conda.yml",
    "conda.yaml",
    "tox.ini",
    # JavaScript / TypeScript / Node
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "bun.lock",
    # Ruby
    "gemfile",
    "gemfile.lock",
    "gems.rb",
    "gems.locked",
    # Go
    "go.mod",
    "go.sum",
    # Java / JVM
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "gradle.lockfile",
    # .NET
    "packages.config",
    "packages.lock.json",
    "global.json",
    # Rust / PHP / misc ecosystems useful for OSV-like evidence
    "cargo.toml",
    "cargo.lock",
    "composer.json",
    "composer.lock",
}

CI_SECURITY_FILENAMES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "jenkinsfile",
    "gitlab-ci.yml",
    "circle.yml",
}

CI_SECURITY_PATH_PREFIXES = (
    ".github/workflows/",
    ".github/actions/",
    ".gitlab/ci/",
    ".circleci/",
    ".azure-pipelines/",
)

CI_SECURITY_PATH_SUFFIXES = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    "azure-pipelines.yml",
    "azure-pipelines.yaml",
)


# Downstream high-yield surfaces are used only for scan prioritisation / evidence
# candidacy. They are based on the PR artifacts and patch, not upstream issue words.
SECURITY_SENSITIVE_PATH_TERMS = (
    "auth", "oauth", "login", "logout", "token", "secret", "credential", "password",
    "permission", "policy", "role", "rbac", "session", "cookie", "csrf", "cors",
    "webhook", "callback", "api/", "routes/", "server", "middleware", "controller",
    "database", "db/", "query", "sql", "supabase", "prisma", "migration",
    "crypto", "encrypt", "decrypt", "hash", "signature", "verify", "validate",
    "sanitize", "escape", "upload", "download", "file", "path", "proxy", "fetch",
    "request", "http", "exec", "spawn", "shell", "command", "process",
    "tauri", "electron", "pair", "pairing", "deeplink", "deep-link", "qr",
)

SECURITY_SENSITIVE_PATCH_TERMS = (
    "auth", "oauth", "token", "secret", "password", "credential", "permission",
    "session", "cookie", "csrf", "cors", "webhook", "callback", "bearer",
    "process.env", "import.meta.env", "github_token", "secrets.", "id-token",
    "fetch(", "axios", "request(", "http://", "https://", "supabase",
    "prisma", "select ", "insert ", "update ", "delete ", "sql",
    "eval(", "exec(", "spawn(", "shell", "child_process", "subprocess",
    "pickle", "yaml.load", "deserialize", "innerhtml", "dangerouslysetinnerhtml",
    "verify", "validate", "sanitize", "bypass", "allow", "deny",
)

LOW_VALUE_SOURCE_PATH_TERMS = (
    "/components/", "/ui/", "/styles/", ".css", ".scss", ".less",
    "storybook", "stories.", "/icons/", "/theme/", "/themes/",
)

def _strict_evidence_surface() -> bool:
    return os.getenv("EVIDENCE_STRICT_SURFACE", "").strip().lower() in {"1", "true", "yes", "on"}

def changed_file_count(files: Iterable[dict[str, Any] | str]) -> int:
    return len(list(files))

def high_yield_surface_reasons(files: Iterable[dict[str, Any] | str]) -> list[str]:
    file_list = list(files)
    reasons: list[str] = []
    for f in file_list:
        path = _norm(_path(f))
        name = _name(path)
        patch = str(f.get("patch") or "").lower() if isinstance(f, dict) else ""
        if is_dependency_file(path):
            reasons.append(f"dependency:{path}")
            continue
        if is_ci_security_file(path):
            reasons.append(f"ci_security:{path}")
            continue
        if is_codeql_source_file(path):
            if any(term in path for term in SECURITY_SENSITIVE_PATH_TERMS):
                reasons.append(f"security_path:{path}")
                continue
            added_text = "\n".join(
                line[1:] for line in patch.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            )
            if any(term in added_text for term in SECURITY_SENSITIVE_PATCH_TERMS):
                reasons.append(f"security_patch:{path}")
                continue
            # General source files are observable, but style-only source files
            # are lower-yield for introduced security evidence. They remain
            # structural cases when structural-only mode is added, but by default
            # do not drive expensive evidence mining.
            if not any(term in path for term in LOW_VALUE_SOURCE_PATH_TERMS):
                if not _strict_evidence_surface():
                    reasons.append(f"general_source:{path}")
                    continue
    # Deduplicate and cap for stable logs.
    out=[]
    seen=set()
    for r in reasons:
        if r not in seen:
            seen.add(r); out.append(r)
    return out[:12]

def has_high_yield_downstream_surface(files: Iterable[dict[str, Any] | str]) -> bool:
    return bool(high_yield_surface_reasons(files))

WORKER_LABELS = {
    "codeql": "CodeQL source analysis",
    "secret_ci": "Secret scanner",
    "osv_dependency": "OSV dependency scan",
    "trivy_dependency": "Trivy dependency scan",
    "dependency_downgrade": "Dependency downgrade detector",
    "ci_security": "CI/workflow security artifact",
}

PRIMARY_WORKER_KEYS = {"codeql", "osv_dependency", "trivy_dependency", "dependency_downgrade", "ci_security"}


def _path(file: dict[str, Any] | str) -> str:
    if isinstance(file, str):
        return file
    return str(file.get("filename") or file.get("path") or "")


def _name(path: str) -> str:
    return PurePosixPath(path).name.lower()


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("/").lower()


def is_python_file(path: str) -> bool:
    return path.lower().endswith(PYTHON_EXTENSIONS)


def is_codeql_source_file(path: str) -> bool:
    return path.lower().endswith(CODEQL_SOURCE_EXTENSIONS)


def codeql_languages_for_paths(paths: Iterable[str]) -> list[str]:
    detected: list[str] = []
    lower_paths = [p.lower() for p in paths]
    for language, extensions in CODEQL_LANGUAGE_EXTENSIONS.items():
        if any(p.endswith(extensions) for p in lower_paths):
            detected.append(language)
    return detected


def is_dependency_file(path: str) -> bool:
    lower = _norm(path)
    name = _name(lower)
    return name in DEPENDENCY_FILENAMES or (lower.startswith("requirements/") and lower.endswith(".txt"))


def is_ci_security_file(path: str) -> bool:
    lower = _norm(path)
    name = _name(lower)
    return (
        name in CI_SECURITY_FILENAMES
        or any(lower.startswith(prefix) for prefix in CI_SECURITY_PATH_PREFIXES)
        or any(lower.endswith(suffix) for suffix in CI_SECURITY_PATH_SUFFIXES)
    )


def has_patch(file: dict[str, Any] | str) -> bool:
    return isinstance(file, dict) and bool(str(file.get("patch") or "").strip())


def has_added_lines(file: dict[str, Any]) -> bool:
    patch = str(file.get("patch") or "")
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            return True
    return False


def route_reasons(files: Iterable[dict[str, Any] | str]) -> dict[str, str]:
    """Return downstream-worker routes from artifact regions, not issue words.

    This is the methodology pivot: changed artifacts are first classified into
    behavioral regions; scanners are then scheduled from those regions. Keywords
    remain features for later review, never collection gates.
    """
    file_list = list(files)
    classes = classify_files(file_list)
    summary = profile_summary(classes)
    counts = summary["region_counts"]

    source_paths = [c.path for c in classes if c.region in {"source_code", "agentic_tooling", "script_execution"}]
    dep_paths = [c.path for c in classes if c.region == "dependency_config"]
    ci_paths = [c.path for c in classes if c.region == "ci_workflow"]
    secret_paths = [c.path for c in classes if c.region == "secret_config"]
    unknown_paths = [c.path for c in classes if c.region == "unknown_machine_readable"]
    patch_paths = [_path(f) for f in file_list if isinstance(f, dict) and has_added_lines(f)]

    routes: dict[str, str] = {}
    if source_paths:
        langs = ",".join(codeql_languages_for_paths(source_paths)) or ",".join(summary.get("languages") or []) or "unknown"
        routes["codeql"] = "artifact_regions=source/agent/script languages=%s paths=%s" % (langs, ", ".join(source_paths[:8]))
    else:
        routes["codeql"] = "not_applicable:no_source_code_region"

    if dep_paths:
        desc = ", ".join(dep_paths[:8])
        routes["osv_dependency"] = "artifact_region=dependency_config paths=" + desc
        routes["trivy_dependency"] = "artifact_region=dependency_config paths=" + desc
        routes["dependency_downgrade"] = "artifact_region=dependency_config paths=" + desc
    else:
        routes["osv_dependency"] = "not_applicable:no_dependency_config_region"
        routes["trivy_dependency"] = "not_applicable:no_dependency_config_region"
        routes["dependency_downgrade"] = "not_applicable:no_dependency_config_region"

    broad_paths = ci_paths + secret_paths + unknown_paths + patch_paths
    if broad_paths:
        routes["secret_ci"] = "artifact_regions=ci/secret/unknown/patch paths=" + ", ".join(broad_paths[:8])
    else:
        routes["secret_ci"] = "not_applicable:no_secret_or_patch_scan_region"

    routes["artifact_profile"] = "regions=" + ",".join(f"{k}:{v}" for k, v in sorted(counts.items()))
    return routes


def has_primary_applicable_downstream_worker(files: Iterable[dict[str, Any] | str]) -> bool:
    routes = route_reasons(files)
    return any(not routes.get(k, "").startswith("not_applicable:") for k in PRIMARY_WORKER_KEYS)


def has_any_applicable_downstream_worker(files: Iterable[dict[str, Any] | str]) -> bool:
    routes = route_reasons(files)
    return any(not reason.startswith("not_applicable:") for reason in routes.values())
