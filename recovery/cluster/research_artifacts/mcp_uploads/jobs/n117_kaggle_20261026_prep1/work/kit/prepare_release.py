#!/usr/bin/env python3
"""Prepare the published, hash-pinned N117 local-effect Kaggle notebook.

No training, replay substitution, or access to Kaggle credentials is performed.
Copying the exact published notebook avoids accidentally replacing its embedded
1.6 MiB frozen checkpoint with a random/untrained agent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

COMPETITION = "arc-prize-2026-arc-agi-3"
DEFAULT_USER = "arnostrauss"
DEFAULT_SLUG = "arc-agi-3-n117-local-effect-20261026"
SOURCE_PATH = Path("src/best_public_agent.py")
NOTEBOOK_PATH = Path("notebooks/local_effect_best_public.ipynb")
EXPECTED_SHA256 = {
    SOURCE_PATH: "0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa",
    NOTEBOOK_PATH: "0f049935a633a14ba82c0427386e5eef852f3a8972aa205b61a3ca0e70c01acd",
}


def verify_sha(path: Path, expected_sha256: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Required N117 file missing: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            f"Source-integrity verification FAILED: {path}\n"
            f"  expected: {expected_sha256}\n  actual:   {actual}\n"
            "Do not submit; fetch the published frozen research artifact."
        )
    return actual


def cell_source(cell: dict) -> str:
    s = cell.get("source", "")
    return "".join(s) if isinstance(s, list) else s


def verify_notebook(notebook: dict, source: str) -> None:
    cells = notebook.get("cells")
    if notebook.get("nbformat") != 4 or not isinstance(cells, list) or len(cells) != 5:
        raise ValueError("Unexpected notebook layout; refusing an unverified submission")
    embedded = cell_source(cells[2])
    prefix = "%%writefile /tmp/my_agent.py\n"
    if embedded != prefix + source:
        raise ValueError("Notebook's actual embedded agent differs from frozen N117 source")
    if "class MyAgent(_FrozenBaselineMyAgent)" not in embedded:
        raise ValueError("Notebook does not expose the intended local-effect agent")
    if "mode='local'" not in embedded:
        raise ValueError("Agent is not in the intended local-effect mode")
    if "base64.b85decode" not in embedded:
        raise ValueError("Frozen pretrained checkpoint is not embedded")
    run_cell = cell_source(cells[3])
    for expected in (
        "KAGGLE_IS_COMPETITION_RERUN", "http://gateway:8001/api/games",
        "python main.py --agent myagent", "/tmp/my_agent.py",
    ):
        if expected not in run_cell:
            raise ValueError(f"Competition rerun contract missing: {expected}")
    phase_a = cell_source(cells[4])
    if "if not os.getenv('KAGGLE_IS_COMPETITION_RERUN')" not in phase_a:
        raise ValueError("Phase A placeholder not separated from Kaggle scoring")
    if "submission.parquet" not in phase_a:
        raise ValueError("Validation-mode notebook doesn't produce an output file")
    meta = notebook.get("metadata", {}).get("kaggle", {})
    if meta.get("isInternetEnabled") is not False or meta.get("isGpuEnabled") is not False:
        raise ValueError("Expected the tested CPU-only offline Kaggle notebook")


def build(repo: Path, output: Path, username: str, slug: str) -> dict:
    repo = repo.resolve()
    output = output.resolve()
    if not username or "/" in username or not slug or "/" in slug:
        raise ValueError("Invalid Kaggle account or notebook slug")
    if output == repo or repo in output.parents:
        raise ValueError("Refusing to overwrite/create Kaggle release inside frozen repository")
    verified = {
        str(p): verify_sha(repo / p, digest) for p, digest in EXPECTED_SHA256.items()
    }
    source = (repo / SOURCE_PATH).read_text(encoding="utf-8")
    notebook_bytes = (repo / NOTEBOOK_PATH).read_bytes()
    notebook = json.loads(notebook_bytes)
    verify_notebook(notebook, source)

    # Do not round-trip through json.dump(): preserve the exact checked notebook bytes.
    output.mkdir(parents=True, exist_ok=True)
    nb_dest = output / "submission.ipynb"
    nb_dest.write_bytes(notebook_bytes)
    kernel_id = f"{username}/{slug}"
    metadata = {
        "id": kernel_id,
        "title": "ARC AGI 3 N117 Local Effect 20261026",
        "code_file": "submission.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": False,
        "keywords": ["arc-agi-3", "reinforcement-learning"],
        "dataset_sources": [],
        "kernel_sources": [],
        "competition_sources": [COMPETITION],
        "model_sources": [],
    }
    (output / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "research_repository": "https://github.com/Stralb/arc-agi-3-rl-research",
        "agent": "N117_local_effect_experimental",
        "notebook_kernel": kernel_id,
        "source_sha256": verified[str(SOURCE_PATH)],
        "notebook_sha256": verified[str(NOTEBOOK_PATH)],
        "submission_file_sha256": hashlib.sha256(nb_dest.read_bytes()).hexdigest(),
        "cpu": True, "internet": False,
        "kaggle_official_evaluation": "NOT RUN BY THIS SCRIPT",
        "public_evidence": "13 Level-1 + 2 Level-2 on 25 historically exposed games",
    }
    (output.parent / "N117_RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path,
                        help="Local clone of Stralb/arc-agi-3-rl-research")
    parser.add_argument("--output", type=Path, default=Path("kaggle_kernel"))
    parser.add_argument("--username", default=DEFAULT_USER)
    parser.add_argument("--slug", default=DEFAULT_SLUG)
    args = parser.parse_args()
    info = build(args.repo, args.output, args.username, args.slug)
    print("PASS: N117 source SHA-256 verified; notebook embeds the exact source and checkpoint")
    print(f"Ready Kaggle kernel: {args.output.resolve()}")
    print(f"Notebook: {info['notebook_kernel']}")
    print("Next: kaggle kernels push -p " + str(args.output.resolve()))
    print("IMPORTANT: Kaggle Phase A's placeholder is NOT a real hidden-game score.")


if __name__ == "__main__":
    main()
