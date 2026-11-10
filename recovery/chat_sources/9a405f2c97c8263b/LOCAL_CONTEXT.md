# BOUNDED PRE-CHANGE IMPLEMENTATION CONTEXT

The task is localized to the CSV-import passphrase-persistence path.

Relevant files:
- `application/defaultKeyPassphrases.ts`
- `components/vault/useVaultImportHandlers.ts`

Relevant pre-change interfaces:

```ts
import {
  encryptField,
  decryptField,
} from "../infrastructure/persistence/secureFieldAdapter";

export async function resolveDefaultKeyPassphraseAliases(
  keyPath: string,
): Promise<string[]> {
  // resolves equivalent key-path aliases
}

export async function saveDefaultKeyPassphrase(
  keyPath: string,
  passphrase: string,
): Promise<void> {
  // Existing persistence implementation intentionally omitted
  // from this bounded packet.
}

export async function loadDefaultKeyPassphrase(
  keyPath: string,
): Promise<string | null> {
  // reads/decrypts a previously stored value
}
```

The existing vault import React handler parses the selected import file, obtains an import result, filters/merges hosts, updates custom groups/hosts, and reports import status.

Implement the passphrase-persistence portion of the CSV KeyPath/Passphrase feature using the supplied repository APIs. A complete rewrite of unrelated import formats is not required.
