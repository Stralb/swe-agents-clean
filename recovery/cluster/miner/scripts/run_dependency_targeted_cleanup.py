#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import csv
import json
import re
import sqlite3
import subprocess
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path('/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart')
DB = ROOT / 'data' / 'miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db'
AUDIT_CSV = ROOT / 'data' / 'scanner_provenance_audit_138' / 'case_provenance_audit.csv'
OUT = ROOT / 'data' / 'dependency_targeted_cleanup_20'
CACHE = OUT / 'git_cache'
FINDING_CSV = OUT / 'dependency_finding_validation.csv'
CASE_CSV = OUT / 'dependency_case_summary.csv'
MANIFEST = OUT / 'dependency_cleanup_manifest.json'
ZIP_OUT = ROOT / 'data' / 'dependency_targeted_cleanup_20_bundle.zip'

VULN_CASES = {664, 3623, 4665, 4811, 10187, 10188, 10189, 13918, 16311}
DEPDIFF_CASES = {147, 155, 3689, 7682, 8298, 8473, 9279, 9942, 10268, 12898, 12925}
CASE_IDS = sorted(VULN_CASES | DEPDIFF_CASES)

DEP_FILES = (
    'requirements.txt', 'requirements-dev.txt', 'requirements-test.txt', 'dev-requirements.txt',
    'test-requirements.txt', 'requirements.in', 'pyproject.toml', 'setup.py', 'setup.cfg',
    'pipfile', 'pipfile.lock', 'poetry.lock', 'uv.lock', 'pdm.lock', 'environment.yml',
    'environment.yaml', 'conda.yml', 'conda.yaml', 'tox.ini', 'package.json',
    'package-lock.json', 'npm-shrinkwrap.json', 'yarn.lock', 'pnpm-lock.yaml', 'bun.lock',
    'bun.lockb', 'gemfile', 'gemfile.lock', 'gems.rb', 'gems.locked', 'go.mod', 'go.sum',
    'pom.xml', 'build.gradle', 'build.gradle.kts', 'gradle.lockfile', 'packages.config',
    'packages.lock.json', 'global.json', 'cargo.toml', 'cargo.lock', 'composer.json',
    'composer.lock',
)

COMPANION_GROUPS = (
    ('package.json', 'package-lock.json', 'npm-shrinkwrap.json', 'yarn.lock', 'pnpm-lock.yaml', 'bun.lock', 'bun.lockb'),
    ('Cargo.toml', 'Cargo.lock'),
    ('pyproject.toml', 'poetry.lock', 'uv.lock', 'pdm.lock'),
    ('Pipfile', 'Pipfile.lock'),
    ('composer.json', 'composer.lock'),
    ('Gemfile', 'Gemfile.lock'),
    ('go.mod', 'go.sum'),
)

OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)


def text(value: Any) -> str:
    return '' if value is None else str(value).strip()


def norm_path(value: Any) -> str:
    value = text(value).replace('\\', '/').lstrip('/')
    while value.startswith('./'):
        value = value[2:]
    return value


def is_dependency_file(path: str) -> bool:
    lower = norm_path(path).lower()
    return any(lower.endswith(name.lower()) for name in DEP_FILES)


def run_git(repo_dir: Path, args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['git', *args], cwd=str(repo_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=timeout,
    )


def safe_name(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '__', value)


def ensure_repo(repo_dir: Path, repo_full_name: str) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    if not (repo_dir / '.git').exists():
        r = run_git(repo_dir, ['init'])
        if r.returncode != 0:
            raise RuntimeError(f'git init failed: {r.stderr[-1000:]}')
    remote = f'https://github.com/{repo_full_name}.git'
    current = run_git(repo_dir, ['remote', 'get-url', 'origin'])
    if current.returncode == 0:
        r = run_git(repo_dir, ['remote', 'set-url', 'origin', remote])
    else:
        r = run_git(repo_dir, ['remote', 'add', 'origin', remote])
    if r.returncode != 0:
        raise RuntimeError(f'git remote failed: {r.stderr[-1000:]}')
    run_git(repo_dir, ['config', 'gc.auto', '0'])


def fetch_commit(repo_dir: Path, sha: str) -> None:
    exists = run_git(repo_dir, ['cat-file', '-e', f'{sha}^{{commit}}'])
    if exists.returncode == 0:
        return
    r = run_git(repo_dir, ['fetch', '--no-tags', '--filter=blob:none', '--depth=1', 'origin', sha], timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f'git fetch {sha} failed: {r.stderr[-1500:]}')


def tree_paths(repo_dir: Path, sha: str) -> set[str]:
    r = run_git(repo_dir, ['-c', 'core.quotePath=false', 'ls-tree', '-r', '--name-only', sha], timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f'git ls-tree failed for {sha}: {r.stderr[-1000:]}')
    return {norm_path(line) for line in r.stdout.splitlines() if norm_path(line)}


def git_show_bytes(repo_dir: Path, sha: str, path: str) -> bytes | None:
    p = subprocess.run(
        ['git', 'show', f'{sha}:{path}'], cwd=str(repo_dir), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=300,
    )
    if p.returncode == 0:
        return p.stdout
    err = p.stderr.decode('utf-8', errors='replace').lower()
    if 'does not exist' in err or 'exists on disk, but not in' in err or 'path ' in err:
        return None
    return None


def git_show_text(repo_dir: Path, sha: str, path: str) -> str | None:
    data = git_show_bytes(repo_dir, sha, path)
    if data is None:
        return None
    return data.decode('utf-8', errors='replace')


def git_diff_for_path(repo_dir: Path, base: str, head: str, path: str) -> str:
    r = run_git(
        repo_dir,
        ['-c', 'core.quotePath=false', 'diff', '--no-color', '--no-ext-diff', '--no-textconv', '--unified=4', base, head, '--', path],
        timeout=600,
    )
    return r.stdout if r.returncode == 0 else ''


def ancestor_dirs(path: str) -> list[str]:
    parent = PurePosixPath(path).parent
    out = []
    while True:
        value = '' if str(parent) == '.' else str(parent)
        out.append(value)
        if not value:
            break
        parent = parent.parent
    return out


def symmetric_scope(changed_paths: list[str], base_tree: set[str], head_tree: set[str]) -> list[str]:
    group_by_name: dict[str, tuple[str, ...]] = {}
    for group in COMPANION_GROUPS:
        for name in group:
            group_by_name[name.lower()] = group

    union_tree = {p.lower(): p for p in (base_tree | head_tree)}
    scope: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        key = path.lower()
        if path and key not in seen:
            seen.add(key)
            scope.append(path)

    for path in changed_paths:
        add(path)
        filename = PurePosixPath(path).name.lower()
        group = group_by_name.get(filename)
        if not group:
            continue
        for directory in ancestor_dirs(path):
            for companion in group:
                candidate = f'{directory}/{companion}' if directory else companion
                actual = union_tree.get(candidate.lower())
                if actual:
                    add(actual)
    return scope


def derive_npm_package_from_path(path_key: str) -> str:
    key = path_key.replace('\\', '/').strip('/')
    marker = 'node_modules/'
    if marker not in key:
        return ''
    tail = key.rsplit(marker, 1)[-1]
    parts = tail.split('/')
    if not parts:
        return ''
    if parts[0].startswith('@') and len(parts) >= 2:
        return parts[0] + '/' + parts[1]
    return parts[0]


def add_occ(inv: dict[tuple[str, str], list[dict[str, str]]], package: Any, version: Any, path: str, locator: str) -> None:
    package = text(package)
    version = text(version)
    if not package or not version:
        return
    inv[(package.lower(), version)].append({'path': path, 'locator': locator})


def inventory_package_lock(path: str, content: str) -> dict[tuple[str, str], list[dict[str, str]]]:
    inv: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    try:
        data = json.loads(content)
    except Exception:
        return inv
    if not isinstance(data, dict):
        return inv

    packages = data.get('packages')
    if isinstance(packages, dict):
        for package_path, obj in packages.items():
            if not isinstance(obj, dict):
                continue
            package = text(obj.get('name')) or derive_npm_package_from_path(str(package_path))
            version = obj.get('version')
            add_occ(inv, package, version, path, f'packages/{package_path}')

    def walk_dependencies(depmap: Any, prefix: str) -> None:
        if not isinstance(depmap, dict):
            return
        for name, obj in depmap.items():
            if not isinstance(obj, dict):
                continue
            locator = f'{prefix}/{name}' if prefix else f'dependencies/{name}'
            add_occ(inv, name, obj.get('version'), path, locator)
            walk_dependencies(obj.get('dependencies'), locator + '/dependencies')

    walk_dependencies(data.get('dependencies'), 'dependencies')
    return inv


def parse_pnpm_key(raw: str) -> tuple[str, str] | None:
    key = raw.strip().strip('"\'').lstrip('/')
    if not key or key in {'packages', 'snapshots', 'importers', 'lockfileVersion', 'settings'}:
        return None
    key = key.split('(', 1)[0]
    # Old pnpm style: /pkg/1.2.3 or /@scope/pkg/1.2.3
    if key.startswith('@') and key.count('/') >= 2 and '@' not in key[1:]:
        parts = key.split('/')
        if len(parts) >= 3:
            return '/'.join(parts[:2]), parts[2]
    if not key.startswith('@') and key.count('/') == 1 and '@' not in key:
        pkg, ver = key.rsplit('/', 1)
        if re.match(r'^[0-9v]', ver):
            return pkg, ver
    # Current style: pkg@1.2.3 / @scope/pkg@1.2.3
    pos = key.rfind('@')
    if pos > 0:
        pkg = key[:pos]
        ver = key[pos + 1:]
        if pkg and re.match(r'^[0-9v]', ver):
            return pkg, ver
    return None


def inventory_pnpm(path: str, content: str) -> dict[tuple[str, str], list[dict[str, str]]]:
    inv: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    section = ''
    for lineno, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if stripped in {'packages:', 'snapshots:'}:
            section = stripped[:-1]
            continue
        if stripped and not line.startswith(' ') and stripped.endswith(':'):
            section = stripped[:-1]
            continue
        if section not in {'packages', 'snapshots'}:
            continue
        m = re.match(r'^\s{2,}([^#][^:]*):\s*$', line)
        if not m:
            continue
        parsed = parse_pnpm_key(m.group(1))
        if parsed:
            pkg, ver = parsed
            add_occ(inv, pkg, ver, path, f'{section}:line:{lineno}:{m.group(1).strip()}')
    return inv


def selector_package(selector: str) -> str:
    selector = selector.strip().strip('"\'')
    if selector.startswith('@'):
        pos = selector.rfind('@')
        return selector[:pos] if pos > selector.find('/') else ''
    if '@' in selector:
        return selector.rsplit('@', 1)[0]
    return ''


def inventory_yarn(path: str, content: str) -> dict[tuple[str, str], list[dict[str, str]]]:
    inv: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    selectors: list[str] = []
    header_line = 0
    for lineno, line in enumerate(content.splitlines(), start=1):
        if line and not line[0].isspace() and line.rstrip().endswith(':'):
            header = line.rstrip()[:-1]
            selectors = [s.strip() for s in re.split(r',\s*', header) if s.strip()]
            header_line = lineno
            continue
        if selectors:
            m = re.match(r'^\s+version\s+["\']?([^"\'\s]+)', line)
            if not m:
                m = re.match(r'^\s+version:\s*["\']?([^"\'\s]+)', line)
            if m:
                ver = m.group(1)
                for selector in selectors:
                    pkg = selector_package(selector)
                    add_occ(inv, pkg, ver, path, f'yarn:line:{header_line}:{selector}')
                selectors = []
    return inv


def inventory_package_json(path: str, content: str) -> dict[tuple[str, str], list[dict[str, str]]]:
    inv: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    try:
        data = json.loads(content)
    except Exception:
        return inv
    if not isinstance(data, dict):
        return inv
    for section in ('dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'):
        mapping = data.get(section)
        if not isinstance(mapping, dict):
            continue
        for pkg, raw in mapping.items():
            ver = text(raw)
            if re.match(r'^[v=]?\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z.-]+)?$', ver):
                add_occ(inv, pkg, ver.lstrip('v='), path, f'{section}/{pkg}')
    return inv


def inventory_file(path: str, content: str | None) -> dict[tuple[str, str], list[dict[str, str]]]:
    if content is None:
        return defaultdict(list)
    name = PurePosixPath(path).name.lower()
    if name in {'package-lock.json', 'npm-shrinkwrap.json'}:
        return inventory_package_lock(path, content)
    if name in {'pnpm-lock.yaml', 'pnpm-lock.yml'}:
        return inventory_pnpm(path, content)
    if name == 'yarn.lock':
        return inventory_yarn(path, content)
    if name == 'package.json':
        return inventory_package_json(path, content)
    return defaultdict(list)


def merge_inventory(target: dict[tuple[str, str], list[dict[str, str]]], source: dict[tuple[str, str], list[dict[str, str]]]) -> None:
    for key, occs in source.items():
        target[key].extend(occs)


def versions_for(inv: dict[tuple[str, str], list[dict[str, str]]], package: str) -> list[str]:
    return sorted({ver for (pkg, ver) in inv if pkg == package.lower()})


def parse_json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(text(value))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def finding_package_version(row: sqlite3.Row) -> tuple[str, str]:
    evidence = parse_json_obj(row['evidence'])
    raw = parse_json_obj(row['raw_json'])
    package = text(evidence.get('package') or raw.get('PkgName') or raw.get('PackageName'))
    version = text(evidence.get('version') or raw.get('InstalledVersion') or raw.get('Version'))
    return package, version


def compact_occurrences(occs: list[dict[str, str]], limit: int = 8) -> str:
    return ' | '.join(f"{o['path']}::{o['locator']}" for o in occs[:limit])


def diff_excerpt(diff_text: str, terms: list[str], max_chars: int = 2500) -> str:
    if not diff_text:
        return ''
    lines = diff_text.splitlines()
    indexes = []
    lower_terms = [t.lower() for t in terms if t]
    for i, line in enumerate(lines):
        low = line.lower()
        if any(term in low for term in lower_terms):
            indexes.append(i)
    if not indexes:
        return '\n'.join(lines[:30])[:max_chars]
    chunks = []
    used = set()
    for i in indexes[:5]:
        start = max(0, i - 4)
        end = min(len(lines), i + 6)
        key = (start, end)
        if key in used:
            continue
        used.add(key)
        chunks.append('\n'.join(lines[start:end]))
    return '\n---\n'.join(chunks)[:max_chars]


def flatten_scalars(value: Any, path: tuple[str, ...] = ()) -> dict[tuple[str, ...], str]:
    out: dict[tuple[str, ...], str] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            out.update(flatten_scalars(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            out.update(flatten_scalars(child, path + (str(index),)))
    elif value is not None:
        out[path] = str(value)
    return out


def infer_package_from_pointer(pointer: tuple[str, ...]) -> str:
    # package-lock v2/v3 packages/<node_modules path>/version
    if len(pointer) >= 3 and pointer[0] == 'packages' and pointer[-1] == 'version':
        pkg = derive_npm_package_from_path(pointer[1])
        if pkg:
            return pkg
    # Legacy/nested dependencies/.../<package>/version
    if pointer and pointer[-1] == 'version':
        for i in range(len(pointer) - 2, -1, -1):
            if pointer[i] == 'dependencies' and i + 1 < len(pointer):
                return pointer[i + 1]
    return ''


def load_merge_bases() -> dict[int, str]:
    result: dict[int, str] = {}
    with AUDIT_CSV.open('r', encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            try:
                cid = int(row['case_id'])
            except Exception:
                continue
            mb = text(row.get('true_merge_base'))
            if mb:
                result[cid] = mb
    return result


if not DB.exists():
    raise FileNotFoundError(DB)
if not AUDIT_CSV.exists():
    raise FileNotFoundError(AUDIT_CSV)

merge_bases = load_merge_bases()
missing_mb = sorted(set(CASE_IDS) - set(merge_bases))
if missing_mb:
    raise RuntimeError(f'Missing true merge-base for cases: {missing_mb}')

conn = sqlite3.connect(f'file:{DB.resolve()}?mode=ro', uri=True)
conn.row_factory = sqlite3.Row

finding_rows_out: list[dict[str, Any]] = []
case_rows_out: list[dict[str, Any]] = []

for index, case_id in enumerate(CASE_IDS, start=1):
    case = conn.execute(
        '''
        SELECT c.id AS case_id, c.pr_id, r.full_name AS repo_full_name,
               p.number AS pr_number, p.head_sha
        FROM cases c
        JOIN repos r ON r.id=c.repo_id
        JOIN pull_requests p ON p.id=c.pr_id
        WHERE c.id=?
        ''',
        (case_id,),
    ).fetchone()
    if case is None:
        raise RuntimeError(f'Case {case_id} not found')

    pr_files = conn.execute(
        'SELECT filename,status,patch FROM pr_files WHERE pr_id=? ORDER BY filename',
        (case['pr_id'],),
    ).fetchall()
    changed_dependency_paths = sorted({norm_path(r['filename']) for r in pr_files if is_dependency_file(r['filename'])})

    findings = conn.execute(
        '''
        SELECT id,case_id,pr_id,scanner,finding_type,severity,rule_id,file_path,line,
               description,evidence,raw_json,introduced
        FROM scanner_findings
        WHERE case_id=? AND COALESCE(introduced,0)=1
          AND scanner IN ('osv-scanner','trivy-scanner','dependency-diff')
        ORDER BY id
        ''',
        (case_id,),
    ).fetchall()

    merge_base = merge_bases[case_id]
    head_sha = text(case['head_sha'])
    repo_dir = CACHE / f'case_{case_id}_{safe_name(case["repo_full_name"])}'

    print(f'[{index:02}/{len(CASE_IDS)}] case={case_id} repo={case["repo_full_name"]} findings={len(findings)}', flush=True)

    ensure_repo(repo_dir, case['repo_full_name'])
    fetch_commit(repo_dir, merge_base)
    fetch_commit(repo_dir, head_sha)
    base_tree = tree_paths(repo_dir, merge_base)
    head_tree = tree_paths(repo_dir, head_sha)
    scope = symmetric_scope(changed_dependency_paths, base_tree, head_tree)

    base_inv: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    head_inv: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    parsed_paths = []
    unparsed_paths = []

    base_texts: dict[str, str | None] = {}
    head_texts: dict[str, str | None] = {}

    for path in scope:
        b = git_show_text(repo_dir, merge_base, path)
        h = git_show_text(repo_dir, head_sha, path)
        base_texts[path] = b
        head_texts[path] = h
        b_inv = inventory_file(path, b)
        h_inv = inventory_file(path, h)
        merge_inventory(base_inv, b_inv)
        merge_inventory(head_inv, h_inv)
        name = PurePosixPath(path).name.lower()
        if name in {'package-lock.json','npm-shrinkwrap.json','pnpm-lock.yaml','pnpm-lock.yml','yarn.lock','package.json'}:
            parsed_paths.append(path)
        else:
            unparsed_paths.append(path)

    status_counts = Counter()

    for f in findings:
        scanner = text(f['scanner'])
        package, version = finding_package_version(f)
        file_path = norm_path(f['file_path'])
        status = ''
        keep = ''
        reason = ''
        base_count = ''
        head_count = ''
        base_versions = ''
        head_versions = ''
        base_occ = ''
        head_occ = ''
        structural_pointers = ''
        inferred_package = ''
        evidence_excerpt = ''

        if scanner in {'osv-scanner', 'trivy-scanner'}:
            key = (package.lower(), version)
            b_occ = base_inv.get(key, []) if package and version else []
            h_occ = head_inv.get(key, []) if package and version else []
            base_count = len(b_occ)
            head_count = len(h_occ)
            base_versions = ', '.join(versions_for(base_inv, package)) if package else ''
            head_versions = ', '.join(versions_for(head_inv, package)) if package else ''
            base_occ = compact_occurrences(b_occ)
            head_occ = compact_occurrences(h_occ)

            if not package or not version:
                status = 'UNRESOLVED_MISSING_PACKAGE_OR_VERSION'
                keep = 'Review'
                reason = 'Original scanner finding does not expose a usable package and exact installed version.'
            elif b_occ and h_occ:
                status = 'PREEXISTING_EXACT_PACKAGE_VERSION'
                keep = 'No'
                reason = 'The exact vulnerable package/version is present in the true merge-base dependency scope and remains present at PR head.'
            elif (not b_occ) and h_occ:
                status = 'CONFIRMED_PACKAGE_VERSION_INTRODUCED'
                keep = 'Yes'
                reason = 'The exact vulnerable package/version is absent from the true merge-base dependency scope and present at PR head.'
                target_paths = sorted({o['path'] for o in h_occ})
                diffs = []
                terms = [package, version] + [o['locator'] for o in h_occ]
                for target in target_paths[:4]:
                    excerpt = diff_excerpt(git_diff_for_path(repo_dir, merge_base, head_sha, target), terms)
                    if excerpt:
                        diffs.append(f'FILE {target}\n{excerpt}')
                evidence_excerpt = '\n=====\n'.join(diffs)[:6000]
            elif not h_occ:
                status = 'HEAD_PACKAGE_VERSION_NOT_REPRODUCED'
                keep = 'Review'
                reason = 'The exact scanner-reported package/version could not be reconstructed from supported dependency inventories at PR head.'
            else:
                status = 'UNRESOLVED'
                keep = 'Review'
                reason = 'State comparison was inconclusive.'

        elif scanner == 'dependency-diff':
            ev = parse_json_obj(f['evidence'])
            reported_package = text(ev.get('package'))
            old_version = text(ev.get('old_version'))
            new_version = text(ev.get('new_version'))
            path = file_path
            b_text = base_texts.get(path)
            h_text = head_texts.get(path)
            if b_text is None:
                b_text = git_show_text(repo_dir, merge_base, path)
            if h_text is None:
                h_text = git_show_text(repo_dir, head_sha, path)

            try:
                b_json = json.loads(b_text) if b_text is not None else None
                h_json = json.loads(h_text) if h_text is not None else None
            except Exception:
                b_json = h_json = None

            if not isinstance(b_json, (dict, list)) or not isinstance(h_json, (dict, list)):
                status = 'UNRESOLVED_JSON_PARSE'
                keep = 'Review'
                reason = 'Could not parse both dependency file states as JSON for same-field structural validation.'
            else:
                b_flat = flatten_scalars(b_json)
                h_flat = flatten_scalars(h_json)
                matches = []
                key_name = reported_package.lower()
                for pointer, b_value in b_flat.items():
                    if not pointer or pointer[-1].lower() != key_name:
                        continue
                    if b_value != old_version:
                        continue
                    if h_flat.get(pointer) == new_version:
                        matches.append(pointer)

                if matches:
                    status = 'CONFIRMED_SAME_JSON_FIELD_CHANGE'
                    keep = 'Yes'
                    reason = 'The scanner-reported old and new values occur at the same JSON field path in the true merge-base and PR head.'
                    structural_pointers = ' | '.join('/'.join(p) for p in matches[:20])
                    inferred = sorted({infer_package_from_pointer(p) for p in matches if infer_package_from_pointer(p)})
                    inferred_package = ', '.join(inferred)
                    terms = [reported_package, old_version, new_version, *inferred]
                    evidence_excerpt = diff_excerpt(git_diff_for_path(repo_dir, merge_base, head_sha, path), terms)
                else:
                    status = 'NOT_REPRODUCED_SAME_JSON_FIELD'
                    keep = 'No'
                    reason = 'No identical JSON field path changes from the scanner-reported old value to the reported new value; the line-oriented detector paired unrelated fields.'

        status_counts[status] += 1
        finding_rows_out.append({
            'Case ID': case_id,
            'Repository': case['repo_full_name'],
            'PR #': case['pr_number'],
            'Scanner Finding DB ID': f['id'],
            'Source Finding ID': f'snapshot:{f["id"]}',
            'Scanner': scanner,
            'Finding Type': f['finding_type'],
            'Rule ID': f['rule_id'] or '',
            'Package': package,
            'Version': version,
            'Primary File': file_path,
            'Original Description': f['description'] or '',
            'Validation Status': status,
            'Keep As Introduced': keep,
            'Validation Reason': reason,
            'Base Exact Occurrence Count': base_count,
            'Head Exact Occurrence Count': head_count,
            'Base Versions For Package': base_versions,
            'Head Versions For Package': head_versions,
            'Base Occurrences': base_occ,
            'Head Occurrences': head_occ,
            'Confirmed JSON Pointer(s)': structural_pointers,
            'Inferred Package For version Field': inferred_package,
            'Diff Evidence': evidence_excerpt,
            'True Merge Base': merge_base,
            'Head SHA': head_sha,
            'Symmetric Dependency Scope': ' | '.join(scope),
        })

    case_rows_out.append({
        'Case ID': case_id,
        'Repository': case['repo_full_name'],
        'PR #': case['pr_number'],
        'True Merge Base': merge_base,
        'Head SHA': head_sha,
        'Changed Dependency Paths': ' | '.join(changed_dependency_paths),
        'Symmetric Dependency Scope': ' | '.join(scope),
        'Parsed Scope Paths': ' | '.join(sorted(set(parsed_paths))),
        'Unsupported Scope Paths': ' | '.join(sorted(set(unparsed_paths))),
        'Introduced Dependency Finding Rows Checked': len(findings),
        'Keep Yes': sum(1 for r in finding_rows_out if r['Case ID'] == case_id and r['Keep As Introduced'] == 'Yes'),
        'Keep No': sum(1 for r in finding_rows_out if r['Case ID'] == case_id and r['Keep As Introduced'] == 'No'),
        'Needs Review': sum(1 for r in finding_rows_out if r['Case ID'] == case_id and r['Keep As Introduced'] == 'Review'),
        'Status Counts': json.dumps(dict(status_counts), sort_keys=True),
    })

conn.close()

finding_fields = list(finding_rows_out[0].keys())
with FINDING_CSV.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=finding_fields)
    writer.writeheader()
    writer.writerows(finding_rows_out)

case_fields = list(case_rows_out[0].keys())
with CASE_CSV.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=case_fields)
    writer.writeheader()
    writer.writerows(case_rows_out)

counts = Counter(r['Validation Status'] for r in finding_rows_out)
keep_counts = Counter(r['Keep As Introduced'] for r in finding_rows_out)
manifest = {
    'purpose': 'Targeted dependency cleanup after Step 2 causal mapping.',
    'affected_case_ids': CASE_IDS,
    'dependency_vulnerability_case_ids': sorted(VULN_CASES),
    'dependency_diff_case_ids': sorted(DEPDIFF_CASES),
    'method': {
        'vulnerability_findings': (
            'Do not rerun vulnerability databases. Preserve the original scanner finding, but compare the exact scanner-reported package/version against dependency inventories reconstructed from the true PR merge-base and PR head over one symmetric changed-file-plus-companion scope. Exact presence at base means the vulnerability condition pre-existed the PR; absence at base and presence at head confirms package/version introduction.'
        ),
        'dependency_diff_findings': (
            'Parse base/head package-lock JSON and require the scanner-reported old and new values to occur at the identical JSON field path. This rejects line-oriented pairings between unrelated lockfile objects.'
        ),
        'why_no_scanner_rerun': (
            'Avoids vulnerability-database drift after the original mining run. The original advisory result is treated as frozen; this cleanup validates only whether its exact vulnerable package/version was already present before the PR.'
        ),
    },
    'finding_rows_checked': len(finding_rows_out),
    'validation_status_counts': dict(counts),
    'keep_counts': dict(keep_counts),
}
MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')

with zipfile.ZipFile(ZIP_OUT, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    archive.write(FINDING_CSV, FINDING_CSV.name)
    archive.write(CASE_CSV, CASE_CSV.name)
    archive.write(MANIFEST, MANIFEST.name)

print('\n' + '=' * 80)
print('TARGETED DEPENDENCY CLEANUP COMPLETE')
print('=' * 80)
print(f'Cases checked: {len(CASE_IDS)}')
print(f'Raw dependency finding rows checked: {len(finding_rows_out)}')
print(f'Keep counts: {dict(keep_counts)}')
print(f'Validation statuses: {dict(counts)}')
print(f'Bundle: {ZIP_OUT}')
