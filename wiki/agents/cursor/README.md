# Cursor overlay for llm-wiki

Cursor-specific layer on top of the agent-agnostic llm-wiki core. Parallel to `wiki/agents/claude-code/`, both can be active in the same project.

> **⚠ Status: shipped but not yet validated in a live Cursor session.**
>
> Only the Claude Code overlay (`wiki/agents/claude-code/`) has been exercised end-to-end against a real agent. This overlay's `.cursor/rules/*.mdc` format, `@`-mention invocation, and `alwaysApply` / Agent Requested semantics are derived from Cursor's published documentation, not from observed behavior in a running Cursor IDE.
>
> If you are the first to try the Cursor path, please [open an issue](https://github.com/crcresearch/llm-wiki-memory-template/issues/new) reporting:
>
> - Cursor version (Cursor → About)
> - Whether `@wiki-experiment`, `@wiki-source`, `@wiki-lint` appear in the chat autocomplete
> - Whether the `wiki-as-memory.mdc` rule (alwaysApply) is being injected into the agent's prompt
> - Whether the agent honors the read/write/commit loop
> - Anything that does not match this README's "First-session walkthrough" further down
>
> Honest reports of failures are at least as useful as confirmations. The README content here is a hypothesis; your run is the test.

## What's here

| File | Purpose |
|---|---|
| `setup.sh` | Idempotent installer. Verifies the wiki and rules, patches `CLAUDE.md` (shares the marker with the Claude Code overlay so they don't double-patch). |
| `templates/` | Reserved for future Cursor-specific template content. The `.cursor/rules/*.mdc` files and `.cursorrules.template` ship directly at the project root, not under `templates/`, because Cursor reads them from there. |

The actual Cursor configuration lives at the project root:

| Location | Purpose |
|---|---|
| `.cursor/rules/wiki-as-memory.mdc` | `alwaysApply: true`. Codifies the read/write/commit loop for the wiki. Equivalent to the CLAUDE.md "Wiki maintenance behavior" subsection but in Cursor's rules format. |
| `.cursor/rules/wiki-experiment.mdc` | Agent Requested. Procedure for filing an experiment result. Invoke explicitly with `@wiki-experiment` or let Cursor pull it in when intent matches. |
| `.cursor/rules/wiki-source.mdc` | Agent Requested. Procedure for ingesting a new source document. `@wiki-source`. |
| `.cursor/rules/wiki-lint.mdc` | Agent Requested. Procedure for health-checking the wiki. `@wiki-lint`. |
| `.cursorrules.template` | Legacy single-file fallback for Cursor builds that don't read `.mdc` rules. Activate with `setup.sh --legacy`. |

## Flags

| Flag | What it does |
|---|---|
| (none) | Base mode: wiki verification + `CLAUDE.md` patch + rules check |
| `--legacy` | Installs `.cursorrules` from the template, substituting `{{REPO_NAME}}` |
| `-h`, `--help` | Prints the script's header comment |

## Note on Cursor capabilities

Cursor has no SessionStart hook equivalent and no IDE-managed per-user memory directory, so the Claude Code overlay's `--hook` and `--seed-memory` flags have no analog here. The `wiki-as-memory.mdc` rule has `alwaysApply: true` so it is injected into every Cursor agent prompt for the project; that is the closest equivalent to the Claude Code SessionStart hook.

## Verify the install

```bash
ls .cursor/rules/                   # wiki-as-memory.mdc + wiki-{experiment,source,lint}.mdc
grep -n "Wiki maintenance" CLAUDE.md   # CLAUDE.md subsection present (shared with Claude Code overlay)
test -f .cursorrules && echo "legacy active" || echo "legacy not in use"
```

## First-session walkthrough

Open Cursor in the project root, start a chat session, and try the following.

### 0. Sanity — `@`-mention autocomplete

In the Cursor chat, type `@wiki` and confirm the autocomplete offers `@wiki-experiment`, `@wiki-source`, `@wiki-lint`, `@wiki-as-memory`. If they don't appear, Cursor is not reading `.cursor/rules/`. Check the Cursor version (modern builds support `.mdc`); fall back to `setup.sh --legacy` if needed.

### 1. Read path — Query

Ask Cursor (in chat) a project-knowledge question without mentioning the wiki. Example: *"Summarize what we know about <topic central to the project>."*

**Expected:** the `wiki-as-memory` rule is always applied, so Cursor opens `index_{{REPO_NAME}}.md`, drills into named pages, and cites them. No `@` invocation needed.

### 2. Write path — Ingest with auto-commit

Tell Cursor about a new finding from a script run, with the result path or command. Example: *"My new run produced X = 42 on the Y benchmark. Record it in the wiki. Output is at `experiments/results/run-NNN.json`."*

**Expected:** Cursor pulls in `wiki-experiment` automatically (its description matches the intent), reads existing pages to integrate, writes a synthesis page, updates index and log, and runs `git -C wiki/{{REPO_NAME}}.wiki add ... && git -C ... commit -m "..."` without an approval prompt. If your number is not backed by a real script output, the honest-reporting rule should make Cursor refuse to file it and ask for the evidence.

### 3. Explicit invocation — `@wiki-experiment`

Same scenario, but type `@wiki-experiment` to force the procedure even if the description match is uncertain.

### 4. Lint — `@wiki-lint`

Type `@wiki-lint` and confirm Cursor scans the wiki, reports findings grouped by check type, and asks which to fix. Run this every few sessions or after a large ingest.

## What you've learned

| Trigger | When to use |
|---|---|
| `@wiki-experiment` | A run finished. File metrics, config, and the diff against prior runs. |
| `@wiki-source` | A new external document entered the project and you want it integrated. |
| `@wiki-lint` | Periodic health check. Every few sessions or after a large ingest. |
| *(default)* | The `wiki-as-memory` rule is always applied; Cursor proactively reads and writes without needing an `@` mention. |

## Sharing the CLAUDE.md subsection with the Claude Code overlay

Both overlays write the same "Wiki maintenance behavior" subsection into `CLAUDE.md`, using the same marker for idempotency. Whichever overlay's `setup.sh` runs first patches; the second one sees the marker and skips. The subsection is generic (it doesn't mention Claude Code or Cursor specifically); the agent-specific text lives in the rules / commands / skills of each overlay.

## Updating after pulling template improvements

When `scripts/update-from-template.sh` syncs improvements from the template repo, it refreshes `.cursor/rules/wiki-*.mdc`, `wiki/agents/cursor/setup.sh`, and `wiki/agents/cursor/templates/` (when present). It does not touch `.cursorrules` or your project-specific Cursor rules at `.cursor/rules/*.mdc` that don't start with `wiki-`.
