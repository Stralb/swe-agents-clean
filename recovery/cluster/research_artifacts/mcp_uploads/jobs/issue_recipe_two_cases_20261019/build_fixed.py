#!/usr/bin/env python3
from pathlib import Path
p=Path.home()/"research_artifacts/mcp_uploads/jobs/issue_recipe_two_cases_20261019/build.py"
source=p.read_text()
source=source.replace(chr(92)+chr(96),chr(96))
assert "before=\"## Suggested fix" in source
exec(compile(source,str(p),"exec"),{"__name__":"__main__"})
