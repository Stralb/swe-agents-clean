from src.filters.pr_filters import categorize_file, classify_pr_files


def files(*names):
    return [{"filename": n} for n in names]


def test_docs_and_assets_are_non_behaviour_only():
    assert classify_pr_files(files("README.md")) == "non_behaviour_only"
    assert classify_pr_files(files("docs/usage.rst", "docs/logo.png")) == "non_behaviour_only"
    assert classify_pr_files(files("CHANGELOG.md", "LICENSE")) == "non_behaviour_only"


def test_behaviour_affecting_files_are_kept():
    assert classify_pr_files(files("src/app.py")) == "behaviour_affecting"
    assert classify_pr_files(files("tests/test_auth.py")) == "behaviour_affecting"
    assert classify_pr_files(files(".github/workflows/ci.yml")) == "behaviour_affecting"
    assert classify_pr_files(files("requirements.txt")) == "behaviour_affecting"
    assert classify_pr_files(files("pyproject.toml")) == "behaviour_affecting"
    assert classify_pr_files(files("examples/demo.py")) == "behaviour_affecting"


def test_ambiguous_machine_readable_files_are_kept():
    assert classify_pr_files(files("docs/mkdocs.yml")) == "ambiguous"
    assert classify_pr_files(files("data/schema.json")) == "ambiguous"
    assert classify_pr_files(files("notebooks/tutorial.ipynb")) == "ambiguous"

from src.filters.pr_filters import is_docs_scope_only


def test_docs_scope_only_catches_docs_conf_py_but_not_source_or_dependency():
    assert is_docs_scope_only(files("docs/conf.py"))
    assert is_docs_scope_only(files("docs/conf.py", "docs/index.rst"))
    assert not is_docs_scope_only(files("docs/conf.py", "src/app.py"))
    assert not is_docs_scope_only(files("docs/conf.py", "requirements.txt"))
