# Both remaining CodeQL-negative research implementations

**Case 08152**: 4 baseline -> 4 patched; zero NEW CodeQL findings. New Telegram voice uses grammY files plugin to construct/download a URL and checks the exact TLS origin. Existing settings and credential storage unchanged. New dependency needs a package lock update before production use; voice unit tests 3/3 pass; project typecheck did NOT run due to missing tsc.

**Case 31207**: 60 baseline -> 60 patched; zero NEW CodeQL findings. Uses a short-lived healthcheck environment variable populated from the existing Docker-mounted file-backed secret, with no CORS wildcard. The credential still traverses from disk to an authenticated HTTP probe; using environment indirection does not demonstrate a security benefit and may introduce process-environment exposure.

**Validity:** These were retrospective researcher-designed implementation repairs, not independent agent generations from distinct minimum-information issue prompts. CodeQL zero-new-finding is not equivalent to security or complete functional correctness. Native integration and deployment acceptance must be tested before a strong claim. 03429's previous scanner-negative was achieved with a pre-existing unit-test fixture change, so it may not satisfy a strict additive-only intervention restriction.

The zip includes the exact git-apply-able full patches against the clean frozen O repositories, baseline and after SARIF, scan logs, result JSON, and test logs.
