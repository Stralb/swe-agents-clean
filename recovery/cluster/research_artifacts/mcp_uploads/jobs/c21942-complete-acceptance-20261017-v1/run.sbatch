#!/bin/bash
#SBATCH --job-name=case21942accept
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:20:00
export PATH="$HOME/.bun/bin:$HOME/tools/node/bin:$PATH"
python3 - <<'PY'
from pathlib import Path
import zipfile,io,hashlib,os,tempfile,subprocess,shutil,json
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
out=root/('case21942_acceptance_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=True)
scratch=Path(tempfile.mkdtemp(prefix='c21942_accept_',dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
source=root/'two_new_clean_baselines_job70029/PHASE2_TWO_NEW_CASES_ONE_ZIP.zip'
with zipfile.ZipFile(source) as outer:
 source_data=outer.read('CASE_1_21942/SOURCE_21942.zip')
 assert hashlib.sha256(source_data).hexdigest()=='eb431888a4a29c866ddbf6dbc019350ab6c2a3bcd42cf039c4d920fced8a4788'
base=scratch/'base';base.mkdir()
with zipfile.ZipFile(io.BytesIO(source_data)) as z:
 for entry in z.infolist():
  if not entry.filename.startswith('REPO/'):continue
  short=entry.filename[5:]
  if not short:continue
  parts=Path(short).parts
  assert '..' not in parts
  target=base.joinpath(*parts)
  if entry.is_dir():target.mkdir(parents=True,exist_ok=True)
  else:
   target.parent.mkdir(parents=True,exist_ok=True)
   target.write_bytes(z.read(entry))
records={}
variants={
 'base':None,
 'G':root/'case21942_GW_G_eval_job70109/CASE21942_G.patch',
 'W':root/'case21942_GW_W_eval_job70110/CASE21942_W.patch'
}
expected={
 'G':'a9817c6b554545044a7212caf78b597ba9de25fba32351b21a4161ebc06ff99f',
 'W':'c11d9b40fc9758cbcf7ace5679826cb008564e81b414785e9f1a87bd717ee51d'
}
test=r"""
import {mkdtemp,mkdir,writeFile,readFile,rm} from "fs/promises";
import {tmpdir} from "os";
import {join} from "path";
import {existsSync} from "fs";
import {installCodexPluginMarketplace, isCodexV2Format,detectCodexVersion} from "./src/cli/installer.ts";
const t = await mkdtemp(join(tmpdir(),"arra21942audit-"));
const skillRoot=join(t,"skill-source");await mkdir(skillRoot,{recursive:true});
const content="---\nname: rrr\ndescription: Session retrospective\n---\n# Real skill instructions\n";
await writeFile(join(skillRoot,"SKILL.md"),content);
const sample={name:"rrr",description:"Session retrospective",path:skillRoot};
const root=join(t,"marketplace");
const config=join(t,".codex","config.toml");await mkdir(join(t,".codex"),{recursive:true});
await writeFile(config,"[marketplaces.openai-bundled]\nsource_type = \"bundled\"\n");
const install=async(ver,dir=root,cfg=config)=>installCodexPluginMarketplace([sample],"26.5.14","no-shell",{marketplaceDir:dir,configPath:cfg,codexVersion:ver});
const plugin=join(root,"plugins","rrr");
const found=(...p)=>existsSync(join(...p));
const facts={};
facts.version_matrix={old:!isCodexV2Format("0.128.0"),boundary: isCodexV2Format("0.130.0"),newer: isCodexV2Format("0.131.3")};
await install("0.128.0");
facts.fresh_v1={
 manifest:found(root,"manifest.toml"),
 toml:found(plugin,"plugin.toml"),
 prompt:found(plugin,"prompt.md"),
 promptBody:(await readFile(join(plugin,"prompt.md"),"utf8"))===content
};
await install("0.130.0");
const v2file=join(plugin,".codex-plugin","plugin.json"),skillFile=join(plugin,"skills","rrr","SKILL.md");
const meta=JSON.parse(await readFile(v2file,"utf8"));
const cfg=await readFile(config,"utf8");
facts.upgrade_v1_to_v2={
 pluginJsonExists:found(v2file),
 metaName:meta.name==="rrr",
 metaSkills:meta.skills==="./skills/",
 metaInterface:!!meta.interface&&!!meta.interface.displayName,
 skillMdExists:found(skillFile),
 skillMdContent:(await readFile(skillFile,"utf8"))===content,
 configRegistration:cfg.includes('[plugins."rrr@arra-oracle-skills"]'),
 manifestRemoved:!found(root,"manifest.toml"),
 legacyTomlRemoved:!found(plugin,"plugin.toml"),
 legacyPromptRemoved:!found(plugin,"prompt.md")
};
await install("0.128.0");
facts.downgrade_v2_to_v1={
 restoredToml:found(plugin,"plugin.toml"),
 restoredPrompt:found(plugin,"prompt.md"),
 pluginJsonRemoved:!found(plugin,".codex-plugin"),
 skillDirRemoved:!found(plugin,"skills")
};
const newRoot=join(t,"fresh-v2");const newCfg=join(t,"fresh-v2.toml");
await writeFile(newCfg,"[marketplaces.openai-bundled]\nsource_type = \"bundled\"\n");
await install("0.130.0",newRoot,newCfg);
const newPlugin=join(newRoot,"plugins","rrr");
facts.fresh_v2={
 noManifest:!found(newRoot,"manifest.toml"),
 pluginJson:found(newPlugin,".codex-plugin","plugin.json"),
 skillContent:(await readFile(join(newPlugin,"skills","rrr","SKILL.md"),"utf8"))===content
};
facts.versionDetectionNote="Version detection exists in pre-PR source; optional codexVersion is supplied in this test.";
facts.needsReinstallAfterCodexAutoUpgrade="This helper runs only when arra install runs; no upgrade event listener.";
console.log("AUDIT_JSON:"+JSON.stringify(facts));
await rm(t,{recursive:true,force:true});
"""
for label,patch in variants.items():
 project=base if label=='base' else scratch/label
 if label!='base':
  shutil.copytree(base,project,symlinks=True)
  assert hashlib.sha256(patch.read_bytes()).hexdigest()==expected[label]
  ck=subprocess.run(['git','apply','--check',str(patch)],cwd=project,capture_output=True,text=True)
  if ck.returncode!=0:raise RuntimeError(label+' patch apply '+ck.stderr[:500])
  subprocess.run(['git','apply',str(patch)],cwd=project,check=True)
 (project/'case21942-acceptance-audit.ts').write_text(test)
 bun=str(Path.home()/'.bun/bin/bun')
 with (out/(label+'_install.log')).open('w') as f:
  install_result=subprocess.run([bun,'install','--ignore-scripts','--frozen-lockfile'],cwd=project,stdout=f,stderr=subprocess.STDOUT,timeout=240)
 with (out/(label+'_audit.log')).open('w') as f:
  if install_result.returncode==0:
   p=subprocess.run([bun,'run','case21942-acceptance-audit.ts'],cwd=project,stdout=f,stderr=subprocess.STDOUT,timeout=100)
   exitcode=p.returncode
  else:
   f.write('install dependencies failed');exitcode=None
 log=(out/(label+'_audit.log')).read_text(errors='replace')
 for line in log.splitlines():
  if line.startswith('AUDIT_JSON:'):
   facts=json.loads(line[len('AUDIT_JSON:'):])
   break
 else:facts={'error':log[-1200:]}
 records[label]={'install_exit':install_result.returncode,'audit_exit':exitcode,'facts':facts}
 (out/'ACCEPTANCE_RESULT.json').write_text(json.dumps(records,indent=2)+'\n')
 print('AUDIT',label,'exit',exitcode,'fresh',facts.get('fresh_v2'), 'upgrade', facts.get('upgrade_v1_to_v2'),flush=True)
(out/'ACCEPTANCE_RESULT.json').write_text(json.dumps(records,indent=2)+'\n')
PY
