# Remaining steps

1. Full functional acceptance checks for the two new negatives:
   - 03429: run full Ruler tests and ensure changed unit test fixture actually runs, confirms backup/revert, no test interference; the scanner result is fixture-specific.
   - 12344: run native Windows DPAPI encryption, decryption, update, delete, legacy .bin compatibility, file-permission and persistence tests. Canonical path retains names for valid IDs.
2. 08152: threat model fixed Telegram HTTPS BOT token URL and downstream Whisper transcription. Ensure credentials never reach arbitrary origins/redirects/logs. The remaining CodeQL trace is settings file -> BOT token -> Telegram URL. Do NOT bypass by hiding flow.
3. 31207: verify Compose auth/header/CORS requirements and PAT file -> loopback Authorization endpoint. Ensure loopback endpoint cannot be redirected/reconfigured and auth headers never reach foreign hosts. Retain authorization behavior.
4. For the actual minimum-information research question, feed concise candidate safety properties to FRESH independent coding agents, preserving original issue and repo. Count CodeQL + functionality; these researcher repairs are ORACLE follow-ups, not issue-addition causal estimates.
5. If scanner-negative is an absolute definition even for authorized flows, explicitly report unsatisfiable/ambiguous targets or introduce a separate alternative mechanism and test full functionality. NEVER label code that drops required features as successful prevention.
