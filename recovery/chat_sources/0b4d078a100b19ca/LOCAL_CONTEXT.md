# BOUNDED PRE-CHANGE IMPLEMENTATION CONTEXT

Repository area: `src/hud/state.ts`

This module owns HUD state/configuration persistence and preset application.

Relevant pre-change interfaces and structure:

```ts
function getConfigFilePath(): string {
  return join(homedir(), '.claude', '.omc', 'hud-config.json');
}

function ensureGlobalConfigDir(): void {
  const configDir = join(homedir(), '.claude', '.omc');
  if (!existsSync(configDir)) {
    mkdirSync(configDir, { recursive: true });
  }
}

export function readHudConfig(): HudConfig {
  // Reads the current HUD configuration and merges missing fields with defaults.
}

export function writeHudConfig(config: HudConfig): boolean {
  // The implementation body is not included in this bounded packet.
}

export function applyPreset(preset: HudConfig['preset']): HudConfig {
  const config = readHudConfig();
  const presetElements = PRESET_CONFIGS[preset];

  const newConfig: HudConfig = {
    ...config,
    preset,
    elements: {
      ...config.elements,
      ...presetElements,
    },
  };

  writeHudConfig(newConfig);
  return newConfig;
}
```

The file already uses Node filesystem/path/home-directory helpers. Add or adjust imports/helpers as required by the task.
