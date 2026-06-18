---
name: wiki-as-project-memory
description: "The wiki IS my memory for this project. Read it to recall, write to it to remember, proactively. Edit → stage → commit, without asking."
metadata:
  node_type: memory
  type: feedback
---

`wiki/${REPO_NAME}.wiki/` is my memory for this project. Treat it that way.

The rule, in one sentence: **if I will need to remember it later, it goes in the wiki; if I need to recall something, the wiki is where I look.**

## Read to recall

Whenever context about the research would help (a question, a decision, a comparison, deciding whether something is new), read the wiki first. `index_${REPO_NAME}.md` is the entry point. Cite page names when synthesizing answers. If a wiki claim conflicts with current code or results, trust what is observed now and flag the stale page.

## Write to remember

If something happens in our work that a future session would need to know, write it to the wiki. Do this proactively, without waiting to be asked.

- New source document enters the project → summarize it, link to related pages. (Skill: `/wiki-source`.)
- Experiment finishes a run → record configuration, metrics, what changed, what was surprising. Link to the experiment's `results/` directory. (Skill: `/wiki-experiment`.)
- Architecture / parameter / methodology decision is made → record it and the reasons.
- A reusable synthesis emerges from a question → file it.
- A finding contradicts or supersedes a wiki claim → update the affected pages, don't leave the contradiction.
- Periodic health check → orphans, dead links, stale claims, missing frontmatter. (Skill: `/wiki-lint`.)

For every write: frontmatter (`type:`, `up:`, typed edges like `extends:` / `supports:` / `criticizes:` when the relationship is clear), cross-references in both directions, update `index_${REPO_NAME}.md`, append a `## [YYYY-MM-DD] verb | Subject` entry to `log_${REPO_NAME}.md`. Defer to `SCHEMA_${REPO_NAME}.md` for conventions; do not duplicate them into memory.

Honest reporting: bad results, contradicted claims, and worsened metrics get filed truthfully. Per the project's CLAUDE.md and global instructions, never report accuracy from projections, only from real script outputs. The canonical "Universal Rationalizations (Always Wrong)" list — the rationalizations that lead to dishonest writes — lives at `wiki/agents/discipline-gates.md`. Before committing any wiki write, run the Verification Gate procedure at `wiki/agents/verification-gate.md`.

## Finish the cycle: stage and commit

The wiki is its own git repo at `wiki/${REPO_NAME}.wiki/`, separate from the main project repo, with its own remote. **Editing a page is not enough — finish with stage + commit in the wiki's repo.** Use `git -C` so you do not need to change directories:

```bash
git -C wiki/${REPO_NAME}.wiki add <files-by-name>
git -C wiki/${REPO_NAME}.wiki commit -m "<descriptive message>"
```

Run these commands without asking — a commit in the wiki's local repo is trivially reversible (`git -C ... reset --soft HEAD~1`), so the cautious posture that applies to push, PR creation, or shared infrastructure does not apply here. **Push only when explicitly asked.**

## Boundary with my private memory

The wiki is shared, project-scoped, durable across collaborators, for facts about the work itself. My private memory (this directory) is for facts about the user and the working relationship. When in doubt for this project, prefer the wiki.

## How to apply

- Default to reading the wiki when context would help, not only for analytical questions.
- Default to writing to the wiki the moment something happens that a future session would benefit from knowing.
- Don't ask permission for the edit, the `git add`, or the `git commit` — these are routine and reversible. Report what was written and committed.
- Skip the wiki only for pure coding/debugging with no findings, and questions about my own behavior/configuration.
