from __future__ import annotations

from pathlib import PurePosixPath
from typing import Iterable

# Conservative behaviour-affecting file classifier.
# Rule: keep ambiguous files. Exclude only PRs whose changed files are all clearly
# non-behavioural prose/assets/legal/release-note artifacts.

SOURCE_EXTS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".cs", ".rb", ".php",
    ".swift", ".kt", ".kts", ".scala", ".sh", ".bash", ".zsh", ".fish", ".ps1",
}

DEPENDENCY_NAMES = {
    "requirements.txt", "requirements-dev.txt", "requirements-test.txt", "requirements.in",
    "pyproject.toml", "poetry.lock", "pipfile", "pipfile.lock", "setup.py", "setup.cfg",
    "environment.yml", "environment.yaml", "conda.yml", "conda.yaml", "uv.lock",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
}

BUILD_CONFIG_NAMES = {
    "tox.ini", "noxfile.py", "pytest.ini", "mypy.ini", "ruff.toml", ".ruff.toml",
    ".pre-commit-config.yaml", ".pre-commit-config.yml", "makefile", "cmakelists.txt",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "jenkinsfile",
    ".gitlab-ci.yml", "azure-pipelines.yml", "manifest.in", "hatch.toml",
}

MACHINE_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".lock", ".ipynb"}
PROSE_EXTS = {".md", ".rst", ".adoc"}
ASSET_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".pdf", ".mp4", ".mov",
    ".avi", ".mp3", ".wav", ".woff", ".woff2", ".ttf", ".eot",
}
PROSE_NAMES = {
    "readme", "readme.md", "readme.rst", "changelog", "changelog.md", "history.md",
    "license", "license.md", "copying", "citation.cff", "code_of_conduct.md",
    "contributing.md", "authors.md", "notice", "notice.md", "security.md",
}


def _parts(path: str) -> list[str]:
    return [p.lower() for p in PurePosixPath(path).parts if p and p != "."]


def categorize_file(filename: str) -> str:
    """Return a conservative file category.

    Categories:
      - source / test / script / dependency / ci / build_config / deployment are behaviour-affecting.
      - non_behaviour is clearly prose/assets/legal/release-only.
      - ambiguous is retained by the collector.
    """
    path = (filename or "").strip()
    lower = path.lower()
    pp = PurePosixPath(path)
    name = pp.name.lower()
    suffix = pp.suffix.lower()
    parts = _parts(path)

    if not path:
        return "ambiguous"

    if lower.startswith(".github/workflows/") or lower.startswith(".github/actions/"):
        return "ci"
    if name in {n.lower() for n in DEPENDENCY_NAMES}:
        return "dependency"
    if name in {n.lower() for n in BUILD_CONFIG_NAMES}:
        return "build_config"
    if "dockerfile" in name:
        return "deployment"
    if any(p in {"k8s", "kubernetes", "helm", "charts", "deploy", "deployment"} for p in parts):
        if suffix in MACHINE_EXTS or not suffix:
            return "deployment"
    if suffix in SOURCE_EXTS:
        if any(p in {"test", "tests", "testing"} for p in parts) or name.startswith("test_") or name.endswith("_test.py") or ".test." in name or ".spec." in name:
            return "test"
        if any(p in {"scripts", "tools", "bin"} for p in parts):
            return "script"
        return "source"
    if name in PROSE_NAMES or suffix in PROSE_EXTS:
        return "non_behaviour"
    if suffix in ASSET_EXTS:
        return "non_behaviour"
    # Treat text as prose unless it is a known dependency file handled above.
    if suffix == ".txt":
        return "non_behaviour"
    # Machine-readable or unknown files may affect behaviour; keep them.
    if suffix in MACHINE_EXTS:
        return "ambiguous"
    return "ambiguous"


def enrich_files(files: list[dict]) -> list[dict]:
    for f in files:
        f["category"] = categorize_file(f.get("filename", ""))
    return files


def classify_pr_files(files: Iterable[dict]) -> str:
    categories = [categorize_file(f.get("filename", "")) for f in files]
    if not categories:
        return "non_behaviour_only"
    behaviour = {"source", "test", "script", "dependency", "ci", "build_config", "deployment"}
    if any(c in behaviour for c in categories):
        return "behaviour_affecting"
    if all(c == "non_behaviour" for c in categories):
        return "non_behaviour_only"
    return "ambiguous"


def has_relevant_file(files: list[dict]) -> bool:
    return classify_pr_files(files) in {"behaviour_affecting", "ambiguous"}


def is_docs_only(files: list[dict]) -> bool:
    return classify_pr_files(files) == "non_behaviour_only"

DOC_SCOPE_DIRS = {"doc", "docs", "documentation", "site", "website"}
DOC_SCOPE_NAMES = PROSE_NAMES | {"conf.py", "mkdocs.yml", "mkdocs.yaml"}


def is_docs_scope_only(files: Iterable[dict]) -> bool:
    """Return true when every changed file is confined to documentation scope.

    This is stricter than `non_behaviour_only`: it catches documentation config
    files such as docs/conf.py that are syntactically Python but are not a
    meaningful downstream source/dependency/CI artifact for this study. The rule
    is deliberately mechanical and only excludes a PR when *all* changed files
    are documentation-scoped.
    """
    file_list = list(files)
    if not file_list:
        return False
    for f in file_list:
        path = str(f.get("filename") or "").strip()
        if not path:
            return False
        lower = path.lower()
        parts = _parts(path)
        name = PurePosixPath(path).name.lower()
        suffix = PurePosixPath(path).suffix.lower()
        # Any explicit downstream artifact means it is not docs-only.
        if lower.startswith(".github/workflows/") or lower.startswith(".github/actions/"):
            return False
        if name in {n.lower() for n in DEPENDENCY_NAMES}:
            return False
        if name in {n.lower() for n in BUILD_CONFIG_NAMES} and not (parts and parts[0] in DOC_SCOPE_DIRS):
            return False
        if any(p in {"src", "lib", "app", "apps", "package", "packages"} for p in parts):
            return False
        # Documentation directories are docs-scoped even for docs/conf.py.
        if parts and parts[0] in DOC_SCOPE_DIRS:
            continue
        if name in DOC_SCOPE_NAMES or suffix in PROSE_EXTS or suffix in ASSET_EXTS:
            continue
        return False
    return True


JS_TS_SOURCE_EXTS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts",
}

JS_TS_ECOSYSTEM_NAMES = {
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "bun.lockb",
    ".npmrc",
    ".yarnrc",
    ".yarnrc.yml",
    "jsconfig.json",
    "tsconfig.json",
    "deno.json",
    "deno.jsonc",
}

JS_TS_CONFIG_PREFIXES = (
    "tsconfig.",
    "jsconfig.",
    "eslint.config.",
    ".eslintrc",
    "prettier.config.",
    ".prettierrc",
    "babel.config.",
    ".babelrc",
    "webpack.config.",
    "vite.config.",
    "vitest.config.",
    "jest.config.",
    "rollup.config.",
    "next.config.",
    "nuxt.config.",
    "svelte.config.",
    "astro.config.",
)


def has_javascript_typescript_surface(files: Iterable[dict]) -> bool:
    """Require a changed artifact relevant to the JS/TS ecosystem.

    This includes JS/TS source, package manifests/lockfiles, common JS tooling
    configuration, CI workflows in a JS/TS repository, and explicit scripts.
    """

    for file_info in files:
        path = str(file_info.get("filename") or "").strip()
        if not path:
            continue

        lower = path.lower()
        pp = PurePosixPath(path)
        name = pp.name.lower()
        suffix = pp.suffix.lower()
        parts = _parts(path)

        if suffix in JS_TS_SOURCE_EXTS:
            return True

        if name in JS_TS_ECOSYSTEM_NAMES:
            return True

        if name.startswith(JS_TS_CONFIG_PREFIXES):
            return True

        if lower.startswith(".github/workflows/"):
            return True

        if suffix in {".sh", ".bash", ".zsh", ".ps1"} and any(
            part in {"script", "scripts", "tool", "tools", "bin"}
            for part in parts
        ):
            return True

    return False
