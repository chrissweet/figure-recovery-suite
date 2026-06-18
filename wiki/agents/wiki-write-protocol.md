# Wiki Write Protocol (agent-agnostic)

Canonical procedure for pushing changes to the wiki sub-repo when multiple agents may be writing concurrently. The reference implementation at `scripts/wiki-write-protocol/protocol.sh` handles the optimistic-push-with-retry mechanics (CI-validated on 9 scenarios); this file is the agent-facing procedure that tells overlays how to invoke it.

## When to run

Whenever about to push the wiki sub-repo to its remote (typically because the user requested a push after a successful ingest or lint). Use this in place of plain `git push` for any wiki sub-repo push.

## Procedure

1. From the project root: `source scripts/wiki-write-protocol/protocol.sh`.
2. Run `wiki_push "$WIKI_DIR" "$USER_HANDLE" llm_resolve` where:
   - `$WIKI_DIR` is the wiki sub-repo path (e.g. `wiki/<repo>.wiki/`)
   - `$USER_HANDLE` is `git config user.name` from the wiki repo
   - `llm_resolve` is the no-op resolver defined below
3. Exit 0: push succeeded; done.
4. Exit 2 (retry cap reached): escalate to the user with the conflict summary from stderr.
5. Any other non-zero exit on a content conflict: a conflicted file remains on disk with conflict markers. **The agent's next turn resolves the conflict in Claude context** (read the file, decide the merged content, write it back, `git add` + `git commit`, re-run `wiki_push`).

## The llm_resolve function

Define before calling `wiki_push`:

```bash
llm_resolve() {
    # Defer to agent turn: leave conflict markers in the file.
    # wiki_push exits non-zero; the agent's next turn handles the
    # actual resolution in Claude context, which has more context
    # than this subshell.
    return 1
}
```

## Index and log files

Conflicts on `index_*` and `log_*` files merge mechanically via `.gitattributes` `merge=union`, set by the protocol's setup. The agent never sees these conflicts — they resolve before `llm_resolve` would be called. This is why the empirical `web_forager` collision (both writers appended a 2026-06-12 log entry) becomes zero-attention under the protocol.

## How agent overlays consume this file

Each overlay's per-skill files (Claude Code's `.claude/skills/wiki-*.md`, Cursor's `.cursor/rules/wiki-*.mdc`, etc.) reference this file in their push step rather than inlining the procedure:

> When pushing the wiki sub-repo, follow the procedure at `wiki/agents/wiki-write-protocol.md`.

Same DRY pattern as `verification-gate.md` and `discipline-gates.md`. When the protocol's API evolves, the per-overlay files do not need to be updated.

---

See also: `scripts/wiki-write-protocol/README.md` for the reference implementation and its scenarios; `wiki/agents/verification-gate.md` for the pre-commit gate (orthogonal to this protocol — the gate applies to the merge commit as well).
