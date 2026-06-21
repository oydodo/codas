This subsystem is the single, typed gateway between Codas's *authored* governance surfaces — the YAML files a human writes — and the deterministic core that consumes them. Everything in Codas that reads `.codas/config.yml`, `policies`, `waivers`, the structure map, or the program plan goes through `load_yaml_mapping`, and `load_codas_config` projects the central config into a frozen `CodasConfig` dataclass: declared authoritative/supporting constraint-source globs, the workflow (Trellis) adapter and roots, the dogfooding protocol, plus a `line_index` for evidence anchors. The app commands (`check`, `doctor`, `preflight`, `calibrate`, `impact`) load it once; the policies and the `ScanContext` in `facts/context.py` only ever receive the already-typed object. That keeps parsing in exactly one place and gives every downstream consumer a stable, immutable shape rather than raw dict-spelunking.

### Why the strictness
Because these files are *claims* about how the repo is governed, the loader refuses to lose any of them silently. `_UniqueKeyLoader` subclasses PyYAML's `SafeLoader` and raises on duplicate mapping keys — last-write-wins would quietly drop a duplicated unit, source, or rule and corrupt the claim surface. `load_yaml_mapping` insists the document is a top-level mapping (or empty), and any parse or shape failure becomes a typed `ConfigLoadError` instead of a leaking `YAMLError`. Coercion helpers (`_mapping`, `_string_list`, `_optional_str`) tolerate missing or malformed sections without crashing, so a partial config still yields a usable object.

### Invariants it upholds
PyYAML-only, no schema framework, no network — consistent with Codas's serverless, lightweight moat. `index_yaml_list_lines` is a deliberately regex-free, parser-independent scan that maps each list-item scalar to its 1-based source line, letting findings about source globs point a human back to the exact line. The frozen dataclass and deterministic projection mean two runs over identical bytes produce identical config, preserving the byte-identical guarantee the rest of the core depends on.

```atlas:claims
defines: codas config typed projection -> src/codas/config/loader.py::::load_codas_config
defines: codas config dataclass -> src/codas/config/loader.py::::CodasConfig
defines: yaml mapping safe loader -> src/codas/config/loader.py::::load_yaml_mapping
```
