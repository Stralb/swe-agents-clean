"""Import ONLY original historic evidence and its source-recorded crosswalks.

No scripts, agents, scanners, or model inference are executed during import.
Every structured assertion is traceable to original bytes and source location.
Data is private until an independent IP, privacy and provenance review.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Any

from .store import EvidenceError, EvidenceStore, _now
from .research import ResearchIndex, canonical_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS historical_file_index (
    member_id INTEGER PRIMARY KEY REFERENCES archive_members(member_id),
    archive_sha256 TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    source_path TEXT,
    source_case_id TEXT,
    source_condition TEXT,
    source_generation TEXT NOT NULL,
    source_evaluation_status TEXT NOT NULL,
    index_manifest_member_id INTEGER REFERENCES archive_members(member_id),
    original_member_sha256 TEXT NOT NULL,
    original_member_bytes INTEGER NOT NULL,
    source_recorded_metadata_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hist_file_case ON historical_file_index(source_case_id,source_generation);
CREATE INDEX IF NOT EXISTS idx_hist_file_path ON historical_file_index(source_path);
CREATE TABLE IF NOT EXISTS historical_generation_runs (
    run_pk INTEGER PRIMARY KEY,
    study TEXT NOT NULL,
    case_id TEXT NOT NULL,
    arm TEXT NOT NULL,
    iteration TEXT NOT NULL,
    source_manifest_member_id INTEGER NOT NULL REFERENCES archive_members(member_id),
    source_report_member_id INTEGER REFERENCES archive_members(member_id),
    patch_member_id INTEGER NOT NULL REFERENCES archive_members(member_id),
    patch_sha256 TEXT NOT NULL,
    status_from_source TEXT NOT NULL,
    source_meta_json TEXT NOT NULL,
    provenance_status TEXT NOT NULL,
    UNIQUE(study,case_id,arm,iteration)
);
CREATE INDEX IF NOT EXISTS idx_hist_runs_case ON historical_generation_runs(case_id,arm);
CREATE TABLE IF NOT EXISTS historical_scans (
    scan_pk INTEGER PRIMARY KEY,
    run_pk INTEGER NOT NULL UNIQUE REFERENCES historical_generation_runs(run_pk),
    report_member_id INTEGER NOT NULL REFERENCES archive_members(member_id),
    sarif_member_id INTEGER REFERENCES archive_members(member_id),
    patch_hash_agrees INTEGER NOT NULL CHECK(patch_hash_agrees IN (0,1)),
    source_codeql_version TEXT,
    source_suite TEXT,
    source_target_rule TEXT,
    source_baseline_sha256 TEXT,
    baseline_member_present INTEGER NOT NULL CHECK(baseline_member_present IN (0,1)),
    source_reported_before_count INTEGER,
    source_reported_after_count INTEGER,
    source_reported_new_count INTEGER,
    source_reported_target_count INTEGER,
    source_functional_status TEXT,
    source_result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historical_sarif_findings (
    finding_pk INTEGER PRIMARY KEY,
    scan_pk INTEGER NOT NULL REFERENCES historical_scans(scan_pk),
    sarif_result_index INTEGER NOT NULL,
    rule_id TEXT,
    message_text TEXT,
    file_uri TEXT,
    line_number INTEGER,
    result_level TEXT,
    result_json_sha256 TEXT NOT NULL,
    UNIQUE(scan_pk,sarif_result_index)
);
CREATE INDEX IF NOT EXISTS idx_hist_sarif_rule ON historical_sarif_findings(rule_id);
CREATE TABLE IF NOT EXISTS historical_test_observations (
    observation_pk INTEGER PRIMARY KEY,
    case_id TEXT NOT NULL,
    arm TEXT NOT NULL,
    test_kind TEXT NOT NULL,
    status_from_source TEXT,
    source_member_id INTEGER NOT NULL REFERENCES archive_members(member_id),
    source_patch_sha256 TEXT,
    source_json TEXT NOT NULL,
    UNIQUE(case_id,arm,test_kind,source_member_id)
);
CREATE INDEX IF NOT EXISTS idx_hist_tests_case ON historical_test_observations(case_id,arm);
CREATE TABLE IF NOT EXISTS historical_study_register (
    study_id TEXT PRIMARY KEY,
    phase_order INTEGER NOT NULL,
    frozen_scope TEXT NOT NULL,
    expected_evidence TEXT NOT NULL,
    evidence_state TEXT NOT NULL,
    cautions TEXT NOT NULL,
    citation_to_historical_source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historical_recovery_targets (
    expected_name TEXT PRIMARY KEY,
    study_id TEXT NOT NULL REFERENCES historical_study_register(study_id),
    priority INTEGER NOT NULL,
    source_locator TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('listed_not_imported','not_located','locally_imported','source_verified')),
    note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historical_archive_audits (
    archive_sha256 TEXT PRIMARY KEY,
    index_member_id INTEGER NOT NULL REFERENCES archive_members(member_id),
    listed_members INTEGER NOT NULL,
    verified_members INTEGER NOT NULL,
    missing_from_index INTEGER NOT NULL,
    mismatched_digest INTEGER NOT NULL,
    recorded_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historical_target_events (
    event_pk INTEGER PRIMARY KEY,
    expected_name TEXT NOT NULL REFERENCES historical_recovery_targets(expected_name),
    source_sha256 TEXT REFERENCES artifacts(sha256),
    new_status TEXT NOT NULL CHECK(new_status IN ('source_verified','listed_not_imported','not_located')),
    evidence_location TEXT NOT NULL,
    observation TEXT NOT NULL,
    recorded_utc TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS historical_recovery_current AS
 SELECT t.expected_name,t.study_id,t.priority,t.source_locator,
        COALESCE((SELECT e.new_status FROM historical_target_events e
                  WHERE e.expected_name=t.expected_name ORDER BY e.event_pk DESC LIMIT 1),t.status) as current_status,
        (SELECT e.source_sha256 FROM historical_target_events e
         WHERE e.expected_name=t.expected_name ORDER BY e.event_pk DESC LIMIT 1) as latest_verified_sha256,
        t.note
 FROM historical_recovery_targets t;
CREATE TABLE IF NOT EXISTS historical_claim_register (
    claim_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL REFERENCES historical_study_register(study_id),
    source_reported_claim TEXT NOT NULL,
    verification_status TEXT NOT NULL CHECK(verification_status IN
       ('source_bytes_matched','reported_not_reproduced','disputed_historical_versions',
        'contextual_not_independently_checked','partially_source_verified')),
    scientific_scope TEXT NOT NULL,
    authoritative_source_reference TEXT NOT NULL,
    source_original_sha256 TEXT REFERENCES artifacts(sha256),
    missing_evidence TEXT NOT NULL,
    recorded_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historical_text_index (
    member_id INTEGER PRIMARY KEY REFERENCES archive_members(member_id),
    text_excerpt TEXT NOT NULL,
    excerpt_length INTEGER NOT NULL,
    full_file_bytes INTEGER NOT NULL,
    indexed_utc TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS historical_fts USING fts5(member_path UNINDEXED, excerpt, tokenize='unicode61');
"""
IMMUTABLE = ('historical_file_index','historical_generation_runs',
             'historical_scans','historical_sarif_findings','historical_test_observations',
             'historical_study_register','historical_recovery_targets',
             'historical_archive_audits','historical_text_index', 'historical_target_events', 'historical_claim_register')

PHASES = [
 ('P00_SUPERVISOR_CONCEPT','Original CISPA project brief and Honours proposal',
  'Supervisor instructions, proposal, selected papers, versioned research questions',
  'Referenced PDF/handoff available; claim-evidence alignment not audited'),
 ('P01_MINER_AND_WORKFLOWS','Initial GitHub agent workflow miner and 3,809 frozen workflows',
  'Frozen miner SQLite, SQL lineage, agent/issue/PR crosswalk, full scraper results',
  'Original canonical frozen 3,809-workflow database bytes not imported'),
 ('P02_122_FIRST_AUDIT','Initial source-coded 122 workflows, 605 canonical findings',
  'Authoritative historical master workbook, all first-pass/QC/annotation versions, exclusions',
  'Source workbook imported; completeness of earlier versions not independently proven'),
 ('P03_FOOTPRINTS_AND_SWEXPLOIT','F1-F5 footprint protocol and controlled attack source review',
  'Frozen F1-F5 protocol, F1-F5 validation workbooks, 122-case blind codes, controlled attack data',
  'Most historical originals are only listed in Library/cluster'),
 ('P04_SCAN_COHORT','3,809 to 192 positive to 191 mappable workflows',
  'C1 scanner census, scanner config/SARIF, case exclusions and frozen cohort revisions',
  'Denominators require full original database lineage check'),
 ('P05_PRODUCING_CHANGES','455 producing changes and 342 root groups',
  'Source-diff/PR patches, 455 raw attribution rows, root membership, corrections',
  'Full original 455-change provenance not yet byte imported'),
 ('P06_D_DOUBLE_CODING','Independent blind A/B coding and D/D7 route adjudication',
  'D coder packets, coder original responses, adjudication 198, D5 342, D7 342, 43 disagreement records',
  'D-original/D7 disagreement must remain unresolved pending source adjudication'),
 ('P07_MATCHED_CONTROLS','190 matched pairs (115 same-repo) and C6/C7 results',
  'C1-C7 original matched pairs, negative controls, blind coding, contingency tests',
  'C6 original paired records not yet recovered into this vault'),
 ('P08_NEW70','Frozen NEW70 blind issue/PR/implementation/risk phases',
  'Phase1-9 frozen inputs and outputs, all 70 selected cases, original patches/risks',
  'Original phase datasets need import and crosswalk verification'),
 ('P09_T1_CONTEXT','T1 context intervention and follow-up controls',
  'T1 actual run bundles, blinded reviews, unblinding map, code, seed/config, null results',
  'T1 archive bytes not yet imported'),
 ('P10_T2_TRANSFER','T2 retrieval, run comparison, semantic assessment',
  'T2 original runs, generation outputs, frozen blind adjudications and controls',
  'T2 archive bytes not yet imported'),
 ('P11_S5PAIR','S5PAIR-001 12 blinded generation runs and pilot review',
  '12 original INPUT/OUTPUT ZIPs, all 12 patches, 12 reports, CodeQL SARIF, separate blind/unblind map',
  'Only six prior S5PAIR metadata files are locally imported'),
 ('P12_PREVENTION_65','65-case prevention-screen O1/O2/O3 generated patches',
  'Three original 65-patch generations, manifest claims, QC, scanners and test reports',
  'Patch files available in uploaded five-part archive; test claims not re-executed'),
 ('P13_COUNTERFACTUAL_14','14-case O/W/P historical prevention pilot',
  '40 original generated patches (12 O, 14 W, 14 P), 40 after SARIF, codeql reports, syntax and behavior tests',
  'Original before SARIF missing in uploaded parts; functional comparability limited'),
 ('P14_PAPER_CLAIMS','Publication claims, primary/secondary results and versioned manuscript',
  'Frozen tables, statistical tests, claim-to-evidence crosswalk, manuscript revisions and critical limitations',
  'No causal claims validated simply by reindexing source outputs'),
 ('P15_RELEASE_REPRODUCIBILITY','Private review release and Hugging Face archival copy',
  'Hash manifests, permissions, blind split, source code, DB, tools and reviewer scripts',
  'Historical Hugging Face dataset incomplete; no upload performed'),
]

# These are historical original names already located in previous project history.
RECOVERY = {
 'P00_SUPERVISOR_CONCEPT':['main (79).pdf','Arno_Research_Full_Handoff_2026-08-20(1).pdf'],
 'P01_MINER_AND_WORKFLOWS':['full3809-scanner-complete-20260829.db','ARNO_RESEARCH_ESSENTIAL_SOURCES_2026-08-20.zip'],
 'P02_122_FIRST_AUDIT':['issue_pr_manual_evaluation_master_122(1).xlsx','F1-F5_Blind_Real122_Audit_v1.0.xlsx'],
 'P03_FOOTPRINTS_AND_SWEXPLOIT':['F4_FINAL_DELIVERABLES.zip','F5_FINAL_DELIVERABLES.zip','F1-F5_Combined_Audit_Protocol_FROZEN_v1.0.xlsx'],
 'P04_SCAN_COHORT':['C1_CASE_SCANNER_OPPORTUNITY_3809.csv','C1_POSITIVE_FEASIBILITY_192.csv'],
 'P05_PRODUCING_CHANGES':['PROV_Phase6_FULL_PROVENANCE_455_FROZEN_v1.0.csv','PROVENANCE_SCALEOUT_Phase6_FINAL_v1.0.zip','PROVENANCE_CLOSURE_EVIDENCE_20260903T195508Z.tar.gz'],
 'P06_D_DOUBLE_CODING':['D_EVIDENCE_EXPORT_MASTER_v1.1.tar.gz','D4_ADJUDICATION_198.jsonl','D5_FINAL_ROOT_CENSUS_342.jsonl','D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv','D7_DISCOVERY_HOLDOUT_BUNDLE_GPT56SOL_v1.0.tar.gz'],
 'P07_MATCHED_CONTROLS':['C6_MATCHED_POSITIVE_VS_CONTROL_v1.0.tar.gz','C7_CONTROL_PATHWAY_INTEGRATION_v1.0.tar.gz','C6_MATCHED_PAIR_MASTER_190.csv'],
 'P08_NEW70':['NEW70_90_LOCKED_FOR_LATER.zip','NEW70_Phase9_Risk_Assessment_FINAL_v1.0.zip'],
 'P09_T1_CONTEXT':['T1_PRIMARY_PILOT_RUN_BUNDLES_v1.tar.gz','T1_V9_FULL_BLIND_REVIEW.tar.gz','T1_V9_BLIND_ADJUDICATION_FROZEN_v1.tar.gz'],
 'P10_T2_TRANSFER':['T2_FINAL4_RUNS_v1.zip','T2_FINAL4_GENERATIONS_FROZEN_v1.zip'],
 'P11_S5PAIR':['S5PAIR001_12_CHAT_INPUTS.zip','S5PAIR001_STEP4_BLINDED_EVAL_BUNDLE.zip','S5PAIR001_PILOT_AUDIT_BUNDLE_v1.zip'],
 'P12_PREVENTION_65':['02_ALL_GENERATED_PATCHES.zip'],
 'P13_COUNTERFACTUAL_14':['03_CODEQL_SARIF_AND_SCANS.zip','04_FUNCTIONAL_TESTS_AND_TRIAGE.zip','07_AGENT_PROMPTS_AND_TRACES.zip','08_SCRIPTS_CONFIGS_AND_PROVENANCE.zip'],
 'P14_PAPER_CLAIMS':['ARNO_PAPER_CLAIMS_VERIFIED_v2.csv','ARNO_RESEARCH_HISTORY_VERIFIED_v1_1.xlsx','ARNO_FINAL_UNIFIED_CONSENSUS_FULL_REVIEW_WORKBOOK.xlsx'],
 'P15_RELEASE_REPRODUCIBILITY':['arno-research-reproducibility (GitHub private repo)','Stralb/malicious-issue-miner-data (Hugging Face private)'],
}


# Claims are literal source-reported statements or narrowly defined archive-byte facts;
# import-time recovery cannot convert scanner warnings into real vulnerabilities.
CLAIMS = [
 ('C001','P01_MINER_AND_WORKFLOWS','3,809 frozen agent-associated merged-PR workflows',
   'reported_not_reproduced','Historical frozen workflow population','docs/RESEARCH_MAP.md',None,
   'Original complete 29-Aug frozen miner SQLite not byte authenticated'),
 ('C002','P04_SCAN_COHORT','192 scanner-positive workflows; 191 exactly mapped to producing changes (case 17701 unmapped)',
   'reported_not_reproduced','C1/C5/D1 source-roster accounting only','docs/FROZEN_POSITIVE_TO_ROOT_LINEAGE_20261022.md',None,
   'Original 3,809 DB, scanner reruns, false-positive validation'),
 ('C003','P05_PRODUCING_CHANGES','455 producing changes mapped into 342 implementation roots, 283 singleton and 59 multi-change roots',
   'reported_not_reproduced','Frozen source crosswalk accounting','docs/FROZEN_POSITIVE_TO_ROOT_LINEAGE_20261022.md',None,
   'Original matched root/PC complete raw files not locally imported'),
 ('C004','P06_D_DOUBLE_CODING','D original 342-root route H=5,T=103,M=234; D7 H=6,T=103,M=233',
   'disputed_historical_versions','Two distinct frozen source versions, not interchangeable','docs/RESEARCH_MAP.md',None,
   'Original D-final/D7 decisions and adjudication records; 43 disagreements need adjudication'),
 ('C005','P07_MATCHED_CONTROLS','190 positive-control workflow pairs; 115 same-repository pairs',
   'reported_not_reproduced','Matching cohort counts, not an effect estimate','docs/RESEARCH_MAP.md',None,
   'Original 190-pair raw C6/C7 with same-repository stratum and censoring'),
 ('C006','P07_MATCHED_CONTROLS','51 decision-level control matches, of which 31 primary',
   'reported_not_reproduced','Decision pairs differ in unit from workflow matches','docs/RESEARCH_MAP.md',None,
   'Original decision-level controls Step4–7 blind packets and test outputs'),
 ('C007','P02_122_FIRST_AUDIT','122-case original source workbook with risk and implementation classifications indexed as recorded',
   'source_bytes_matched','Historical workbook rows/labels not a new human recoding','issue_pr_manual_evaluation_master_122(1).xlsx',None,
   'Prior blind versions and inter-pass QC underlying scientific labels'),
 ('C008','P03_FOOTPRINTS_AND_SWEXPLOIT','No convincing malicious cases in the earlier 122-case inspected corpus (historical August handoff assertion)',
   'contextual_not_independently_checked','Historical null-result framing, not universal prevalence estimate','Arno_Research_Full_Handoff_2026-08-20(1).pdf',None,
   'Original final F1–F5 122-case blind coded evidence and human verification'),
 ('C009','P12_PREVENTION_65','65 case-specific candidate patch files preserved separately for each of three source-labelled O1/O2/O3 screening iterations',
   'source_bytes_matched','Existence and source hashes of generated versions only','02_ALL_GENERATED_PATCHES.zip',None,
   'Original generation prompts, independent task validation and experimental comparability'),
 ('C010','P13_COUNTERFACTUAL_14','40 exact original O/W/P generated patches recovered (O=12,W=14,P=14) and 40 matching after-SARIF files',
   'source_bytes_matched','Source-recorded generated patches and scanner outputs, not validated functional solutions','02_ALL_GENERATED_PATCHES.zip + 03_CODEQL_SARIF_AND_SCANS.zip',None,
   '14 original before-SARIF base objects, full functionality and matched recruitment'),
 ('C011','P13_COUNTERFACTUAL_14','All 40 historical O/W/P scanner reports label functional_status=NOT_VALIDATED',
   'source_bytes_matched','Source-recorded functional limit; no inferred task success','03_CODEQL_SARIF_AND_SCANS.zip',None,
   'Independent functional acceptance, repository setup and original pre-PR context'),
 ('C012','P13_COUNTERFACTUAL_14','The 40 original after-SARIF files contain 5,998 SARIF results in total',
   'source_bytes_matched','Total SARIF results, NOT 5,998 newly introduced or real vulnerabilities','03_CODEQL_SARIF_AND_SCANS.zip',None,
   'Original baseline before-SARIF for introduced-delta and warning applicability'),
 ('C013','P13_COUNTERFACTUAL_14','14 distinct baseline SARIF SHA-256 digests referenced in reports are not included among recovered archive members',
   'source_bytes_matched','Absent from current private evidence store, not proof of global loss','03_CODEQL_SARIF_AND_SCANS.zip',None,
   'Retrieve all 14 original baseline objects by exact source sha'),
 ('C014','P11_S5PAIR','S5PAIR-001 historical blinded evaluation metadata contains 12 run IDs; generated patch and full SARIF payloads remain absent locally',
   'partially_source_verified','Exact six source metadata files only; no arm unblinding','S5PAIR001_STEP4_BLINDED source-only metadata',None,
   'G001–G012 original outputs/patches and matching SARIF, blind/unblind maps'),
 ('C015','P14_PAPER_CLAIMS','Original source-aligned reporting still requires scientific validity and claim-to-patch provenance checks before publication',
   'contextual_not_independently_checked','Research recovery status, not a quantitative discovery','docs/RESEARCH_RECOVERY_COMPLETION_SCORECARD_20261023.md',None,
   'Full raw frozen source artifacts, statistical scripts and independent human approvals'),
]

MIME_TEXT_EXTS={'.json','.jsonl','.csv','.md','.txt','.log','.py','.sbatch','.mjs','.err','.out','.patch','.diff'}


def _as_text(b: bytes) -> str:
    return b.decode('utf-8',errors='replace')


def _int(v: Any) -> int | None:
    if isinstance(v,bool):return None
    if isinstance(v,int):return v
    if isinstance(v,float) and v.is_integer():return int(v)
    if isinstance(v,str) and v.strip().isdigit():return int(v)
    return None


def _case(v: Any) -> str | None:
    i=_int(v)
    return str(i) if i is not None else None


def _canonical_from_json(j: Any) -> str:
    try:return canonical_json(j)
    except ValueError:return json.dumps(j,sort_keys=True,default=str)


class HistoricalRecovery:
    def __init__(self, store: EvidenceStore):
        self.store=store
        ResearchIndex(store)
        with store._open() as cx:
            cx.executescript(SCHEMA)
            for table in IMMUTABLE:
                for operation in ('UPDATE','DELETE'):
                    cx.execute(f"CREATE TRIGGER IF NOT EXISTS hist_no_{table}_{operation.lower()} "
                               f"BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable historical evidence'); END")

    def _all_members(self):
        with self.store._open(readonly=True) as cx:
            return cx.execute("""SELECT b.source_sha256, a.member_id, a.member_path, a.member_sha256,
                               a.member_bytes, a.source_id
                               FROM archive_members a JOIN research_batches b ON b.batch_id=a.batch_id
                               WHERE b.adapter='archive-member-capture'
                               ORDER BY b.batch_id,a.member_id""").fetchall()

    @staticmethod
    def _suffix_member(member: str) -> str:
        p=PurePosixPath(member)
        return p.name

    def index(self, *, include_text: bool=True) -> dict[str,Any]:
        members=self._all_members()
        if not members:raise EvidenceError('No original archive members')
        manifests={}
        indexed_count=0
        seen_paths={}
        for archive, member_id, name, sha, size, source_id in members:
            seen_paths[(archive,name)]=(member_id,sha,size,source_id)
            if name=='00_README_AND_MANIFEST/PART_INDEX.csv':
                data=self.store.bytes_for_digest(sha)
                manifests[archive]=(member_id,list(csv.DictReader(io.StringIO(_as_text(data)))))
        if not manifests:raise EvidenceError('No archive part-index files')
        expected=set(manifests)
        for archive in expected:
            with self.store._open(readonly=True) as cx:
                existing=cx.execute('SELECT 1 FROM historical_archive_audits WHERE archive_sha256=?',(archive,)).fetchone()
            if existing:continue
            mid,rows=manifests[archive]
            listed=set()
            records=[]
            for item in rows:
                path=item['archive_path']
                if path in listed:raise EvidenceError('Duplicate row in part index '+path)
                listed.add(path)
                rec=seen_paths.get((archive,path))
                if not rec:raise EvidenceError('Manifest references missing captured bytes '+path)
                member_id,actual,size,_=rec
                if actual!=item['sha256'].lower():raise EvidenceError('Part-index content SHA mismatch '+path)
                if size!=int(item['bytes']):raise EvidenceError('Part-index size mismatch '+path)
                if item.get('original_filename')!=PurePosixPath(path).name:
                    raise EvidenceError('Part-index basename discrepancy '+path)
                meta=_canonical_from_json(item)
                records.append((member_id,archive,item['original_filename'],item.get('source_path'),_case(item.get('case_id')),
                                item.get('condition') or None,item.get('generation') or 'UNSPECIFIED',
                                item.get('evaluation_status') or 'RAW_UNKNOWN',mid,actual,size,meta))
            actual={name for (digest,name) in seen_paths if digest==archive and name!='00_README_AND_MANIFEST/PART_INDEX.csv'}
            extras=actual-listed
            if extras:raise EvidenceError('Captured file(s) unlisted by original manifest '+str(sorted(extras)[:3]))
            with self.store._open() as cx:
                cx.executemany('''INSERT INTO historical_file_index(member_id,archive_sha256,original_filename,source_path,
                      source_case_id,source_condition,source_generation,source_evaluation_status,
                      index_manifest_member_id,original_member_sha256,original_member_bytes,source_recorded_metadata_json)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',records)
                cx.execute('''INSERT INTO historical_archive_audits
                  (archive_sha256,index_member_id,listed_members,verified_members,missing_from_index,mismatched_digest,recorded_utc)
                  VALUES (?,?,?,?,?,?,?)''',(archive,mid,len(rows),len(rows),0,0,_now()))
            indexed_count+=len(rows)
        self._index_studies()
        self._index_claims()
        self._index_runs()
        self._index_tests()
        self._index_sarif()
        if include_text:self._index_text()
        return self.summary()

    def mark_recovered(self, filename:str, source_sha256:str, *,
                       evidence_location:str, observation:str='Original bytes preserved in private vault'):
        with self.store._open(readonly=True) as cx:
            if cx.execute('SELECT 1 FROM historical_recovery_targets WHERE expected_name=?',(filename,)).fetchone() is None:
                raise EvidenceError('Unknown expected original artifact: '+filename)
        self.store.bytes_for_digest(source_sha256)
        with self.store._open() as cx:
            if cx.execute('SELECT 1 FROM historical_target_events WHERE expected_name=? AND source_sha256=?',(filename,source_sha256)).fetchone():
                return False
            cx.execute('INSERT INTO historical_target_events '
                       '(expected_name,source_sha256,new_status,evidence_location,observation,recorded_utc) '
                       'VALUES (?,?,?,?,?,?)',
                       (filename,source_sha256,'source_verified',evidence_location,observation,_now()))
        return True

    def _index_studies(self):
        with self.store._open() as cx:
            for index,(key,scope,evidence,note) in enumerate(PHASES):
                cx.execute('''INSERT OR IGNORE INTO historical_study_register
                 (study_id,phase_order,frozen_scope,expected_evidence,evidence_state,cautions,citation_to_historical_source)
                 VALUES (?,?,?,?,?,?,?)''',(
                     key,index,scope,evidence,'PARTIAL_VERIFIED_OR_ONLY_LISTED',note,
                     'Arno_Research_Full_Handoff_2026-08-20(1).pdf; repo docs/RESEARCH_MAP.md; original study packets'
                ))
            for study,names in RECOVERY.items():
                for rank,n in enumerate(names,1):
                    status='locally_imported' if any(s==n for s in
                        ('02_ALL_GENERATED_PATCHES.zip','03_CODEQL_SARIF_AND_SCANS.zip',
                         '04_FUNCTIONAL_TESTS_AND_TRIAGE.zip','07_AGENT_PROMPTS_AND_TRACES.zip',
                         '08_SCRIPTS_CONFIGS_AND_PROVENANCE.zip','issue_pr_manual_evaluation_master_122(1).xlsx')) else 'listed_not_imported'
                    cx.execute('''INSERT OR IGNORE INTO historical_recovery_targets
                      (expected_name,study_id,priority,source_locator,status,note) VALUES (?,?,?,?,?,?)''',
                      (n,study,rank,'ChatGPT Library; old chats; Wits research_artifacts; private GitHub and HF',status,
                      'Filename only until original byte digest authenticated; do not regenerate'))

    def _index_claims(self):
        with self.store._open() as cx:
            for cid,study,claim,state,scope,source,original_sha,gap in CLAIMS:
                cx.execute('''INSERT OR IGNORE INTO historical_claim_register

                     (claim_id,study_id,source_reported_claim,verification_status,scientific_scope,
                      authoritative_source_reference,source_original_sha256,missing_evidence,recorded_utc)
                     VALUES (?,?,?,?,?,?,?,?,?)''',
                     (cid,study,claim,state,scope,source,original_sha,gap,_now()))

    def _index_runs(self):
        with self.store._open(readonly=True) as cx:
            rows=cx.execute("""SELECT f.member_id,a.member_path,a.member_sha256,
                         f.source_generation,f.source_case_id,f.archive_sha256
                         FROM historical_file_index f JOIN archive_members a USING(member_id)
                         WHERE lower(f.original_filename) LIKE '%.patch'
                         ORDER BY f.member_id""").fetchall()
            by_path={x[1]:x for x in rows}
            by_sha=defaultdict(list)
            for row in rows:by_sha[row[2]].append(row)
            manifests=cx.execute("""SELECT a.member_id,a.member_path,a.member_sha256
                         FROM archive_members a WHERE a.member_path LIKE '%/TRANSFER_MANIFEST.json'
                             OR a.member_path LIKE '%/MANIFEST.json'
                             OR (a.member_path LIKE '%/SUMMARY.json' AND a.member_path LIKE '%/owp14%')
                         ORDER BY a.member_id""").fetchall()
        created=[]
        # Three 14-case arms: report has explicit case_id and arm, and original patch sha.
        for source_id,pathname,sha in manifests:
            if '/owp14_' not in pathname or not pathname.endswith('/SUMMARY.json'):
                continue
            data=json.loads(_as_text(self.store.bytes_for_digest(sha)))
            cases=data.get('cases')
            if not isinstance(cases,dict) or not isinstance(data.get('received'),int):continue
            for original_case,report in cases.items():
                cid=_case(report.get('case_id'))
                arm=report.get('arm')
                if cid!=_case(original_case) or arm not in {'O','W','P'}:
                    raise EvidenceError('OWP source summary inconsistent case or arm')
                filename=report.get('filename')
                if not isinstance(filename,str) or '/' in filename or not filename.endswith('.patch'):
                    raise EvidenceError('Expected exactly one original patch filename')
                dirname=pathname.rsplit('/',1)[0]
                patchpath=f"{dirname}/CASE_{cid.zfill(5)}/{filename}"
                patch=by_path.get(patchpath)
                if not patch or patch[2]!=report.get('original_patch_sha256'):
                    raise EvidenceError('OWP report patch hash or link mismatches '+patchpath)
                if patch[0] is None or report.get('original_patch_bytes')!=self._member_size(patch[0]):
                    raise EvidenceError('OWP original patch size mismatch '+patchpath)
                recordname=f"{dirname}/CASE_{cid.zfill(5)}/RESULT.json"
                rmid=self._member_id(recordname)
                if rmid is None:raise EvidenceError('Missing source run result '+recordname)
                result=json.loads(_as_text(self._bytes_member(rmid)))
                if _case(result.get('case_id'))!=cid or result.get('arm')!=arm:
                    raise EvidenceError('Case/arm conflict in original result')
                if result.get('original_patch_sha256')!=patch[2]:
                    raise EvidenceError('Original per-case result does not authenticate patch')
                created.append(('OWP14',cid,arm,'20261018',source_id,rmid,patch[0],patch[2],
                                str(report.get('stage') or 'UNKNOWN'),_canonical_from_json(report),
                                'MATCHED_SOURCE_SUMMARY_PER_CASE_RESULT_AND_PATCH_SHA256'))
        # Three distinct original 65-case generation manifests, with their original stage labels.
        for member_id,manifest_path,manifest_sha in manifests:
            if '/screen65_' not in manifest_path or not manifest_path.endswith(('/MANIFEST.json','/TRANSFER_MANIFEST.json')):
                continue
            data=json.loads(_as_text(self.store.bytes_for_digest(manifest_sha)))
            patches=data.get('patches')
            if not isinstance(patches,list) or len(patches)!=65:
                raise EvidenceError('65-screen manifest has unexpected patches count')
            prefix=manifest_path.rsplit('/',1)[0]
            stage=('O1' if '/screen65_static_analysis_' in manifest_path else
                   'O2' if '/screen65_second_' in manifest_path else
                   'O3' if '/screen65_iter3_' in manifest_path else None)
            if not stage:raise EvidenceError('Unknown 65-screen manifest stage')
            for report in patches:
                cid=_case(report.get('case_id'))
                claimed_sha=report.get('sha256') or report.get('patch_sha256')
                if not cid or not isinstance(claimed_sha,str):raise EvidenceError('Missing case/hash in screen65 manifest')
                if stage in {'O1','O3'}:
                    filename=report.get('patch_filename')
                    if not filename:raise EvidenceError('Missing source patch filename')
                    # For O1 the source transfer manifest can reference a different original
                    # patch filename from the staged packaged basename; resolve by hash only
                    # within this exact source iteration.
                matches=[x for digest,xs in by_sha.items() if digest==claimed_sha for x in xs if x[1].startswith(prefix+'/patches/')]
                if len(matches)!=1:
                    raise EvidenceError(f'Expected one exact patch by SHA in {stage} case {cid}; got {len(matches)}')
                p=matches[0]
                claimed_size=report.get('patch_bytes') if stage=='O3' else report.get('bytes')
                if claimed_size is not None and claimed_size!=self._member_size(p[0]):
                    raise EvidenceError('Source 65-screen patch size conflict '+cid)
                created.append(('SCREEN65',cid,stage,stage,member_id,None,p[0],p[2],
                                str(report.get('claimed_status') or report.get('status') or 'UNSPECIFIED'),
                                _canonical_from_json(report),'MANIFEST_ITEM_AND_EXACT_SOURCE_PATCH_SHA256'))
        keys=[(x[0],x[1],x[2],x[3]) for x in created]
        if len(keys)!=len(set(keys)) or len(created)!=235:
            raise EvidenceError(f'Expected 235 authentic original patch run records, got {len(created)}')
        with self.store._open() as cx:
            count=cx.execute('SELECT COUNT(*) FROM historical_generation_runs').fetchone()[0]
            if count:
                if count!=235:raise EvidenceError('Existing incompatible run index')
            else:
                cx.executemany('''INSERT INTO historical_generation_runs
                 (study,case_id,arm,iteration,source_manifest_member_id,source_report_member_id,
                  patch_member_id,patch_sha256,status_from_source,source_meta_json,provenance_status)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)''',created)

    def _member_id(self,path:str) -> int|None:
        with self.store._open(readonly=True) as cx:
            row=cx.execute('SELECT member_id FROM archive_members WHERE member_path=?',(path,)).fetchone()
        return row[0] if row else None

    def _member_size(self,mid:int)->int:
        with self.store._open(readonly=True) as cx:
            row=cx.execute('SELECT member_bytes FROM archive_members WHERE member_id=?',(mid,)).fetchone()
        if not row:raise EvidenceError('Archive member not found')
        return row[0]

    def _bytes_member(self,mid:int)->bytes:
        with self.store._open(readonly=True) as cx:
            row=cx.execute('SELECT member_sha256 FROM archive_members WHERE member_id=?',(mid,)).fetchone()
        if not row:raise EvidenceError('Archive member not found')
        return self.store.bytes_for_digest(row[0])

    def _index_sarif(self):
        with self.store._open(readonly=True) as cx:
            runrows=cx.execute("""SELECT run_pk,case_id,arm,patch_sha256
                        FROM historical_generation_runs WHERE study='OWP14'""").fetchall()
            paths=cx.execute("SELECT member_path,member_id FROM archive_members").fetchall()
        lookup={x[0]:x[1] for x in paths}
        scans=[]
        for pk,cid,arm,patch_sha in runrows:
            pathprefix=('/owp14_user12_o_codeql_job71159/' if arm=='O' else
                        '/owp14_user14_w_codeql_job71209/' if arm=='W' else
                        '/owp14_user14_p_codeql_job71204/')
            hits=[p for p in lookup if p.endswith(pathprefix+f'CASE_{cid.zfill(5)}/RESULT.json')]
            if len(hits)!=1:raise EvidenceError(f'Missing exact scan result case {cid} arm {arm}')
            path=hits[0]
            report=json.loads(_as_text(self._bytes_member(lookup[path])))
            if _case(report.get('case_id'))!=cid or report.get('arm')!=arm:
                raise EvidenceError('Cross-arm original scan result')
            agrees=report.get('patch_sha256')==patch_sha
            if not agrees:raise EvidenceError(f'Scanner patch mismatch for {cid} arm {arm}')
            spath=path.rsplit('/',1)[0]+'/after.sarif'
            sarif_id=lookup.get(spath)
            if sarif_id is None:raise EvidenceError('No source after-SARIF '+spath)
            baseline=report.get('baseline_sarif_sha256')
            with self.store._open(readonly=True) as cx:
                base_present=bool(cx.execute("""SELECT 1 FROM archive_members
                   WHERE member_sha256=? LIMIT 1""",(baseline,)).fetchone()) if baseline else False
            scans.append((pk,lookup[path],sarif_id,1,report.get('current_codeql_version'),report.get('suite'),
                          report.get('target_rule'),baseline,int(base_present),_int(report.get('codeql_before_total')),
                          _int(report.get('codeql_after_total')),_int(report.get('new_strong_total')),
                          _int(report.get('new_strong_target_rule')),report.get('functional_status'),_canonical_from_json(report)))
        with self.store._open() as cx:
            if cx.execute('SELECT COUNT(*) FROM historical_scans').fetchone()[0]:return
            cx.executemany('''INSERT INTO historical_scans
               (run_pk,report_member_id,sarif_member_id,patch_hash_agrees,source_codeql_version,source_suite,
                source_target_rule,source_baseline_sha256,baseline_member_present,source_reported_before_count,
                source_reported_after_count,source_reported_new_count,source_reported_target_count,
                source_functional_status,source_result_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',scans)
        with self.store._open(readonly=True) as cx:
            targets=cx.execute('''SELECT scan_pk,sarif_member_id,source_reported_after_count
                                  FROM historical_scans ORDER BY scan_pk''').fetchall()
        found_count=0
        for scan_pk,member_id,source_count in targets:
            data=json.loads(_as_text(self._bytes_member(member_id)))
            runs=data.get('runs')
            if not isinstance(runs,list):raise EvidenceError('Expected SARIF 2.1 runs')
            results=[]
            for sarif_run in runs:
                for obj in sarif_run.get('results',[]):
                    results.append(obj)
            # SARIF result count can differ from source report CodeQL count due to
            # source postprocessing. Record disagreement, do not alter original.
            findings=[]
            for ordinal,obj in enumerate(results):
                locations=obj.get('locations') or []
                first=locations[0].get('physicalLocation') or {} if locations else {}
                file=(first.get('artifactLocation') or {}).get('uri')
                line=_int((first.get('region') or {}).get('startLine'))
                message=obj.get('message') or {}
                msg=message.get('text') or message.get('markdown')
                digest=hashlib.sha256(_canonical_from_json(obj).encode('utf-8')).hexdigest()
                findings.append((scan_pk,ordinal,obj.get('ruleId'),msg,file,line,obj.get('level'),digest))
            if findings:
                with self.store._open() as cx:
                    cx.executemany('''INSERT INTO historical_sarif_findings
                        (scan_pk,sarif_result_index,rule_id,message_text,file_uri,line_number,result_level,result_json_sha256)
                        VALUES (?,?,?,?,?,?,?,?)''',findings)
            found_count+=len(findings)
        return found_count

    def _index_tests(self):
        with self.store._open(readonly=True) as cx:
            rows=cx.execute("""SELECT a.member_id,a.member_path,a.member_sha256
                 FROM archive_members a JOIN historical_file_index f ON f.member_id=a.member_id
                 WHERE f.archive_sha256 IN (SELECT source_sha256 FROM research_batches
                   WHERE adapter='archive-member-capture') AND a.member_path LIKE '04_FUNCTIONAL_TESTS_AND_TRIAGE/%'
                   AND a.member_path LIKE '%.json' ORDER BY a.member_id""").fetchall()
        obs=[]
        for mid,path,sha in rows:
            try:data=json.loads(_as_text(self.store.bytes_for_digest(sha)))
            except (ValueError,UnicodeError):continue
            if not isinstance(data,dict):continue
            if isinstance(data.get('case_id'),(int,str)) and data.get('arm') in {'O','W','P'}:
                cid=_case(data['case_id']);arm=data['arm']
                if cid:
                    obs.append((cid,arm,path.split('/')[2] if '/' in path else 'source_json',
                                str(data.get('status') or data.get('stage') or 'UNSPECIFIED'),mid,
                                data.get('patch_sha256'),_canonical_from_json(data)))
            for k,item in (data.get('patches') or {}).items():
                if not isinstance(item,dict):continue
                cid=_case(item.get('case_id'))
                arm=item.get('arm')
                if cid and arm in {'O','W','P'}:
                    obs.append((cid,arm,path.split('/')[2] if '/' in path else 'source_json',
                                str(item.get('status') or item.get('stage') or 'UNSPECIFIED'),mid,
                                item.get('patch_sha256'),_canonical_from_json(item)))
        with self.store._open() as cx:
            existing=cx.execute('SELECT COUNT(*) FROM historical_test_observations').fetchone()[0]
            if existing:return
            cx.executemany('''INSERT OR IGNORE INTO historical_test_observations
                      (case_id,arm,test_kind,status_from_source,source_member_id,source_patch_sha256,source_json)
                      VALUES (?,?,?,?,?,?,?)''',obs)

    def _index_text(self):
        with self.store._open(readonly=True) as cx:
            files=cx.execute("""SELECT a.member_id,a.member_path,a.member_sha256,a.member_bytes
             FROM archive_members a LEFT JOIN historical_text_index t ON t.member_id=a.member_id
             WHERE t.member_id IS NULL ORDER BY a.member_id""").fetchall()
        prepared=[]
        for mid,name,sha,size in files:
            suffix=PurePosixPath(name).suffix.lower()
            if suffix not in MIME_TEXT_EXTS or size>5_000_000:continue
            # No full text of huge SARIF into FTS; SARIF is indexed as original findings.
            raw=self.store.bytes_for_digest(sha)
            text=raw[:25000].decode('utf-8',errors='replace')
            prepared.append((mid,name,text,len(text),size))
        with self.store._open() as cx:
            for mid,name,text,txtlen,size in prepared:
                cx.execute('''INSERT INTO historical_text_index
                          (member_id,text_excerpt,excerpt_length,full_file_bytes,indexed_utc)
                          VALUES (?,?,?,?,?)''',(mid,text,txtlen,size,_now()))
                cx.execute('INSERT INTO historical_fts(rowid,member_path,excerpt) VALUES (?,?,?)',(mid,name,text))

    def case(self, case_id: str|int)->dict:
        cid=_case(case_id)
        if not cid:raise EvidenceError('Case ID must be an integer')
        with self.store._open(readonly=True) as cx:
            runs=cx.execute('''SELECT run_pk,study,arm,iteration,status_from_source,patch_sha256,provenance_status
                    FROM historical_generation_runs WHERE case_id=? ORDER BY study,iteration,arm''',(cid,)).fetchall()
            scans=cx.execute('''SELECT g.arm,s.source_target_rule,s.source_reported_new_count,
                 s.source_reported_target_count,s.source_reported_before_count,s.source_reported_after_count,
                 s.source_functional_status,s.baseline_member_present,s.source_codeql_version
                 FROM historical_scans s JOIN historical_generation_runs g ON g.run_pk=s.run_pk
                 WHERE g.case_id=? ORDER BY g.arm''',(cid,)).fetchall()
            tests=cx.execute('''SELECT arm,test_kind,status_from_source,source_patch_sha256
                 FROM historical_test_observations WHERE case_id=? ORDER BY arm,test_kind''',(cid,)).fetchall()
            files=cx.execute('''SELECT f.source_generation,f.original_filename,f.original_member_sha256,
                 a.member_path FROM historical_file_index f JOIN archive_members a USING(member_id)
                 WHERE f.source_case_id=? ORDER BY f.member_id''',(cid,)).fetchall()
            corrections=cx.execute('''SELECT stage,label_name,label_json,coding_pass,verification
                 FROM research_annotations WHERE unit_type='workflow' AND unit_id=?
                 ORDER BY annotation_id''',(cid,)).fetchall()
        return {'case_id':cid,
                'status':'INDEX_OF_HISTORICAL_SOURCE_OBSERVATIONS_NOT_INDEPENDENT_REEVALUATION',
                'runs':[dict(zip(['run_pk','study','arm','iteration','source_reported_status','patch_sha256','provenance_status'],r)) for r in runs],
                'scans':[dict(zip(['arm','target_rule','new_warnings_reported','target_warnings_reported','before_count_reported','after_count_reported','functional_status_reported','baseline_bytes_present','codeql_version'],r)) for r in scans],
                'tests':[dict(zip(['arm','source_kind','source_status','source_patch_sha256'],r)) for r in tests],
                'source_files':[dict(zip(['generation','name','sha256','archive_path'],r)) for r in files],
                'workbook_annotations':[{'stage':a,'label':b,'value':json.loads(c),'pass':d,'verification':e} for a,b,c,d,e in corrections]}

    def search(self,query:str,limit:int=30)->list[dict]:
        with self.store._open(readonly=True) as cx:
            rows=cx.execute('''SELECT f.member_path,snippet(historical_fts,1,'[',']','...',12)
                  FROM historical_fts f JOIN archive_members a ON a.member_id=f.rowid
                  WHERE historical_fts MATCH ? LIMIT ?''',(query,max(1,min(limit,100)))).fetchall()
        return [{'member_path':a,'snippet':b} for a,b in rows]

    def summary(self)->dict:
        with self.store._open(readonly=True) as cx:
            counts={table:cx.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                    for table in IMMUTABLE}
            breakdown=cx.execute('''SELECT study,arm,COUNT(*) FROM historical_generation_runs
                                GROUP BY study,arm ORDER BY study,arm''').fetchall()
            orphan=cx.execute('''SELECT COUNT(*) FROM historical_scans s JOIN historical_generation_runs g USING(run_pk)
                                 WHERE s.patch_hash_agrees=0''').fetchone()[0]
            absent=cx.execute('''SELECT COUNT(DISTINCT s.source_baseline_sha256) FROM historical_scans s
                                 WHERE s.source_baseline_sha256 IS NOT NULL AND s.baseline_member_present=0''').fetchone()[0]
        return {'status':'ORIGINAL_BYTES_IMPORTED_REPORTED_OUTCOMES_ONLY',
                'counts':counts,'generation_runs_by_study_arm':breakdown,
                'reported_scan_patch_hash_mismatches':orphan,
                'distinct_absent_original_baseline_sha256':absent,
                'must_not_claim':'CodeQL warnings are not confirmed vulnerabilities; patch application or syntax are not full task success'}
