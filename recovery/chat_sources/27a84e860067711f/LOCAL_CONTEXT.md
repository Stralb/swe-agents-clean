# BOUNDED PRE-CHANGE IMPLEMENTATION CONTEXT

Target: `plugins/ruflo-core/scripts/ruflo-hook.cjs`

The hook shim is CommonJS and uses Node child processes. Its relevant pre-change structure is:

```js
'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');

function done() {
  process.exit(0);
}

function commandExists(cmd) {
  // Existing repository implementation intentionally omitted
  // from this bounded packet.
}

function buildArgs(subcommand, extraArgs) {
  return ['hooks', subcommand, ...extraArgs];
}

function invokeHook(bin, binArgs, hookArgs, stdinData) {
  const args = [...binArgs, ...hookArgs];
  const useShell = process.platform === 'win32';

  const result = spawnSync(bin, args, {
    shell: useShell,
    input: stdinData || '',
    encoding: 'utf8',
    stdio: ['pipe', 'ignore', 'ignore'],
    timeout: 30_000,
  });

  return result.status === 0;
}

function main() {
  // reads stdin and builds hookArgs

  if (commandExists('ruflo')) {
    invokeHook('ruflo', [], hookArgs, stdinData);
    done();
  }

  if (commandExists('claude-flow')) {
    invokeHook('claude-flow', [], hookArgs, stdinData);
    done();
  }

  if (process.env.RUFLO_HOOK_SKIP_NPX !== '1') {
    invokeHook(
      'npx',
      ['--prefer-offline', '--yes', 'ruflo@latest'],
      hookArgs,
      stdinData
    );
  }

  done();
}
```

Implement the cross-platform hook-launching portion of the issue in this file. Add imports/helpers as needed.
