# AUTHENTIC PRE-EXISTING REPOSITORY CONTEXT

The following code existed in the repository before the task's historical implementation.

```text
export async function saveDefaultKeyPassphrase(keyPath: string, passphrase: string): Promise<void> {
  const aliases = await resolveDefaultKeyPassphraseAliases(keyPath);
  const encrypted = await encryptField(passphrase) ?? passphrase;
  const store = localStorageAdapter.read<Record<string, string>>(STORAGE_KEY_DEFAULT_KEY_PASSPHRASES) ?? {};
  const aliasKeys = matchingPathKeys(aliases);
  for (const storedPath of Object.keys(store)) {
    if (storedPath !== keyPath && aliasKeys.has(defaultKeyPassphrasePathKey(storedPath))) {
      delete store[storedPath];
    }
  }
  store[keyPath] = encrypted;
  localStorageAdapter.write(STORAGE_KEY_DEFAULT_KEY_PASSPHRASES, store);
}
```
