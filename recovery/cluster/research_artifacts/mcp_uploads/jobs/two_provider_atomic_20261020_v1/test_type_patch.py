from pathlib import Path
p=Path.home()/'research_artifacts/prevention_pilot_phase2/provider_variants_20261020/08152/baseline/REPO/src/telegram/voice.test.ts'
t=p.read_text();a='Request'+'Info | URL';b='Parameters'+chr(60)+'typeof fetch>[0]'
assert t.count(a)==1
p.write_text(t.replace(a,b,1))
