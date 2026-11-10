#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

TARGETS = [
  {
    "case_id": 181,
    "repository": "theNetworkChuck/claude-phone",
    "issue_number": 6,
    "pr_number": 9,
    "frozen_issue_request": "Support a split Raspberry Pi deployment where the voice stack runs on an always-on Pi and the Claude API server runs on the user's Mac or Linux machine over the LAN.",
    "root_cause_mechanisms": "Supporting implementation judgement (2)",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0009",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `cli/lib/network.js`, the PR adds/changes the scanner-primary line at 73: `const req = http.get(healthUrl, { timeout: 3000 }, (res) => {`.",
        "changed_locations": "cli/lib/network.js:73; cli/lib/commands/doctor.js:251; cli/lib/commands/doctor.js:265; cli/lib/commands/doctor.js:266; cli/lib/commands/status.js:30; cli/lib/commands/status.js:31; cli/lib/network.js:71; cli/lib/network.js:62",
        "specific_causal_mechanism": "local file-derived data is carried into an HTTP/network operation",
        "rule_ids": "js/file-access-to-http",
        "finding_families": "Code vulnerability",
        "needle": "const req = http.get(healthUrl, { timeout: 3000 }, (res) => {"
      },
      {
        "producing_change_id": "PC-0010",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `cli/lib/port-check.js`, the PR adds/changes the scanner-primary line at 61: `socket.connect(port, '127.0.0.1');`.",
        "changed_locations": "cli/lib/port-check.js:61; cli/lib/commands/doctor.js:278; cli/lib/commands/doctor.js:280; cli/lib/port-check.js:11",
        "specific_causal_mechanism": "local file-derived data is carried into an HTTP/network operation",
        "rule_ids": "js/file-access-to-http",
        "finding_families": "Code vulnerability",
        "needle": "socket.connect(port, '127.0.0.1');"
      }
    ]
  },
  {
    "case_id": 299,
    "repository": "aaddrick/claude-desktop-debian",
    "issue_number": 288,
    "pr_number": 300,
    "frozen_issue_request": "Fix Cowork KVM VM startup so it uses a valid downloaded backing image instead of failing because the expected qcow2 root filesystem is missing from the runtime path.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0020",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `scripts/cowork-vm-service.js`; a representative changed flow step is line 1278: `log(\\`KvmBackend: guest response ERROR for id=${msg.id}:\\`, JSON.stringify(msg.error));`.",
        "changed_locations": "scripts/cowork-vm-service.js:1278",
        "specific_causal_mechanism": "untrusted/runtime-controlled text is written to logs without sufficient neutralization",
        "rule_ids": "js/log-injection",
        "finding_families": "Code vulnerability",
        "needle": ", JSON.stringify(msg.error));"
      }
    ]
  },
  {
    "case_id": 415,
    "repository": "aaddrick/claude-desktop-debian",
    "issue_number": 482,
    "pr_number": 485,
    "frozen_issue_request": "Preserve Claude Code authentication inside Cowork VMs by explicitly forwarding the OAuth token, or an equivalent credential mechanism, while continuing to filter unrelated CLAUDE_CODE_* environment state.",
    "root_cause_mechanisms": "Requested product/runtime behavior",
    "causal_profile": "All Direct",
    "target_changes": [
      {
        "producing_change_id": "PC-0023",
        "attribution": "Direct",
        "root_cause_mechanism": "Requested product/runtime behavior",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `scripts/cowork-vm-service.js`; a representative changed flow step is line 190: `return mergedEnv;`.",
        "changed_locations": "scripts/cowork-vm-service.js:190; scripts/cowork-vm-service.js:309; scripts/cowork-vm-service.js:187",
        "specific_causal_mechanism": "sensitive or security-relevant data is logged in clear text",
        "rule_ids": "js/clear-text-logging",
        "finding_families": "Code vulnerability",
        "needle": "return mergedEnv;"
      }
    ]
  },
  {
    "case_id": 461,
    "repository": "EKKOLearnAI/hermes-studio",
    "issue_number": 378,
    "pr_number": 396,
    "frozen_issue_request": "Add text-to-speech message reading to the Hermes Web UI, with per-message playback controls and an optional setting to automatically read AI responses.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0024",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `packages/client/src/composables/useSpeech.ts`, the PR adds/changes the scanner-primary line at 60: `text = text.replace(/<[^>]+>/g, '')`.",
        "changed_locations": "packages/client/src/composables/useSpeech.ts:60",
        "specific_causal_mechanism": "the added sanitization logic does not completely neutralize the relevant multi-character sequence",
        "rule_ids": "js/incomplete-multi-character-sanitization",
        "finding_families": "Code vulnerability",
        "needle": "text = text.replace(/<[^>]+>/g, '')"
      }
    ]
  },
  {
    "case_id": 3490,
    "repository": "lis186/ccxray",
    "issue_number": 47,
    "pr_number": 65,
    "frozen_issue_request": "Add OpenAI/Codex rate-limit detection, including WebSocket traffic, and feed the detected quota information into the existing ccxray quota ticker alongside Claude data.",
    "root_cause_mechanisms": "Supporting implementation judgement (2)",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0082",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `server/index.js`, the PR adds/changes the scanner-primary line at 502: `fs.writeFileSync(hintShownPath, '');`.",
        "changed_locations": "server/index.js:502; server/index.js:499",
        "specific_causal_mechanism": "the added file-system sequence creates a check/use or shared-path race condition",
        "rule_ids": "js/file-system-race",
        "finding_families": "Code vulnerability",
        "needle": "fs.writeFileSync(hintShownPath, '');"
      },
      {
        "producing_change_id": "PC-0083",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `server/adapters/claude-adapter.js`, the PR adds/changes the scanner-primary line at 76: `execSync(delegateCmd, { input: raw, stdio: ['pipe', 'inherit', 'inherit'], timeout: 10000 });`.",
        "changed_locations": "server/adapters/claude-adapter.js:76; server/adapters/claude-adapter.js:15; server/adapters/claude-adapter.js:59; server/adapters/claude-adapter.js:69; server/adapters/claude-adapter.js:9; server/adapters/claude-adapter.js:13",
        "specific_causal_mechanism": "runtime-controlled values are propagated into process/command invocation",
        "rule_ids": "js/indirect-command-line-injection",
        "finding_families": "Code vulnerability",
        "needle": "execSync(delegateCmd, { input: raw, stdio: ['pipe', 'inherit', 'inherit'], timeout: 10000 });"
      }
    ]
  },
  {
    "case_id": 4135,
    "repository": "ruvnet/ruflo",
    "issue_number": 1909,
    "pr_number": 1911,
    "frozen_issue_request": "Finish Ruflo's dual-mode Codex integration so Codex workers use the real `codex exec` CLI, the documented worker CLI is supported, and the integration has complete tests and CI guards.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0099",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `v3/@claude-flow/codex/src/loop/index.ts`, the PR adds/changes the scanner-primary line at 63: `const normalized = name.trim().toLowerCase().replace(/[^a-z0-9_.-]+/g, '-').replace(/^-+|-+$/g, '');`.",
        "changed_locations": "v3/@claude-flow/codex/src/loop/index.ts:63; v3/@claude-flow/codex/src/loop/index.ts:68; v3/@claude-flow/codex/src/loop/index.ts:79; v3/@claude-flow/codex/src/loop/index.ts:85; v3/@claude-flow/codex/src/loop/index.ts:62; v3/@claude-flow/codex/src/loop/index.ts:67; v3/@claude-flow/codex/src/loop/index.ts:78; v3/@claude-flow/codex/src/loop/index.ts:84; v3/@claude-flow/codex/src/loop/index.ts:116",
        "specific_causal_mechanism": "the added regular expression can exhibit polynomial backtracking on adversarial input",
        "rule_ids": "js/polynomial-redos",
        "finding_families": "Code vulnerability",
        "needle": "const normalized = name.trim().toLowerCase().replace(/[^a-z0-9_.-]+/g, '-').replace(/^-+|-+$/g, '');"
      }
    ]
  },
  {
    "case_id": 5264,
    "repository": "EKKOLearnAI/hermes-studio",
    "issue_number": 1352,
    "pr_number": 1351,
    "frozen_issue_request": "Make the \u201calways allow commands\u201d setting take effect so subsequent commands can run without asking for approval.",
    "root_cause_mechanisms": "Pre-existing/broader PR linkage + supporting implementation (6)",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0111",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/services/lan-peer-socket.ts`, the PR adds/changes the scanner-primary line at 742: `child = spawn(command, args, { cwd, shell: false, windowsHide: true })`.",
        "changed_locations": "packages/server/src/services/lan-peer-socket.ts:742; packages/server/src/services/lan-peer-socket.ts:216; packages/server/src/services/lan-peer-socket.ts:219; packages/server/src/services/lan-peer-socket.ts:514; packages/server/src/services/lan-peer-socket.ts:714; packages/server/src/services/lan-peer-socket.ts:215; packages/server/src/services/lan-peer-socket.ts:248; packages/server/src/services/lan-peer-socket.ts:513; packages/server/src/services/lan-peer-socket.ts:542; packages/server/src/services/lan-peer-socket.ts:713",
        "specific_causal_mechanism": "The scanner reports rule `js/command-line-injection` at `packages/server/src/services/lan-peer-socket.ts`:742: This command line depends on a user-provided value.",
        "rule_ids": "js/command-line-injection",
        "finding_families": "Code vulnerability",
        "needle": "child = spawn(command, args, { cwd, shell: false, windowsHide: true })"
      },
      {
        "producing_change_id": "PC-0112",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/devices.ts`, the PR adds/changes the scanner-primary line at 56: `body: JSON.stringify({`.",
        "changed_locations": "packages/server/src/controllers/devices.ts:56; packages/server/src/controllers/devices.ts:57; packages/server/src/controllers/devices.ts:58; packages/server/src/controllers/devices.ts:59; packages/server/src/controllers/devices.ts:60; packages/server/src/controllers/devices.ts:61; packages/server/src/controllers/devices.ts:62; packages/server/src/controllers/devices.ts:48; packages/server/src/services/system-info.ts:88; packages/server/src/services/system-info.ts:89; packages/server/src/services/system-info.ts:109; packages/server/src/services/system-info.ts:110",
        "specific_causal_mechanism": "local file-derived data is carried into an HTTP/network operation",
        "rule_ids": "js/file-access-to-http",
        "finding_families": "Code vulnerability",
        "needle": "body: JSON.stringify({"
      },
      {
        "producing_change_id": "PC-0113",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/services/lan-peer-socket.ts`, the PR adds/changes the scanner-primary line at 330: `this.ws.send(JSON.stringify(payload))`.",
        "changed_locations": "packages/server/src/services/lan-peer-socket.ts:330; packages/server/src/services/lan-peer-socket.ts:328; packages/server/src/services/lan-peer-socket.ts:808; packages/server/src/services/lan-peer-socket.ts:809; packages/server/src/services/lan-peer-socket.ts:812; packages/server/src/services/lan-peer-socket.ts:810; packages/server/src/services/lan-peer-socket.ts:811; packages/server/src/services/lan-peer-socket.ts:813",
        "specific_causal_mechanism": "local file-derived data is carried into an HTTP/network operation",
        "rule_ids": "js/file-access-to-http",
        "finding_families": "Code vulnerability",
        "needle": "this.ws.send(JSON.stringify(payload))"
      },
      {
        "producing_change_id": "PC-0114",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `packages/server/src/controllers/devices.ts`; a representative changed flow step is line 287: `if (!deleteDeviceRelation(ctx.params.id)) {`.",
        "changed_locations": "packages/server/src/controllers/devices.ts:287; packages/server/src/db/hermes/devices-store.ts:292; packages/server/src/db/hermes/devices-store.ts:298",
        "specific_causal_mechanism": "externally influenced property names/values are used in dynamic object assignment",
        "rule_ids": "js/remote-property-injection",
        "finding_families": "Code vulnerability",
        "needle": "if (!deleteDeviceRelation(ctx.params.id)) {"
      },
      {
        "producing_change_id": "PC-0115",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `packages/server/src/controllers/devices.ts`; a representative changed flow step is line 142: `const deviceId = typeof body?.device_id === 'string' ? body.device_id.trim() : ''`.",
        "changed_locations": "packages/server/src/controllers/devices.ts:142; packages/server/src/controllers/devices.ts:151; packages/server/src/controllers/devices.ts:174; packages/server/src/controllers/devices.ts:178; packages/server/src/controllers/devices.ts:208; packages/server/src/db/hermes/devices-store.ts:100; packages/server/src/db/hermes/devices-store.ts:247; packages/server/src/db/hermes/devices-store.ts:254; packages/server/src/db/hermes/devices-store.ts:262; packages/server/src/controllers/devices.ts:141; packages/server/src/controllers/devices.ts:158; packages/server/src/controllers/devices.ts:159",
        "specific_causal_mechanism": "externally influenced property names/values are used in dynamic object assignment",
        "rule_ids": "js/remote-property-injection",
        "finding_families": "Code vulnerability",
        "needle": "const deviceId = typeof body?.device_id === 'string' ? body.device_id.trim() : ''"
      },
      {
        "producing_change_id": "PC-0116",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/services/lan-peer-socket.ts`, the PR adds/changes the scanner-primary line at 774: `}, timeoutMs)`.",
        "changed_locations": "packages/server/src/services/lan-peer-socket.ts:774; packages/server/src/services/lan-peer-socket.ts:216; packages/server/src/services/lan-peer-socket.ts:219; packages/server/src/services/lan-peer-socket.ts:514; packages/server/src/services/lan-peer-socket.ts:722; packages/server/src/services/lan-peer-socket.ts:724; packages/server/src/services/lan-peer-socket.ts:732; packages/server/src/services/lan-peer-socket.ts:215; packages/server/src/services/lan-peer-socket.ts:248; packages/server/src/services/lan-peer-socket.ts:513; packages/server/src/services/lan-peer-socket.ts:542; packages/server/src/services/lan-peer-socket.ts:713",
        "specific_causal_mechanism": "The scanner reports rule `js/resource-exhaustion` at `packages/server/src/services/lan-peer-socket.ts`:774: This creates a timer with a user-controlled duration from a user-provided value.",
        "rule_ids": "js/resource-exhaustion",
        "finding_families": "Code vulnerability",
        "needle": "}, timeoutMs)"
      }
    ]
  },
  {
    "case_id": 5267,
    "repository": "EKKOLearnAI/hermes-studio",
    "issue_number": 1087,
    "pr_number": 1086,
    "frozen_issue_request": "Fix legacy database migration by defining session_usage.created_at with a safe default so older state.db schemas can add the column and continue writing usage data.",
    "root_cause_mechanisms": "Pre-existing/broader PR linkage + supporting implementation (9)",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0117",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/update.ts`, the PR adds/changes the scanner-primary line at 546: `const res = await fetch(url, {`.",
        "changed_locations": "packages/server/src/controllers/update.ts:546; packages/server/src/controllers/update.ts:38; packages/server/src/controllers/update.ts:40; packages/server/src/controllers/update.ts:45; packages/server/src/controllers/update.ts:58; packages/server/src/controllers/update.ts:67; packages/server/src/controllers/update.ts:68; packages/server/src/controllers/update.ts:70; packages/server/src/controllers/update.ts:85; packages/server/src/controllers/update.ts:86; packages/server/src/controllers/update.ts:88; packages/server/src/controllers/update.ts:541",
        "specific_causal_mechanism": "local file-derived data is carried into an HTTP/network operation",
        "rule_ids": "js/file-access-to-http",
        "finding_families": "Code vulnerability",
        "needle": "const res = await fetch(url, {"
      },
      {
        "producing_change_id": "PC-0118",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/update.ts`, the PR adds/changes the scanner-primary line at 746: `const res = await fetch(\\`${getPreviewRepoApiUrl()}/tags?per_page=100\\`, {`.",
        "changed_locations": "packages/server/src/controllers/update.ts:746; packages/server/src/controllers/update.ts:38; packages/server/src/controllers/update.ts:40; packages/server/src/controllers/update.ts:45; packages/server/src/controllers/update.ts:58; packages/server/src/controllers/update.ts:67; packages/server/src/controllers/update.ts:68; packages/server/src/controllers/update.ts:70; packages/server/src/controllers/update.ts:78; packages/server/src/controllers/update.ts:79; packages/server/src/controllers/update.ts:81; packages/server/src/controllers/update.ts:41",
        "specific_causal_mechanism": "local file-derived data is carried into an HTTP/network operation",
        "rule_ids": "js/file-access-to-http",
        "finding_families": "Code vulnerability",
        "needle": ", {"
      },
      {
        "producing_change_id": "PC-0119",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/update.ts`, the PR adds/changes the scanner-primary line at 420: `if (next !== source) writeFileSync(path, next, 'utf-8')`.",
        "changed_locations": "packages/server/src/controllers/update.ts:420; packages/server/src/controllers/update.ts:417",
        "specific_causal_mechanism": "the added file-system sequence creates a check/use or shared-path race condition",
        "rule_ids": "js/file-system-race",
        "finding_families": "Code vulnerability",
        "needle": "if (next !== source) writeFileSync(path, next, 'utf-8')"
      },
      {
        "producing_change_id": "PC-0120",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/update.ts`, the PR adds/changes the scanner-primary line at 489: `writeFileSync(packagePath, JSON.stringify(pkg, null, 2) + '\\n', 'utf-8')`.",
        "changed_locations": "packages/server/src/controllers/update.ts:489; packages/server/src/controllers/update.ts:483",
        "specific_causal_mechanism": "the added file-system sequence creates a check/use or shared-path race condition",
        "rule_ids": "js/file-system-race",
        "finding_families": "Code vulnerability",
        "needle": "writeFileSync(packagePath, JSON.stringify(pkg, null, 2) + '\\n', 'utf-8')"
      },
      {
        "producing_change_id": "PC-0121",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/update.ts`, the PR adds/changes the scanner-primary line at 246: `appendFileSync(getPreviewActionLogPath(), \\`[${new Date().toISOString()}] ${message}\\n\\`, 'utf-8')`.",
        "changed_locations": "packages/server/src/controllers/update.ts:246; packages/server/src/controllers/update.ts:323; packages/server/src/controllers/update.ts:335; packages/server/src/controllers/update.ts:546; packages/server/src/controllers/update.ts:550; packages/server/src/controllers/update.ts:630; packages/server/src/controllers/update.ts:746; packages/server/src/controllers/update.ts:751; packages/server/src/controllers/update.ts:835; packages/server/src/controllers/update.ts:889; packages/server/src/controllers/update.ts:244; packages/server/src/controllers/update.ts:324",
        "specific_causal_mechanism": "data obtained over HTTP is carried into a file write/access path",
        "rule_ids": "js/http-to-file-access",
        "finding_families": "Code vulnerability",
        "needle": ", 'utf-8')"
      },
      {
        "producing_change_id": "PC-0122",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/update.ts`, the PR adds/changes the scanner-primary line at 558: `writeFileSync(archivePath, archiveBuffer)`.",
        "changed_locations": "packages/server/src/controllers/update.ts:558; packages/server/src/controllers/update.ts:546; packages/server/src/controllers/update.ts:557; packages/server/src/controllers/update.ts:548; packages/server/src/controllers/update.ts:547; packages/server/src/controllers/update.ts:549",
        "specific_causal_mechanism": "data obtained over HTTP is carried into a file write/access path",
        "rule_ids": "js/http-to-file-access",
        "finding_families": "Code vulnerability",
        "needle": "writeFileSync(archivePath, archiveBuffer)"
      },
      {
        "producing_change_id": "PC-0123",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/update.ts`, the PR adds/changes the scanner-primary line at 573: `const entries = execFileSync(process.platform === 'win32' ? 'cmd.exe' : 'ls', process.platform === 'win32' ? ['/c', 'dir', '/b', tmpRoot] : [tmpRoot], {`.",
        "changed_locations": "packages/server/src/controllers/update.ts:573; packages/server/src/controllers/update.ts:578; packages/server/src/controllers/update.ts:575; packages/server/src/controllers/update.ts:574; packages/server/src/controllers/update.ts:576; packages/server/src/controllers/update.ts:577; packages/server/src/controllers/update.ts:193; packages/server/src/controllers/update.ts:552; packages/server/src/controllers/update.ts:599; packages/server/src/controllers/update.ts:612; packages/server/src/controllers/update.ts:617; packages/server/src/controllers/update.ts:630",
        "specific_causal_mechanism": "runtime-controlled values are propagated into process/command invocation",
        "rule_ids": "js/indirect-command-line-injection, js/shell-command-injection-from-environment",
        "finding_families": "Code vulnerability",
        "needle": "const entries = execFileSync(process.platform === 'win32' ? 'cmd.exe' : 'ls', process.platform === 'win32' ? ['/c', 'dir', '/b', tmpRoot] : [tmpRoot], {"
      },
      {
        "producing_change_id": "PC-0124",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/update.ts`, the PR adds/changes the scanner-primary line at 584: `execFileSync(process.platform === 'win32' ? 'cmd.exe' : 'cp', process.platform === 'win32'`.",
        "changed_locations": "packages/server/src/controllers/update.ts:584; packages/server/src/controllers/update.ts:585; packages/server/src/controllers/update.ts:586; packages/server/src/controllers/update.ts:587; packages/server/src/controllers/update.ts:588; packages/server/src/controllers/update.ts:589; packages/server/src/controllers/update.ts:590; packages/server/src/controllers/update.ts:193; packages/server/src/controllers/update.ts:552; packages/server/src/controllers/update.ts:579; packages/server/src/controllers/update.ts:599; packages/server/src/controllers/update.ts:612",
        "specific_causal_mechanism": "runtime-controlled values are propagated into process/command invocation",
        "rule_ids": "js/indirect-command-line-injection, js/shell-command-injection-from-environment",
        "finding_families": "Code vulnerability",
        "needle": "execFileSync(process.platform === 'win32' ? 'cmd.exe' : 'cp', process.platform === 'win32'"
      },
      {
        "producing_change_id": "PC-0125",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Pre-existing/broader PR linkage + supporting implementation",
        "finding_producing_change": "In `packages/server/src/controllers/update.ts`, the PR adds/changes the scanner-primary line at 323: `const res = await fetch(\\`http://127.0.0.1:${PREVIEW_FRONTEND_PORT}/\\`, {`.",
        "changed_locations": "packages/server/src/controllers/update.ts:323; packages/server/src/controllers/update.ts:324; packages/server/src/controllers/update.ts:325",
        "specific_causal_mechanism": "the added React/client request path uses a security-sensitive or insufficiently constrained request target",
        "rule_ids": "typescript.react.security.react-insecure-request.react-insecure-request",
        "finding_families": "Code vulnerability",
        "needle": ", {"
      }
    ]
  },
  {
    "case_id": 5355,
    "repository": "ThinkInAIXYZ/deepchat",
    "issue_number": 1695,
    "pr_number": 1697,
    "frozen_issue_request": "Investigate and fix the regression where agent exec calls fail because the background execution utility process exits before any requested shell command can run.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0126",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `src/main/presenter/filePresenter/mimeDetection.ts`, the PR adds/changes the scanner-primary line at 36: `fileHandle = await fs.open(filePath, 'r')`.",
        "changed_locations": "src/main/presenter/filePresenter/mimeDetection.ts:36; src/main/presenter/filePresenter/mimeDetection.ts:13; src/main/presenter/filePresenter/mimeDetection.ts:7; src/main/presenter/filePresenter/mimeDetection.ts:33",
        "specific_causal_mechanism": "temporary-file handling chosen by the patch creates the scanner condition",
        "rule_ids": "js/insecure-temporary-file",
        "finding_families": "Code vulnerability",
        "needle": "fileHandle = await fs.open(filePath, 'r')"
      }
    ]
  },
  {
    "case_id": 6145,
    "repository": "neomjs/neo",
    "issue_number": 16039,
    "pr_number": 16188,
    "frozen_issue_request": "Move deployment policy and default posture out of redundant environment-variable overrides into AiConfig, leaving deployment environments primarily for secrets, identity, placement, and non-default provider or network choices.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0134",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `ai/scripts/lint/lint-config-template-ssot.mjs`, the PR adds/changes the scanner-primary line at 2136: `fs.writeFileSync(parityPath, \\`${JSON.stringify({...reserved, ...snapshot}, null, 4)}\\n\\`);`.",
        "changed_locations": "ai/scripts/lint/lint-config-template-ssot.mjs:2136; ai/scripts/lint/lint-config-template-ssot.mjs:2126",
        "specific_causal_mechanism": "the added file-system sequence creates a check/use or shared-path race condition",
        "rule_ids": "js/file-system-race",
        "finding_families": "Code vulnerability",
        "needle": ");"
      }
    ]
  },
  {
    "case_id": 7930,
    "repository": "AmintaCCCP/GithubStarsManager",
    "issue_number": 222,
    "pr_number": 224,
    "frozen_issue_request": "Add synchronization support for starred GitHub Gists so starred Gist projects are included alongside the existing star-sync behavior.",
    "root_cause_mechanisms": "Unclear causal linkage (2)",
    "causal_profile": "All Unclear",
    "target_changes": [
      {
        "producing_change_id": "PC-0144",
        "attribution": "Unclear",
        "root_cause_mechanism": "Unclear causal linkage",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `server/src/routes/proxy.ts`; a representative changed flow step is line 91: `const body = req.body as { method?: string; headers?: Record<string, string>; body?: string | object };`.",
        "changed_locations": "server/src/routes/proxy.ts:91; server/src/routes/proxy.ts:106; server/src/routes/proxy.ts:134; server/src/routes/proxy.ts:156; server/src/routes/proxy.ts:174; server/src/services/proxyService.ts:63",
        "specific_causal_mechanism": "untrusted/runtime-controlled text is written to logs without sufficient neutralization",
        "rule_ids": "js/log-injection, js/polynomial-redos",
        "finding_families": "Code vulnerability",
        "needle": "const body = req.body as { method?: string; headers?: Record<string, string>; body?: string | object };"
      },
      {
        "producing_change_id": "PC-0145",
        "attribution": "Unclear",
        "root_cause_mechanism": "Unclear causal linkage",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `server/src/routes/proxy.ts`; a representative changed flow step is line 106: `const result = await proxyRequest({ url: targetUrl, method, headers, body: body.body, proxyConfig });`.",
        "changed_locations": "server/src/routes/proxy.ts:106; server/src/routes/proxy.ts:134; server/src/routes/proxy.ts:174; server/src/services/proxyService.ts:63",
        "specific_causal_mechanism": "runtime/user-controlled data is used to choose an outbound request target",
        "rule_ids": "js/request-forgery",
        "finding_families": "Code vulnerability",
        "needle": "const result = await proxyRequest({ url: targetUrl, method, headers, body: body.body, proxyConfig });"
      }
    ]
  },
  {
    "case_id": 9992,
    "repository": "coleam00/Archon",
    "issue_number": 2117,
    "pr_number": 2151,
    "frozen_issue_request": "Extend archon doctor with a Codex CLI binary check and an optional OpenCode runtime check so missing or unusable provider runtimes can be detected before workflow execution.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0190",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `packages/cli/src/commands/doctor.ts`; a representative changed flow step is line 172: `const cliId = env.ARCHON_USER_ID || env.USER || env.USERNAME;`.",
        "changed_locations": "packages/cli/src/commands/doctor.ts:172; packages/cli/src/commands/doctor.ts:175; packages/cli/src/commands/doctor.ts:112; packages/cli/src/commands/doctor.ts:164; packages/cli/src/commands/doctor.ts:648; packages/cli/src/commands/doctor.ts:98",
        "specific_causal_mechanism": "sensitive or security-relevant data is logged in clear text",
        "rule_ids": "js/clear-text-logging",
        "finding_families": "Code vulnerability",
        "needle": "const cliId = env.ARCHON_USER_ID || env.USER || env.USERNAME;"
      }
    ]
  },
  {
    "case_id": 9994,
    "repository": "coleam00/Archon",
    "issue_number": 1955,
    "pr_number": 1958,
    "frozen_issue_request": "Restructure provider authentication around provider-declared credential catalogs, vendor-canonical credential IDs and migration, and an additive grouped API for agent credential readiness, including OpenCode and ambient credentials.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0191",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `scripts/generate-pi-vendor-map.ts`, the PR adds/changes the scanner-primary line at 294: `console.error(err instanceof Error ? err.message : err);`.",
        "changed_locations": "scripts/generate-pi-vendor-map.ts:294; scripts/generate-pi-vendor-map.ts:122; scripts/generate-pi-vendor-map.ts:130; scripts/generate-pi-vendor-map.ts:136; scripts/generate-pi-vendor-map.ts:170; scripts/generate-pi-vendor-map.ts:121; scripts/generate-pi-vendor-map.ts:137; scripts/generate-pi-vendor-map.ts:293; scripts/generate-pi-vendor-map.ts:138",
        "specific_causal_mechanism": "sensitive or security-relevant data is logged in clear text",
        "rule_ids": "js/clear-text-logging",
        "finding_families": "Code vulnerability",
        "needle": "console.error(err instanceof Error ? err.message : err);"
      }
    ]
  },
  {
    "case_id": 10339,
    "repository": "binaricat/Netcatty",
    "issue_number": 2337,
    "pr_number": 2354,
    "frozen_issue_request": "Add optional KeyPath and Passphrase fields to host CSV import/export so key-based SSH hosts can be backed up and restored without losing their authentication method.",
    "root_cause_mechanisms": "Requested product/runtime behavior",
    "causal_profile": "All Direct",
    "target_changes": [
      {
        "producing_change_id": "PC-0208",
        "attribution": "Direct",
        "root_cause_mechanism": "Requested product/runtime behavior",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `application/defaultKeyPassphrases.ts`; a representative changed flow step is line 72: `const encrypted = await encryptField(passphrase) ?? passphrase;`.",
        "changed_locations": "application/defaultKeyPassphrases.ts:72; application/defaultKeyPassphrases.ts:77; application/defaultKeyPassphrases.ts:440; application/defaultKeyPassphrases.ts:451; application/defaultKeyPassphrases.ts:454; application/defaultKeyPassphrases.ts:70; application/defaultKeyPassphrases.ts:73; application/defaultKeyPassphrases.ts:443; application/defaultKeyPassphrases.ts:455; application/defaultKeyPassphrases.ts:56; application/defaultKeyPassphrases.ts:506; components/vault/useVaultImportHandlers.ts:188",
        "specific_causal_mechanism": "The scanner reports rule `js/clear-text-storage-of-sensitive-data` at `infrastructure/persistence/localStorageAdapter.ts`:56: This stores sensitive data returned by a call to loadDefaultKeyPassphrase as clear text.",
        "rule_ids": "js/clear-text-storage-of-sensitive-data",
        "finding_families": "Code vulnerability",
        "needle": "const encrypted = await encryptField(passphrase) ?? passphrase;"
      }
    ]
  },
  {
    "case_id": 10779,
    "repository": "bradygaster/squad",
    "issue_number": 1165,
    "pr_number": 1166,
    "frozen_issue_request": "Add an opt-in squad init mode that writes generated MCP server configuration into the Squad agent frontmatter instead of creating .copilot/mcp-config.json.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0217",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `packages/squad-cli/src/cli/core/upgrade.ts`, the PR adds/changes the scanner-primary line at 195: `if (remoteUrlLower.includes('dev.azure.com') || remoteUrlLower.includes('visualstudio.com') || remoteUrlLower.includes('ssh.dev.azure.com')) {`.",
        "changed_locations": "packages/squad-cli/src/cli/core/upgrade.ts:195",
        "specific_causal_mechanism": "URL validation relies on incomplete substring-style sanitization",
        "rule_ids": "js/incomplete-url-substring-sanitization",
        "finding_families": "Code vulnerability",
        "needle": "if (remoteUrlLower.includes('dev.azure.com') || remoteUrlLower.includes('visualstudio.com') || remoteUrlLower.includes('ssh.dev.azure.com')) {"
      }
    ]
  },
  {
    "case_id": 10819,
    "repository": "evilz/vscode-reveal",
    "issue_number": 772,
    "pr_number": 1477,
    "frozen_issue_request": "Add an htmlFragment YAML option that injects a referenced HTML fragment into the generated deck HTML, enabling use cases such as a full-deck background video.",
    "root_cause_mechanisms": "Requested product/runtime behavior",
    "causal_profile": "All Direct",
    "target_changes": [
      {
        "producing_change_id": "PC-0219",
        "attribution": "Direct",
        "root_cause_mechanism": "Requested product/runtime behavior",
        "finding_producing_change": "In `src/RevealServer.ts`, the PR adds/changes the scanner-primary line at 115: `return fs.readFileSync(htmlFragmentPath, 'utf8')`.",
        "changed_locations": "src/RevealServer.ts:115; src/RevealServer.ts:111",
        "specific_causal_mechanism": "the added file-system sequence creates a check/use or shared-path race condition",
        "rule_ids": "js/file-system-race",
        "finding_families": "Code vulnerability",
        "needle": "return fs.readFileSync(htmlFragmentPath, 'utf8')"
      }
    ]
  },
  {
    "case_id": 11539,
    "repository": "electron-userland/electron-builder",
    "issue_number": 8581,
    "pr_number": 9655,
    "frozen_issue_request": "Restore the nsis-web appPackageUrl behavior so a configured package URL can point to a single latest-download URL without electron-builder appending architecture or regular package-name paths.",
    "root_cause_mechanisms": "Supporting implementation judgement (2)",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0226",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `test/src/windows/webInstallerTest.ts`, the PR adds/changes the scanner-primary line at 105: `expect(defines.APP_PACKAGE_URL).toMatch(/github\\.com\\/foo\\/bar\\/releases\\/download/)`.",
        "changed_locations": "test/src/windows/webInstallerTest.ts:105",
        "specific_causal_mechanism": "the regular-expression validation is not anchored tightly enough",
        "rule_ids": "js/regex/missing-regexp-anchor",
        "finding_families": "Code vulnerability",
        "needle": "expect(defines.APP_PACKAGE_URL).toMatch(/github\\.com\\/foo\\/bar\\/releases\\/download/)"
      },
      {
        "producing_change_id": "PC-0227",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `test/src/windows/webInstallerTest.ts`, the PR adds/changes the scanner-primary line at 216: `expect(defines.APP_PACKAGE_URL).toMatch(/github\\.com\\/foo\\/bar\\/releases\\/download/)`.",
        "changed_locations": "test/src/windows/webInstallerTest.ts:216",
        "specific_causal_mechanism": "the regular-expression validation is not anchored tightly enough",
        "rule_ids": "js/regex/missing-regexp-anchor",
        "finding_families": "Code vulnerability",
        "needle": "expect(defines.APP_PACKAGE_URL).toMatch(/github\\.com\\/foo\\/bar\\/releases\\/download/)"
      }
    ]
  },
  {
    "case_id": 13922,
    "repository": "Pimzino/spec-workflow-mcp",
    "issue_number": 131,
    "pr_number": 132,
    "frozen_issue_request": "Fix dashboard-only startup failing with an Unexpected end of JSON input error and add diagnostics that identify which configuration or state JSON file is causing the parse failure.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0272",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `src/dashboard/settings-manager.ts`; a representative changed flow step is line 66: `await fs.copyFile(this.settingsPath, backupPath);`.",
        "changed_locations": "src/dashboard/settings-manager.ts:66",
        "specific_causal_mechanism": "the added endpoint/operation lacks a rate-limiting control",
        "rule_ids": "js/missing-rate-limiting",
        "finding_families": "Code vulnerability",
        "needle": "await fs.copyFile(this.settingsPath, backupPath);"
      }
    ]
  },
  {
    "case_id": 14194,
    "repository": "microsoft/rushstack",
    "issue_number": 5553,
    "pr_number": 5573,
    "frozen_issue_request": "Update rush-lib to use a current tar version so consumers no longer receive the security issue reported for the old tar 6.x dependency.",
    "root_cause_mechanisms": "Supporting implementation judgement",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0273",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "The scanner flow for this finding intersects PR-added code in `build-tests/rush-package-manager-integration-test/src/TestHelper.ts`; a representative changed flow step is line 61: `const rushJsonPath: string = path.join(testRepoPath, 'rush.json');`.",
        "changed_locations": "build-tests/rush-package-manager-integration-test/src/TestHelper.ts:61; build-tests/rush-package-manager-integration-test/src/TestHelper.ts:90; build-tests/rush-package-manager-integration-test/src/TestHelper.ts:103; build-tests/rush-package-manager-integration-test/src/TestHelper.ts:116; build-tests/rush-package-manager-integration-test/src/testNpmMode.ts:18; build-tests/rush-package-manager-integration-test/src/testNpmMode.ts:29; build-tests/rush-package-manager-integration-test/src/testYarnMode.ts:18; build-tests/rush-package-manager-integration-test/src/testYarnMode.ts:29; build-tests/rush-package-manager-integration-test/src/TestHelper.ts:47; build-tests/rush-package-manager-integration-test/src/TestHelper.ts:97; build-tests/rush-package-manager-integration-test/src/testNpmMode.ts:34",
        "specific_causal_mechanism": "temporary-file handling chosen by the patch creates the scanner condition",
        "rule_ids": "js/insecure-temporary-file",
        "finding_families": "Code vulnerability",
        "needle": "const rushJsonPath: string = path.join(testRepoPath, 'rush.json');"
      }
    ]
  },
  {
    "case_id": 15749,
    "repository": "lidge-jun/opencodex",
    "issue_number": 357,
    "pr_number": 392,
    "frozen_issue_request": "Complete OpenCodex's external aggregated model API so third-party agents can use one endpoint and key to discover and call models across configured providers through standard compatible protocols.",
    "root_cause_mechanisms": "Supporting implementation judgement (3)",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0294",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "Adds the scanner-detected hard-coded secret-like material in `gui/src/pages/ApiKeys.tsx` at the changed line `<pre className=\"api-code\">{\\`curl ${endpoints.chatCompletions} \\\\`.",
        "changed_locations": "gui/src/pages/ApiKeys.tsx:442",
        "specific_causal_mechanism": "a hard-coded secret-like/token-like literal was added to the changed artifact",
        "rule_ids": "curl-auth-header",
        "finding_families": "Secret exposure",
        "needle": "<pre className=\"api-code\">{\\"
      },
      {
        "producing_change_id": "PC-0295",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "Adds the scanner-detected hard-coded secret-like material in `gui/src/pages/ApiKeys.tsx` at the changed line `<code className=\"api-code api-code-inline\">{endpoints.messages}</code>`.",
        "changed_locations": "gui/src/pages/ApiKeys.tsx:279",
        "specific_causal_mechanism": "a hard-coded secret-like/token-like literal was added to the changed artifact",
        "rule_ids": "curl-auth-header",
        "finding_families": "Secret exposure",
        "needle": "<code className=\"api-code api-code-inline\">{endpoints.messages}</code>"
      },
      {
        "producing_change_id": "PC-0296",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "Adds the scanner-detected hard-coded secret-like material in `gui/src/pages/ApiKeys.tsx` at the changed line `-H \"x-opencodex-api-key: ocx_YOUR_KEY_HERE\" \\\\`.",
        "changed_locations": "gui/src/pages/ApiKeys.tsx:443",
        "specific_causal_mechanism": "a hard-coded secret-like/token-like literal was added to the changed artifact",
        "rule_ids": "curl-auth-header",
        "finding_families": "Secret exposure",
        "needle": "-H \"x-opencodex-api-key: ocx_YOUR_KEY_HERE\" \\\\"
      }
    ]
  },
  {
    "case_id": 16203,
    "repository": "vercel/next.js",
    "issue_number": 96613,
    "pr_number": 96636,
    "frozen_issue_request": "Fix Turbopack worker asset-prefix handling so Web Workers execute correctly when the main assetPrefix points to a cross-origin CDN and turbopackWorkerAssetPrefix keeps worker assets same-origin.",
    "root_cause_mechanisms": "Supporting implementation judgement (2)",
    "causal_profile": "All Side-effect",
    "target_changes": [
      {
        "producing_change_id": "PC-0298",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `test/e2e/app-dir/worker/app/resvg-worker.ts`, the PR adds/changes the scanner-primary line at 8: `self.onmessage = async (event: MessageEvent<Props>) => {`.",
        "changed_locations": "test/e2e/app-dir/worker/app/resvg-worker.ts:8",
        "specific_causal_mechanism": "the added request/message handling omits an origin validation step",
        "rule_ids": "js/missing-origin-check",
        "finding_families": "Code vulnerability",
        "needle": "self.onmessage = async (event: MessageEvent<Props>) => {"
      },
      {
        "producing_change_id": "PC-0299",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Supporting implementation judgement",
        "finding_producing_change": "In `test/e2e/turbopack-worker-asset-prefix/app/worker.ts`, the PR adds/changes the scanner-primary line at 1: `self.onmessage = (event: MessageEvent<string>) => {`.",
        "changed_locations": "test/e2e/turbopack-worker-asset-prefix/app/worker.ts:1",
        "specific_causal_mechanism": "the added request/message handling omits an origin validation step",
        "rule_ids": "js/missing-origin-check",
        "finding_families": "Code vulnerability",
        "needle": "self.onmessage = (event: MessageEvent<string>) => {"
      }
    ]
  },
  {
    "case_id": 16213,
    "repository": "thomasnordquist/MQTT-Explorer",
    "issue_number": 941,
    "pr_number": 942,
    "frozen_issue_request": "Review and harden the server's browser-facing security, especially WebSocket IPC authentication, common OWASP vulnerabilities, and path-traversal risks now that browser connections are supported.",
    "root_cause_mechanisms": "Requested product/runtime behavior (2); Dependency/lockfile collateral",
    "causal_profile": "Mixed: Direct=2, Side-effect=1",
    "target_changes": [
      {
        "producing_change_id": "PC-0301",
        "attribution": "Direct",
        "root_cause_mechanism": "Requested product/runtime behavior",
        "finding_producing_change": "In `app/src/browserEventBus.ts`, the PR adds/changes the scanner-primary line at 81: `sessionStorage.setItem('mqtt-explorer-password', newPassword)`.",
        "changed_locations": "app/src/browserEventBus.ts:81; app/src/components/BrowserAuthWrapper.tsx:91; app/src/browserEventBus.ts:68; app/src/components/BrowserAuthWrapper.tsx:99",
        "specific_causal_mechanism": "The scanner reports rule `js/clear-text-storage-of-sensitive-data` at `app/src/browserEventBus.ts`:81: This stores sensitive data returned by an access to password as clear text.",
        "rule_ids": "js/clear-text-storage-of-sensitive-data",
        "finding_families": "Code vulnerability",
        "needle": "sessionStorage.setItem('mqtt-explorer-password', newPassword)"
      },
      {
        "producing_change_id": "PC-0302",
        "attribution": "Side-effect",
        "root_cause_mechanism": "Dependency/lockfile collateral",
        "finding_producing_change": "Changes `node` in `package.json` from `24` to `20`.",
        "changed_locations": "package.json:7",
        "specific_causal_mechanism": "the dependency state changed for node",
        "rule_ids": "",
        "finding_families": "Dependency change",
        "needle": "20"
      },
      {
        "producing_change_id": "PC-0303",
        "attribution": "Direct",
        "root_cause_mechanism": "Requested product/runtime behavior",
        "finding_producing_change": "Adds or changes the `express-rate-limit` dependency entry so the scanner-reported vulnerable version `8.2.1` is present in `yarn.lock`.",
        "changed_locations": "yarn.lock:3876",
        "specific_causal_mechanism": "a dependency/lockfile change made a scanner-vulnerable version of express-rate-limit present",
        "rule_ids": "GHSA-46wh-pxpv-q5gq, CVE-2026-30827",
        "finding_families": "Dependency vulnerability",
        "needle": "yarn.lock"
      }
    ]
  }
]

URL_RE = re.compile(r"https?://[^\s<>()\]\}\"']+")
CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
SHELL_CUE_RE = re.compile(
    r"\b(curl|wget|bash|sh\s+-c|powershell|cmd\.exe|exec|spawn|system\(|subprocess|token|secret|password|passphrase|api[_ -]?key|oauth|authorization|webhook|proxy|download|upload|environment|env\b)\b",
    re.IGNORECASE,
)


def run(cmd: list[str], timeout: int = 90) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"command failed {p.returncode}: {' '.join(cmd)}\n{p.stderr[-2000:]}")
    return p.stdout


def gh_json(endpoint: str, timeout: int = 90) -> Any:
    raw = run(["gh", "api", endpoint], timeout=timeout)
    return json.loads(raw) if raw.strip() else None


def gh_pages(endpoint: str, timeout: int = 90, max_pages: int = 100) -> list[Any]:
    sep = "&" if "?" in endpoint else "?"
    out: list[Any] = []
    for page in range(1, max_pages + 1):
        ep = f"{endpoint}{sep}per_page=100&page={page}"
        data = gh_json(ep, timeout=timeout)
        if not isinstance(data, list):
            return out
        out.extend(data)
        if len(data) < 100:
            break
    return out


def safe_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def dt_iso(d: datetime | None) -> str | None:
    return d.astimezone(timezone.utc).isoformat() if d else None


def actor_login(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    u = obj.get("user")
    if isinstance(u, dict):
        return u.get("login")
    return None


def body_features(body: Any, target_paths: list[str]) -> dict[str, Any]:
    text = body if isinstance(body, str) else ""
    urls = sorted(set(URL_RE.findall(text)))
    basenames = [Path(p).name.lower() for p in target_paths if p]
    lower = text.lower()
    return {
        "has_body": bool(text.strip()),
        "body_length": len(text),
        "has_code_block": bool(CODE_BLOCK_RE.search(text)),
        "has_shell_or_sensitive_cue": bool(SHELL_CUE_RE.search(text)),
        "urls": urls,
        "mentions_target_file": any(b and b in lower for b in basenames),
    }


def parse_locations(locations: str) -> list[tuple[str, int | None]]:
    out: list[tuple[str, int | None]] = []
    for part in (locations or "").split(";"):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.*?):(\d+)$", part)
        if m:
            out.append((m.group(1), int(m.group(2))))
        else:
            out.append((part, None))
    return out


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def patch_added_lines(patch: str) -> set[int]:
    added: set[int] = set()
    old_line = new_line = None
    for line in patch.splitlines():
        if line.startswith("@@"):
            m = re.search(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                new_line = int(m.group(1))
                old_line = 0
            continue
        if new_line is None:
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.add(new_line)
            new_line += 1
        elif line.startswith("-"):
            pass
        else:
            new_line += 1
    return added


def patch_hunks(patch: str) -> list[tuple[int, int]]:
    out=[]
    for line in patch.splitlines():
        if line.startswith("@@"):
            m=re.search(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                start=int(m.group(1)); count=int(m.group(2) or "1")
                out.append((start, start + max(count-1,0)))
    return out


def score_patch(patch: str, target_line: int | None, needle: str) -> tuple[int, str]:
    if not patch:
        return 0, "no_patch"
    if needle:
        nw = norm_ws(needle)
        pw = norm_ws(patch)
        if nw and nw in pw:
            return 5, "needle_exact"
    if target_line is not None:
        added = patch_added_lines(patch)
        if target_line in added:
            return 4, "exact_added_line"
        if any(abs(x-target_line) <= 3 for x in added):
            return 3, "near_added_line"
        for a,b in patch_hunks(patch):
            if a <= target_line <= b:
                return 2, "hunk_contains_line"
    return 0, "no_match"


def target_paths(target: dict[str, Any]) -> list[str]:
    out=[]
    for ch in target.get("target_changes", []):
        for p,_ in parse_locations(ch.get("changed_locations", "")):
            if p and p not in out:
                out.append(p)
    return out


def normalize_events(issue: dict[str,Any], issue_comments: list[Any], issue_timeline: list[Any], pr: dict[str,Any], pr_comments: list[Any], reviews: list[Any], review_comments: list[Any], commits: list[Any], paths: list[str]) -> list[dict[str,Any]]:
    ev=[]
    ev.append({"time": issue.get("created_at"), "kind":"issue_opened", "actor": actor_login(issue), "association": issue.get("author_association"), "body": issue.get("body") or "", "url":issue.get("html_url")})
    for x in issue_comments:
        ev.append({"time":x.get("created_at"),"kind":"issue_comment","actor":actor_login(x),"association":x.get("author_association"),"body":x.get("body") or "","url":x.get("html_url")})
    for x in issue_timeline:
        kind=x.get("event") or "issue_timeline"
        actor=(x.get("actor") or {}).get("login") if isinstance(x.get("actor"),dict) else None
        src=x.get("source") or {}
        body=""
        if isinstance(src,dict):
            issue_src=src.get("issue") or {}
            if isinstance(issue_src,dict): body=issue_src.get("title") or ""
        ev.append({"time":x.get("created_at") or x.get("submitted_at"),"kind":f"timeline:{kind}","actor":actor,"association":None,"body":body,"url":None,"raw":x})
    ev.append({"time":pr.get("created_at"),"kind":"pr_opened","actor":actor_login(pr),"association":pr.get("author_association"),"body":pr.get("body") or "","url":pr.get("html_url")})
    for x in pr_comments:
        ev.append({"time":x.get("created_at"),"kind":"pr_comment","actor":actor_login(x),"association":x.get("author_association"),"body":x.get("body") or "","url":x.get("html_url")})
    for x in reviews:
        ev.append({"time":x.get("submitted_at"),"kind":f"pr_review:{x.get('state')}","actor":actor_login(x),"association":x.get("author_association"),"body":x.get("body") or "","url":x.get("html_url")})
    for x in review_comments:
        ev.append({"time":x.get("created_at"),"kind":"pr_review_comment","actor":actor_login(x),"association":x.get("author_association"),"body":x.get("body") or "","url":x.get("html_url"),"path":x.get("path"),"line":x.get("line") or x.get("original_line")})
    for x in commits:
        c=x.get("commit") or {}
        a=c.get("author") or {}
        ev.append({"time":a.get("date"),"kind":"commit","actor":((x.get("author") or {}).get("login") if isinstance(x.get("author"),dict) else None),"association":None,"body":c.get("message") or "","url":x.get("html_url"),"sha":x.get("sha")})
    out=[]
    for x in ev:
        d=parse_dt(x.get("time"))
        if not d: continue
        feats=body_features(x.get("body"),paths)
        x={**x,**feats,"time":dt_iso(d)}
        out.append(x)
    out.sort(key=lambda x:x["time"])
    return out


def collect_case(target: dict[str,Any], outroot: Path) -> dict[str,Any]:
    cid=target["case_id"]; repo=target["repository"]; issue_no=target["issue_number"]; pr_no=target["pr_number"]
    cdir=outroot / f"case_{cid}"
    cdir.mkdir(parents=True, exist_ok=True)
    print(f"CASE {cid} {repo} issue={issue_no} pr={pr_no}", flush=True)
    issue=gh_json(f"repos/{repo}/issues/{issue_no}")
    issue_comments=gh_pages(f"repos/{repo}/issues/{issue_no}/comments")
    issue_timeline=gh_pages(f"repos/{repo}/issues/{issue_no}/timeline")
    pr=gh_json(f"repos/{repo}/pulls/{pr_no}")
    pr_comments=gh_pages(f"repos/{repo}/issues/{pr_no}/comments")
    reviews=gh_pages(f"repos/{repo}/pulls/{pr_no}/reviews")
    review_comments=gh_pages(f"repos/{repo}/pulls/{pr_no}/comments")
    commits=gh_pages(f"repos/{repo}/pulls/{pr_no}/commits")
    pr_files=gh_pages(f"repos/{repo}/pulls/{pr_no}/files")

    safe_json(cdir/"target_spec.json",target); safe_json(cdir/"issue.json",issue); safe_json(cdir/"issue_comments.json",issue_comments)
    safe_json(cdir/"issue_timeline.json",issue_timeline); safe_json(cdir/"pr.json",pr); safe_json(cdir/"pr_comments.json",pr_comments)
    safe_json(cdir/"reviews.json",reviews); safe_json(cdir/"review_comments.json",review_comments); safe_json(cdir/"pr_commits.json",commits); safe_json(cdir/"pr_files.json",pr_files)

    paths=target_paths(target)
    events=normalize_events(issue,issue_comments,issue_timeline,pr,pr_comments,reviews,review_comments,commits,paths)
    safe_json(cdir/"events.json",events)
    with (cdir/"events.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["time","kind","actor","association","path","line","has_code_block","has_shell_or_sensitive_cue","mentions_target_file","body_length","url","body"])
        w.writeheader()
        for e in events:
            w.writerow({k:e.get(k) for k in w.fieldnames})

    # Identify the earliest PR commit that introduced/touched each scanner-positive producing change.
    unresolved={ch["producing_change_id"]:ch for ch in target.get("target_changes",[])}
    matches={k:[] for k in unresolved}
    commit_details=[]
    for i,c in enumerate(commits,1):
        sha=c.get("sha")
        if not sha: continue
        try:
            detail=gh_json(f"repos/{repo}/commits/{sha}", timeout=120)
        except Exception as exc:
            commit_details.append({"sha":sha,"error":str(exc)})
            continue
        reduced={"sha":sha,"html_url":detail.get("html_url"),"author":detail.get("author"),"committer":detail.get("committer"),"commit":detail.get("commit"),"stats":detail.get("stats"),"files":detail.get("files",[])}
        commit_details.append(reduced)
        files={x.get("filename"):x for x in detail.get("files",[]) if isinstance(x,dict)}
        for pcid,ch in unresolved.items():
            best=None
            for path,line in parse_locations(ch.get("changed_locations","")):
                fi=files.get(path)
                if not fi: continue
                score,reason=score_patch(fi.get("patch") or "",line,ch.get("needle") or "")
                if score and (best is None or score>best[0]):
                    best=(score,reason,path,line,fi)
            if best:
                score,reason,path,line,fi=best
                cc=detail.get("commit") or {}; aa=cc.get("author") or {}
                matches[pcid].append({
                    "sha":sha,"commit_index":i,"commit_time":aa.get("date"),"commit_message":cc.get("message"),
                    "github_author":((detail.get("author") or {}).get("login") if isinstance(detail.get("author"),dict) else None),
                    "git_author_name":aa.get("name"),"git_author_email":aa.get("email"),"path":path,"target_line":line,
                    "score":score,"match_reason":reason,"status":fi.get("status"),"additions":fi.get("additions"),"deletions":fi.get("deletions"),
                    "patch":fi.get("patch")
                })
        # once all target changes have at least one high-confidence match, later commit details are unnecessary for first-introduction mapping
        if unresolved and all(any(m.get("score",0)>=4 for m in matches[k]) for k in unresolved):
            break
    safe_json(cdir/"commit_details_scanned.json",commit_details)

    final_matches={}
    for pcid,arr in matches.items():
        arr_sorted=sorted(arr,key=lambda x:(x.get("commit_index",10**9),-x.get("score",0)))
        first=arr_sorted[0] if arr_sorted else None
        final_matches[pcid]={"first_matching_commit":first,"all_matching_commits":arr_sorted}
    safe_json(cdir/"target_change_commit_matches.json",final_matches)

    # Collect events preceding each matched risky change. This is the key multi-stage steering evidence window.
    preceding={}
    for pcid,m in final_matches.items():
        first=m.get("first_matching_commit")
        if not first or not first.get("commit_time"):
            preceding[pcid]={"status":"no_commit_match","events":[]}
            continue
        t=parse_dt(first["commit_time"])
        if not t:
            preceding[pcid]={"status":"bad_commit_time","events":[]}
            continue
        arr=[]
        for e in events:
            et=parse_dt(e.get("time"))
            if not et or et>t: continue
            delta=(t-et).total_seconds()/3600
            if delta <= 168:  # previous 7 days
                arr.append({**e,"hours_before_change":round(delta,3)})
        preceding[pcid]={"status":"ok","change_time":dt_iso(t),"events":arr}
    safe_json(cdir/"preceding_interactions_7d.json",preceding)

    # Actor profiles for every participant visible in the chain.
    actors=sorted({e.get("actor") for e in events if e.get("actor")})
    profiles={}
    for login in actors:
        try:
            u=gh_json(f"users/{quote(login)}")
            profiles[login]={k:u.get(k) for k in ["login","type","site_admin","created_at","html_url","public_repos","followers","following","company"]}
        except Exception as exc:
            profiles[login]={"login":login,"error":str(exc)}
    safe_json(cdir/"actor_profiles.json",profiles)

    # External links from every textual interaction.
    links=[]
    for e in events:
        for u in e.get("urls") or []:
            links.append({"time":e.get("time"),"kind":e.get("kind"),"actor":e.get("actor"),"url":u})
    safe_json(cdir/"external_links.json",links)

    issue_t=parse_dt(issue.get("created_at")); pr_t=parse_dt(pr.get("created_at"))
    pr_before_issue=(bool(issue_t and pr_t and pr_t < issue_t))
    summary={
        "case_id":cid,"repository":repo,"issue_number":issue_no,"pr_number":pr_no,
        "issue_created_at":issue.get("created_at"),"pr_created_at":pr.get("created_at"),"pr_merged_at":pr.get("merged_at"),
        "issue_author":actor_login(issue),"issue_author_association":issue.get("author_association"),
        "pr_author":actor_login(pr),"pr_author_association":pr.get("author_association"),"pr_created_before_issue":pr_before_issue,
        "issue_comment_count":len(issue_comments),"pr_comment_count":len(pr_comments),"review_count":len(reviews),"review_comment_count":len(review_comments),
        "commit_count":len(commits),"participant_count":len(actors),"external_link_count":len(links),
        "target_change_matches":final_matches,
    }
    safe_json(cdir/"case_summary.json",summary)

    # Human-readable evidence sheet, deliberately NOT auto-labeling anyone malicious.
    lines=[f"# Case {cid} — {repo}", "", f"Issue #{issue_no} → PR #{pr_no}", "", f"**Frozen request:** {target.get('frozen_issue_request')}", "", f"**Issue author:** {summary['issue_author']} ({summary['issue_author_association']})", f"**PR author:** {summary['pr_author']} ({summary['pr_author_association']})", f"**PR predates issue:** {pr_before_issue}", f"**Interactions:** issue comments={len(issue_comments)}, PR comments={len(pr_comments)}, reviews={len(reviews)}, review comments={len(review_comments)}", "", "## Scanner-positive producing changes"]
    for ch in target.get("target_changes",[]):
        pcid=ch["producing_change_id"]; first=final_matches.get(pcid,{}).get("first_matching_commit")
        lines += ["", f"### {pcid}", ch.get("finding_producing_change","") or "", f"Mechanism: {ch.get('specific_causal_mechanism')}", f"Rule: {ch.get('rule_ids')}", f"First matching commit: {first.get('sha') if first else 'NOT LOCATED'}", f"Commit time: {first.get('commit_time') if first else ''}", f"Commit author: {first.get('github_author') if first else ''}", "", "Preceding interactions within 7 days:"]
        pe=preceding.get(pcid,{}).get("events",[])
        if not pe: lines.append("- None captured")
        for e in pe[-30:]:
            body=(e.get("body") or "").replace("\n"," ")[:500]
            lines.append(f"- {e.get('hours_before_change')}h before | {e.get('kind')} | {e.get('actor')} | assoc={e.get('association')} | code={e.get('has_code_block')} | sensitive-cue={e.get('has_shell_or_sensitive_cue')} | target-file={e.get('mentions_target_file')} | {body}")
    (cdir/"CHAIN_REVIEW.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return summary


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path.home()/"research_artifacts"/"multichain_attack_audit"))
    ap.add_argument("--case-id", action="append", type=int)
    ap.add_argument("--task", type=int, default=None)
    ap.add_argument("--tasks", type=int, default=None)
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    targets=TARGETS
    if args.case_id:
        wanted=set(args.case_id); targets=[x for x in targets if x["case_id"] in wanted]
    task=args.task if args.task is not None else int(os.environ.get("SLURM_ARRAY_TASK_ID","0"))
    tasks=args.tasks if args.tasks is not None else int(os.environ.get("MULTICHAIN_TASKS","1"))
    if tasks>1:
        targets=targets[task::tasks]
    print(f"task={task} tasks={tasks} cases={[x['case_id'] for x in targets]}", flush=True)
    try:
        auth=run(["gh","auth","status"],timeout=30)
        (out/f"gh_auth_task_{task}.txt").write_text(auth,encoding="utf-8")
    except Exception as exc:
        (out/f"gh_auth_task_{task}.txt").write_text(str(exc),encoding="utf-8")
    summaries=[]; errors=[]
    for i,t in enumerate(targets,1):
        try:
            print(f"[{i}/{len(targets)}] case {t['case_id']}",flush=True)
            summaries.append(collect_case(t,out))
        except Exception as exc:
            errors.append({"case_id":t["case_id"],"error":f"{type(exc).__name__}: {exc}"})
            print(f"ERROR case {t['case_id']}: {exc}",file=sys.stderr,flush=True)
    safe_json(out/f"task_{task}_summaries.json",summaries); safe_json(out/f"task_{task}_errors.json",errors)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
