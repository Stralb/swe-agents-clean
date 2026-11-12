"""End-to-end control tests for E074; no human or game data is invented."""
import importlib.util,json,sys,pathlib
import pytest
BASE=pathlib.Path(__file__).resolve().parents[1]
sys.path[0:0]=[str(BASE/'code'),str(BASE/'vendor/e068/code'),str(BASE/'vendor/e069/code')]
from e074_pipeline import ROOT,parent_reference,check_dependencies,train,REFERENCE,sha
from e072_audit import verify_human_manifest
from acquire_human import REPO,REV
from e068_split import TRAIN_FAMILIES,TEST_FAMILIES,FORBIDDEN

def test_provenance_of_original_native_evidence():
 z=parent_reference()
 assert z['real_native_reward_events']==3
 assert z['successful_families']==['s5i5','lf52','tn36']
 assert z['native_e072_sdk_calls']==0

def test_parent_has_closed_exact_prospective_families():
 z=parent_reference()
 assert z['frozen_prospective_source_test_families']==['cn04','lp85','m0r0','r11l','sk48']
 assert z['frozen_historic_reserve']==['ar25','dc22','re86','tu93']
 assert len(z['frozen_quarantined_dev_and_protected'])==11
 assert set(TRAIN_FAMILIES)==set(z['frozen_train_families'])
 assert len(set(TRAIN_FAMILIES+TEST_FAMILIES+FORBIDDEN))==25

def test_real_pinned_huggingface_revision():
 assert REPO=='magic-sword/arc_agi_3_public_demo_human_testing'
 assert REV=='455b7c58eaa9d5ea05f91cd1b5b603121599e758'

def test_no_silent_parquet_dependency():
 deps=('numpy','torch','huggingface_hub','pyarrow')
 if all(importlib.util.find_spec(d) is not None for d in deps):
  assert len(check_dependencies()['dependencies_found'])==len(deps)
 else:
  with pytest.raises(ImportError):check_dependencies()

def test_no_unverified_human_data(tmp_path):
 mf=tmp_path/'E068_HUMAN_TRAINING_MANIFEST.json'
 mf.write_text(json.dumps({'status':'FIXTURE_ONLY_NOT_HUMAN_DATA','data_provenance':{'repo':REPO,'revision':REV}}))
 with pytest.raises(PermissionError):verify_human_manifest(mf)

def test_no_model_without_data(tmp_path,monkeypatch):
 monkeypatch.setattr('e074_pipeline.check_dependencies',lambda:{})
 with pytest.raises((FileNotFoundError,RuntimeError)):
  train(work=tmp_path/'job',fetch=False,only_ingest=True)
 assert not (tmp_path/'job'/'E074_TRAINING_COMPLETE_FREEZE.json').exists()

def test_package_directory_cannot_be_overwritten(monkeypatch):
 monkeypatch.setattr('e074_pipeline.check_dependencies',lambda:{})
 with pytest.raises(PermissionError):train(work=ROOT/'wrong-output',fetch=False)

def test_no_test_codes_in_decode_whitelist():
 from ingest_human import canonical_env,convert_session
 for code in ('cn04','lp85','m0r0','r11l','sk48','ar25','dc22','re86','tu93','bp35'):
  with pytest.raises(PermissionError):convert_session({'env':code,'trajectory':[], 'guid':'test'})
 assert canonical_env('g50t-veryrandom')=='g50t'

def test_human_scanner_uses_arrow_predicate_before_events_materialized():
 import inspect
 from ingest_human import scan_parquet
 source=inspect.getsource(scan_parquet)
 assert "filter=ds.field('env').isin(list(TRAIN_FAMILIES))" in source
 assert 'yield row' in source

def test_freeze_stage_never_opens_sdk():
 import inspect
 import e074_pipeline
 source=inspect.getsource(e074_pipeline)
 assert 'Arcade(' not in source
 assert 'sdk.make(' not in source
 assert 'evaluate_checkpoint(' not in source
 assert 'native_score_claimed' in source

def test_source_reference_hashes_are_known():
 for x in ('SOURCE_PROVENANCE.json','E071_INDEPENDENT_AUDIT.json','E067_SOURCE5_ONLY_NATIVE_RECORDS.zip'):
  assert (REFERENCE/x).is_file()
  assert len(sha(REFERENCE/x))==64


def test_vendor_training_modules_resolve_self_contained_roots():
 import source_audit,e069_human_train
 assert source_audit.E068==BASE/'vendor/e068'
 assert e069_human_train.E068==BASE/'vendor/e068'
 assert (e069_human_train.E068/'code/acquire_human.py').is_file()

def test_native_smoke_is_not_labeled_human():
 from source_audit import audit_source
 source=BASE/'reference/native_source5_smoke/native_self_play_5.npz'
 proof=audit_source(source,None)
 assert proof['kind']=='verified_legacy_native_self_play'
 assert proof['native_reward_events']==3
 with pytest.raises(PermissionError):audit_source(source,BASE/'fake.json')
