# Discipline Gates (agent-agnostic)

Cross-skill enforcement patterns for any agent that writes to this project's wiki. The rationalizations and gate definitions here apply equally to Claude Code, Cursor, and any other agent: only the *injection mechanism* (CLAUDE.md, `.cursor/rules`, etc.) differs by overlay. Each overlay should reference this file rather than copy its content.

The rationale: a wiki-as-memory pattern that is purely declarative (lint catches mistakes post-hoc) admits failure modes that an agent rationalizes into the wiki between lint passes. Discipline gates flip that — they enumerate the rationalizations the agent might use to justify a bad write, and the right counter to apply *before* the write commits.

---

## Universal Rationalizations (Always Wrong)

Patterns the agent may use to justify cutting a corner. Each row is a thought the agent might have, and the reason it is dishonest with itself.

| Rationalization | Why it's wrong |
|---|---|
| "I'll add the corpus tag / frontmatter / cross-references later" | Later never comes. Do it now while context is fresh. Unindexed and untagged content drifts faster than it can be cleaned. |
| "The estimate / projection is fine to file" | Honest reporting is non-negotiable: numbers in the wiki must be backed by a real script output, a cached judge result, or an external citation. Projections must be marked as such, not slipped in as fact. |
| "The cross-corpus comparison is close enough to cite directly" | A gap arithmetic between rows on different corpora is not a gap. Tag every number with its corpus and refuse the direct subtraction. |
| "Substring agreement is enough — skip the LLM-judge / verification step" | Substring matching has known false positives and false negatives on entity disambiguation. When the project uses an LLM-judge as the canonical metric, the judge cache is the source of truth. |
| "I have enough context, the log / index need not be read first" | Session-start ritual exists for a reason. Reading the recent log entries and skimming the index is the cheapest way to avoid contradicting yesterday's findings. |
| "Quick note — I'll wire it into the wiki later" | A wiki page without inbound links is invisible to retrieval. Inline back-references from related pages while writing, not after. |
| "Good enough to commit" | Verification before commit is non-negotiable. The Verification Gate (see [verification-gate.md](verification-gate.md)) is a small criteria list — running it costs seconds and catches the failure modes above. |
| "These changes don't need a log entry" | The log is the session-start ritual's input. A change that bypasses the log is invisible to the next agent picking up the project. |

This list is intended to grow as new failure modes are observed. Add an entry whenever a real session produces a wrong write that traces back to a rationalization not yet on the list.

---

## Gate Types

Three reusable patterns for cross-skill enforcement. Each gate is a procedural step that interrupts an otherwise-flowing write to apply a check.

### Design Gate

**What:** plan before executing. Present plan to user, get approval, then execute.

**Where used:** any multi-step write where the layout decision is non-obvious. Ingest of a complex source document, restructuring an existing page family, or splitting a page into two.

**Pattern:** Gather → Assess → Propose plan → Get approval → Execute.

### Verification Gate

**What:** read back created or edited work and check against concrete criteria before committing.

**Where used:** all skills that write to the wiki. See [verification-gate.md](verification-gate.md) for the canonical criteria list.

**Pattern:** Create → Read back → Check criteria → Fix failures → Commit.

### Sequential Gate

**What:** step N must pass before step N+1 can begin. Prevents premature optimization or out-of-order operations.

**Where used:** ingest skills where structural correctness must precede content (e.g., frontmatter must be valid before the body is reviewed for stale claims).

**Pattern:** Run step N → Check pass criteria → If fail, fix and re-run → If pass, proceed to N+1.

---

## Skill Dependency Chain

When skill X runs, the listed downstream skill / procedure MUST also run before the cycle is complete. Not "should," not "consider" — MUST.

| When this runs... | ...this MUST also run | Why |
|---|---|---|
| Wiki experiment ingest (file an experiment result) | Verification Gate over the created/edited pages | Catches projection-as-fact, missing corpus tags, missing back-references before commit |
| Wiki source ingest (summarize an external document) | Verification Gate over the created summary | Same reasons, plus catches source-attribution drift |
| Any wiki write that introduces a new typed edge (`extends:`, `criticizes:`, `supports:`) | Update the reciprocal edge on the target page | Bidirectional cross-references are a hard requirement, not advisory |
| Any wiki write to a numbered claim | Append a `## [YYYY-MM-DD] update` entry to `log_<repo>.md` | The session-start ritual depends on the log; bypassing it is invisible to the next session |

---

## How agent overlays consume this file

Each overlay should reference this file in its native injection mechanism rather than copying its content:

- **Claude Code overlay:** the `## Wiki maintenance behavior` subsection installed into `CLAUDE.md` should reference `wiki/agents/discipline-gates.md` and instruct the agent to consult it before writes. The skill files at `.claude/skills/wiki-*.md` should reference the Verification Gate row of the Skill Dependency Chain table above.
- **Cursor overlay:** the relevant rule under `.cursor/rules/wiki-as-memory.mdc` should reference this file. Per-skill rules (`wiki-experiment.mdc`, `wiki-source.mdc`) should reference the Verification Gate procedure.
- **Other overlays:** install whatever pointer mechanism the agent supports. Minimum bar: the agent should encounter a reference to this file as part of its proactive wiki-maintenance behavior.

DRY from day one: when a new rationalization is added to the table above, every overlay picks it up without per-overlay edits.

---

See also: [verification-gate.md](verification-gate.md) for the canonical pre-commit criteria list referenced by the Skill Dependency Chain.
