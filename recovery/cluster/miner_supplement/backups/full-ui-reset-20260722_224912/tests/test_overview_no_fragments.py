from __future__ import annotations

import ast
import unittest
from pathlib import Path


class OverviewDirectRenderTests(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
        self.path = Path(
            "ui/views/overview_fast.py"
        )

        self.source = self.path.read_text(
            encoding="utf-8"
        )

    def test_fragment_wrappers_removed(
        self,
    ) -> None:
        self.assertNotIn(
            'hasattr(st, "fragment")',
            self.source,
        )

        self.assertNotIn(
            "@st.fragment",
            self.source,
        )

        self.assertNotIn(
            "st.fragment(",
            self.source,
        )

    def test_live_status_directly_calls_renderer(
        self,
    ) -> None:
        self.assertIn(
            "def _live_status_fragment(",
            self.source,
        )

        self.assertIn(
            "_live_status(\n"
            "        db_path\n"
            "    )",
            self.source,
        )

    def test_research_directly_calls_renderer(
        self,
    ) -> None:
        self.assertIn(
            "def _research_fragment(",
            self.source,
        )

        self.assertIn(
            "render_research_map(\n"
            "        db_path\n"
            "    )",
            self.source,
        )

    def test_cases_use_direct_renderer(
        self,
    ) -> None:
        self.assertIn(
            "_live_cases_fragment = (\n"
            "    _case_fragment\n"
            ")",
            self.source,
        )

    def test_full_overview_flow_remains(
        self,
    ) -> None:
        required = (
            "_live_status_fragment(",
            "_research_fragment(",
            "options = filter_options(",
            "_live_cases_fragment(",
            '"overview_search"',
            '"overview_stage"',
            '"overview_region"',
            '"overview_repository"',
        )

        for token in required:
            self.assertIn(
                token,
                self.source,
            )

    def test_valid_python(
        self,
    ) -> None:
        tree = ast.parse(
            self.source,
            filename=str(self.path),
        )

        self.assertIsInstance(
            tree,
            ast.Module,
        )


if __name__ == "__main__":
    unittest.main()
