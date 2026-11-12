"""E069 fail-closed data provenance and family-split audit.

No heuristic filename-based claim that a dataset is human is permitted. Real
human mode requires E068 source snapshot, digest inventory, and a successful
E068 human training manifest that is reverified before training.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
from e068_split import TRAIN_FAMILIES,TEST_FAMILIES,FORBIDDEN,sha

BASE=Path(__file__).resolve().parents[3]
KNOWN_NATIVE_SHA='b67e4a9c5c9776ef9ade149b6acd1293169bb9057f641efe4fe42b97d0f48f43'
E068=BASE/'vendor'/'e068'


def audit_source(data_path,manifest=None):
    data_path=Path(data_path);actual=sha(data_path)
    if actual==KNOWN_NATIVE_SHA:
        if manifest is not None:raise PermissionError('Native dataset cannot be labeled human')
        return {'kind':'verified_legacy_native_self_play', 'sha256':actual,
            'families':list(TRAIN_FAMILIES),'human_sessions':0,'native_reward_events':3}
    if manifest is None:
        raise PermissionError('Unrecognized dataset digest. Explicit verified human manifest required.')
    manifest=Path(manifest);summary=json.loads(manifest.read_text())
    if (summary.get('sha256')!=actual or tuple(summary.get('families',()))!=TRAIN_FAMILIES or
        set(summary.get('excluded',()))!=set(TEST_FAMILIES) or
        set(summary.get('forbidden',()))!=set(FORBIDDEN) or
        summary.get('source_type')!='public_human_playing_not_self_generated'):
        raise PermissionError('Human dataset manifest SHA/provenance/split invalid')
    if Path(summary.get('path','')).resolve()!=data_path.resolve():
        raise PermissionError('Human merge path differs from audited manifest')
    # Check the underlying Parquet dataset, not only a self-declared JSON string.
    ingestion_path=manifest.parent.parent/'human_five_training'/'E068_HUMAN_TRAINING_MANIFEST.json'
    if not ingestion_path.exists():
        raise PermissionError('Missing original human ingestion manifest')
    if sha(ingestion_path)!=summary.get('manifest_sha256'):
        raise PermissionError('Original human manifest checksum mismatch')
    ingestion=json.loads(ingestion_path.read_text())
    if (ingestion.get('status')!='VERIFIED_READY_FOR_TRAINING' or
        tuple(ingestion.get('train_families',()))!=TRAIN_FAMILIES or
        not ingestion.get('human_data_not_native_self_generated')):
        raise PermissionError('Ingestion authorization failed')
    runtime=E068/'code';sys.path.insert(0,str(runtime))
    from acquire_human import verify
    prov=ingestion['data_provenance']
    snap=verify(prov['snapshot_root'],revision=prov['revision'])
    if {e['file']:e['sha256'] for e in snap['shards']}!=prov['sha256_by_shard']:
        raise PermissionError('Raw Parquet inventory changed')
    if int(summary.get('native_advancements',-1))!=int(ingestion.get('native_advancements',-2)):
        raise PermissionError('Native reward counts differ')
    return {'kind':'hash_locked_public_human_sessions','sha256':actual,
        'families':list(TRAIN_FAMILIES),'human_sessions':int(summary['sessions']),
        'native_reward_events':int(summary['native_advancements']),
        'underlying_hf_revision':prov['revision'],'source_manifest_sha256':sha(ingestion_path)}
