# Miner consolidation phase 2B — Side-effect-free configuration preview

**Recovery and engineering only.** This is a NEW partial inspection adapter, not a modification or replacement of the frozen historical settings loader.

## Historical loader boundary

The original settings source is identical across August 17, August 19 and October 20 (SHA-256 `1d802da61674def4ee92f0ee74b3174739c72287c44d1cb3dfffc98011a56102`). It calls `load_dotenv()` during module import, reads YAML and ambient environment, and creates the database parent directory when `load_settings()` runs. It remains in `historical/`, not active source.

## New preview adapter

`src/runtime/config_preview.py` takes already-decoded config and a supplied environment mapping. It summarizes:

- Relative/absolute config and database paths, using an explicit absolute project root.
- The priority of the token environment keys without returning credential values.
- Limits for repositories, PRs, cases, cases per repo and seconds.
- GitHub language and languages override order.
- Selected scanner environment booleans, **without launching any scanners**.

It performs no YAML parsing, ambient environment lookup, directory creation, network activity or database connections. The original loader supports many other settings and expands home-relative paths; home-relative paths are deliberately refused by this preview. This partial preview is **not a drop-in replacement** and has not been wired into the historical collector.

## Tests and next gate

Use `python -m unittest discover -s tests -v`. Synthetic tests cover path precedence, redaction, limit defaults, invalid input, language settings, immutable input data and no directory creation. The historical module is inspected with AST and **never imported**.

Next: isolate an injectable GitHub HTTP transport and cache behind tests. Do not initialize the archived GitHubClient: its constructor creates a cache directory; its rate-limit manager and collector access SQLite. Test only in explicit temporary workspaces before attempting a full miner reproduction.

