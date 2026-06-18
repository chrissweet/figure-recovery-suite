# Claude Code overlay for llm-wiki

This directory contains the Claude Code-specific layer that sits on top of
the agent-agnostic `llm-wiki` pattern (rooted in `llm-wiki.md` at the repo
root and `wiki/init-wiki.sh`). The overlay teaches a fresh Claude Code
instance to treat the project's wiki as its durable memory, complete with
the read-write-commit loop.

Other agents (Codex, Cursor, etc.) would live in parallel directories
under `wiki/agents/`.

## What's here

| File | Purpose |
|---|---|
| `setup.sh` | Idempotent installer: patches `CLAUDE.md`, registers the SessionStart hook, seeds personal memory. |
| `templates/claude-md-snippet.md` | The "Wiki maintenance behavior" subsection injected into `CLAUDE.md`. |
| `templates/memory-seed.md` | The personal-memory file written to `~/.claude/projects/<encoded>/memory/wiki-as-project-memory.md`. |
| `templates/session-start-hook.sh` | Optional hook printed at every SessionStart, reinforcing the read-write-commit pattern. |

## New-user bootstrap

For a fresh clone of this project, four commands:

```bash
git clone <main-repo>
cd {{REPO_NAME}}
./wiki/init-wiki.sh --github                     # 1. clone the wiki sub-repo
./wiki/agents/claude-code/setup.sh --all         # 2. install overlay
```

After this, opening Claude Code in the project root will:

1. Read `CLAUDE.md` (which now contains the "Wiki maintenance behavior" subsection).
2. Read the personal memory at `~/.claude/projects/<encoded>/memory/wiki-as-project-memory.md`.
3. Print a SessionStart reminder about the wiki and the commit step.

## Verify the install

After `setup.sh --all`, confirm each artifact is in place:

```bash
ls .claude/commands/    # wiki-experiment.md, wiki-lint.md, wiki-source.md
ls .claude/skills/      # same three filenames
ls .claude/hooks/       # session-start.sh (if --hook ran)

# CLAUDE.md gained the Wiki maintenance behavior subsection?
grep -n "Wiki maintenance behavior" CLAUDE.md

# Personal memory seeded?
ENCODED=$(pwd | tr '/._' '---')
ls "$HOME/.claude/projects/${ENCODED}/memory/"   # MEMORY.md  wiki-as-project-memory.md

# settings.json carries the wiki-flow permissions?
cat .claude/settings.json
```

If anything is missing, re-run `setup.sh` with the appropriate flag. The script is idempotent and only fills the gaps.

## First-session walkthrough

Open Claude Code from the project root:

```bash
claude
```

On the first turn you should see, in context: the project's `CLAUDE.md` (now carrying the "Wiki maintenance behavior" subsection), the personal memory file (if `--seed-memory` ran), and a one-line `<system-reminder>` from the SessionStart hook (if `--hook` ran).

The five exercises below double as smoke tests and as a tour of the four entry points to the wiki.

### 0. UI sanity — slash commands autocomplete

```text
> /wiki
```

**Expected:** the autocomplete menu shows `/wiki-experiment`, `/wiki-source`, `/wiki-lint`. If none appear, the slash commands were not picked up. Pull the latest changes and restart Claude Code (commands are discovered at session start, not on file change).

### 1. Read path — Query

```text
> Summarize what we know about Energy-Based Drift so far.
```

**Expected:** Claude opens `index_{{REPO_NAME}}.md`, drills into 2 to 4 relevant pages (likely `Energy-Based-Drift`, `BM25-Energy-Drift`, `Drift-Variants-MuSiQue`, `Trajectory-Length-Argument`), and synthesizes an answer that cites page names. This exercises the "read to recall" half of the wiki-as-memory rule. No writes, no commits.

### 2. Write path — Ingest with auto-commit

```text
> I just got a new result: BM25-Energy-Drift at T=0.3 gave 58% all-gold@50 on MuSiQue TEST. Record it in the wiki.
```

**Expected behavior depends on whether the number is backed by a real script output.** This is intentional, and watching which branch fires tells you whether the honest-reporting rule is operational:

- **No supporting artifact found** (no recent JSON in `experiments/musique/results/` or `cache/`, metric vocabulary doesn't match prior work, etc.) → Claude **should refuse to file the number** and ask for the script output path, the command to reproduce, or explicit confirmation. This is the global "never report accuracy from projections, only from real script outputs" rule operating correctly.
- **Artifact provided** (you point Claude at the script output) → Claude reads existing pages first, updates the relevant page, the index, and the log, then runs `git -C wiki/<repo>.wiki add <files>` and `git -C wiki/<repo>.wiki commit -m "..."` automatically. The local commit happens without an approval prompt because it is trivially reversible. Push only on explicit request.

This exercise covers the "write to remember" half of the rule, the commit step that closes the cycle, and the honest-reporting brake.

### 3. Slash command — `/wiki-experiment`

```text
> /wiki-experiment
```

**Expected:** the slash command injects a procedure-bound prompt. Claude asks which experiment, the configuration, headline metrics, what changed, what was surprising. Then it reads existing pages to integrate without duplicating, writes a synthesis page with proper frontmatter (`type: synthesis` or `entity`, `up:`, typed edges), updates the index and the log, and commits in the wiki repo. Use this when you have a real run to file and want the procedure to start without re-typing the framing.

### 4. Slash command — `/wiki-lint`

```text
> /wiki-lint
```

**Expected:** Claude lists `index_…md`, scans all wiki pages, and reports findings grouped by check type (orphans, dead links, stale claims, missing frontmatter, untyped pages, missing concept pages, missing cross-references, index gaps, naming, special-file integrity). It then asks which findings to fix in this pass. Lint is incremental by design — not every issue needs to be addressed at once. Run this every few sessions or after a large ingest.

## What you've learned

After the walkthrough you have three slash commands and one default behavior:

| Trigger | When to use |
|---|---|
| `/wiki-experiment` | A run finished. File metrics, config, and the diff against prior runs. |
| `/wiki-source` | A new external document (paper, design doc, article) entered the project and you want it integrated. |
| `/wiki-lint` | Periodic health check. Run every few sessions or after a large ingest. |
| *(default)* | Claude proactively reads the wiki to answer questions and writes to it when significant work happens, **without** a slash command. The slash commands are a safety net for the cases where you want to force the action explicitly. |

## What `setup.sh --all` does

The script is idempotent. It reports each item as applied or skipped, and
exits without committing anything.

1. **Verifies the wiki is present** at `wiki/<repo>.wiki/SCHEMA_<repo>.md`. Errors out with instructions if missing.
2. **Patches `CLAUDE.md`** with the "Wiki maintenance behavior" subsection, if the marker is not already present. Injected immediately before "### Knowledge Graph" when that subsection exists.
3. **Verifies the three slash commands** are present in `.claude/commands/` (`wiki-experiment.md`, `wiki-source.md`, `wiki-lint.md` — invoked as `/wiki-experiment`, `/wiki-source`, `/wiki-lint` in the Claude Code UI) **and the three model-side skills** at `.claude/skills/`. Both ship with the repository.
4. **Installs the SessionStart hook** at `.claude/hooks/session-start.sh`, then registers it in `.claude/settings.json` (creating the file if missing, or merging via `jq` if it exists with other content).
5. **Seeds personal memory** at `~/.claude/projects/<encoded-path>/memory/wiki-as-project-memory.md`. Also creates or appends to `MEMORY.md` in the same directory. Does not overwrite an existing file with different content.

## Flags

| Flag | What it does |
|---|---|
| (none) | Base mode: wiki verification + `CLAUDE.md` patch + commands and skills check |
| `--hook` | Adds SessionStart hook installation and `settings.json` registration |
| `--seed-memory` | Adds personal memory seeding |
| `--all` | Both `--hook` and `--seed-memory` |
| `-h`, `--help` | Prints the script's header comment |

## Encoded path for personal memory

Claude Code derives the per-project memory directory from the repository's
absolute path by replacing `/`, `.`, and `_` with `-`. Examples:

| Repo path | Memory directory |
|---|---|
| `/Users/alice/{{REPO_NAME}}` | `~/.claude/projects/-Users-alice-markov-embeddings-and-rag/memory/` |
| `/mnt/slow_data/.../{{REPO_NAME}}` | `~/.claude/projects/-mnt-slow-data-...-markov-embeddings-and-rag/memory/` |

`setup.sh --seed-memory` computes this path automatically.

## Updating an existing setup

`setup.sh` is conservative: it skips files that already exist rather than
overwriting them. After pulling template improvements, you have two
options:

**Option A — reset and re-run** (gets the latest templates everywhere):

```bash
# Reset the patched/seeded files
rm .claude/hooks/session-start.sh
rm ~/.claude/projects/<encoded>/memory/wiki-as-project-memory.md
# Remove the "### Wiki maintenance behavior" subsection from CLAUDE.md by hand

./wiki/agents/claude-code/setup.sh --all
```

**Option B — leave the existing artifacts alone**. The committed
`CLAUDE.md` already reflects the latest wording (since the maintainers
update it together with the template), so existing setups stay coherent.
Personal memory and the hook may lag behind the current template; they
update on the next Option A reset.

## Prerequisites

- The wiki must exist at `wiki/<repo>.wiki/SCHEMA_<repo>.md`. If missing, `setup.sh` errors out and tells you to run `./wiki/init-wiki.sh` first (use `--github` to clone the wiki from a `<main-repo>.wiki.git` remote).
- **GitHub Wiki backend, one-time UI step:** if you plan to back the wiki with the project's GitHub Wiki (passing `--github-wiki` to `scripts/instantiate.sh`, or `--github` to `wiki/init-wiki.sh` directly), GitHub requires the first Wiki page to be created through the UI before `<repo>.wiki.git` becomes a clonable/pushable repository. Open `https://github.com/<owner>/<repo>/wiki`, click *"Create the first page"* (title `Home`, any content), save. One-time per project. See the root `README.md` of the template, section "Path A", for the full bootstrap order.
- Both the slash commands at `.claude/commands/wiki-*.md` and the model-side skills at `.claude/skills/wiki-*.md` ship with this repository on the overlay branch. If either set is missing, the bootstrap is incomplete; pull the latest changes.
- `jq` is required to merge the SessionStart hook into an existing `.claude/settings.json`. Without `jq`, `setup.sh --hook` falls back to a manual-edit instruction.

## Design notes

- `setup.sh` does not commit anything. It tells you which files were modified and leaves the staging decision to you and your team policy.
- `.claude/settings.local.json` is per-user, gitignored, and never touched by `setup.sh`.
- The Claude Code overlay is intentionally kept separate from `wiki/init-wiki.sh`: the latter is agent-agnostic, while this directory is the place to add agent-specific quirks without polluting the shared wiki tooling.
