# Verification Gate (agent-agnostic)

Canonical pre-commit check for any wiki write. The Verification Gate is a small, project-extensible criteria list that every ingest skill (`/wiki-experiment`, `/wiki-source`, or any future write skill) runs before staging and committing.

The rationale: declarative honesty rules (e.g., the discipline-gates "Universal Rationalizations" table) describe what is wrong but rely on the agent self-applying them. Adding a procedural verification step right before commit converts those rules into a check the agent runs against its own draft. It catches projection-as-fact, cross-corpus drift, missing back-references, and missing log/index entries at write-time rather than at the next lint pass.

---

## When to run

Always, before staging and committing any wiki write. Specifically:

1. After the wiki page(s) have been created or edited and saved to disk.
2. Before any `git add` / `git commit` in the wiki repo.

This is a Sequential Gate per [discipline-gates.md](discipline-gates.md): if any criterion fails, fix it and re-run the gate. Do not commit until all criteria pass.

---

## Procedure

For each page created or edited in the current write:

1. **Re-read the page from disk.** Do not work from the in-context draft — read the actual saved file. This catches edit-window artifacts (e.g., a frontmatter block that didn't save cleanly).
2. **Run the criteria list below**, top to bottom. Each criterion is a yes/no question with a concrete fix when the answer is no.
3. **If any criterion fails:** apply the fix, save the file, re-run the gate from step 1 on the affected page.
4. **When all criteria pass on all pages:** proceed to stage and commit.

---

## Criteria

Apply each criterion to each created or edited page.

### Numerical claims

- **Every numerical claim is backed by a real script output, cached judge result, or external citation.** Estimated or projected values are explicitly marked as such ("estimated", "projected", "untested") and tagged with the basis of the estimate. *Fix if failed:* either remove the claim, replace it with a measured value, or mark it as projection with an explicit "untested" tag.
- **Every numerical claim is tagged with its corpus / dataset / configuration scope.** A bare "73.3%" is ambiguous; "73.3% on the 281-chunk gold-only corpus" is honest. *Fix if failed:* add the corpus / scope tag inline at the first mention and every comparison.
- **No cross-corpus gap arithmetic is presented as a direct gap.** If page A reports X% on corpus 1 and page B reports Y% on corpus 2, the wiki must not state "(X − Y)pp gap" without a same-corpus measurement. *Fix if failed:* either remove the gap claim, mark the comparison as cross-corpus and untested, or run the same-corpus measurement first.

### Cross-references and structure

- **Every new typed-edge reference in frontmatter (`extends:`, `supports:`, `criticizes:`, etc.) is paired with a body-level back-reference on the target page** — typically a See also entry or an explicit prose mention, so a reader navigating from the target can find this page. The frontmatter inverse (`extendedBy`, `supportedBy`, `criticizedBy`, ...) is materialised by the KG build pipeline; **agents do not assert inverse predicates in source documents**. *Fix if failed:* edit the target page's See also section (or relevant body prose) to mention this page; do not add the inverse predicate to the target's frontmatter.
- **Every new body-link `[Display](Page-Name)` resolves to an existing wiki page.** Broken links are not acceptable except for documented external-resource markers. *Fix if failed:* fix the link target or create the missing page.
- **Frontmatter is valid YAML and includes `type:` and `up:` (required) plus any typed edges that apply.** *Fix if failed:* repair frontmatter.
- **For `type: analysis` or `type: decision` pages, the required sections and frontmatter fields named in the SCHEMA "Page types" section are present.** Analysis pages need Question / Context / Analysis / Conclusion / Open follow-ups and a `derived_from:` field; decision pages need Question / Options considered / Decision / Rejected alternatives / Revisit triggers and a `decided_at:` field. *Fix if failed:* add the missing sections or pick a different page type that matches what was actually written.

### Index and log

- **`index_<repo>.md` lists every new page in the right category with a one-line description.** *Fix if failed:* add the entry.
- **`log_<repo>.md` has a `## [YYYY-MM-DD] <verb> | <subject>` entry covering this write, with 2 to 5 bullets of substance.** *Fix if failed:* append the entry.
- **`Home_<repo>.md` reflects category-level changes.** If this ingest introduced a new top-level category in `index_<repo>.md`, OR added a page significant enough to be a representative link for its category, the `## Categories` section on Home is updated. Routine page additions inside an existing category that already has its representative links on Home: Index-only, no Home update needed. *Fix if failed:* add the category header on Home with 1-3 representative links from that category.

### Honest reporting

- **Bad results, contradicted claims, and worsened metrics are filed truthfully.** No polishing, no "needs more investigation" hedges that hide a real negative result. *Fix if failed:* rewrite the relevant paragraph to state the result plainly.
- **No projection or speculation is filed as a measured fact.** *Fix if failed:* mark or remove. See the discipline-gates "Universal Rationalizations" table for related patterns.

---

## Project-specific criteria

Add criteria below as failure modes emerge in real sessions. Each entry should describe the failure, the criterion, and the fix.

*No project-specific criteria yet — add them as they are observed.*

---

## How agent overlays consume this file

Each overlay's per-skill files (Claude Code's `.claude/skills/wiki-*.md`, Cursor's `.cursor/rules/wiki-*.mdc`, etc.) should include a short block before the commit step:

> Before staging and committing, run the Verification Gate procedure at `wiki/agents/verification-gate.md`. Do not commit until all criteria pass.

This keeps the criteria list in one place and easy to evolve. When a new failure mode is observed, the criterion is added here once and picked up by every overlay automatically.

---

See also: [discipline-gates.md](discipline-gates.md) for the Universal Rationalizations and Gate Types this Verification Gate is the canonical instance of.
