"""Reviewer-safe local lookups without implied adjudication or safety claims.

All labels and scan outcomes are explicitly source-reported. A byte is treated
as available only if the content-addressed store can retrieve and hash it.
This API does not unblind identities, infer case/run mappings, or recompute scans.
"""
from __future__ import annotations

import json
from collections import deque
from typing import Any

from .research import ResearchIndex
from .store import EvidenceError, EvidenceStore


class ReviewerView:
    def __init__(self, store: EvidenceStore):
        self.store = store
        ResearchIndex(store)

    def _records(self, cx, unit_type: str, unit_id: str, *, max_rows: int = 150) -> list[dict[str, Any]]:
        rows = cx.execute("""SELECT r.locus,r.row_index,r.stage,r.kind,r.payload_json,r.payload_sha256,
                       b.source_sha256,s.origin_uri,s.origin_revision,s.scientific_status
                    FROM research_records r JOIN research_batches b ON b.batch_id=r.batch_id
                    JOIN sources s ON s.source_id=b.source_id
                    WHERE r.unit_type=? AND r.unit_id=? ORDER BY r.record_id LIMIT ?""",
                          (unit_type, unit_id, max_rows + 1)).fetchall()
        if len(rows) > max_rows:
            raise EvidenceError(f"More than {max_rows} records for {unit_type}/{unit_id}; narrow query")
        columns = ("source_locus", "source_row", "stage", "kind", "payload", "payload_sha256",
                   "source_sha256", "source_uri", "source_revision", "source_status")
        return [{**dict(zip(columns,row)), "payload": json.loads(row[4])} for row in rows]

    def case_dossier(self, case_id: str | int, *, max_nodes: int = 100) -> dict[str, Any]:
        """Records for a case and at most two hops of explicit relations.

        No inferred ownership. When an edge is absent, the join is absent and
        must not be papered over from case-specific naming conventions.
        """
        cid=str(case_id)
        if not cid or len(cid)>120:
            raise EvidenceError("Invalid case identifier")
        seen = {("workflow", cid)}
        queue = deque([("workflow", cid, 0)])
        edges: dict[tuple, dict] = {}
        while queue:
            unit_type,unit_id,depth=queue.popleft()
            if depth>=2:
                continue
            with self.store._open(readonly=True) as cx:
                rels=cx.execute("""SELECT from_type,from_id,to_type,to_id,relation,batch_id
                        FROM research_edges
                        WHERE (from_type=? AND from_id=?) OR (to_type=? AND to_id=?)
                        ORDER BY edge_id LIMIT 1001""", (unit_type,unit_id,unit_type,unit_id)).fetchall()
            if len(rels)>1000:
                raise EvidenceError("Case relations exceed bounded reviewer export; narrow query")
            for frt,fid,tot,tid,relation,bid in rels:
                edges[(frt,fid,tot,tid,relation,bid)]={"from_type":frt,"from_id":fid,"to_type":tot,"to_id":tid,"relation":relation,"batch_id":bid}
                for neigh in ((frt,fid),(tot,tid)):
                    if neigh not in seen:
                        if len(seen)>=max_nodes:
                            raise EvidenceError("Bounded case graph exceeded; narrow query")
                        seen.add(neigh)
                        queue.append((*neigh,depth+1))
        with self.store._open(readonly=True) as cx:
            evidence=[]
            for utype,uid in sorted(seen):
                records=self._records(cx,utype,uid)
                labels=cx.execute("""SELECT a.stage,a.label_name,a.label_json,a.coding_pass,a.coder_identity,a.verification,
                                      r.locus,b.source_sha256
                                  FROM research_annotations a
                                  JOIN research_records r ON a.record_id=r.record_id
                                  JOIN research_batches b ON r.batch_id=b.batch_id
                                  WHERE a.unit_type=? AND a.unit_id=? ORDER BY a.annotation_id LIMIT 501""",(utype,uid)).fetchall()
                if len(labels)>500:
                    raise EvidenceError("Too many labels for one unit; narrow query")
                if records or labels:
                    evidence.append({"unit_type":utype,"unit_id":uid,"records":records,
                        "source_recorded_labels":[{
                            "stage":x[0],"label":x[1],"value":json.loads(x[2]),
                            "coding_pass":x[3],"coder_id":x[4],"verification":x[5],
                            "source_locus":x[6],"source_sha256":x[7]}
                            for x in labels]})
            run_ids=cx.execute("""SELECT study_id,run_id,analysis_status FROM experiment_runs
                WHERE case_id=? ORDER BY study_id,run_id""",(cid,)).fetchall()
            gaps=cx.execute("""SELECT dataset,missing_role,explanation FROM evidence_gaps
                WHERE unit_type='workflow' AND unit_id=? ORDER BY gap_id""",(cid,)).fetchall()
        return {"case_id":cid,
                "interpretation_policy":"All labels are historical source observations, not independent human adjudication",
                "case_to_run_join_policy":"Only explicit experiment_runs.case_id links",
                "related_node_count":len(seen),
                "edges":list(edges.values()),
                "units":evidence,
                "explicit_runs":[{"study_id":s,"run_id":r,"analysis_status":a} for s,r,a in run_ids],
                "gaps":[{"dataset":a,"role":b,"reason":c} for a,b,c in gaps]}

    def run_dossier(self, study_id: str, run_id: str) -> dict[str, Any]:
        with self.store._open(readonly=True) as cx:
            rows=cx.execute("""SELECT run_pk,case_id,pair_id,arm,model,seed,base_commit_sha,
                generated_commit_sha,analysis_status,protocol_revision,metadata_json
                FROM experiment_runs WHERE study_id=? AND run_id=? ORDER BY run_pk""",(study_id,run_id)).fetchall()
            if not rows:
                observed = self._records(cx, "generation", f"{study_id}:{run_id}")
                if observed:
                    return {"study_id":study_id,"run_id":run_id,
                        "status":"SOURCE_OBSERVATIONS_ONLY_NOT_A_GENERATED_PATCH_IMPORT",
                        "raw_source_observations":observed,
                        "case_id":None,"arm":None,
                        "asset_availability":"NO_EXPLICIT_ARCHIVE_ASSET_LINK",
                        "caveat":"Rows and their exact source digests are preserved; generated patch and SARIF bytes are not locally captured"}
                return {"study_id":study_id,"run_id":run_id,"status":"NO_EXPLICIT_RUN_MAPPING_IN_LOCAL_CATALOG"}
            if len(rows)!=1:
                raise EvidenceError("Run ID is ambiguous across source manifest versions: specify source revision")
            pk,cid,pair,arm,model,seed,base,generated,status,protocol,metadata=rows[0]
            assets=cx.execute("""SELECT e.evidence_role,e.artifact_sha256,e.archive_path,
                    s.origin_uri,s.origin_revision,a.bytes
                FROM experiment_run_assets e JOIN sources s ON s.source_id=e.source_id
                JOIN artifacts a ON a.sha256=e.artifact_sha256
                WHERE e.run_pk=? ORDER BY e.evidence_role,e.archive_path""",(pk,)).fetchall()
            gaps=cx.execute("""SELECT missing_role,explanation FROM evidence_gaps
                WHERE unit_type='generation' AND unit_id=? ORDER BY gap_id""",
                (f"{study_id}:{run_id}",)).fetchall()
        files=[]
        for role,digest,path,uri,rev,size in assets:
            try:
                self.store.bytes_for_digest(digest)
                available=True
            except EvidenceError:
                available=False
            files.append({"role":role,"sha256":digest,"bytes":size,"archive_member":path,
                          "original_source_uri":uri,"original_revision":rev,
                          "byte_integrity_pass":available})
        return {"study_id":study_id,"run_id":run_id,"status":"SOURCE_RECORDED_ONLY",
                "case_id":cid,"pair_id":pair,"arm":arm,"model":model,"seed":seed,
                "base_commit_sha":base,"generated_commit_sha":generated,
                "analysis_status":status,"protocol_revision":protocol,
                "source_recorded_metadata":json.loads(metadata),
                "assets":files,
                "missing_roles":[{"role":a,"reason":b} for a,b in gaps],
                "result_caveat":"Scanner reports are not proof of patch correctness or vulnerability absence"}

    def study_coverage(self, study_id: str) -> dict[str, Any]:
        with self.store._open(readonly=True) as cx:
            runs=cx.execute("""SELECT r.run_pk,r.run_id,r.arm,r.case_id,r.model,
                  r.analysis_status,COUNT(a.run_asset_id)
                  FROM experiment_runs r LEFT JOIN experiment_run_assets a ON r.run_pk=a.run_pk
                  WHERE r.study_id=? GROUP BY r.run_pk ORDER BY r.run_id""",(study_id,)).fetchall()
            gaps=cx.execute("""SELECT missing_role,COUNT(*) FROM evidence_gaps
                WHERE dataset=? GROUP BY missing_role ORDER BY missing_role""",(study_id,)).fetchall()
            observed_count=cx.execute("""SELECT COUNT(DISTINCT unit_id) FROM research_records
                WHERE unit_type='generation' AND stage=?""",(study_id,)).fetchone()[0]
            byrole=cx.execute("""SELECT a.evidence_role,COUNT(DISTINCT a.run_pk) FROM experiment_run_assets a
                JOIN experiment_runs r ON r.run_pk=a.run_pk
                WHERE r.study_id=? GROUP BY a.evidence_role ORDER BY a.evidence_role""",(study_id,)).fetchall()
        return {"study_id":study_id,"runs":len(runs),"source_observed_run_ids":observed_count,
                "recorded_blinded_runs":sum(1 for x in runs if x[2]=="BLINDED_UNMAPPED"),
                "runs_without_case":sum(1 for x in runs if x[3] is None),
                "runs_without_model":sum(1 for x in runs if x[4] is None),
                "runs_without_independent_analysis":sum(1 for x in runs if x[5]=="unverified"),
                "roles_with_bytes":dict(byrole),"gaps_by_role":dict(gaps),
                "interpretation":"Counts index declared local run assets, not regenerated or independently validated outcomes"}
