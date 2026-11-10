#!/usr/bin/env python3
"""Read-only E074 provenance and human-coverage diagnostics.

Does not decode Parquet, access ARC games, alter frozen splits, or train.
Writes a fresh diagnostic outside the original 27-file release.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text()) if path.is_file() else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--work', required=True, type=Path)
    args = p.parse_args()
    root, work = args.root.resolve(), args.work.resolve()
    sys.path[:0] = [str(root/'code'), str(root/'vendor/e068/code'),
                    str(root/'vendor/e069/code')]
    from e068_split import TRAIN_FAMILIES
    from e072_audit import verify_human_manifest

    out = {
        'report_kind': 'E074_RESTART_AND_QUALITY_DIAGNOSTIC',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'root': str(root), 'work': str(work),
        'heldout_environments_opened_by_this_report': False,
        'human_data_origin': 'unknown_until_raw_snapshot_verified',
    }
    base = read_json(root/'SHA256_MANIFEST.json')
    if base is None:
        out['source_status'] = 'SOURCE_MANIFEST_MISSING'
    else:
        unexpected = []
        for rel, expected in base['files'].items():
            f = root/rel
            if not f.is_file() or digest(f) != expected:
                unexpected.append(rel)
        out['source_hashes'] = {
            'matched': len(base['files'])-len(unexpected),
            'expected': len(base['files']), 'failed': unexpected,
        }
        out['source_status'] = 'ORIGINAL_INTACT' if not unexpected else 'SOURCE_MODIFIED_STOP'

    snap = work/'human_snapshot'
    lock = read_json(snap/'E068_HUMAN_DATA_LOCK.json')
    if lock is None:
        out['snapshot'] = {'status': 'NOT_ACQUIRED'}
    else:
        out['snapshot'] = {
            'status': lock.get('state', 'UNKNOWN'),
            'repo': lock.get('repo'), 'revision': lock.get('revision'),
            'shard_names': [row.get('file') for row in lock.get('shards', [])],
            'shard_hashes': {row['file']:row['sha256'] for row in lock.get('shards', [])},
            'total_bytes': lock.get('total_bytes'),
            'raw_integrity_rechecked_by_probe': False,
        }

    manifest_path = work/'human_five_training/E068_HUMAN_TRAINING_MANIFEST.json'
    ing = read_json(manifest_path)
    if ing is None:
        out['ingestion'] = {'status': 'NOT_AVAILABLE'}
    else:
        per_family = {family: dict(sessions=0, transitions=0, native_advancements=0,
                                    resets=0, successful_sessions=0,
                                    reward_actions={})
                      for family in TRAIN_FAMILIES}
        errors = Counter()
        positive_types = Counter()
        bad_shards = []
        for row in ing.get('shards', []):
            family = row.get('family')
            if family not in per_family:
                bad_shards.append({'name': row.get('file'), 'issue': 'NONTRAIN_FAMILY'})
                continue
            dst = per_family[family]
            dst['sessions'] += 1
            dst['transitions'] += int(row.get('observed_transitions', 0))
            dst['native_advancements'] += int(row.get('native_advancements', 0))
            dst['successful_sessions'] += int(row.get('native_advancements', 0) > 0)
            dst['resets'] += int(row.get('session_resets', 0))
            errors.update(row.get('errors', {}))
            name = row.get('file', '')
            if Path(name).name != name or not name.endswith('.npz'):
                bad_shards.append({'name': name, 'issue': 'UNSAFE_PATH'})
                continue
            f = manifest_path.parent/name
            if not f.is_file() or digest(f) != row.get('file_sha256'):
                bad_shards.append({'name': name, 'issue': 'CHECKSUM_MISMATCH_OR_MISSING'})
                continue
            # Inspect allowlisted source-five transition arrays ONLY, never excluded frames.
            import numpy as np
            with np.load(f, allow_pickle=False) as d:
                if 'reward' in d.files and 'action' in d.files:
                    for a, r in zip(d['action'], d['reward']):
                        if r > 0:
                            positive_types[str(int(a))] += int(r)
                            ra = dst['reward_actions']
                            key = str(int(a))
                            ra[key] = ra.get(key, 0) + int(r)
        sessions = sum(x['sessions'] for x in per_family.values())
        advances = sum(x['native_advancements'] for x in per_family.values())
        success_families = sorted(f for f,x in per_family.items() if x['native_advancements'] > 0)
        primitive_rewards = sum(v for a,v in positive_types.items() if a != '6')
        gates = {
            'preliminary_ingest_status_is_ready': ing.get('status') == 'VERIFIED_READY_FOR_TRAINING',
            'at_least_20_independent_recorded_sessions': sessions >= 20,
            'at_least_30_native_advancements': advances >= 30,
            'at_least_4_successful_source_families': len(success_families) >= 4,
            'both_click_and_primitive_successes': positive_types.get('6', 0) > 0 and primitive_rewards > 0,
            'all_5_source_families_have_sessions': all(x['sessions'] > 0 for x in per_family.values()),
            'all_allowlisted_session_hashes_match': len(bad_shards) == 0,
        }
        out['ingestion'] = {
            'status': ing.get('status'),
            'manifest_sha256': digest(manifest_path),
            'rows_in_recorded_sessions': sessions,
            'total_native_advancements': advances,
            'successful_families': success_families,
            'positive_reward_action_types': dict(positive_types),
            'session_errors_visible_in_manifest': dict(errors),
            'note': 'Rejected zero-transition sessions are not retained in the original ingestion manifest',
            'per_family': per_family,
            'exact_existing_gates': gates,
            'hash_failures': bad_shards,
        }
        try:
            check = verify_human_manifest(manifest_path)
            out['verification'] = {'status': 'PASSED_ORIGINAL_STRICT_GATES', 'details': check}
            out['human_data_origin'] = 'hash_verified_pinned_human_parquet'
        except Exception as exc:
            out['verification'] = {'status': 'FAILED_CLOSED',
                                   'error': type(exc).__name__ + ': ' + str(exc)}

    frozen = read_json(work/'E074_TRAINING_COMPLETE_FREEZE.json')
    trained = work/'trained_human'
    model_names = ('bc', 'ddqn', 'shuffled', 'no_history')
    checkpoints = {}
    for mode in model_names:
        f = trained/f'history_{mode}.pt'
        checkpoints[mode] = {'exists': f.is_file(),
                             'sha256': digest(f) if f.is_file() else None,
                             'bytes': f.stat().st_size if f.is_file() else None}
    out['checkpoints'] = checkpoints
    if frozen is None:
        out['freeze'] = {'status': 'ABSENT', 'partial_models': [m for m,v in checkpoints.items() if v['exists']]}
    else:
        expected = {row['mode']:row['sha256'] for row in frozen.get('models', [])}
        valid = set(expected) == set(model_names) and all(
            checkpoints[m]['exists'] and checkpoints[m]['sha256'] == expected[m] for m in model_names)
        out['freeze'] = {
            'status': 'FOUR_HASH_VERIFIED_CHECKPOINTS' if valid else 'FREEZE_PRESENT_BUT_INCOMPLETE_OR_INVALID',
            'freeze_sha256': digest(work/'E074_TRAINING_COMPLETE_FREEZE.json'),
            'trained_modes': sorted(expected), 'expected_checkpoint_sha256': expected,
        }
    gate = read_json(work/'E074_VALIDATED_HUMAN_GATE.json')
    merged_path = trained/'human_train_source5.npz'
    merged_sha = digest(merged_path) if merged_path.is_file() else None
    lock_path = snap/'E068_HUMAN_DATA_LOCK.json'
    full_freeze_ok = bool(
        frozen and gate and ing and lock and
        out.get('verification', {}).get('status') == 'PASSED_ORIGINAL_STRICT_GATES' and
        out['freeze']['status'] == 'FOUR_HASH_VERIFIED_CHECKPOINTS' and
        frozen.get('human_dataset_verified') is True and
        frozen.get('human_data_sha256') == merged_sha and
        gate.get('input_manifest_sha256') == digest(manifest_path) and
        gate.get('human_snapshot_lock_sha256') == digest(lock_path) and
        bool(gate.get('gates')) and all(gate['gates'].values()) and
        frozen.get('source_revision') == ing.get('data_provenance', {}).get('revision') and
        frozen.get('holdout_never_trained_on') is True
    )
    out['freeze']['original_data_gate_and_merge_verified'] = full_freeze_ok
    if out['source_status'] != 'ORIGINAL_INTACT':
        out['next_step'] = 'STOP_SOURCE_INTEGRITY'
    elif full_freeze_ok:
        out['next_step'] = 'ALREADY_TRAINED_DO_NOT_REPEAT'
    elif frozen or any(v['exists'] for v in checkpoints.values()):
        out['next_step'] = 'STOP_INSPECT_PARTIAL_OR_INVALID_CHECKPOINTS'
    elif ing and out['verification']['status'] != 'PASSED_ORIGINAL_STRICT_GATES':
        out['next_step'] = 'STOP_DATA_GATE_FAILURE_DO_NOT_WEAKEN'
    else:
        out['next_step'] = 'ACQUIRE_OR_RESUME_AND_VALIDATE_BEFORE_TRAINING'
    work.mkdir(parents=True, exist_ok=True)
    target = work/'E074_CONTINUATION_STATE.json'
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    tmp.replace(target)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
