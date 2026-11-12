"""Strict synthetic-to-exact-original dependency-diff provider.

This is the original byte-preserved pure parser, not a scanner response stub.
Never accept a live repo, arbitrary PR path, or unpublished patch. The owning
harness also rejects non-disposable DBs and non-example.invalid case URLs.
"""
from __future__ import annotations

from src.scanners.dependency_diff import detect_dependency_regressions
from tests.support.archived_fixture_scan_case import (
    FixtureScannerProviders, MissingScannerFixture,
)


class OriginalDependencyDiffProvider(FixtureScannerProviders):
    """Execute original parsing only on a single explicitly allowed test patch."""

    def __init__(self, *, expected_patch, filename="fixture/requirements.txt"):
        super().__init__()
        if not filename.startswith("fixture/") or not filename.endswith("requirements.txt"):
            raise ValueError("Original provider requires a fixture/requirements.txt path")
        if expected_patch is not None and not isinstance(expected_patch, str):
            raise TypeError("Expected fixture patch must be a string or None")
        self.filename = filename
        self.expected_patch = expected_patch

    def detect_dependency_regressions(self, files):
        if (
            not isinstance(files, list)
            or len(files) != 1
            or not isinstance(files[0], dict)
            or files[0].get("filename") != self.filename
            or files[0].get("patch") != self.expected_patch
            or files[0].get("category") != "dependency"
        ):
            raise MissingScannerFixture(
                "Exact original dependency parser refuses non-approved synthetic files"
            )
        self.calls.append(("dependency-diff-original", len(files)))
        return detect_dependency_regressions(files)
