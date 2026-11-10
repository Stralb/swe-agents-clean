from pathlib import Path
p=Path.home()/'research_artifacts/prevention_pilot_phase2/provider_variants_20261020/08152/baseline/REPO/src/telegram/voice.test.ts'
t=p.read_text()
print(len(t))
