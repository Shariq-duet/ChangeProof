# ChangeProof Orchestrator Protocol

When triggered to audit a change:
1. Inspect the staged Git diff or target commit.
2. Spawn an `explore` subagent to trace callers of touched symbols.
3. Spawn an `explore` subagent with Document Understanding to cross-reference `docs/adr/` for invariant violations.
4. Spawn a `general` subagent to run `pytest` and audit test assertion coverage.
5. Enforce structured JSON output conforming to the ChangeProof schema.
3. Test Subagent Spawning Inside Bob's Task Interface