#!/bin/bash
#SBATCH --job-name=t1pairsel
#SBATCH --partition=bigbatch
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_BIDIR_PAIR_SELECTION_%j.out

set -euo pipefail

GROUP="${GROUP:?submit with --export=ALL,GROUP=0 or GROUP=1}"

python3 -u <<'PY'
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tarfile
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
GROUP = int(os.environ["GROUP"])

STEP6 = ROOT / "DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz"
V9 = ROOT / "T1_V9_FULL_BLIND_REVIEW.tar.gz"
OUT = ROOT / f"T1_BIDIR_PAIR_SELECTION_v1_G{GROUP}"
ARCHIVE = ROOT / f"T1_BIDIR_PAIR_SELECTION_v1_G{GROUP}.tar.gz"

if not STEP6.exists():
    raise SystemExit(f"MISSING={STEP6}")
if not V9.exists():
    raise SystemExit(f"MISSING={V9}")

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()

def json_strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from json_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from json_strings(v)
    elif obj is not None:
        yield str(obj)

def contains_exact_any(obj, values):
    vals = {norm(v) for v in values if str(v or "").strip()}
    if not vals:
        return False
    for s in json_strings(obj):
        if norm(s) in vals:
            return True
    return False

def contains_substr_any(obj, values):
    vals = [norm(v) for v in values if str(v or "").strip()]
    if not vals:
        return False
    hay = "\n".join(norm(s) for s in json_strings(obj))
    return any(v in hay for v in vals if len(v) >= 6)

# --- Step 6: authoritative matched-pair table ---
with tarfile.open(STEP6, "r:*") as tf:
    member = next(
        m for m in tf.getmembers()
        if m.isfile() and m.name.endswith("STEP6_UNBLINDED_PAIRS_51.csv")
    )
    rows = list(csv.DictReader(
        io.StringIO(tf.extractfile(member).read().decode("utf-8-sig"))
    ))

# Strong production-code population only.
eligible_step6 = [
    r for r in rows
    if r.get("analysis_role") == "PRIMARY"
    and r.get("match_tier") in {"D1_SAME_REPO", "D2_EXISTING_C2_WORKFLOW"}
    and r.get("positive_decision_test_only") == "NO"
    and r.get("control_decision_test_only") == "NO"
]

eligible_step6.sort(
    key=lambda r: (
        0 if r["match_tier"] == "D1_SAME_REPO" else 1,
        r["pair_id"],
    )
)

# Split deterministically across exactly two jobs.
selected_rows = [
    r for i, r in enumerate(eligible_step6)
    if i % 2 == GROUP
]

# --- Index V9 members by pair/side ---
with tarfile.open(V9, "r:*") as tf:
    members = [m for m in tf.getmembers() if m.isfile()]
    member_by_name = {m.name: m for m in members}

    pairs = {}
    for m in members:
        mo = re.search(r"(S5PAIR-\d+)/(A|B)/([^/]+)$", m.name)
        if not mo:
            continue
        pid, side, fn = mo.groups()
        pairs.setdefault(pid, {}).setdefault(side, {})[fn] = m

    manifest = []
    review_index = []

    for r in selected_rows:
        pid = r["pair_id"]
        rec = {
            "pair_id": pid,
            "match_tier": r["match_tier"],
            "decision_family": r["decision_family"],
            "step6_primary": True,
            "production_only": True,
            "v9_present": pid in pairs,
            "role_mapping_status": "UNRESOLVED",
            "positive_candidate_count": None,
            "control_candidate_count": None,
            "positive_extraction_status": None,
            "control_extraction_status": None,
            "retrieval_clean_both": None,
            "review_status": "NOT_READY",
        }

        if pid not in pairs or not {"A","B"}.issubset(pairs[pid]):
            rec["review_status"] = "MISSING_V9_PACKET"
            manifest.append(rec)
            continue

        side_data = {}
        for side in ("A","B"):
            files = pairs[pid][side]
            meta_m = files.get("PACKET_METADATA.json")
            cand_m = files.get("PRECHANGE_REPO_SEARCH_CANDIDATES.json")
            diff_m = files.get("HISTORICAL_DECISION_CONTEXT.diff")
            if not meta_m or not cand_m:
                continue
            meta = json.loads(tf.extractfile(meta_m).read().decode("utf-8", errors="ignore"))
            cand_raw = tf.extractfile(cand_m).read()
            diff_raw = tf.extractfile(diff_m).read() if diff_m else b""
            side_data[side] = {
                "meta": meta,
                "cand_raw": cand_raw,
                "diff_raw": diff_raw,
                "files": files,
            }

        if set(side_data) != {"A","B"}:
            rec["review_status"] = "INCOMPLETE_V9_PACKET"
            manifest.append(rec)
            continue

        # Resolve A/B -> positive/control without guessing.
        pos_ids = [r.get("positive_source_id","")]
        ctrl_ids = [r.get("control_source_id","")]
        pos_path = r.get("positive_file_path","")
        ctrl_path = r.get("control_file_path","")
        pos_summary = r.get("positive_decision_summary","")
        ctrl_summary = r.get("control_decision_summary","")

        scores = {}
        for side in ("A","B"):
            meta = side_data[side]["meta"]
            scores[side] = {
                "pos": (
                    5 * int(contains_exact_any(meta, pos_ids))
                    + 3 * int(contains_substr_any(meta, [pos_path]))
                    + 1 * int(contains_substr_any(meta, [pos_summary]))
                ),
                "ctrl": (
                    5 * int(contains_exact_any(meta, ctrl_ids))
                    + 3 * int(contains_substr_any(meta, [ctrl_path]))
                    + 1 * int(contains_substr_any(meta, [ctrl_summary]))
                ),
            }

        mapping = None
        # Require a strict, non-tied assignment.
        if scores["A"]["pos"] > scores["A"]["ctrl"] and scores["B"]["ctrl"] > scores["B"]["pos"]:
            mapping = {"positive": "A", "control": "B"}
        elif scores["B"]["pos"] > scores["B"]["ctrl"] and scores["A"]["ctrl"] > scores["A"]["pos"]:
            mapping = {"positive": "B", "control": "A"}

        if mapping is None:
            rec["role_mapping_status"] = "AMBIGUOUS"
            rec["role_mapping_scores"] = scores
            rec["review_status"] = "ROLE_MAPPING_AMBIGUOUS"
            manifest.append(rec)
            continue

        rec["role_mapping_status"] = "RESOLVED"
        rec["role_mapping_scores"] = scores

        pair_dir = OUT / "REVIEW_PACKETS" / pid
        pair_dir.mkdir(parents=True)

        # Frozen mechanism M comes directly from the historical positive coding.
        mechanism = {
            "pair_id": pid,
            "match_tier": r["match_tier"],
            "decision_family": r["decision_family"],
            "M_positive_decision_summary": r["positive_decision_summary"],
            "M_positive_mechanism_summary": r["positive_mechanism_summary"],
            "M_positive_mechanism_shape": r["positive_mechanism_shape"],
            "positive_guard_or_validation_visible": r["positive_guard_or_validation_visible"],
            "control_historical_decision_summary": r["control_decision_summary"],
            "control_historical_mechanism_summary": r["control_mechanism_summary"],
            "control_historical_mechanism_shape": r["control_mechanism_shape"],
            "control_guard_or_validation_visible": r["control_guard_or_validation_visible"],
            "selection_note":
                "M is frozen from the historical positive. Candidate Xp/Xn must be authentic pre-change local precedent "
                "for the same mechanism class M; they need not be the same literal file.",
        }
        (pair_dir / "FROZEN_MECHANISM.json").write_text(
            json.dumps(mechanism, indent=2, ensure_ascii=False) + "\n"
        )

        for role in ("positive","control"):
            side = mapping[role]
            sd = side_data[side]
            rd = pair_dir / role.upper()
            rd.mkdir()

            # Keep sensitive code/context available for internal review, but no scanner rule/outcome is added.
            (rd / "PACKET_METADATA.json").write_text(
                json.dumps(sd["meta"], indent=2, ensure_ascii=False) + "\n"
            )
            (rd / "PRECHANGE_REPO_SEARCH_CANDIDATES.json").write_bytes(sd["cand_raw"])
            if sd["diff_raw"]:
                (rd / "HISTORICAL_DECISION_CONTEXT.diff").write_bytes(sd["diff_raw"])

            stats = sd["meta"].get("search_stats", {}) if isinstance(sd["meta"], dict) else {}
            rec[f"{role}_candidate_count"] = int(stats.get("candidate_count", 0) or 0)
            rec[f"{role}_extraction_status"] = sd["meta"].get("extraction_status")
            rec[f"{role}_grep_timeout_count"] = int(stats.get("grep_timeout_count", 0) or 0)
            rec[f"{role}_grep_call_count"] = int(stats.get("grep_call_count", 0) or 0)

        # "Clean retrieval" is descriptive only; timeout does not imply ineligibility.
        rec["retrieval_clean_both"] = all(
            rec.get(f"{role}_extraction_status") == "PASS"
            and rec.get(f"{role}_candidate_count", 0) > 0
            for role in ("positive","control")
        )

        # Ready means sufficient material exists for semantic X adjudication.
        if rec["retrieval_clean_both"]:
            rec["review_status"] = "READY_FOR_X_ADJUDICATION"
        else:
            rec["review_status"] = "RETRIEVAL_INCOMPLETE_OR_ZERO"

        # Blank frozen adjudication form. Do not auto-decide semantic equivalence.
        adjudication = {
            "pair_id": pid,
            "frozen_M": r["positive_mechanism_summary"],
            "criteria": {
                "same_decision_opportunity_both_tasks": None,
                "Xp_authentic_prechange": None,
                "Xn_authentic_prechange": None,
                "Xp_supports_M": None,
                "Xn_supports_M": None,
                "Xp_separable_from_indispensable_target": None,
                "Xn_separable_from_indispensable_target": None,
                "plus_minus_can_differ_only_by_X_visibility": None,
                "both_tasks_functionally_evaluable": None,
                "same_mechanism_class_not_same_literal_code": None,
            },
            "decision": "UNADJUDICATED",
            "allowed_decisions": ["PROCEED","RESERVE","REJECT"],
            "note":
                "Do not use scanner outcomes, rule identities, or desired direction of effect to make this decision.",
        }
        (pair_dir / "ADJUDICATION_TEMPLATE.json").write_text(
            json.dumps(adjudication, indent=2) + "\n"
        )

        review_index.append({
            "pair_id": pid,
            "match_tier": r["match_tier"],
            "decision_family": r["decision_family"],
            "positive_mechanism_summary": r["positive_mechanism_summary"],
            "positive_mechanism_shape": r["positive_mechanism_shape"],
            "control_mechanism_summary": r["control_mechanism_summary"],
            "positive_candidate_count": rec["positive_candidate_count"],
            "control_candidate_count": rec["control_candidate_count"],
            "review_status": rec["review_status"],
        })
        manifest.append(rec)

# Save machine-readable index.
(OUT / "PAIR_MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
)
(OUT / "REVIEW_INDEX.json").write_text(
    json.dumps(review_index, indent=2, ensure_ascii=False) + "\n"
)

ready = [x for x in manifest if x["review_status"] == "READY_FOR_X_ADJUDICATION"]
summary = {
    "group": GROUP,
    "step6_strong_production_pairs_in_group": len(selected_rows),
    "packets_ready_for_X_adjudication": len(ready),
    "role_mapping_ambiguous": sum(x["role_mapping_status"] == "AMBIGUOUS" for x in manifest),
    "retrieval_incomplete_or_zero": sum(
        x["review_status"] == "RETRIEVAL_INCOMPLETE_OR_ZERO" for x in manifest
    ),
    "selection_population":
        "PRIMARY + D1/D2 + production-code on both sides; pair identity joined directly by frozen S5PAIR pair_id.",
    "scientific_rule":
        "Select only where both sides contain authentic, separable pre-change local precedent instantiating the same "
        "mechanism class M. Literal code/file identity across repositories is NOT required.",
}
(OUT / "SUMMARY.json").write_text(
    json.dumps(summary, indent=2) + "\n"
)

if ARCHIVE.exists():
    ARCHIVE.unlink()
with tarfile.open(ARCHIVE, "w:gz") as tf:
    tf.add(OUT, arcname=OUT.name)

print("STATUS=DONE")
print("GROUP=", GROUP)
print("STRONG_PRODUCTION_PAIRS=", len(selected_rows))
print("READY_FOR_X_ADJUDICATION=", len(ready))
print("ROLE_MAPPING_AMBIGUOUS=", summary["role_mapping_ambiguous"])
print("RETRIEVAL_INCOMPLETE_OR_ZERO=", summary["retrieval_incomplete_or_zero"])
print("OUTPUT=", ARCHIVE)
print("SHA256=", sha256_bytes(ARCHIVE.read_bytes()))
PY
