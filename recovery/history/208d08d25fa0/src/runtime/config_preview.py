"""Pure preview of selected historical miner settings; NOT load_settings().

Accepts explicit dictionaries; never reads ambient env, config files, GitHub,
SQLite, or performs filesystem writes. Does not contain credential values.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LimitsPreview:
    max_repos: int | None
    max_prs: int | None
    max_cases: int | None
    max_cases_per_repo: int | None
    max_seconds: int | None


@dataclass(frozen=True)
class SettingsPreview:
    config_path: Path
    db_path: Path
    token_source: str | None
    limits: LimitsPreview
    github_language: str | None
    github_languages: tuple[str, ...]
    scanner_env_overrides: tuple[tuple[str, bool], ...]


_SCANNER_ENV = (
    ("SCAN_CODEQL", "codeql"),
    ("SCAN_GITLEAKS", "gitleaks"),
    ("SCAN_OSV", "osv"),
    ("SCAN_DEPENDENCY_DOWNGRADE", "dependency_downgrade"),
    ("SCAN_SEMGREP", "semgrep"),
)
_TRUE = {"1", "true", "yes", "on"}


def _int_env(environ: Mapping[str, str], name: str, default: int | None) -> int | None:
    value = environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _path(base: Path, value: str) -> Path:
    if value.startswith("~"):
        raise ValueError("Home-relative paths are deliberately not previewed")
    candidate = Path(value)
    return candidate if candidate.is_absolute() else base / candidate


def preview_settings(
    project_root: Path,
    decoded_config: Mapping[str, Any],
    environ: Mapping[str, str],
) -> SettingsPreview:
    """Preview path/token/limit precedence without invoking the legacy loader.

    Only the listed subset is covered. The caller supplies decoded_config and
    environ explicitly; no ambient state is accessed. Token *names*, not values,
    are reported. This is not a production replacement for the miner loader.
    """
    root = Path(project_root)
    if not root.is_absolute():
        raise ValueError("project_root must be absolute")
    if not isinstance(decoded_config, Mapping):
        raise TypeError("decoded_config must be a mapping")
    database = decoded_config.get("database") or {}
    collection = decoded_config.get("collection") or {}
    github = decoded_config.get("github") or {}
    if not all(isinstance(section, Mapping) for section in (database, collection, github)):
        raise TypeError("database, collection and github must be mappings")

    config_path = _path(root, str(environ.get("CONFIG") or "config.yml"))
    db_path = _path(root, str(environ.get("DB_PATH") or database.get("path") or "data/miner.db"))
    token_source = next(
        (key for key in ("GITHUB_TOKENS", "GITHUB_TOKEN", "GH_TOKEN") if environ.get(key)),
        None,
    )

    language = github.get("language")
    languages = github.get("languages") or []
    if isinstance(languages, str):
        languages = [languages]
    names = tuple(str(x) for x in languages)
    primary = str(language) if language is not None else None

    single = str(environ.get("GITHUB_LANGUAGE") or "").strip()
    if single:
        primary = single
        names = (single,)
    plural = str(environ.get("GITHUB_LANGUAGES") or "")
    if plural:
        parsed = tuple(x.strip() for x in plural.split(",") if x.strip())
        names = parsed
        if parsed and not single:
            primary = parsed[0]

    overrides = tuple(
        (key, str(environ[env_name]).strip().lower() in _TRUE)
        for env_name, key in _SCANNER_ENV
        if environ.get(env_name) not in (None, "")
    )
    fallback = collection.get("max_cases_per_repo", 10)
    try:
        fallback = int(fallback) if fallback is not None else None
    except (TypeError, ValueError):
        fallback = None

    return SettingsPreview(
        config_path=config_path,
        db_path=db_path,
        token_source=token_source,
        limits=LimitsPreview(
            max_repos=_int_env(environ, "MAX_REPOS", None),
            max_prs=_int_env(environ, "MAX_PRS", None),
            max_cases=_int_env(environ, "MAX_CASES", None),
            max_cases_per_repo=_int_env(environ, "MAX_CASES_PER_REPO", fallback),
            max_seconds=_int_env(environ, "MAX_SECONDS", None),
        ),
        github_language=primary,
        github_languages=names,
        scanner_env_overrides=overrides,
    )
