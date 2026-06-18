---
description: Ingest a new source document (paper, article, design doc) into the wiki.
---

You are ingesting a new external source document (paper, article, design doc, README, external reference) into the wiki. This is the llm-wiki-style Ingest. It is NOT for filing experiment results — for experiment results, use `/wiki-experiment` instead.

Full procedure: see `.claude/skills/wiki-source.md` and `wiki/{{REPO_NAME}}.wiki/SCHEMA_{{REPO_NAME}}.md`. Summary:

1. Read the source. If long, ask the user which sections matter most for this project.
2. Discuss key takeaways with the user briefly before writing pages. Confirm framing and cross-link targets.
3. Create a source-summary page named after the source (e.g., `Karpathy-Memex-Gist.md`). Frontmatter: `type: source-summary`, `up:` to the closest existing parent page, `source:` set to URL or filesystem path. Add `supports:` / `criticizes:` / `extends:` typed edges where the relationship is clear.
4. Page body: one-sentence opening line, then sections for contribution, methods or arguments relevant here, where it intersects with this project, quotes worth keeping, link to the source.
5. Update related entity and concept pages so the new source reinforces or revises what they say. If contradiction, update or flag the affected page.
6. Fix cross-references in both directions on every affected page.
7. Update `index_{{REPO_NAME}}.md` under "Source summaries".
8. Append a `## [YYYY-MM-DD] ingest | Source title` entry to `log_{{REPO_NAME}}.md`. The first bullet is the attribution line `- by: <name> via claude-code`, where `<name>` is the output of `git config user.name` in the wiki repo (read it, do not invent it). Then 2 to 5 bullets describing the ingest. See "Log Entry Attribution" in `SCHEMA_{{REPO_NAME}}.md`.
9. Optionally rebuild the knowledge graph: `./scripts/kg/build-graph.sh`.
10. **Run the Verification Gate** at `wiki/agents/verification-gate.md` over every page created or edited. Do not commit until all criteria pass. It catches projection-as-fact, missing corpus tags, missing back-references, and missing log/index entries.
11. **Finish the cycle.** Commit in the wiki's own git repo in two steps, without asking. One commit per log entry keeps `git blame` on the log a faithful per-entry record (see "Log Entry Attribution" in SCHEMA):
    ```
    git -C wiki/{{REPO_NAME}}.wiki add <page-and-index-files-by-name>
    git -C wiki/{{REPO_NAME}}.wiki commit -m "<descriptive message>"
    git -C wiki/{{REPO_NAME}}.wiki add log_{{REPO_NAME}}.md
    git -C wiki/{{REPO_NAME}}.wiki commit -m "log: <descriptive message>"
    ```
    Local commits are reversible. Push only if the user requests. **When pushing, follow the procedure at `wiki/agents/wiki-write-protocol.md`** rather than plain `git push`.

After filing, report which pages were created or updated, and which existing pages now link to the new source.
