The Current pipeline.



1.Collecting Candidates

Query GitHub for merged pr with explicit linked issue.

restricted by

&#x09;1.1 Min stars >= 100

&#x09;1.2 Merged after 1 Nov 2025

&#x09;1.4 Stored as a Case = issue + linked pr.

&#x09;1.5 Explicit AI indicators.



Included from "The Rise of AI Teammates in Software Engineering (SE) 3.0"

|Agent|:head-> source branch|:author-> who opened the pr|Other|
|-|-|-|-|
|OpenAI Codex|head:codex/|||
|Devin||author:devin-ai-integration\[bot]||
|GitHub Copilot|head:copilot/|author:@copilot||
|Cursor|head:cursor/|||
|Claude Code|||"Co-Authored-By: Claude", "Generated with Claude Code"|



Excluded

|Maintenance/automation bots|dependabot\[bot]<br />dependabot-preview\[bot]<br />renovate\[bot]<br />github-actions\[bot]<br />pre-commit-ci\[bot]<br />mergify\[bot]<br />pyup\[bot]<br />pyup-bot<br />linear\[bot]|
|-|-|



Since pr gives actual code/config/dependency change and issue gives the stated intent.



2\. Extracting Metadata.

For each Case, collect:

&#x09;2.1 Base commit and head commit.

&#x09;2.2 Diffs for changed files, including file paths and +/- line changes.

&#x09;2.3 File type and region analysis on changed files.

&#x09;



2.3. File Type/Region Analysis

Identify neutral file facts.

&#x09;2.3.1 pre-commit Identify provides tags i.e Python/C/C++/YAML/JSON

&#x09;s.t

&#x09;(src/app.py→ file, text, python)

&#x09;which scanner could apply here.

&#x09;

&#x09;2.3.2 Github Linguist provides repo-context  i.e file vs repo level language.

&#x09;(.py in Python repo-> likely project source VS .py in C++ repo-> likely support script.)

&#x09;

&#x09;=> File fact=tags+metadata+path/name rules.



3.Region Mapping

&#x09;Map file Facts -> Regions -> Static analysis scanner routes to apply.



|Regions|Activation<br />(if file fact indicates)|Tool|
|-|-|-|
|Source Code|JavaScript + TS > 50%|SemGrep + CodeQL v2.25<br />more structured queries via<br />-> codeql-suites/javascript-security-extended.qls<br />-> codeql/javascript-queries|
|Dependency|(package.json/pom.xml/build.gradle ect...)|Dependency diff + OSV Scanner v2.4|
|Secrets|(.env/config like files)|Gitleaks v8.3|
|Unknown|other|Manual inspection and update regions next iteration.|

Trivy\* Used as broad signal to determine which region is productive and worth spending more mining on.





4\. Downstream Analysis.

For each Case:

&#x09;Run static analysis type on base commit

&#x09;Run same static analysis type on head commit



&#x09;If head findings - base findings > 0:

&#x20;   		mark as downstream-positive candidate

&#x20;   		manually review candidate.





5\. Current insights

Secrets leaked:

2 cases, 5 findings → all were generic-api-key detections in mocks/tests (\_\_tests\_\_/mocks.gcal/... and auth.test.ts).



Dependency downgrades:

5 cases, 16 findings → the findings mainly came from migration regenerating and realigning its dependency graph.



Vulnerabilities introduced:

6 cases → most findings came from newly added lockfiles exposing existing vulnerabilities; compatibility/tooling overrides for migrations. 





6\. Current limitations

\-> should I inspect commit level traces for Implicit ai-agent-indicators?(mainly for enrichment)

roughly "For each PR, I can inspect the commit message, GitHub author and committer identities, email metadata and Co-Authored-By trailers."



\-> Can I exclude findings from test/mock directories and newly added lockfiles as likely false positives

\-> can I limit the languages used in the prs/issues discriptions to be only English?



\->"red teaming paper "take issues + prs + use different channel other than llms + validation of current framework"

Run the miner on SWExploit’s paired benign and adversarial issue–patch artifacts to test whether it detects known attacks using non-LLM ground truth?































































\-> this limitation where a pr might have been created at date X and then at date X+1 were using more modern static analysis tools, implying that perhaps there is no maliciousness.

\-> Risk of overfitting to early noisy scanner results.

\-> Each scanner only sees one part of the threat surface.

\-> Single issue-Pr pair limitations, in multi-linked attacks.(exclude)



\-> finding the right region to mine without making bad initial biased assumptions.

\-> Is Pr-Issue linked candidates the right unit of analysis? (considering Pr without issue/commiting to main/package registry tampering)



\-> how can I move closer to a region where more downstream signals exist?

\-> better static analysis tools?



\-> how many candidates to mine per methodology run to know if successful?

\-> is there any specific criteria I should manually evaluate a candidate on once I start having more true positive cases?

