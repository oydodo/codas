from __future__ import annotations

import unittest

from codas.adapters.references import (
    DefinitionRecord,
    ReferenceCandidate,
    resolve_reference_edges,
)


def _definition(name: str, path: str, qualified_name: str | None = None) -> DefinitionRecord:
    return DefinitionRecord(
        name=name,
        qualified_name=qualified_name or name,
        module=path,
        path=path,
        kind="type",
        line=1,
    )


def _reference(name: str, path: str, qualified_name: str | None = None) -> ReferenceCandidate:
    return ReferenceCandidate(
        name=name,
        qualified_name=qualified_name,
        module=path,
        path=path,
        line=3,
        syntax_kind="type_annotation",
    )


class ReferenceDependencyResolverTests(unittest.TestCase):
    def test_unique_simple_name_emits_import_fact(self) -> None:
        facts = resolve_reference_edges(
            (_definition("AgentRuntime", "Agent.swift"),),
            (_reference("AgentRuntime", "UI.swift"),),
        )

        self.assertEqual(
            [(fact.module, fact.target, fact.target_path, fact.line) for fact in facts.imports],
            [("UI.swift", "AgentRuntime", "Agent.swift", 3)],
        )
        self.assertEqual(facts.skipped, ())

    def test_ambiguous_simple_name_emits_no_edge(self) -> None:
        facts = resolve_reference_edges(
            (
                _definition("Store", "A/Store.swift", "A.Store"),
                _definition("Store", "B/Store.swift", "B.Store"),
            ),
            (_reference("Store", "UI.swift"),),
        )

        self.assertEqual(facts.imports, ())

    def test_qualified_name_resolves_before_simple_fallback(self) -> None:
        facts = resolve_reference_edges(
            (
                _definition("Store", "A/Store.swift", "A.Store"),
                _definition("Store", "B/Store.swift", "B.Store"),
            ),
            (_reference("Store", "UI.swift", "B.Store"),),
        )

        self.assertEqual(
            [(fact.module, fact.target, fact.target_path) for fact in facts.imports],
            [("UI.swift", "B.Store", "B/Store.swift")],
        )

    def test_same_file_reference_is_not_a_file_dependency(self) -> None:
        facts = resolve_reference_edges(
            (_definition("LocalType", "Types.swift"),),
            (_reference("LocalType", "Types.swift"),),
        )

        self.assertEqual(facts.imports, ())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
