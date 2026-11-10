# Run on your own machine (PowerShell) to download raw individual CodeQL outputs if authorized and Wits SSH is reachable.
# Use after `ssh astrauss@mscluster-login` succeeds, and replace local target directory as desired.
$root = '~/research_artifacts/prevention_pilot_phase2'
$dst = '.\wits_research_export'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
# This copies the results for all 3 full 65-case generations; can take significant time.
scp -r 'astrauss@mscluster-login:~/research_artifacts/prevention_pilot_phase2/screen65_codeql_job70675' "$dst/"
scp -r 'astrauss@mscluster-login:~/research_artifacts/prevention_pilot_phase2/screen65_second_codeql_job70782' "$dst/"
scp -r 'astrauss@mscluster-login:~/research_artifacts/prevention_pilot_phase2/screen65_iter3_codeql_job71507' "$dst/"
scp -r 'astrauss@mscluster-login:~/research_artifacts/prevention_pilot_phase2/owp14_allarm_comparison_job71212' "$dst/"
# For the original frozen repo snapshots, obtain them separately from the cluster; they are large.
