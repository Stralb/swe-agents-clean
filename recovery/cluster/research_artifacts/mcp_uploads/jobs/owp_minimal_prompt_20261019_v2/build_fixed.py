#!/usr/bin/env python3
from pathlib import Path
p=Path.home()/'research_artifacts/mcp_uploads/jobs/owp_minimal_prompt_20261019_v2/build.py'
source=p.read_text()
source=source.replace(chr(92)*2+'n',chr(92)+'n')
assert "patch+'\\n'" in source
exec(compile(source,str(p),'exec'),{'__name__':'__main__'})
