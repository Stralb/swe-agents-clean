from miner.filters.tool_applicability import (
    has_high_yield_downstream_surface,
    high_yield_surface_reasons,
)


def test_plain_ui_component_is_observable_but_not_high_yield_by_default():
    files = [{"filename": "apps/web/src/components/Button.tsx", "patch": "+export function Button() { return <div/> }"}]
    assert not has_high_yield_downstream_surface(files)


def test_security_sensitive_source_path_is_high_yield():
    files = [{"filename": "apps/api/routes/auth/callback.ts", "patch": "+export async function GET(req) { return fetch(url) }"}]
    reasons = high_yield_surface_reasons(files)
    assert reasons
    assert reasons[0].startswith("security_path:")


def test_dependency_and_ci_are_high_yield():
    files = [
        {"filename": "package.json", "patch": "+  \"lodash\": \"4.17.20\""},
        {"filename": ".github/workflows/build.yml", "patch": "+permissions: write-all"},
    ]
    reasons = high_yield_surface_reasons(files)
    assert any(r.startswith("dependency:") for r in reasons)
    assert any(r.startswith("ci_security:") for r in reasons)


def test_sensitive_patch_content_is_high_yield_even_in_generic_source_path():
    files = [{"filename": "src/utils/client.ts", "patch": "+const token = process.env.API_TOKEN\n+fetch(url, { headers: { Authorization: token }})"}]
    assert has_high_yield_downstream_surface(files)
