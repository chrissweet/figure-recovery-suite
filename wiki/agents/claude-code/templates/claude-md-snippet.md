<!--
  Template: Memory boundary + Wiki maintenance behavior subsections for CLAUDE.md.
  Injected by wiki/agents/claude-code/setup.sh into the ## Wiki section,
  immediately before the ### Knowledge Graph subsection.
  Idempotency: setup.sh checks two markers independently:
    "### Memory boundary"          (added in PR #28)
    "### Wiki maintenance behavior" (original marker)
  A derived project missing either marker triggers injection of the
  corresponding subsection; both present → setup.sh skips.
  When extending this snippet with a new subsection, add a matching
  marker check in setup.sh, do not just rely on the existing one.
-->

### Memory boundary

This project uses two persistent memory layers; mis-allocation drops content into ambiguity.

- **Claude-memory holds**: user identity, preferences, workflow style, cross-project guidance. Persists across all sessions for *this user*, regardless of project.
- **Wiki holds**: project-specific knowledge, syntheses, decisions, experiment results. Persists across all sessions for *this project*, regardless of user.

When a fact emerges and the destination is unclear, ask: does it follow the user across projects, or does it stay with the project across users? User-shaped goes to Claude-memory; project-shaped goes to the wiki. If both, file the project-shaped half to the wiki and let the user-shaped half live in Claude-memory.

### Wiki maintenance behavior

The wiki is this project's durable memory. Read it to recall context; write to it to remember. Apply this rule in both directions, proactively, without waiting to be asked.

- **Read** the wiki when context about the research would help an answer: start at `index_${REPO_NAME}.md`, then drill into named pages. Cite page names when synthesizing answers. If a wiki claim conflicts with current code or results, trust what is observed now and flag the stale page rather than repeating it.
- **Write** to the wiki whenever significant work produces something that a future session would benefit from knowing: experiment results (configuration, metrics per hop count where applicable, what changed, what was surprising), decisions with stated reasons, reusable syntheses, contradictions of prior claims. Follow the Ingest procedure in `SCHEMA_${REPO_NAME}.md`.

**Finish the cycle: every wiki edit ends with a commit.** The wiki at `wiki/${REPO_NAME}.wiki/` is a separate git repo with its own remote. Before committing, **run the Verification Gate** at `wiki/agents/verification-gate.md` over every page created or edited — it catches projection-as-fact, missing corpus tags on numerical claims, missing back-references, and missing log/index entries. Then:

```bash
git -C wiki/${REPO_NAME}.wiki add <files-by-name>
git -C wiki/${REPO_NAME}.wiki commit -m "<descriptive message>"
```

Execute these without asking — local commits in the wiki repo are trivially reversible. Push only when explicitly asked. **When pushing, follow the procedure at `wiki/agents/wiki-write-protocol.md`** rather than plain `git push`: it uses the `wiki_push` wrapper to handle multi-writer collisions safely.

Honest reporting: bad results and contradicted claims get filed truthfully, not polished. Per the global rule, never report accuracy from projections, only from real script outputs. See `wiki/agents/discipline-gates.md` for the canonical "Universal Rationalizations (Always Wrong)" table that names the failure modes the Verification Gate catches.

Claude Code users have project-level slash commands available for explicit invocation: `/wiki-experiment`, `/wiki-source`, `/wiki-lint`. See `.claude/commands/`. The project also ships the same procedures as model-side skills at `.claude/skills/` (referenced by the slash commands). The slash commands are a safety net: the proactive behavior described above is the default, the slash commands exist for cases where the user wants to force the action explicitly.
