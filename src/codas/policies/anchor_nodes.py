from __future__ import annotations


def anchor_symbol_node(node: str) -> tuple[str, str] | None:
    parts = node.split("::")
    if len(parts) != 3 or parts[1] != "" or not parts[0] or not parts[2]:
        return None
    return parts[0], parts[2]


def anchor_call_key(subject: str, obj: str) -> tuple[str, str, str, str, str, str] | None:
    left = subject.split("::")
    right = obj.split("::")
    if len(left) != 3 or len(right) != 3:
        return None
    return (left[0], left[1], left[2], right[0], right[1], right[2])
