#!/usr/bin/env python3
"""Isolated targeted *subcomponent* behavior smoke tests. Not full issue acceptance."""
import os,re,json,zipfile,subprocess,tempfile,hashlib,traceback
from pathlib import Path,PurePosixPath
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2"
OUT=ROOT/("owp14_targeted_behavior_extended_job"+os.environ["SLURM_JOB_ID"]);OUT.mkdir(parents=True,exist_ok=False)
SCRATCH=ROOT/"owp14_targeted_behavior_scratch";SCRATCH.mkdir(exist_ok=True)
PACK=ROOT/"owp14_allcases_packets_job71014"
PREF={"W":ROOT/"owp14_user14_w_preflight_job71208","P":ROOT/"owp14_user14_p_preflight_job71201"}
meta={a:json.loads((path/"SUMMARY.json").read_text()) for a,path in PREF.items()}
node=Path.home()/"tools/node24/bin/node"
bun=Path.home()/".bun/bin/bun"
assert node.exists() and bun.exists()
checked=[(31207,"W"),(16633,"W"),(3581,"W"),(6104,"W"),(6104,"P")]
cases={}
def sha(b):return hashlib.sha256(b).hexdigest()
for cid,arm in checked:
 key="%05d_%s"%(cid,arm)
 row={"case_id":cid,"arm":arm,"stage":"INIT","interpretation":"SUBCOMPONENT_ONLY_NOT_FULL_FUNCTIONAL_ACCEPTANCE"}
 caseout=OUT/key;caseout.mkdir()
 info=meta[arm]["cases"][str(cid)]
 assert info["patch_applied"]
 with tempfile.TemporaryDirectory(prefix=key+"_",dir=SCRATCH) as d:
  base=Path(d);repo=base/"repo";repo.mkdir()
  try:
   archive=PACK/("CASE_%05d_O.zip"%cid)
   patch=PREF[arm]/("CASE_%05d"%cid)/info["filename"]
   assert sha(patch.read_bytes())==info["original_patch_sha256"]
   with zipfile.ZipFile(archive) as z:
    for p in info["changed_paths"]:
     src="REPO/"+p
     if src not in z.namelist():continue
     rel=PurePosixPath(p)
     assert ".." not in rel.parts and ".git" not in rel.parts
     dst=repo.joinpath(*rel.parts);dst.parent.mkdir(parents=True,exist_ok=True)
     dst.write_bytes(z.read(src))
   done=subprocess.run(["git","apply",str(patch)],cwd=repo,
     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120,
     env={"PATH":"/usr/bin:/bin","HOME":str(base),"GIT_CONFIG_GLOBAL":"/dev/null"})
   assert done.returncode==0,done.stdout[:700]
   if cid==31207:
    runner=node;cmd=[runner,"--test","ai/services/fleet/fleetPlaneHttp.test.mjs"]
    row["contract_test"]="W fleet HTTP admission/probe/refusal standalone tests"
   elif cid==16633:
    runner=node;cmd=[runner,"--experimental-strip-types","--test",
      "apps/sarah/src/agent-runtime/relationship-policy.test.ts"]
    row["contract_test"]="W relationship policy standalone tests"
   elif cid==3581:
    runner=node;cmd=[runner,"--experimental-transform-types","--test",
      "src/extension/services/jsonl-watcher-service.test.mjs"]
    row["contract_test"]="W independent JSONL watcher tests (creation, partial lines, replay)"
   else:
    runner=bun
    harness=base/"buzz_sanity.mjs"
    f=repo/"server/src/services"/("buzz-replay-cursor.ts" if arm=="W" else "buzz-replay-checkpoint.ts")
    if arm=="W":
     harness.write_text("""
import assert from 'node:assert/strict';
const {compareBuzzCursor, cursorFor, buzzDedupeKey, replaySince, advanceCommittedCursor} = await import(process.argv[2]);
const x='a'.repeat(64),y='b'.repeat(64);
const first=cursorFor({id:x,created_at:100,kind:9,pubkey:y});
const second=cursorFor({id:y,created_at:100,kind:9,pubkey:x});
assert.ok(compareBuzzCursor(first,second)<0);
assert.deepEqual(advanceCommittedCursor(first,second),second);
assert.equal(buzzDedupeKey('one',x),buzzDedupeKey('one',x.toUpperCase()));
assert.notEqual(buzzDedupeKey('one',x),buzzDedupeKey('two',x));
assert.equal(replaySince(second),40);
assert.throws(()=>cursorFor({id:'invalid',created_at:100,kind:9,pubkey:y}));
console.log('PASS 6 standalone cursor invariants');
""")
     row["contract_test"]="W buzz cursor 6 external invariant assertions"
    else:
     harness.write_text("""
import assert from 'node:assert/strict';
const {compareBuzzCursors, commitBuzzEvent, shouldProcessBuzzEvent, replaySince} = await import(process.argv[2]);
const x='a'.repeat(64),y='b'.repeat(64);
const first={eventId:x,createdAt:100},second={eventId:y,createdAt:100};
assert.ok(compareBuzzCursors(first,second)<0);
let state=commitBuzzEvent({processedEventIds:[]},first);
state=commitBuzzEvent(state,second);
assert.deepEqual(state.cursor,second);
assert.equal(state.processedEventIds.length,2);
assert.equal(shouldProcessBuzzEvent(state,first),false);
assert.equal(replaySince(state),40);
assert.throws(()=>commitBuzzEvent({processedEventIds:[]},{eventId:'bad',createdAt:-1}));
console.log('PASS 6 standalone checkpoint invariants');
""")
     row["contract_test"]="P buzz checkpoint 6 external invariant assertions"
    cmd=[runner,str(harness),str(f)]
   env={"HOME":str(base),"TMPDIR":str(base),"PATH":str(node.parent)+":"+str(bun.parent)+":/usr/bin:/bin",
       "CI":"1","NO_COLOR":"1","NODE_NO_WARNINGS":"1","NPM_CONFIG_OFFLINE":"true","BUN_INSTALL_CACHE_DIR":str(base/"cache")}
   p=subprocess.run([str(x) for x in cmd],cwd=repo,env=env,stdout=subprocess.PIPE,
       stderr=subprocess.STDOUT,text=True,timeout=90)
   row["exit_code"]=p.returncode;row["stage"]="PASS" if p.returncode==0 else "FAIL"
   row["output_log"]=key+".log";(OUT/(key+".log")).write_text(p.stdout[:22000])
   row["log_excerpt"]=p.stdout[-800:]
  except Exception as e:
   row["stage"]="HARNESS_ERROR";row["error"]=repr(e)
   (OUT/(key+".error")).write_text(traceback.format_exc())
 cases[key]=row
 print("COMPONENT_TEST",key,row["stage"],row.get("exit_code"),flush=True)
(OUT/"SUMMARY.json").write_text(json.dumps({"stage":"COMPLETE","tests":cases,
 "warning":"These targeted tests do not establish original-issue acceptance or comparable treatment functionality.",
 "no_external_dependencies_installed":True},indent=2)+"\n")
print("COMPONENT_TESTS_DONE",sum(x["stage"]=="PASS" for x in cases.values()),"of",len(cases),flush=True)
