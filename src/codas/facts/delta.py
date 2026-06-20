from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from codas.adapters.callgraph import CallFact
from codas.adapters.python import ImportFact, SymbolFact
from codas.facts.snapshot import FactSnapshot

# Identity keys diffed between snapshots. Incidental fields (line numbers, and
# fields fully derived from the identity within one snapshot) are dropped so a pure
# line shift or a re-rendered derived value is NOT spurious drift — a coupling must
# fire on a real symbol/import/call appearing or disappearing, not on a def moving
# down three lines. (``Optional`` not ``| None``: these are runtime alias values, and
# PEP 604 unions are evaluated at runtime — unsupported on the 3.9 floor.)
SymbolKey = tuple[str, str, str]                     # (module, name, kind)
ImportKey = tuple[str, str, Optional[str]]           # (module, target, target_path)
CallKey = tuple[str, str, str, str, str, str]        # (caller_path/class/symbol, callee_*)


@dataclass(frozen=True)
class FactDelta:
    """The added/removed code facts between two :class:`FactSnapshot`s.

    ``added`` are identity keys present in the second snapshot but not the first;
    ``removed`` are present in the first but not the second. Each tuple is sorted, so
    the delta is deterministic and total-ordered. Carries identity keys (not whole
    facts): the set-equality couplings v2-B authors match on identity.
    """

    symbols_added: tuple[SymbolKey, ...]
    symbols_removed: tuple[SymbolKey, ...]
    imports_added: tuple[ImportKey, ...]
    imports_removed: tuple[ImportKey, ...]
    calls_added: tuple[CallKey, ...]
    calls_removed: tuple[CallKey, ...]

    def is_empty(self) -> bool:
        return not (
            self.symbols_added
            or self.symbols_removed
            or self.imports_added
            or self.imports_removed
            or self.calls_added
            or self.calls_removed
        )


def diff_snapshots(base: FactSnapshot, head: FactSnapshot) -> FactDelta:
    """Identity-key delta from ``base`` to ``head`` (e.g. base=HEAD, head=working)."""
    s_base = {_symbol_key(f) for f in base.symbols.definitions}
    s_head = {_symbol_key(f) for f in head.symbols.definitions}
    i_base = {_import_key(f) for f in base.imports.imports}
    i_head = {_import_key(f) for f in head.imports.imports}
    c_base = {_call_key(f) for f in base.calls.edges}
    c_head = {_call_key(f) for f in head.calls.edges}
    return FactDelta(
        symbols_added=tuple(sorted(s_head - s_base)),
        symbols_removed=tuple(sorted(s_base - s_head)),
        imports_added=tuple(sorted(i_head - i_base, key=_import_sort)),
        imports_removed=tuple(sorted(i_base - i_head, key=_import_sort)),
        calls_added=tuple(sorted(c_head - c_base)),
        calls_removed=tuple(sorted(c_base - c_head)),
    )


def _symbol_key(fact: SymbolFact) -> SymbolKey:
    return (fact.module, fact.name, fact.kind)


def _import_key(fact: ImportFact) -> ImportKey:
    # target_path stays in the identity: dependency_direction-style couplings read it
    # as semantic evidence, and a first-party<->external resolution flip is real drift.
    return (fact.module, fact.target, fact.target_path)


def _call_key(fact: CallFact) -> CallKey:
    return (
        fact.caller_path,
        fact.caller_class,
        fact.caller_symbol,
        fact.callee_path,
        fact.callee_class,
        fact.callee_symbol,
    )


def _import_sort(key: ImportKey) -> tuple[str, str, str]:
    # target_path may be None; normalize for a total order without dropping the value.
    return (key[0], key[1], key[2] or "")
