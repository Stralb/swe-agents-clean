#!/usr/bin/env python3
"""Read-only static import inventory for one historical miner source snapshot.

No archive member is extracted, imported or executed. The script reads the ZIP
and prints JSON or CSV to stdout. Import classification and filesystem-operation
flags are conservative static indicators, NOT proofs of runtime behavior.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import PurePosixPath, Path
import sys
from zipfile import ZipFile

ROOT = "historical/miner/2026-10-20-live-export/"
SCOPES = ("src/", "scripts/", "ui/", "analysis/", "tests/")
LOCAL_ROOTS = {"src", "scripts", "ui", "analysis", "tests"}
STDLIB = frozenset(sys.stdlib_module_names) | {"__future__"}
MUTATION_HINTS = frozenset({
    "shutil.rmtree", "os.unlink", "os.remove", "os.replace", "os.rename",
    "os.makedirs", "os.mkdir", "shutil.move", "shutil.copy", "shutil.copy2",
    "subprocess.run", "subprocess.Popen", "subprocess.call", "os.system",
    "Path.mkdir", "Path.unlink", "Path.write_text", "Path.write_bytes",
    "Path.rename", "Path.replace", "tarfile.extractall", "ZipFile.extractall",
})
# `obj.method()` is not enough to determine object type. These method names
# only raise conservative flags and can produce false positives.
MUTATION_METHODS = frozenset({
    "rmtree", "mkdir", "unlink", "write_text", "write_bytes", "rename",
    "replace", "extractall", "execute", "executemany", "commit", "touch",
})


def callable_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = callable_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def module_name(relative_path: str) -> str:
    if not relative_path.endswith(".py"):
        raise ValueError("Only Python modules are supported")
    stem = relative_path[:-3]
    if stem.endswith("/__init__"):
        stem = stem[: -len("/__init__")]
    return stem.replace("/", ".")


def top_level_unguarded_calls(tree: ast.Module) -> tuple[str, ...]:
    """Top-level calls outside functions/classes and a __main__ guard.

    This is a deliberately limited syntactic scan; no imported code runs.
    """
    calls = []
    def in_main_guard(node: ast.If) -> bool:
        try:
            expr = ast.unparse(node.test).replace(" ", "")
        except (AttributeError, ValueError):
            return False
        return expr in {"__name__=='__main__'", '"__main__"==__name__',
                        '"__main__"==__name__', '__name__=="__main__"',
                        "'__main__'==__name__"}

    def visit_statements(statements: list[ast.stmt]) -> None:
        for node in statements:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.If) and in_main_guard(node):
                visit_statements(node.orelse)
                continue
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With,
                                  ast.AsyncFor, ast.AsyncWith)):
                nested = []
                for field in ("body", "orelse", "finalbody"):
                    nested.extend(getattr(node, field, []) or [])
                if isinstance(node, ast.Try):
                    for handler in node.handlers:
                        nested.extend(handler.body)
                visit_statements(nested)
                continue
            # Top-level expression/assignment evaluation can invoke code.
            for child in ast.walk(node):
                if isinstance(child, (ast.FunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                if isinstance(child, ast.Call):
                    calls.append(callable_name(child.func))
    visit_statements(tree.body)
    return tuple(sorted({x for x in calls if x}))


def get_modules(z: ZipFile, *, root: str = ROOT) -> dict[str, tuple[str, bytes]]:
    members = z.infolist()
    names = [info.filename for info in members]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate ZIP member paths")
    out: dict[str, tuple[str, bytes]] = {}
    for info in members:
        name = info.filename
        if not name.startswith(root) or info.is_dir():
            continue
        rel = name[len(root):]
        if not rel.endswith(".py") or not rel.startswith(SCOPES):
            continue
        path = PurePosixPath(rel)
        if path.is_absolute() or ".." in path.parts or "\\" in rel:
            raise ValueError(f"Unsafe ZIP source path: {name}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError(f"Symlink source path: {name}")
        if any(part.startswith(".") or part in {"__pycache__", "backups"} for part in path.parts):
            continue
        out[rel] = (name, z.read(info))
    if not out:
        raise ValueError(f"No relevant source files under {root}")
    return out


def describe_module(rel: str, blob: bytes, available: set[str]) -> dict:
    info = {
        "source_path": rel,
        "module": module_name(rel),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "bytes": len(blob),
    }
    try:
        root = ast.parse(blob.decode("utf-8-sig"), filename=rel)
    except (SyntaxError, UnicodeError) as exc:
        return {**info, "parse_status": "FAIL", "parse_error": str(exc),
                "stdlib_imports": "", "third_party_imports": "", "local_imports": "",
                "unresolved_local_imports": "", "top_level_calls": "", "risky_call_hints": ""}
    stdlib, third_party, local, unresolved = set(), set(), set(), set()
    sibling_prefix = module_name(rel).rsplit(".", 1)[0] if "." in module_name(rel) else ""
    risky = set()
    for node in ast.walk(root):
        imports = []
        if isinstance(node, ast.Import):
            imports.extend(x.name for x in node.names)
        if isinstance(node, ast.ImportFrom):
            if node.level:
                local.add("<relative import>")
            elif node.module:
                imports.append(node.module)
        for path in imports:
            top = path.split(".", 1)[0]
            if top in LOCAL_ROOTS:
                local.add(path)
                # We can resolve only modules, not exported symbols.
                if not any(p == path or p.startswith(path + ".") for p in available):
                    unresolved.add(path)
            elif top in STDLIB:
                stdlib.add(top)
            elif sibling_prefix and any(p == sibling_prefix + "." + path or
                                        p.startswith(sibling_prefix + "." + path + ".")
                                        for p in available):
                # Analysis packages sometimes use bare imports by adding their
                # own folder to sys.path at runtime. Record them as local
                # sibling dependencies, not third-party installations.
                local.add("<sibling>:" + path)
            else:
                third_party.add(top)
        if isinstance(node, ast.Call):
            target = callable_name(node.func)
            if target in MUTATION_HINTS or target.rsplit(".", 1)[-1] in MUTATION_METHODS:
                risky.add(target)
    info.update({
        "parse_status": "PASS", "parse_error": "",
        "stdlib_imports": ";".join(sorted(stdlib)),
        "third_party_imports": ";".join(sorted(third_party)),
        "local_imports": ";".join(sorted(local)),
        "unresolved_local_imports": ";".join(sorted(unresolved)),
        "top_level_calls": ";".join(top_level_unguarded_calls(root)),
        "risky_call_hints": ";".join(sorted(risky)),
    })
    return info


def inspect(archive: Path, *, root: str = ROOT) -> tuple[dict, list[dict]]:
    with ZipFile(archive, "r") as z:
        modules = get_modules(z, root=root)
    available = {module_name(rel) for rel in modules}
    rows = [describe_module(path, blob, available) for path, (_, blob) in sorted(modules.items())]
    top = lambda rel: rel.split("/", 1)[0]
    external = Counter(x for r in rows for x in r["third_party_imports"].split(";") if x)
    by_scope = Counter(top(r["source_path"]) for r in rows)
    return {
        "status": "STATIC_INVENTORY_ONLY_NO_SOURCE_EXECUTION",
        "python_files": len(rows),
        "parse_pass": sum(r["parse_status"] == "PASS" for r in rows),
        "parse_fail": sum(r["parse_status"] == "FAIL" for r in rows),
        "scope_counts": dict(sorted(by_scope.items())),
        "third_party_imported_top_level_modules": dict(sorted(external.items())),
        "modules_with_top_level_calls": sum(bool(r["top_level_calls"]) for r in rows),
        "modules_with_mutation_hints": sum(bool(r["risky_call_hints"]) for r in rows),
        "modules_with_unresolved_local_imports": sum(bool(r["unresolved_local_imports"]) for r in rows),
        "limitations": "AST static signals only; no transitive import, dynamic import, install or runtime check",
    }, rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source_only_zip", type=Path)
    ap.add_argument("--format", choices=["summary", "csv"], default="summary")
    args = ap.parse_args()
    summary, rows = inspect(args.source_only_zip)
    if args.format == "csv":
        fields = list(rows[0])
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        print(output.getvalue(), end="")
    else:
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
