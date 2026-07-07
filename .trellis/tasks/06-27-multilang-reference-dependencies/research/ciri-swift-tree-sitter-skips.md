# Ciri Swift Tree-sitter Skips

## Summary

Ciri validation found 30 Swift files skipped by the current tree-sitter Swift
adapter. These are not broken source files. The skip is caused by Codas treating
any `tree.root_node.has_error` as a whole-file parse failure.

Current behavior in `src/codas/adapters/swift_parse.py`:

```python
if tree.root_node.has_error:
    modules.append(ParsedSwiftModule(path=path, tree=None, source=source))
```

Effect: one local tree-sitter `ERROR` node removes all symbols and reference
edges from that file.

Follow-up implementation changed this strategy to partial parsing:

- keep the tree even when `root_node.has_error`;
- collect line/column/snippet parse diagnostics;
- skip `ERROR` subtrees during extraction;
- continue extracting valid top-level declarations and explicit type references.

## Impact

The Swift reference graph remains a reliable lower bound, but it is incomplete.
The missing files include core Ciri files, so users must not interpret absent
edges involving these files as proof of no dependency.

Skipped core examples:

- `Ciri/Agent/AgentEngine.swift`
- `Ciri/App/CiriApp.swift`
- `Ciri/Agent/ToolDispatcher.swift`
- `Ciri/Agent/PermissionCenter.swift`
- `Ciri/Agent/LLM/ClaudeProvider.swift`

Original Ciri output with Python 3.12 + `codas[swift]`:

- Swift symbols: 1366
- import/reference edges: 2464
- first-party `target_path` edges: 1028
- Swift first-party edges: 985
- symbol skipped files: 30
- import skipped files: 30

After partial parsing:

- Swift symbols: 1448
- import/reference edges: 2749
- first-party `target_path` edges: 1221
- Swift first-party edges: 1178
- parse diagnostics: 132
- `Ciri/Agent/AgentEngine.swift` now contributes `AgentRuntimeActor`,
  `AgentContinuationError`, and `AgentContinuationRequest`.
- `Ciri/App/CiriApp.swift` now contributes `CiriApp`.
- `target_path=Ciri/Agent/AgentEngine.swift` now returns real dependency edges
  from `Ciri/App/CiriApp.swift`, `Ciri/App/DashboardView.swift`,
  `Ciri/UI/Chat/ChatView.swift`, tests, and others.

## Root Causes

The skipped files use modern Swift syntax that `tree-sitter-swift 0.7.3` parses
with `ERROR` nodes, while Xcode/Swift accepts the files.

Observed syntax triggers:

- `nonisolated(unsafe)`
  - `Ciri/Agent/ToolDispatcher.swift:58`
  - `Ciri/Agent/LLM/ClaudeProvider.swift:136`
  - several notification/settings files
- shorthand optional binding with `try? await`
  - `Ciri/Agent/AgentEngine.swift:1795`
- `switch try await ...`
  - `Ciri/App/CiriApp.swift:1012`
  - `Ciri/Agent/Wiki/WikiLinkResolver.swift:22`
- multi-pattern `catch`
  - `Ciri/Agent/Memory/MemoryFrontmatterMigrator.swift:34`
- `case ... where ...`
  - `Ciri/UI/Settings/NotificationSettingsView.swift:207`
- multiline bitwise expression parsing issue
  - `CiriTests/VaultExportRoundTripTests.swift:256`

Representative source examples:

```swift
if let threadId,
   let snapshot = try? await storedConversationSnapshot(threadId: threadId) {
```

```swift
nonisolated(unsafe) let arguments: [String: Any] = {
```

```swift
switch try await wikiStore.resolveEntity(name: canonicalKey) {
```

```swift
} catch CocoaError.fileReadNoSuchFile, CocoaError.fileNoSuchFile {
```

## Assessment

Current behavior is too conservative for Swift:

- good for avoiding false facts from corrupted parses;
- bad for large valid Swift files where only one modern syntax form fails;
- especially harmful for core orchestration files because they use newer
  concurrency/isolation syntax.

This is a coverage/diagnostics problem, not a Ciri correctness problem.

## Implemented Fix

1. Stop treating `root_node.has_error` as whole-file failure.
   - Keep `ParsedSwiftModule.tree`.
   - Record parse errors separately.
   - Skip only `ERROR` subtrees during extraction.

2. Add parse diagnostics:
   - `ParsedSwiftModule.parse_errors: tuple[ParseError, ...]`
   - fields: `line`, `column`, `snippet`, `node_type`
   - report skipped/partial files with reason, not just path.

3. Make Swift extraction partial:
   - top-level symbol extraction should still inspect valid top-level declarations;
   - reference extraction should walk valid subtrees and avoid `ERROR` nodes;
   - inventory should distinguish `parsed`, `partial`, `unavailable/read_failed`.

4. Add fixture tests for observed syntax:
   - `nonisolated(unsafe) let`
   - shorthand `if let foo, let bar = try? await ...`
   - `switch try await`
   - multi-pattern `catch A, B`
   - `case .x where condition`
   - multiline bitwise expressions

5. Do not pursue SourceKit/indexstore for the current route. Tree-sitter remains
   the gate-grade lower-bound extractor; CodeGraph remains advisory for impact.

## Report Implication

Codas reports should surface Swift coverage explicitly:

- parsed files count;
- partial files count;
- whole-file skipped/read-failed count;
- top parse-error examples;
- statement that dependency/call results are lower-bound when partial files exist.

This prevents users from mistaking absent edges for architectural absence.
