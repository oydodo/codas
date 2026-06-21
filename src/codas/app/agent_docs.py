from __future__ import annotations

from pathlib import Path

from codas.app.agents_block import verify_agents_block, write_agents_block
from codas.integrations.claude import verify_claude_shim, write_claude_shim

# App-layer orchestration for the rendered agent-instruction docs: the NEUTRAL AGENTS.md
# governance block (app/agents_block) + the platform CLAUDE.md shim (integrations/claude).
# The CLI umbrella (`codas-source`) must not import `role-integrations` directly; `codas-app`
# is the permitted bridge, so the CLI `agents` command calls THESE and never touches
# integrations itself (mirrors app/hooks.py for git hooks). Verified via `codas agents --verify`,
# a surface DISTINCT from `codas wiki --verify` (which fans in only Atlas sections + the book).


def write_agent_docs(repo: Path) -> list[Path]:
    """Write the AGENTS.md Codas block + the CLAUDE.md shim; return all written paths sorted."""
    return sorted(write_agents_block(repo) + write_claude_shim(repo))


def verify_agent_docs(repo: Path) -> list[Path]:
    """Paths whose on-disk bytes differ from a fresh render (block stale/hand-edited/missing or
    shim drifted); empty == up to date."""
    return sorted(verify_agents_block(repo) + verify_claude_shim(repo))
