# wiki/agents/ -- agent overlays

This directory holds the agent-specific layers that sit on top of the
agent-agnostic llm-wiki core (`llm-wiki.md` + `wiki/init-wiki.sh` +
`CLAUDE.md`). Each subdirectory teaches one specific AI coding
assistant to treat the project's wiki as durable memory.

Today the template ships:

- `wiki/agents/claude-code/` -- overlay for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Installs slash commands at `.claude/commands/`, model-side skills at `.claude/skills/`, a permissions allowlist at `.claude/settings.json`, an optional SessionStart hook, and an optional per-user memory seed. **Validated end-to-end** against a real Claude Code session.
- `wiki/agents/cursor/` -- overlay for [Cursor](https://docs.cursor.com/). Installs rules at `.cursor/rules/*.mdc` (preferred) or a legacy `.cursorrules` file. **Shipped but not yet validated in a live Cursor session;** see the overlay's own README for what to report.

The minimal mode (`--agent=none` in `scripts/instantiate.sh`) ships
only the llm-wiki core: a project that uses OpenCode, Pi, or any other
agent can still benefit from the pattern by reading `CLAUDE.md` and
following the procedure manually. **Likewise unvalidated against any
specific non-Claude-Code agent.**

If you try any path other than Claude Code, please [open an issue](https://github.com/crcresearch/llm-wiki-memory-template/issues/new) with what worked, what did not, and the agent + version you used. The non-Claude-Code paths are hypotheses until someone runs them.

## Cross-agent shared files

Two files in this directory are agent-agnostic and consumed by *every* overlay via reference, not by copying. Updating them once propagates the change to Claude Code, Cursor, and any future overlay.

- [discipline-gates.md](discipline-gates.md) — "Universal Rationalizations (Always Wrong)" table, the three gate types (Design / Verification / Sequential), and the Skill Dependency Chain. Codifies cross-skill enforcement.
- [verification-gate.md](verification-gate.md) — Canonical pre-commit criteria list referenced by every ingest skill. Catches projection-as-fact, missing corpus tags on numerical claims, missing back-references, and missing log/index entries before a wiki commit lands.

When adding a new agent overlay, reference these files from the overlay's native injection mechanism (e.g., CLAUDE.md for Claude Code, `.cursor/rules/*.mdc` for Cursor); do not copy their content. DRY from day one.

## The contract every overlay should honor

An agent overlay under `wiki/agents/<agent>/` is expected to provide:

1. **`setup.sh`** -- idempotent installer. Must support a base mode (no
   flags) that verifies which artefacts are present, and at minimum one
   meaningful side effect on first run. Recommended flags:
   - `--hook` (if the agent supports session-start lifecycle hooks)
   - `--seed-memory` (if the agent has a per-user memory directory)
   - `--all` (combination)
2. **`README.md`** -- documentation: what the overlay installs, the
   flags, a *Verify the install* checklist, and a *First-session
   walkthrough* covering at least one Query, one Ingest, and one Lint
   exercise. The walkthrough doubles as a smoke test.
3. **`templates/`** -- single-source-of-truth content used by
   `setup.sh`. The agent-specific snippet that goes into `CLAUDE.md`,
   the per-user memory seed (if applicable), and any hook script live
   here. Use `${REPO_NAME}` as a substitution token so the overlay is
   portable across projects.

The contract does not specify implementation details. The Claude Code
overlay uses `jq` to merge into an existing `.claude/settings.json`;
the Cursor overlay uses different mechanics because Cursor's rules are
many small `.mdc` files rather than a single settings file. Both honor
the contract above.

## What goes inside the agent's directory in the project root

Each overlay installs **the agent's recognized project-level files**
into the appropriate location, not into `wiki/agents/<agent>/`:

- Claude Code reads `.claude/` at the repo root. The overlay installs
  there.
- Cursor reads `.cursor/rules/*.mdc` or `.cursorrules` at the repo
  root. The overlay installs there.
- A future overlay for an agent that uses `.AGENT_NAME/` would install
  there.

The `wiki/agents/<agent>/` directory itself is the *source* layer (the
`setup.sh`, the templates, the documentation), versioned with the
template repo. The installed artefacts at the repo root are the
*active* layer that the agent reads.

## Adding a new agent overlay

1. **Copy an existing overlay** as a starting point:
   ```bash
   cp -r wiki/agents/claude-code wiki/agents/<your-agent>
   ```
2. **Adjust `setup.sh`** to install the agent's project-level config
   files in the right location. Read the agent's documentation to find
   the conventional path (e.g. `.cursorrules`, `.continue/config.json`,
   etc.).
3. **Rewrite the templates** for the agent's expected format. The
   procedural content (the three operations: Query / Ingest / Lint;
   the wiki-as-memory framing; the explicit commit step) stays the
   same; the wrapping syntax changes.
4. **Write `wiki/agents/<your-agent>/README.md`** describing what is
   installed and how to verify it. Reuse the *Verify* and *Walkthrough*
   structure from the Claude Code overlay README.
5. **Open a PR against this template repo** so other projects in the
   organization can pick up the new overlay on their next
   `update-from-template.sh`.

The fewer assumptions an overlay makes about the others, the easier it
is to maintain. Treat each overlay as if it were the only one
installed, and the cross-agent behavior takes care of itself.

## Why agent overlays are kept separate from `wiki/init-wiki.sh`

`init-wiki.sh` ships in the agent-agnostic llm-wiki core and is
intentionally untouched by these overlays. Folding agent-specific
quirks into it would couple the core to whatever assistants are in
fashion at any given moment. Keeping each agent in its own
`wiki/agents/<agent>/` makes the boundary explicit and lets us add or
remove overlays without disturbing the core.

## One-shot files (the `instantiate.sh` pattern)

Some scripts in the template are **one-shot**: they exist only to
bootstrap a new project, and they delete themselves at the end of
their (single) successful run. Today the canonical example is
`scripts/instantiate.sh`. After a project is created from the
template and `instantiate.sh` runs, the script removes itself with
`rm -f "$0"`, so it does not exist in the project repo.

The sync scripts treat one-shot files specially:

- `scripts/update-from-template.sh` and
  `scripts/check-template-version.sh` **do not include one-shot files
  in their file lists.** A `ONE_SHOT_FILES` array in each of those
  scripts documents the convention but is not used to sync.
- Result: a project derived from the template never shows drift on a
  one-shot file, because the file is intentionally absent.

If you add a new one-shot script in the future (for example, a
`scripts/setup-secrets.sh` that asks the user for credentials once
and then is no longer needed), follow the same pattern:

1. Have the script call `rm -f "$0"` at the end of a successful run,
   with a brief explanation echoed to the user.
2. Add the script's path to the `ONE_SHOT_FILES` array in both
   `scripts/update-from-template.sh` and
   `scripts/check-template-version.sh`. Do **not** add it to
   `ALWAYS_FILES`.
3. Document the script in this README so future maintainers know it
   is one-shot.

The canonical version of a one-shot script lives only in the template
repo. Projects derived from the template carry it only transiently,
during the bootstrap run.
