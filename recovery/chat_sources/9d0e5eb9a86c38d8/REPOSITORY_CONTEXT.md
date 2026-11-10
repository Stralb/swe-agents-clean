# AUTHENTIC PRE-EXISTING REPOSITORY CONTEXT

The following code existed in the repository before the task's historical implementation.

```text
export function writeHudConfig(config: HudConfig): boolean {
  try {
    ensureGlobalConfigDir();
    const configFile = getConfigFilePath();
    writeFileSync(configFile, JSON.stringify(config, null, 2));
    return true;
  } catch {
    return false;
  }
}
```
