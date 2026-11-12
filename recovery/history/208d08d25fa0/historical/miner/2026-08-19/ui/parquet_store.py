#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Iterable, Sequence

import duckdb
import pandas as pd
import streamlit as st
from huggingface_hub import snapshot_download

DEFAULT_DATASET_REPO = "Stralb/malicious-issue-miner-data"
DEFAULT_DATASET_REVISION = "main"

HOT_FILES: dict[str, str] = {
    "summary_overview": "parquet/v1/summary/overview.parquet",
    "summary_cases": "parquet/v1/summary/cases.parquet",
    "summary_findings": "parquet/v1/summary/findings.parquet",
    "summary_regions": "parquet/v1/summary/regions.parquet",
    "summary_repos": "parquet/v1/summary/repos.parquet",
    "summary_timeline": "parquet/v1/summary/timeline.parquet",
    "summary_filters": "parquet/v1/summary/filter_options.parquet",
    "case_index": "parquet/v1/ui/case_index.parquet",
    "case_detail": "parquet/v1/ui/case_detail/data_0.parquet",
    "finding_index": "parquet/v1/ui/finding_index.parquet",
    "finding_detail": "parquet/v1/ui/finding_detail/data_0.parquet",
    "file_index": "parquet/v1/ui/file_index.parquet",
    "excluded_index": "parquet/v1/ui/excluded_case_index.parquet",
    "excluded_route": "parquet/v1/ui/excluded_case_route.parquet",
    "artifact_region_index": "parquet/v1/ui/artifact_region_index.parquet",
    "ai_markers": "parquet/v1/ui/ai_markers.parquet",
    "case_notes": "parquet/v1/ui/case_notes.parquet",
    "reference_repos": "parquet/v1/reference/repos.parquet",
}

VIEW_NAMES: dict[str, str] = {
    "summary_overview": "pq_summary_overview",
    "summary_cases": "pq_summary_cases",
    "summary_findings": "pq_summary_findings",
    "summary_regions": "pq_summary_regions",
    "summary_repos": "pq_summary_repos",
    "summary_timeline": "pq_summary_timeline",
    "summary_filters": "pq_summary_filters",
    "case_index": "pq_cases",
    "case_detail": "pq_case_detail",
    "finding_index": "pq_findings",
    "finding_detail": "pq_finding_detail",
    "file_index": "pq_files",
    "excluded_index": "pq_excluded",
    "excluded_route": "pq_excluded_route",
    "artifact_region_index": "pq_artifact_regions",
    "ai_markers": "pq_ai_markers",
    "case_notes": "pq_case_notes",
    "reference_repos": "pq_repos",
}


class ParquetBackendError(RuntimeError):
    pass


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _streamlit_secret_token() -> str | None:
    try:
        direct = st.secrets.get("HF_TOKEN")
        if direct:
            return str(direct)
    except Exception:
        pass

    try:
        section = st.secrets.get("hf")
        if section and section.get("token"):
            return str(section.get("token"))
    except Exception:
        pass

    return None


def _token() -> str | None:
    return (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        or _streamlit_secret_token()
        or None
    )


def _sql_quote(value: str | Path) -> str:
    return str(value).replace("'", "''")


class ParquetStore:
    """Fast read-only research store backed by HF-cached Parquet + DuckDB."""

    def __init__(
        self,
        repo_id: str,
        revision: str,
        token: str | None,
        local_files_only: bool = False,
    ) -> None:
        self.repo_id = repo_id
        self.revision = revision
        self.token = token
        self.local_files_only = local_files_only
        self._lock = threading.RLock()
        self._patch_snapshot_root: Path | None = None

        try:
            snapshot_root = snapshot_download(
                repo_id=self.repo_id,
                repo_type="dataset",
                revision=self.revision,
                allow_patterns=list(HOT_FILES.values()),
                token=self.token,
                local_files_only=self.local_files_only,
                max_workers=8,
            )
        except Exception as exc:
            raise ParquetBackendError(
                "Unable to prepare the private Hugging Face Parquet dataset. "
                "Authenticate with `hf auth login`, set HF_TOKEN, or add "
                "HF_TOKEN to Streamlit secrets. Original error: "
                f"{exc}"
            ) from exc

        self.snapshot_root = Path(snapshot_root)
        self.paths: dict[str, Path] = {
            key: self.snapshot_root / relative
            for key, relative in HOT_FILES.items()
        }

        missing = [
            f"{key}: {path}"
            for key, path in self.paths.items()
            if not path.is_file()
        ]
        if missing:
            raise ParquetBackendError(
                "The Hugging Face snapshot is missing required Parquet files:\n"
                + "\n".join(missing)
            )

        self.connection = duckdb.connect(database=":memory:")
        self._configure_duckdb()
        self._create_views()

    def _configure_duckdb(self) -> None:
        con = self.connection
        con.execute("SET threads = 4")
        con.execute("SET enable_http_metadata_cache = true")
        con.execute("SET httpfs_connection_caching = true")
        con.execute("SET parquet_metadata_cache = true")
        con.execute("SET enable_external_file_cache = true")

        try:
            con.execute("LOAD httpfs")
        except Exception:
            try:
                con.execute("INSTALL httpfs")
                con.execute("LOAD httpfs")
            except Exception as exc:
                raise ParquetBackendError(
                    "DuckDB could not load the httpfs extension required for "
                    "lazy remote detail reads."
                ) from exc

        if self.token:
            escaped = self.token.replace("'", "''")
            con.execute(
                "CREATE OR REPLACE SECRET hf_token "
                f"(TYPE huggingface, TOKEN '{escaped}')"
            )
        else:
            con.execute(
                "CREATE OR REPLACE SECRET hf_token "
                "(TYPE huggingface, PROVIDER credential_chain)"
            )

    def _create_views(self) -> None:
        for key, view_name in VIEW_NAMES.items():
            path = _sql_quote(self.paths[key])
            self.connection.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS "
                f"SELECT * FROM read_parquet('{path}')"
            )

    def query_df(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
    ) -> pd.DataFrame:
        with self._lock:
            return self.connection.execute(sql, params or []).fetchdf()

    def query(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            cursor = self.connection.execute(sql, params or [])
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def one(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
    ) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def local_path(self, key: str) -> Path:
        return self.paths[key]

    def hot_cache_rows(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for key, path in sorted(self.paths.items()):
            out.append(
                {
                    "dataset": key,
                    "size_mb": round(path.stat().st_size / 1024**2, 3),
                    "path": str(path),
                }
            )
        return out

    @property
    def hot_cache_size_bytes(self) -> int:
        return sum(path.stat().st_size for path in self.paths.values())

    def excluded_route(self, excluded_case_id: int) -> list[str]:
        rows = self.query(
            """
            SELECT DISTINCT detail_file
            FROM pq_excluded_route
            WHERE ? BETWEEN min_excluded_case_id AND max_excluded_case_id
            ORDER BY detail_file
            """,
            [int(excluded_case_id)],
        )
        return [str(row["detail_file"]) for row in rows]

    def excluded_detail(self, excluded_case_id: int) -> dict[str, Any] | None:
        candidates = self.excluded_route(excluded_case_id)
        if not candidates:
            return None

        base = (
            f"hf://datasets/{self.repo_id}/"
            "parquet/v1/ui/excluded_case_detail/"
        )
        urls = [base + filename for filename in candidates]
        sql_urls = ", ".join(f"'{_sql_quote(url)}'" for url in urls)

        return self.one(
            f"""
            SELECT excluded_case_id, details, changed_files_json
            FROM read_parquet([{sql_urls}])
            WHERE excluded_case_id = ?
            LIMIT 1
            """,
            [int(excluded_case_id)],
        )

    def _ensure_patch_snapshot(self) -> list[Path]:
        if self._patch_snapshot_root is None:
            try:
                root = snapshot_download(
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    revision=self.revision,
                    allow_patterns=["parquet/v1/ui/file_patch/*.parquet"],
                    token=self.token,
                    local_files_only=self.local_files_only,
                    max_workers=8,
                )
            except Exception as exc:
                raise ParquetBackendError(
                    "Unable to cache PR patch Parquet shards from Hugging Face."
                ) from exc
            self._patch_snapshot_root = Path(root)

        files = sorted(
            (
                self._patch_snapshot_root
                / "parquet"
                / "v1"
                / "ui"
                / "file_patch"
            ).glob("*.parquet")
        )
        if not files:
            raise ParquetBackendError("No cached file_patch Parquet shards were found.")
        return files

    def patch_detail(self, file_id: int) -> dict[str, Any] | None:
        files = self._ensure_patch_snapshot()
        glob_path = _sql_quote(files[0].parent / "*.parquet")
        return self.one(
            f"""
            SELECT file_id, pr_id, patch
            FROM read_parquet('{glob_path}')
            WHERE file_id = ?
            LIMIT 1
            """,
            [int(file_id)],
        )

    def close(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass


@st.cache_resource(show_spinner=False)
def get_parquet_store() -> ParquetStore:
    repo_id = os.getenv("HF_DATASET_REPO", DEFAULT_DATASET_REPO).strip()
    revision = os.getenv("HF_DATASET_REVISION", DEFAULT_DATASET_REVISION).strip()
    local_files_only = _truthy(os.getenv("HF_LOCAL_FILES_ONLY"))

    return ParquetStore(
        repo_id=repo_id,
        revision=revision,
        token=_token(),
        local_files_only=local_files_only,
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_query(
    sql: str,
    params: tuple[Any, ...] = (),
) -> pd.DataFrame:
    return get_parquet_store().query_df(sql, list(params))


def clear_parquet_caches() -> None:
    cached_query.clear()
