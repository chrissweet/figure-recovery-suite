# llm-wiki-memory-template

A template repository for the [llm-wiki pattern](https://github.com/tobi/llm-wiki), with optional overlays for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Cursor](https://docs.cursor.com/). The llm-wiki layer is agent-agnostic, so the same template also works in minimal mode for OpenCode, Pi, OpenInterpreter, or any agent you write yourself.

## Status

**Only the Claude Code path has been validated end-to-end.** The slash commands `/wiki-experiment`, `/wiki-source`, `/wiki-lint`, the proactive read/write/commit loop, and the auto-commit step have all been exercised on a project derived from this template. The Claude Code overlay is ready for CRC use.

**Every other path is shipped but unvalidated in a live session.** That includes:

- The **Cursor overlay** (`.cursor/rules/*.mdc`, `wiki/agents/cursor/setup.sh`, `.cursorrules.template`). The `.mdc` rule format, `@`-mention invocation, and `alwaysApply` semantics here are derived from Cursor's published documentation, not from observed behavior in a running Cursor IDE.
- The **minimal mode** (`--agent=none`). The wiki bootstrap and CLAUDE.md generation work mechanically, but the proactive behavior depends on whatever agent you bring (OpenCode, Pi, OpenInterpreter, your own) honoring the CLAUDE.md instructions. No specific non-Claude-Code agent has been verified yet.

**If you are the first to try any of these paths, please [open an issue](https://github.com/crcresearch/llm-wiki-memory-template/issues/new) reporting:**

- Which agent and which version (e.g. *Cursor 0.42*, *OpenCode build XYZ*, *Pi*)
- Whether the agent picks up the configuration files this template installed (slash commands, rules, CLAUDE.md instructions)
- Whether the read/write/commit loop is honored
- Anything that does not match the walkthrough in the respective overlay README

Honest reports of failures are at least as useful as confirmations. The non-Claude-Code paths are hypotheses until someone runs them.

## 1. What this template gives you

- **A persistent, LLM-maintained wiki** as durable project memory (Query / Ingest / Lint operations). The wiki is its own git repository, separate from the project repo.
- **A skeleton `CLAUDE.md`** that any AI coding assistant reading repo-level instructions will find, codifying the read-to-recall / write-to-remember behavior.
- **Optional agent overlays** under `wiki/agents/<agent>/` that add slash commands, rules, settings, and personal memory seeds for a specific assistant. Today the template ships overlays for Claude Code and Cursor. Adding a new one (OpenCode, Pi, your own) follows a documented pattern.
- **Update tooling** so that projects instantiated from this template can pull in template improvements later without overwriting their own content.

## 2. Create a new project from this template

On GitHub, click **"Use this template" → "Create a new repository"**, choose a name (e.g. `data-platform-notes`), then clone the new repo locally. The next step depends on whether you want the wiki published as the project's GitHub Wiki or kept local-only.

### Path A: GitHub Wiki backend (recommended for sharing)

Use this path if the wiki should be browsable at `https://github.com/<owner>/<repo>/wiki` and pushable as a separate git remote. There is **one mandatory one-time UI step** before running `instantiate.sh`:

1. **Activate the GitHub Wiki** for the new repo (one-time):
   - Open `https://github.com/<owner>/<repo>/wiki` in a browser.
   - Click **"Create the first page"**.
   - Title: `Home`. Content: anything (this seed page is overwritten by `init-wiki.sh`). Save.

   *Why this is necessary:* GitHub creates `<repo>.wiki.git` lazily — it does not exist as a clonable/pushable git repo until the first page is created through the UI. Until then, every clone or push returns 404 *Repository not found*. This is GitHub's architecture; no API call, gh command, or git push can substitute for the UI click. **`instantiate.sh` will tell you to do this if you skip it**, but it costs less to do it now.

2. **Run instantiate** (one-time, the script self-deletes at the end):

   ```bash
   ./scripts/instantiate.sh "My Project Name" --agent=claude-code --github-wiki
   ```

   Other agent options: `--agent=cursor`, `--agent=all`, `--agent=none`.

3. **Commit and push** the generated files:

   ```bash
   git add -A && git commit -m "chore: instantiate from llm-wiki-memory-template"
   git push origin main
   git -C wiki/<repo-name>.wiki push -u origin master    # publish wiki seed pages
   ```

### Path B: local-only wiki (no UI step required)

Use this path if you don't intend to publish the wiki, or you want to skip the one-time UI step:

```bash
./scripts/instantiate.sh "My Project Name" --agent=claude-code
# (no --github-wiki flag)
git add -A && git commit -m "chore: instantiate from llm-wiki-memory-template"
git push origin main
```

The wiki lives inside the project at `wiki/<repo-name>.wiki/` as a separate git repo with no remote. You can attach a remote and switch to Path B later (see `wiki/agents/README.md` for the procedure).

### Path C: template-contributor dev self-instance

Use this path **only** if you are developing on the template itself and want Claude Code to function as an llm-wiki instance against the template's own GitHub Wiki — i.e., to dogfood the pattern while working on it. The motivation and the recursive-bootstrap finding it addresses are documented at [Lessons-Learned-From-model_fusion § The recursive bootstrap problem](https://github.com/crcresearch/llm-wiki-memory-template/wiki/Lessons-Learned-From-model_fusion#the-recursive-bootstrap-problem).

Two commands, both run from a fresh clone of this template:

```bash
# 1. Clone the template's own GitHub Wiki manually (one-time).
git clone https://github.com/crcresearch/llm-wiki-memory-template.wiki.git \
  wiki/llm-wiki-memory-template.wiki

# 2. Render CLAUDE.md at the template root and install the SessionStart + PostToolUse hooks.
./scripts/instantiate.sh --dev-self
```

After this, Claude Code opened in the template clone has:
- A `CLAUDE.md` pointing at `wiki/llm-wiki-memory-template.wiki/` as durable memory.
- A `SessionStart` hook injecting the wiki reminder at every session start.
- A `PostToolUse` hook nudging the verification-gate workflow on every wiki write.

**All four artifacts** (`CLAUDE.md`, `wiki/llm-wiki-memory-template.wiki/`, `.claude/settings.json`, `.claude/hooks/`) **are excluded locally** via `.git/info/exclude`, which `--dev-self` writes (and re-writes idempotently on re-runs). The exclusion is deliberately not in the tracked `.gitignore`: leading-slash anchors there would resolve to a derived project's own root after `update-from-template.sh` synced the file, shadowing that project's real `CLAUDE.md`, `.claude/settings.json`, and `.claude/hooks/`. The artifacts are local-only by construction: never committed, never propagated to derived projects (which generate their own equivalents via Paths A or B). `--dev-self` does not call `init-wiki.sh`, does not modify `.claude/commands/` or `.claude/skills/`, and does not self-delete.

#### Updating after a template-side hook change

The hook scripts at `.claude/hooks/*.sh` are *snapshots* taken from `wiki/agents/claude-code/templates/` when `--dev-self` first installed them. `setup.sh` defensively refuses to overwrite a live hook that already exists (correct for derived projects where a user might have hand-customized their hook; not what a dev-self contributor wants). So after a PR lands that modifies a hook template, `git pull` updates the source-of-truth but your live hooks stay stale.

To force-refresh the live hooks against the latest template source:

```bash
git pull origin main
rm -f .claude/hooks/*.sh
./wiki/agents/claude-code/setup.sh --hook --posttooluse-hook
```

The `rm -f` is what makes `setup.sh` re-install rather than skip. `.claude/settings.json` is unaffected — `setup.sh` always re-asserts the hook registrations there idempotently via `jq`.

### What `instantiate.sh` does (either path)

1. Substitutes placeholders in `CLAUDE.md.template` (`{{PROJECT_NAME}}`, `{{REPO_NAME}}`, `{{DESCRIPTION}}`, `{{AGENT_NOTE}}`) and writes `CLAUDE.md`.
2. Runs `wiki/init-wiki.sh` to bootstrap the wiki sub-repository at `wiki/<repo-name>.wiki/`. With `--github-wiki`, this clones the GitHub Wiki; without, it inits a local-only repo.
3. Strips the upstream `init-wiki.sh`'s `### Knowledge Graph` subsection from `CLAUDE.md` when the project does not ship a `scripts/kg/` directory (most projects).
4. Substitutes `{{REPO_NAME}}` in shipped `.claude/commands/`, `.claude/skills/`, `.cursor/rules/`, and `.claude/settings.json.template` files; renames `.claude/settings.json.template` to `.claude/settings.json`.
5. Runs the chosen overlay's `setup.sh` (Claude Code, Cursor, or both). Deletes the unused overlay directories so the project ships only what it uses.
6. **Self-deletes** at the end of a successful run. `instantiate.sh` is a one-shot bootstrap script; after a project is instantiated, the file does not exist in it.

If you pick `--agent=none`, only steps 1–3 (and the self-delete) run. The minimal install leaves `wiki/agents/` populated but inert; you can later add a custom agent overlay following the pattern documented in `wiki/agents/README.md`.

## 3. Pull updates from this template into an existing project

The llm-wiki pattern, the agent overlays, the slash commands and rules, and the instantiate/update scripts evolve in this template. Once you have created a project from the template, run this **periodically** to pull improvements without overwriting your own narrative:

```bash
./scripts/update-from-template.sh --dry-run    # preview what would change
./scripts/update-from-template.sh              # apply changes
```

**What it updates** (generic, shared content):

- `llm-wiki.md`, `wiki/init-wiki.sh`, `.gitignore`
- `wiki/agents/<agent>/setup.sh` and `wiki/agents/<agent>/templates/*` for every overlay present in the project
- `.claude/commands/wiki-*.md`, `.claude/skills/wiki-*.md` (only if `.claude/` exists in the project)
- `.cursor/rules/wiki-*.mdc` (only if `.cursor/` exists in the project)
- `scripts/instantiate.sh`, `scripts/update-from-template.sh`, `scripts/check-template-version.sh`

**What it does NOT touch** (project-specific content):

- `CLAUDE.md` (your project's narrative)
- `.cursorrules` (your project's narrative for Cursor)
- `README.md` (your project's user-facing docs)
- `.claude/settings.json` (your project's permissions)
- `.claude/hooks/` (per-machine hooks installed by `setup.sh --hook`)
- The wiki itself at `wiki/<your-repo>.wiki/` (separate git repo with its own history)
- Anything under your project source tree

After each run, an entry is appended to `.llm-wiki-template-log.md` (e.g. `## [2026-MM-DD] pulled template @<sha> -- N files updated`) so the sync history stays in the repo.

To check drift without making any changes:

```bash
./scripts/check-template-version.sh
```

## 4. Layout

```
llm-wiki-memory-template/
  README.md                      this file
  CLAUDE.md.template             skeleton with {{PLACEHOLDERS}}
  llm-wiki.md                    the underlying pattern (read first)
  .gitignore                     ignores wiki sub-repo, settings.local.json, .venv
  .claude/                       Claude Code overlay artefacts
    commands/                    slash commands -- /wiki-experiment, /wiki-source, /wiki-lint
    skills/                      model-side procedure references
    settings.json.template       permissions allowlist for wiki-flow commands
  .cursor/                       Cursor overlay artefacts
    rules/                       Cursor's .mdc rules format
  .cursorrules.template          legacy Cursor format (single file)
  wiki/
    init-wiki.sh                 agent-agnostic wiki bootstrap
    agents/
      README.md                  how to add a new agent overlay
      claude-code/               Claude Code overlay: setup.sh + templates + docs
      cursor/                    Cursor overlay: setup.sh + templates + docs
  scripts/
    instantiate.sh               first-use bootstrap of a new project
    update-from-template.sh      pull generic + overlay updates from this template
    check-template-version.sh    read-only drift check
    enable-feature.sh            opt in to a feature retroactively
    disable-feature.sh           opt out of a feature, symmetric removal
    lib/install-feature.sh       shared install/uninstall logic (sourced)
  features/                      opt-in feature definitions (see section 7)
  docs/
    adding-a-feature.md          canonical guide for authoring a feature
```

## 5. The three wiki operations (Query / Ingest / Lint)

The wiki has three operations: read it (Query), write to it (Ingest), and health-check it (Lint). All three are codified in:

- `CLAUDE.md` (the in-project AI guidance, generated from the template)
- The agent overlays (`/wiki-experiment`, `/wiki-source`, `/wiki-lint` for Claude Code; equivalent rules for Cursor)
- The wiki's own `SCHEMA_<repo>.md` (the authoritative procedures)

See [llm-wiki.md](llm-wiki.md) for the underlying pattern and [wiki/agents/README.md](wiki/agents/README.md) for the overlay structure.

## 6. Adding a new agent overlay (OpenCode, Pi, your own)

Each agent overlay lives in `wiki/agents/<agent>/` and follows a small contract documented in [wiki/agents/README.md](wiki/agents/README.md). To add support for a new agent:

1. Copy `wiki/agents/claude-code/` to `wiki/agents/<your-agent>/` as a starting point.
2. Adjust `setup.sh` to install the agent's project-level configuration files (its equivalent of `.claude/commands/`).
3. Update `templates/` with the agent-appropriate phrasings (rule format, command format, etc.).
4. Open a PR against this template repo so other projects in the organization can pick it up.

## 7. Opt-in features

Some capabilities are useful in some projects and unwanted in others (a knowledge-graph pipeline, a Socratic tutor behavior overlay, an agent-memory tool). Rather than ship every capability on by default and ask projects to delete what they do not want, the template hosts them under `features/<name>/` as **opt-in features**.

Enable a feature at instantiation:

```bash
./scripts/instantiate.sh "My Project" --agent=claude-code --features=<name>
# multiple at once:
./scripts/instantiate.sh "My Project" --agent=claude-code --features=kg,socratic-tutor
```

Enable or remove later:

```bash
./scripts/enable-feature.sh <name>
./scripts/enable-feature.sh --list       # see what is available and what is on
./scripts/disable-feature.sh <name>      # symmetric removal
```

Each feature is self-contained under `features/<name>/`: a `feature.json` plus optional code, tests, CI workflow, and a CLAUDE.md section. Installing copies these into the derived project; uninstalling removes them. The state lives in `.features-enabled` (plain text, one feature per line) at the project root.

Authoring a new feature is documented in [docs/adding-a-feature.md](docs/adding-a-feature.md). The architecture is RFC #13; Etapa 1 (this infrastructure) shipped in PR #17.

The template ships **no** real features yet. The shape and machinery are validated; the first real feature is the next milestone.

## 8. Contributing back

Improvements to the agent-agnostic parts (the llm-wiki pattern, `init-wiki.sh`, the schema, the scripts) are most valuable when they land here, in the template. Once merged, every project that runs `update-from-template.sh` will pick them up on the next sync.

For project-specific customizations, edit your project's `CLAUDE.md`, README, or settings -- those never propagate.

## 9. Quick reference

```bash
# First use (after "Use this template" -> Create repository -> clone locally):
#   Local-only wiki (no UI step):
./scripts/instantiate.sh "My Project" --agent=claude-code

#   GitHub Wiki backend (UI step required ONCE before this command:
#     open https://github.com/<owner>/<repo>/wiki -> Create the first page -> save)
./scripts/instantiate.sh "My Project" --agent=claude-code --github-wiki

# Enable or remove an opt-in feature (see section 7):
./scripts/enable-feature.sh --list
./scripts/enable-feature.sh <name>
./scripts/disable-feature.sh <name>

# Periodic sync from the template (preview, then apply):
./scripts/update-from-template.sh --dry-run
./scripts/update-from-template.sh

# Read-only drift check (CI-friendly):
./scripts/check-template-version.sh

# After any wiki edit, in the wiki sub-repo:
git -C wiki/<repo-name>.wiki add <files>
git -C wiki/<repo-name>.wiki commit -m "..."

# Publish wiki to GitHub (only when using --github-wiki backend):
git -C wiki/<repo-name>.wiki push origin master
```
