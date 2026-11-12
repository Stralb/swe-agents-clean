# Run from your Windows PowerShell (requires Wits VPN/SSH access).
scp "astrauss@mscluster-login:/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/owp_research_handoff_job71701/OWP_65x3_14OWP_RESEARCH_HANDOFF.zip" "$env:USERPROFILE\Downloads\"
# Verify downloaded ZIP (expected hash):
Get-FileHash "$env:USERPROFILE\Downloads\OWP_65x3_14OWP_RESEARCH_HANDOFF.zip" -Algorithm SHA256
# Expected: A31C58014B37112B30942ACF60D53C2DFA253499F705B3707F27B130D48CD62A
