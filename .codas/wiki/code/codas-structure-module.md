The structure module is where Codas turns three authored governance documents — the Structure Map (`.codas/structure.yml`), the Program Plan (`.codas/program.yml`), and the Document Role Manifest (`.codas/documents.yml`) — into typed, frozen, deterministic facts, and then reconciles those *declared* facts against what is *observed* on disk. It is the front half of the Atlas pipeline: authored claims in, a normalized inventory out, which downstream policies consume to detect drift (declared-but-absent units, unowned files, broken dependency rules, stale documents).

Two responsibilities are kept deliberately separate. The loaders (`load_structure_map`, `load_program_plan`, `load_document_manifest`) parse pyyaml-only YAML through the shared `load_yaml_mapping` and validate it hard — required fields, valid `status`/`authority` enums, referential integrity of `allowed_children` and `dependency_rules`, and (for the program) an iterative DFS cycle check in `_assert_acyclic` so a malformed plan fails loudly rather than producing a silent half-fact. Everything they emit is a frozen dataclass (`StructureUnit`, `WorkItem`, `DocumentRole`), so a fact, once built, cannot mutate underneath a policy.

### Observation and the open-world boundary
`index.py` does the reconciling. `build_artifact_index` scans the working tree, assigns every file a single owning unit by longest-prefix (literal beats glob via `_owning_unit`), and records per-unit existence and counts. The scan funnels through `filter_to_roots` — the *one* chokepoint that applies workspace roots and drops reserved Codas-rendered output (the `wiki/` book) so the inventory never chases its own derived bytes. `build_inventory` then projects a shared `ScanContext` into the normalized §5 JSON, never importing adapters directly except the trellis fact extractor. The observed counts are an open-world lower bound: a unit existing is asserted, but absence of files under it is reported, never used to deny.

```atlas:claims
defines: structure inventory builder -> src/codas/structure/inventory.py::::build_inventory
defines: structure map loader -> src/codas/structure/loader.py::::load_structure_map
defines: artifact ownership index -> src/codas/structure/index.py::::build_artifact_index
```
