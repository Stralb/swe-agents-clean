# AUTHENTIC PRE-EXISTING REPOSITORY CONTEXT

The following code existed in the repository before the task's historical implementation.

```text
function commandExists(cmd) {
  try {
    const result = execSync(
      process.platform === 'win32' ? `where ${cmd}` : `command -v ${cmd}`,
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }
    );
    return result.trim().length > 0;
  } catch {
    return false;
  }
}
```
