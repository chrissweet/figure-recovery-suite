#!/usr/bin/env bash
#
# init-wiki.sh — Bootstrap or update an LLM-maintained wiki for any project.
#
# Usage:
#   ./init-wiki.sh                        # Auto-detects repo name, uses wiki/ directory
#   ./init-wiki.sh --name "My Project"    # Custom project name
#   ./init-wiki.sh --github               # Clone the GitHub wiki repo instead of creating locally
#
# Modes:
#   Create — wiki doesn't exist yet. Creates all files from scratch with
#            namespaced navigation files for Obsidian compatibility.
#   Update — wiki exists. Adds missing sections to SCHEMA and CLAUDE.md
#            without overwriting existing content.
#
# Navigation files are namespaced to avoid collisions when multiple wikis
# share an Obsidian vault:
#   Home_${REPO_NAME}.md, index_${REPO_NAME}.md, log_${REPO_NAME}.md,
#   SCHEMA_${REPO_NAME}.md
#
# Home.md is kept as a redirect for GitHub wiki compatibility.
#
# ─── FOR THE LLM ──────────────────────────────────────────────────────────────
# If a user gave you the path to this script, EXECUTE it — do NOT reimplement
# it manually. It is idempotent: safe to re-run on existing wikis (auto-detects
# create vs. update mode).
#
# Before running, if llm-wiki.md exists at the repo root, read it for context
# on the underlying pattern (compounding wiki vs. RAG; LLM owns the wiki layer;
# Obsidian + LLM workflow). This shapes judgment calls during the first ingest.
#
# After it completes successfully, perform the first ingest:
#   1. Read the project README and any key docs the user points you to.
#   2. Create initial concept/entity pages per wiki/<repo>.wiki/SCHEMA_<repo>.md.
#   3. Add the new pages to index_<repo>.md and append a log_<repo>.md entry.
#
# Flags:
#   --name "Display Name"   custom project name (default: repo name)
#   --github                clone an existing GitHub wiki instead of init'ing locally
#   --agent "name"          coding assistant running this (e.g. claude-code,
#                           cursor); recorded in the create log entry's by: line
# ──────────────────────────────────────────────────────────────────────────────
#

set -euo pipefail

# --- Parse arguments ---
PROJECT_NAME=""
USE_GITHUB=false
WIKI_AGENT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --name) PROJECT_NAME="$2"; shift 2 ;;
        --github) USE_GITHUB=true; shift ;;
        --agent) WIKI_AGENT="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Detect project info ---
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
REPO_NAME=$(basename "$REPO_ROOT")

if [[ -z "$PROJECT_NAME" ]]; then
    PROJECT_NAME="$REPO_NAME"
fi

# --- Attribution: who is performing this operation ---
# The human is read from git config (never invented). The agent is whatever
# the caller passed via --agent. See the Log Entry Attribution section of the
# generated SCHEMA for the convention.
WIKI_USER=$(git config user.name 2>/dev/null || echo "unknown")
if [[ -n "$WIKI_AGENT" ]]; then
    BY_LINE="- by: ${WIKI_USER} via ${WIKI_AGENT}"
else
    BY_LINE="- by: ${WIKI_USER}"
fi

WIKI_DIR="$REPO_ROOT/wiki/${REPO_NAME}.wiki"

# Namespaced file names
HOME_NS="Home_${REPO_NAME}"
INDEX_NS="index_${REPO_NAME}"
LOG_NS="log_${REPO_NAME}"
SCHEMA_NS="SCHEMA_${REPO_NAME}"

# --- Detect mode ---
if [[ -f "$WIKI_DIR/${SCHEMA_NS}.md" ]] || [[ -f "$WIKI_DIR/SCHEMA.md" ]]; then
    MODE="update"
    echo "Existing wiki detected at $WIKI_DIR — running in update mode."
else
    MODE="create"
    echo "No wiki found — creating new wiki at $WIKI_DIR."
fi

# --- Helper: append a section to a file if a marker string is absent ---
append_section_if_missing() {
    local file="$1"
    local marker="$2"
    local content="$3"
    if [[ -f "$file" ]] && grep -qF "$marker" "$file"; then
        return 1  # already present
    fi
    printf '\n%s\n' "$content" >> "$file"
    return 0  # added
}

# --- Create or clone wiki (create mode only) ---
if [[ "$MODE" == "create" ]]; then
    if $USE_GITHUB; then
        REMOTE_URL=$(git remote get-url origin 2>/dev/null || true)
        if [[ -z "$REMOTE_URL" ]]; then
            echo "Error: No git remote 'origin' found. Can't derive GitHub wiki URL."
            exit 1
        fi
        WIKI_URL=$(echo "$REMOTE_URL" | sed 's/\.git$/.wiki.git/')
        echo "Cloning GitHub wiki from $WIKI_URL ..."
        mkdir -p "$REPO_ROOT/wiki"
        git clone "$WIKI_URL" "$WIKI_DIR" 2>/dev/null || {
            echo "Could not clone wiki. You may need to create the wiki on GitHub first"
            echo "(go to the repo → Wiki tab → create a page → save)."
            echo "Falling back to local initialization..."
            USE_GITHUB=false
        }
    fi

    if ! $USE_GITHUB; then
        mkdir -p "$WIKI_DIR"
        if [[ ! -d "$WIKI_DIR/.git" ]]; then
            git -C "$WIKI_DIR" init
            echo "Initialized local wiki repo at $WIKI_DIR"
        fi
    fi
fi

# --- Write Home_${REPO_NAME}.md (create only — never overwrite) ---
if [[ ! -f "$WIKI_DIR/${HOME_NS}.md" ]]; then
cat > "$WIKI_DIR/${HOME_NS}.md" << HOMEEOF
---
type: index
up: "[[WIKI-INDEX]]"
---

# ${PROJECT_NAME}

Welcome to the project wiki. This is an LLM-maintained knowledge base that grows as the project evolves.

## Navigation

- **[Index](${INDEX_NS})** — Full catalog of all wiki pages
- **[Log](${LOG_NS})** — Chronological record of wiki updates

## Categories

<!-- As top-level categories emerge in ${INDEX_NS}.md, mirror their
     headers here with 1-3 representative links per category. This is a
     curated human-facing nav surface, not a comprehensive catalog —
     leave that to the Index. -->

*No categories yet. Add them here as the wiki grows.*

## Getting Started

Ask your LLM to ingest key project documents:

> "Read the README and any key docs, then build out the wiki with concept pages, entity pages, and cross-references."

See [SCHEMA](${SCHEMA_NS}) for wiki conventions and maintenance workflows.
HOMEEOF
fi

# --- Write Home.md redirect (GitHub wiki landing page) ---
if [[ ! -f "$WIKI_DIR/Home.md" ]] || ! grep -qF "redirect" "$WIKI_DIR/Home.md" 2>/dev/null; then
cat > "$WIKI_DIR/Home.md" << REDIRECTEOF
<!-- redirect: this file exists for GitHub wiki compatibility -->
<!-- The real home page is ${HOME_NS}.md -->
See [${PROJECT_NAME}](${HOME_NS})
REDIRECTEOF
fi

# --- Write index_${REPO_NAME}.md (create only — never overwrite) ---
if [[ ! -f "$WIKI_DIR/${INDEX_NS}.md" ]]; then
cat > "$WIKI_DIR/${INDEX_NS}.md" << INDEXEOF
---
type: index
up: "[[${HOME_NS}]]"
---

# Index — ${PROJECT_NAME}

Catalog of all wiki pages, organized by category.

## Overview
- [Home](${HOME_NS}) — Project summary and navigation

<!-- Add pages here as the wiki grows -->
INDEXEOF
fi

# --- Write log_${REPO_NAME}.md (create only — never overwrite) ---
if [[ ! -f "$WIKI_DIR/${LOG_NS}.md" ]]; then
cat > "$WIKI_DIR/${LOG_NS}.md" << LOGEOF
---
type: index
up: "[[${HOME_NS}]]"
---

# Log — ${PROJECT_NAME}

Chronological record of wiki activity.

## [$(date +%Y-%m-%d)] create | Wiki initialized
${BY_LINE}
- Created wiki structure with namespaced navigation files
- Ready for first ingest
LOGEOF
fi

# --- SCHEMA: create or update ---
#
# MAINTENANCE NOTE: the SCHEMA content is intentionally written in two
# places. Create mode (the SCHEMAEOF heredoc just below) writes the whole
# SCHEMA from scratch. Update mode (the `else` branch further down) adds
# only the sections an older wiki is missing, one append_section_if_missing
# call per section. A section that should reach existing wikis therefore
# has TWO copies: one in the heredoc, one in an append call. They must be
# kept byte-identical. This applies to "Frontmatter", "Edges as Interface
# Operations", "Topology vs Content", and "Log Entry Attribution". If you
# edit a section's wording, edit both copies.
if [[ "$MODE" == "create" ]]; then
    cat > "$WIKI_DIR/${SCHEMA_NS}.md" << SCHEMAEOF
---
type: reference
up: "[[${HOME_NS}]]"
---

# Wiki Schema — ${PROJECT_NAME}

> Conventions and workflows for LLM maintenance of this wiki.
> Based on the [llm-wiki pattern](https://github.com/tobi/llm-wiki).

## Purpose

This wiki is a persistent, compounding knowledge base. The LLM writes and maintains all pages. The human curates sources, directs analysis, and asks questions. Knowledge is compiled once and kept current, not re-derived every session.

## Source of Truth

**Raw sources** (immutable — read but never modify):
- Project code and documentation
- Data files and results
- External references

**The wiki** (LLM-owned — create, update, cross-reference, maintain):
- All \`.md\` files in this directory

## Page Format

Every content page should include:

1. **Title** — \`# Page Name\` as H1
2. **Opening line** — One sentence summarizing what this page is about
3. **Body** — Tables, prose, code blocks as appropriate. Concise reference style.
4. **Cross-references** — \`See also:\` line at the bottom with \`[Display Name](Page-Name)\` links

## Frontmatter

Every page gets standard YAML frontmatter:

\`\`\`markdown
---
type: concept | entity | source-summary | synthesis | analysis | decision | index | comparison | untyped
up: "[[Parent-Page]]"
tags: [topic-a, topic-b]
---
\`\`\`

**Required fields**:
- \`type:\` — what kind of page this is (use \`untyped\` if unsure)
- \`up:\` — parent page in the hierarchy (usually a category page or index)

**Optional typed edges** (add when the relationship is clear):
- \`source:\` — literature or raw source this page summarizes
- \`extends:\` — concept or page this builds upon
- \`supports:\` / \`criticizes:\` — claim or page this provides evidence for or against
- \`related:\` — lateral connection (prefer specific edges above when possible)

**Rules**:
- Every page gets frontmatter — no exceptions
- Use \`type: untyped\` rather than skipping frontmatter entirely
- Cross-references in frontmatter use \`[[Page-Name]]\` wikilink format for Obsidian compatibility
- Cross-references in body text use \`[Display](Page-Name)\` format for GitHub wiki compatibility
- The frontmatter feeds the knowledge graph pipeline for SPARQL queries

## Page types

Most page types (\`concept\`, \`entity\`, \`synthesis\`, etc.) have no required structure beyond the page format. Two query-driven types do, because they exist to capture content that would otherwise be dropped on the floor mid-session.

### \`analysis\`

A query-driven assessment or evaluation. Use when the user asks a synthesis question (\`why X\`, \`compare A and B\`, \`should we ...\`) and the answer is fileable.

**Required sections**:
1. **Question** — the synthesis question being answered, verbatim or close to it
2. **Context** — what background drove the question
3. **Analysis** — the body of the assessment
4. **Conclusion** — the bottom line
5. **Open follow-ups** — what is unresolved

**Required frontmatter**: \`derived_from:\` listing the source pages synthesised (one or more wikilinks). Without it, the analysis is unprovenanced.

### \`decision\`

A design choice with rationale. Use when the project picks one option over alternatives and the reasoning should outlast the decision.

**Required sections**:
1. **Question** — the choice being made
2. **Options considered** — each option with pros / cons
3. **Decision** — what was chosen
4. **Rejected alternatives** — what was not chosen, and why
5. **Revisit triggers** — conditions under which the choice should be re-opened

**Required frontmatter**: \`decided_at: YYYY-MM-DD\`. **Optional**: \`superseded_by: [[Page]]\` once a later decision replaces this one.

## Naming Convention

- Use \`Title-Case-Hyphenated.md\` for page files (e.g., \`Neural-Embeddings.md\`)
- Navigation files are namespaced: \`index_${REPO_NAME}.md\`, \`log_${REPO_NAME}.md\`, etc.

## Special Files

### ${INDEX_NS}.md
- Catalog of every page with one-line descriptions
- Organized by category
- **Update on every ingest**

### ${LOG_NS}.md
- Append-only chronological record
- Format: \`## [YYYY-MM-DD] verb | Subject\` (verbs: ingest, query, lint, update, create)
- The first bullet of every entry is the \`- by:\` attribution line (see Log Entry Attribution)
- Then 2-5 bullet points describing the operation
- **Append on every operation**, and commit each entry on its own (see Log Entry Attribution)

### ${HOME_NS}.md
- Human-facing entry point. Project description + a \`## Categories\` section mirroring the top-level categories in \`${INDEX_NS}.md\`, with 1-3 representative links per category. **Not** a comprehensive catalog; that is the Index's job.
- **Update when a new top-level category emerges in the Index, or when a page lands that is significant enough to be one of its category's representative links.** Routine page additions inside an existing category: Index-only, no Home update needed.
- Distinct from \`Home.md\` (the GitHub-wiki redirect below), which is never edited.

### Home.md
- GitHub wiki redirect only — do not edit
- Real home page is [${HOME_NS}](${HOME_NS})

## Cross-Referencing

- Use \`[Display Text](Page-Name)\` format in body text (GitHub wiki style)
- Use \`[[Page-Name]]\` wikilinks in frontmatter edge fields (Obsidian graph)
- Every page should have at least 2 inbound and 2 outbound links
- Link concepts on first mention within a page
- Bidirectional: if A links to B, B should link back to A

## Edges as Interface Operations

A typed edge is not a label that says "these two things are related." It is an **interface contract** that defines an *operation* the agent should perform when it traverses the edge. Each edge type has an expected behavior, an expected target type, and a semantic commitment that shapes how downstream retrieval and reasoning should handle it.

| Edge | Inverse | What it licenses the agent to do |
|---|---|---|
| \`extends:\` | \`extendedBy\` | Inherit semantic context from the parent. Treat the parent's claims as background assumptions for the current page. |
| \`supports:\` | \`supportedBy\` | Evidence aggregation. When traversing this edge, expect to combine claims; consistency across supporting pages is desirable. |
| \`criticizes:\` | \`criticizedBy\` | Contradiction detection. Expect an unresolved tension that should trigger conflict-resolution logic before combining evidence. |
| \`source:\` | (none — external) | Grounding check. The target is an external source; verify that any cited claim traces back to the source. |
| \`up:\` | (none — implicit) | Parent / breadcrumb. Navigate upward in the hierarchy for category context. |
| \`related:\` | (none — symmetric) | Fallback — no specific operation contract. Prefer a more specific edge type where one applies. |

**Inverses are materialised by the KG, not authored.** Inverse predicates exist so that SPARQL queries can traverse a typed edge in either direction. The KG build pipeline (\`scripts/kg/\`) emits the inverse triple automatically from each forward assertion. **Agents do not write \`extendedBy:\`, \`supportedBy:\`, etc. in source documents.** When a back-reference would help a reader navigate, add it at the body level (typically in the target page's See also section), not as a frontmatter inverse. See [Edge-Types](Edge-Types) for the full 16-predicate vocabulary.

Practical implications:

- Different edge types license different retrievals. The KG pipeline (\`scripts/kg/\`) consumes these typed edges to build a SPARQL-queryable graph; the typing is what makes structural queries useful.
- Edge types have domain and range. \`extends:\` points at a concept or theory; \`source:\` points at an external resource. Violating the domain/range breaks the operation.
- Populate edge fields with the most specific type you can justify. Treat \`related:\` as a fallback. Over time, \`related:\` uses should become rarer as the edge vocabulary fits the work.

## Inline body annotations (Variant 1)

The same predicates from \`extends:\` / \`supports:\` / \`criticizes:\` etc. in frontmatter can be applied inline to body links. The form is a content link followed by a parenthesised italicised link to the [Edge-Types](Edge-Types) page anchor:

\`\`\`markdown
This claim extends the framing in [Theory X](Theory-X) ([*extends*](Edge-Types#extends)).
\`\`\`

Two links in the rendered output: the content link is the normal cross-reference (emits a \`mentions\` edge), and the parenthesised italicised predicate link is the carrier (adds the typed edge from the source page to the target). The predicate link is filtered out of \`mentions\` by the KG extractor so the Edge-Types page does not become a spurious hub.

**Frontmatter versus inline.** Two granularities, both processed by the KG.

- **Frontmatter** asserts a page-level relationship: the entire page \`extends:\` X.
- **Inline (Variant 1)** asserts a per-mention relationship: this specific paragraph's reference to X carries the typed edge.

Use frontmatter when the whole page relates to the target that way. Use inline when only one particular reference in one paragraph carries the relationship, or when the same target appears multiple times with different rhetorical positions.

**Agent judgment, not heuristic.** Annotations are added by reading the prose: in this specific context, is there a clear typed-edge predicate that captures the relationship between the source page and the target page? Apply the most specific predicate that fits. Default to no annotation when uncertain. Sparse-accurate beats dense-speculative; a spurious typed-edge claim distorts downstream queries.

**When to annotate**: the predicate is clearly the most-specific fit, the relationship is a per-mention claim, the target is a real wiki page (not an external URL, not a fragment-only reference), and the annotation would be informative to a future reader and queryable by the KG.

**When not to annotate**: multiple predicates plausibly fit and none clearly wins; the relationship is too vague to commit to (default \`mentions\` is fine); the link target is a fragment (\`Page-Name#section\`). Do not pair a fragment-targeted link with an inline annotation; the annotation asserts a page-level relationship and the fragment implies a sub-page target, so the two are incoherent together.

**Where the vocabulary lives.** [Edge-Types](Edge-Types) lists the 16 forward predicates with one-line definitions; each section is the anchor target for the parenthesised carrier (e.g. \`[*partOf*](Edge-Types#partOf)\` resolves to the \`## partOf\` heading on that page).

## Topology vs Content (when to use the KG)

Two distinct retrieval shapes, each suited to a different question:

- **Topology questions** — *what connects to what*. Multi-hop relationships, concept chains, parent/child rollups, hub detection ("which pages cite this finding?"). Use the KG via SPARQL queries against \`scripts/kg/build/graph-full.ttl\` (in-process via rdflib by default; load into Fuseki when a live endpoint is needed).
- **Content questions** — *what does this page actually say*. Definitions, prose claims, specific numbers, source quotations. Use a direct file read or grep.

The right pattern: use the KG to discover *where* to look (which pages connect to the topic), then file tools to read *what* the chosen pages say. Reserve grep for non-wiki code or for content searches that span many files.

## Log Entry Attribution

The wiki is a shared memory across a team. Every log entry records who performed the operation, so provenance is answerable on the page itself and not only through \`git blame\`.

**The \`by:\` field.** The first bullet of every \`${LOG_NS}.md\` entry is an attribution line:

\`\`\`
- by: <human> via <agent>
\`\`\`

- \`<human>\` is the value of \`git config user.name\` in the wiki repo at the time of the operation. Read it; do not invent it. If it does not match the identity that commits the entry, that is a bug to fix, not a value to guess.
- \`<agent>\` is the coding assistant the operation ran under, for example \`claude-code\` or \`cursor\`.

**One commit per log entry.** Never bundle multiple log operations into a single commit. Each append to \`${LOG_NS}.md\` is committed on its own: commit the page and index changes first, then the log entry as its own commit. This keeps \`git blame\` on the log file a faithful per-entry record, one entry mapping to one commit and one author.

**Two records, one source of truth.** The \`by:\` field is the human-readable copy; git history is the verifiable record. They should always agree. If they disagree, trust git and correct the field.

## Operations

### Ingest (new work completed)

When new sources, experiments, or milestones arrive:

1. Read the source material
2. Discuss key takeaways with the user
3. Create new pages or update existing ones (with frontmatter)
4. Update cross-references on all affected pages
5. Update \`${INDEX_NS}.md\`
6. Append to \`${LOG_NS}.md\`

A single ingest typically touches 5-15 pages.

### Query (answering questions)

1. Read \`${INDEX_NS}.md\` to find relevant pages
2. Read those pages and synthesize an answer
3. If the answer is valuable and reusable, offer to file it as a new page

### Lint (health check)

Periodically check for:
- Orphan pages (no inbound links)
- Dead links (links to non-existent pages)
- Stale claims (superseded by newer work)
- Missing pages (concepts mentioned but lacking their own page)
- Missing cross-references
- **Pages missing frontmatter** — add it based on page content (infer type, parent, tags)
- **Pages with \`type: untyped\`** — review and assign a proper type if now obvious

## When to Update

- **Always**: After completing significant work (experiments, milestones, key findings)
- **Always**: When findings contradict or supersede previous ones
- **Often**: When analytical questions produce reusable answers
- **Periodically**: Lint pass every few sessions

## When NOT to Update

- Routine debugging or code fixes (git history is enough)
- Temporary analysis that won't be referenced again
- Speculative plans that haven't been executed

## Git Workflow

After wiki updates:
1. Stage changed files by name
2. Commit with descriptive message
3. Do NOT push unless the user requests it

## Evolution

Update this schema as the project's needs change. It's a living document.
SCHEMAEOF

else
    # Update mode — add missing sections to existing SCHEMA.
    # Each append_section_if_missing call below mirrors a section of the
    # create-mode heredoc above; keep the two copies byte-identical (see
    # the MAINTENANCE NOTE at the "SCHEMA: create or update" marker).
    # Find the schema file (namespaced or bare)
    if [[ -f "$WIKI_DIR/${SCHEMA_NS}.md" ]]; then
        SCHEMA_FILE="$WIKI_DIR/${SCHEMA_NS}.md"
    else
        SCHEMA_FILE="$WIKI_DIR/SCHEMA.md"
    fi

    UPDATED_SECTIONS=()

    # Add Frontmatter section if missing
    if append_section_if_missing "$SCHEMA_FILE" "## Frontmatter" "## Frontmatter

Every page gets standard YAML frontmatter:

\`\`\`markdown
---
type: concept | entity | source-summary | synthesis | analysis | decision | index | comparison | untyped
up: \"[[Parent-Page]]\"
tags: [topic-a, topic-b]
---
\`\`\`

**Required fields**:
- \`type:\` — what kind of page this is (use \`untyped\` if unsure)
- \`up:\` — parent page in the hierarchy (usually a category page or index)

**Optional typed edges** (add when the relationship is clear):
- \`source:\` — literature or raw source this page summarizes
- \`extends:\` — concept or page this builds upon
- \`supports:\` / \`criticizes:\` — claim or page this provides evidence for or against
- \`related:\` — lateral connection (prefer specific edges above when possible)

**Rules**:
- Every page gets frontmatter — no exceptions
- Use \`type: untyped\` rather than skipping frontmatter entirely
- Cross-references in frontmatter use \`[[Page-Name]]\` wikilink format for Obsidian compatibility
- Cross-references in body text use \`[Display](Page-Name)\` format for GitHub wiki compatibility
- The frontmatter feeds the knowledge graph pipeline for SPARQL queries"; then
        UPDATED_SECTIONS+=("Frontmatter")
    fi

    # Add Page types section if missing (analysis + decision page types)
    if append_section_if_missing "$SCHEMA_FILE" "## Page types" '## Page types

Most page types (`concept`, `entity`, `synthesis`, etc.) have no required structure beyond the page format. Two query-driven types do, because they exist to capture content that would otherwise be dropped on the floor mid-session.

### `analysis`

A query-driven assessment or evaluation. Use when the user asks a synthesis question (`why X`, `compare A and B`, `should we ...`) and the answer is fileable.

**Required sections**:
1. **Question** — the synthesis question being answered, verbatim or close to it
2. **Context** — what background drove the question
3. **Analysis** — the body of the assessment
4. **Conclusion** — the bottom line
5. **Open follow-ups** — what is unresolved

**Required frontmatter**: `derived_from:` listing the source pages synthesised (one or more wikilinks). Without it, the analysis is unprovenanced.

### `decision`

A design choice with rationale. Use when the project picks one option over alternatives and the reasoning should outlast the decision.

**Required sections**:
1. **Question** — the choice being made
2. **Options considered** — each option with pros / cons
3. **Decision** — what was chosen
4. **Rejected alternatives** — what was not chosen, and why
5. **Revisit triggers** — conditions under which the choice should be re-opened

**Required frontmatter**: `decided_at: YYYY-MM-DD`. **Optional**: `superseded_by: [[Page]]` once a later decision replaces this one.'; then
        UPDATED_SECTIONS+=("Page types")
    fi

    # Add frontmatter lint rules if missing
    if append_section_if_missing "$SCHEMA_FILE" "Pages missing frontmatter" '### Lint: Frontmatter checks

Also check during lint:
- **Pages missing frontmatter** — add it based on page content (infer type, parent, tags)
- **Pages with `type: untyped`** — review and assign a proper type if now obvious'; then
        UPDATED_SECTIONS+=("Frontmatter lint rules")
    fi

    # Replace old "No YAML frontmatter" instruction if present
    if grep -qF "No YAML frontmatter" "$SCHEMA_FILE"; then
        sed -i '' 's/No YAML frontmatter\. No tags\. Simple markdown that renders on GitHub wikis\./See the Frontmatter section below for frontmatter conventions./' "$SCHEMA_FILE" 2>/dev/null || \
        sed -i 's/No YAML frontmatter\. No tags\. Simple markdown that renders on GitHub wikis\./See the Frontmatter section below for frontmatter conventions./' "$SCHEMA_FILE"
        UPDATED_SECTIONS+=("Replaced 'No YAML frontmatter' directive")
    fi

    # Replace old HTML-comment frontmatter instruction if present
    if grep -qF "HTML comment" "$SCHEMA_FILE"; then
        sed -i '' 's/wrapped in an HTML comment so it renders cleanly on GitHub wikis/standard YAML frontmatter/' "$SCHEMA_FILE" 2>/dev/null || \
        sed -i 's/wrapped in an HTML comment so it renders cleanly on GitHub wikis/standard YAML frontmatter/' "$SCHEMA_FILE"
        UPDATED_SECTIONS+=("Switched from HTML-comment to standard frontmatter")
    fi

    # Add Edges as Interface Operations section if missing
    if append_section_if_missing "$SCHEMA_FILE" "## Edges as Interface Operations" '## Edges as Interface Operations

A typed edge is not a label that says "these two things are related." It is an **interface contract** that defines an *operation* the agent should perform when it traverses the edge. Each edge type has an expected behavior, an expected target type, and a semantic commitment that shapes how downstream retrieval and reasoning should handle it.

| Edge | Inverse | What it licenses the agent to do |
|---|---|---|
| `extends:` | `extendedBy` | Inherit semantic context from the parent. Treat the parent'"'"'s claims as background assumptions for the current page. |
| `supports:` | `supportedBy` | Evidence aggregation. When traversing this edge, expect to combine claims; consistency across supporting pages is desirable. |
| `criticizes:` | `criticizedBy` | Contradiction detection. Expect an unresolved tension that should trigger conflict-resolution logic before combining evidence. |
| `source:` | (none — external) | Grounding check. The target is an external source; verify that any cited claim traces back to the source. |
| `up:` | (none — implicit) | Parent / breadcrumb. Navigate upward in the hierarchy for category context. |
| `related:` | (none — symmetric) | Fallback — no specific operation contract. Prefer a more specific edge type where one applies. |

**Inverses are materialised by the KG, not authored.** Inverse predicates exist so that SPARQL queries can traverse a typed edge in either direction. The KG build pipeline (`scripts/kg/`) emits the inverse triple automatically from each forward assertion. **Agents do not write `extendedBy:`, `supportedBy:`, etc. in source documents.** When a back-reference would help a reader navigate, add it at the body level (typically in the target page'"'"'s See also section), not as a frontmatter inverse. See [Edge-Types](Edge-Types) for the full 16-predicate vocabulary.

Populate edge fields with the most specific type you can justify. Treat `related:` as a fallback. Over time, `related:` uses should become rarer as the edge vocabulary fits the work.'; then
        UPDATED_SECTIONS+=("Edges as Interface Operations")
    fi

    # Add Inline body annotations (Variant 1) section if missing
    if append_section_if_missing "$SCHEMA_FILE" "## Inline body annotations (Variant 1)" "## Inline body annotations (Variant 1)

The same predicates from \`extends:\` / \`supports:\` / \`criticizes:\` etc. in frontmatter can be applied inline to body links. The form is a content link followed by a parenthesised italicised link to the [Edge-Types](Edge-Types) page anchor:

\`\`\`markdown
This claim extends the framing in [Theory X](Theory-X) ([*extends*](Edge-Types#extends)).
\`\`\`

Two links in the rendered output: the content link is the normal cross-reference (emits a \`mentions\` edge), and the parenthesised italicised predicate link is the carrier (adds the typed edge from the source page to the target). The predicate link is filtered out of \`mentions\` by the KG extractor so the Edge-Types page does not become a spurious hub.

**Frontmatter versus inline.** Two granularities, both processed by the KG.

- **Frontmatter** asserts a page-level relationship: the entire page \`extends:\` X.
- **Inline (Variant 1)** asserts a per-mention relationship: this specific paragraph's reference to X carries the typed edge.

Use frontmatter when the whole page relates to the target that way. Use inline when only one particular reference in one paragraph carries the relationship, or when the same target appears multiple times with different rhetorical positions.

**Agent judgment, not heuristic.** Annotations are added by reading the prose: in this specific context, is there a clear typed-edge predicate that captures the relationship between the source page and the target page? Apply the most specific predicate that fits. Default to no annotation when uncertain. Sparse-accurate beats dense-speculative; a spurious typed-edge claim distorts downstream queries.

**When to annotate**: the predicate is clearly the most-specific fit, the relationship is a per-mention claim, the target is a real wiki page (not an external URL, not a fragment-only reference), and the annotation would be informative to a future reader and queryable by the KG.

**When not to annotate**: multiple predicates plausibly fit and none clearly wins; the relationship is too vague to commit to (default \`mentions\` is fine); the link target is a fragment (\`Page-Name#section\`). Do not pair a fragment-targeted link with an inline annotation; the annotation asserts a page-level relationship and the fragment implies a sub-page target, so the two are incoherent together.

**Where the vocabulary lives.** [Edge-Types](Edge-Types) lists the 16 forward predicates with one-line definitions; each section is the anchor target for the parenthesised carrier (e.g. \`[*partOf*](Edge-Types#partOf)\` resolves to the \`## partOf\` heading on that page)."; then
        UPDATED_SECTIONS+=("Inline body annotations (Variant 1)")
    fi

    # Add Topology vs Content section if missing
    if append_section_if_missing "$SCHEMA_FILE" "## Topology vs Content" '## Topology vs Content (when to use the KG)

Two distinct retrieval shapes, each suited to a different question:

- **Topology questions** — *what connects to what*. Multi-hop relationships, concept chains, parent/child rollups, hub detection ("which pages cite this finding?"). Use the KG via SPARQL queries against `scripts/kg/build/graph-full.ttl` (in-process via rdflib by default; load into Fuseki when a live endpoint is needed).
- **Content questions** — *what does this page actually say*. Definitions, prose claims, specific numbers, source quotations. Use a direct file read or grep.

The right pattern: use the KG to discover *where* to look (which pages connect to the topic), then file tools to read *what* the chosen pages say. Reserve grep for non-wiki code or for content searches that span many files.'; then
        UPDATED_SECTIONS+=("Topology vs Content")
    fi

    # Add Log Entry Attribution section if missing
    if append_section_if_missing "$SCHEMA_FILE" "## Log Entry Attribution" "## Log Entry Attribution

The wiki is a shared memory across a team. Every log entry records who performed the operation, so provenance is answerable on the page itself and not only through \`git blame\`.

**The \`by:\` field.** The first bullet of every \`${LOG_NS}.md\` entry is an attribution line:

\`\`\`
- by: <human> via <agent>
\`\`\`

- \`<human>\` is the value of \`git config user.name\` in the wiki repo at the time of the operation. Read it; do not invent it. If it does not match the identity that commits the entry, that is a bug to fix, not a value to guess.
- \`<agent>\` is the coding assistant the operation ran under, for example \`claude-code\` or \`cursor\`.

**One commit per log entry.** Never bundle multiple log operations into a single commit. Each append to \`${LOG_NS}.md\` is committed on its own: commit the page and index changes first, then the log entry as its own commit. This keeps \`git blame\` on the log file a faithful per-entry record, one entry mapping to one commit and one author.

**Two records, one source of truth.** The \`by:\` field is the human-readable copy; git history is the verifiable record. They should always agree. If they disagree, trust git and correct the field."; then
        UPDATED_SECTIONS+=("Log Entry Attribution")
    fi

    # Add Home Special-Files entry if missing. The create-mode heredoc
    # inserts this between the Log and Home.md sub-entries of "## Special
    # Files"; for existing wikis the helper appends at the end of the
    # file (append_section_if_missing is order-agnostic by design). The
    # entry is still discovered by the agent because SCHEMA is read
    # end-to-end. Marker: the literal ### Home_<repo>.md heading line.
    if append_section_if_missing "$SCHEMA_FILE" "### ${HOME_NS}.md" "### ${HOME_NS}.md
- Human-facing entry point. Project description + a \`## Categories\` section mirroring the top-level categories in \`${INDEX_NS}.md\`, with 1-3 representative links per category. **Not** a comprehensive catalog; that is the Index's job.
- **Update when a new top-level category emerges in the Index, or when a page lands that is significant enough to be one of its category's representative links.** Routine page additions inside an existing category: Index-only, no Home update needed.
- Distinct from \`Home.md\` (the GitHub-wiki redirect), which is never edited."; then
        UPDATED_SECTIONS+=("Home Special-Files entry")
    fi

    if [[ ${#UPDATED_SECTIONS[@]} -gt 0 ]]; then
        echo "Updated SCHEMA:"
        for s in "${UPDATED_SECTIONS[@]}"; do
            echo "  + $s"
        done
    else
        echo "SCHEMA already up to date."
    fi
fi

# --- Stamp wiki/*.md.template files into the wiki ---
# Each *.md.template alongside this script gets sed-substituted (same
# placeholders as scripts/instantiate.sh: {{REPO_NAME}}, {{PROJECT_NAME}})
# and written into the wiki sub-repo with the .template suffix stripped.
# Idempotent on update mode: re-stamping overwrites with the same content.
SCRIPT_DIR_INIT="$(cd "$(dirname "$0")" && pwd)"
TEMPLATES_STAMPED=()
shopt -s nullglob
for tpl in "$SCRIPT_DIR_INIT"/*.md.template; do
    out_name="$(basename "${tpl%.template}")"
    out_path="$WIKI_DIR/$out_name"
    sed -e "s|{{REPO_NAME}}|${REPO_NAME}|g" \
        -e "s|{{PROJECT_NAME}}|${PROJECT_NAME:-$REPO_NAME}|g" \
        "$tpl" > "$out_path"
    TEMPLATES_STAMPED+=("$out_name")
done
shopt -u nullglob

if [[ ${#TEMPLATES_STAMPED[@]} -gt 0 ]]; then
    echo "Stamped wiki page templates:"
    for t in "${TEMPLATES_STAMPED[@]}"; do
        echo "  + $t"
    done
fi

# --- WIKI-INDEX: recursive registration ---
# Walk up from the wiki directory, creating/updating WIKI-INDEX files
register_in_wiki_index() {
    local wiki_dir="$1"
    local wiki_name="$2"
    local home_page="$3"
    local description="$4"

    local parent_dir
    parent_dir="$(dirname "$wiki_dir")"
    local parent_name
    parent_name="$(basename "$parent_dir")"

    # Determine the index filename for this level
    # Top-level "wiki/" gets bare WIKI-INDEX.md
    # Sub-collections get WIKI-INDEX_${collection_name}.md
    local index_file
    if [[ "$parent_name" == "wiki" ]]; then
        index_file="$parent_dir/WIKI-INDEX.md"
    else
        index_file="$parent_dir/WIKI-INDEX_${parent_name}.md"
    fi

    # Create the index file if it doesn't exist
    if [[ ! -f "$index_file" ]]; then
        local index_basename
        index_basename="$(basename "$index_file" .md)"
        cat > "$index_file" << WIKIIDXEOF
---
type: index
---

# Wiki Index — ${parent_name}

## Wikis
- [[${home_page}]] — ${description}
WIKIIDXEOF
        echo "Created $index_file"
    else
        # Add entry if not already present
        if ! grep -qF "[[${home_page}]]" "$index_file"; then
            # Find the Wikis section and append, or just append
            if grep -qF "## Wikis" "$index_file"; then
                # Append after the Wikis heading (find line number, insert after)
                local line_num
                line_num=$(grep -n "## Wikis" "$index_file" | tail -1 | cut -d: -f1)
                sed -i '' "${line_num}a\\
- [[${home_page}]] — ${description}" "$index_file" 2>/dev/null || \
                sed -i "${line_num}a\\
- [[${home_page}]] — ${description}" "$index_file"
            else
                printf '\n## Wikis\n- [[%s]] — %s\n' "${home_page}" "${description}" >> "$index_file"
            fi
            echo "Registered ${wiki_name} in $(basename "$index_file")"
        else
            echo "$(basename "$index_file") already has entry for ${wiki_name}"
        fi
    fi

    # Recurse up: register this collection's index in the grandparent
    local grandparent_dir
    grandparent_dir="$(dirname "$parent_dir")"
    local grandparent_name
    grandparent_name="$(basename "$grandparent_dir")"
    local index_basename
    index_basename="$(basename "$index_file" .md)"

    # Stop recursion at repo root or if we've left the wiki/ tree
    if [[ "$grandparent_dir" == "$REPO_ROOT" ]] || [[ "$grandparent_dir" == "/" ]]; then
        return
    fi

    # Check if grandparent has a WIKI-INDEX to register in
    local grandparent_index
    if [[ "$grandparent_name" == "wiki" ]]; then
        grandparent_index="$grandparent_dir/WIKI-INDEX.md"
    else
        grandparent_index="$grandparent_dir/WIKI-INDEX_${grandparent_name}.md"
    fi

    if [[ -f "$grandparent_index" ]] || [[ "$grandparent_name" == "wiki" ]]; then
        # Register this collection in the grandparent
        if [[ ! -f "$grandparent_index" ]]; then
            cat > "$grandparent_index" << GPIDXEOF
---
type: index
---

# Wiki Index

## Collections
- [[${index_basename}]] — ${parent_name} wikis
GPIDXEOF
            echo "Created $grandparent_index"
        elif ! grep -qF "[[${index_basename}]]" "$grandparent_index"; then
            if grep -qF "## Collections" "$grandparent_index"; then
                local gp_line
                gp_line=$(grep -n "## Collections" "$grandparent_index" | tail -1 | cut -d: -f1)
                sed -i '' "${gp_line}a\\
- [[${index_basename}]] — ${parent_name} wikis" "$grandparent_index" 2>/dev/null || \
                sed -i "${gp_line}a\\
- [[${index_basename}]] — ${parent_name} wikis" "$grandparent_index"
            else
                printf '\n## Collections\n- [[%s]] — %s wikis\n' "${index_basename}" "${parent_name}" >> "$grandparent_index"
            fi
            echo "Registered ${parent_name} collection in $(basename "$grandparent_index")"
        fi
    fi
}

# Register this wiki in the WIKI-INDEX hierarchy
register_in_wiki_index "$WIKI_DIR" "$REPO_NAME" "$HOME_NS" "$PROJECT_NAME wiki"

# --- CLAUDE.md: create or update ---
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
CLAUDE_UPDATED=()

WIKI_SECTION="## Wiki

This project maintains a **persistent wiki** at \`wiki/${REPO_NAME}.wiki/\` (separate git repo) following the [llm-wiki pattern](https://github.com/tobi/llm-wiki). The wiki is an LLM-maintained, interlinked knowledge base that compounds over time.

**Read \`wiki/${REPO_NAME}.wiki/${SCHEMA_NS}.md\` before making wiki changes.** It defines page formats, frontmatter conventions, cross-referencing, and the three operations:

- **Ingest**: After completing significant work, update the wiki (create/update pages, cross-references, \`${INDEX_NS}.md\`, \`${LOG_NS}.md\`).
- **Query**: When answering analytical questions, search the wiki first (\`${INDEX_NS}.md\` → relevant pages). File valuable answers as new pages.
- **Lint**: Periodically health-check for orphan pages, stale claims, missing cross-references, and missing frontmatter."

KG_SUBSECTION="### Knowledge Graph

The wiki's frontmatter and body links feed a knowledge graph pipeline (\`scripts/kg/\`) that produces a SPARQL-queryable RDF graph from wiki content. The pipeline runs in Python via rdflib and pyshacl; no separate server is required by default.

- **Rebuild**: \`./scripts/kg/build-graph.sh\` after wiki updates
- **Query (default)**: in-process via rdflib against \`scripts/kg/build/graph-full.ttl\`. Agent tool wrappers run SPARQL queries directly against the loaded graph object.
- **Query (optional)**: load \`graph-full.ttl\` into Apache Jena Fuseki for live multi-client query, agent-write via SPARQL UPDATE, or federation across wikis. rdflib talks to a Fuseki endpoint via \`SPARQLStore\` without changes to tool code.
- Typed edges in frontmatter (\`extends:\`, \`supports:\`, \`criticizes:\`) produce rich graph relationships
- Body cross-references (\`[text](Page-Name)\`) produce \`mentions\` edges
- Pages without frontmatter are included as \`untyped\` nodes — no data is lost"

if [[ -f "$CLAUDE_MD" ]]; then
    if ! grep -qF "## Wiki" "$CLAUDE_MD"; then
        printf '\n---\n\n%s\n' "$WIKI_SECTION" >> "$CLAUDE_MD"
        CLAUDE_UPDATED+=("Wiki section")
    else
        # Wiki section exists — check for missing content within it

        if grep -qF "missing cross-references." "$CLAUDE_MD" && ! grep -qF "missing frontmatter" "$CLAUDE_MD"; then
            sed -i '' 's/missing cross-references\./missing cross-references, and missing frontmatter./' "$CLAUDE_MD" 2>/dev/null || \
            sed -i 's/missing cross-references\./missing cross-references, and missing frontmatter./' "$CLAUDE_MD"
            CLAUDE_UPDATED+=("Updated Lint line to include frontmatter checks")
        fi

        if ! grep -qF "${SCHEMA_NS}.md" "$CLAUDE_MD"; then
            SCHEMA_LINE="**Read \`wiki/${REPO_NAME}.wiki/${SCHEMA_NS}.md\` before making wiki changes.** It defines page formats, frontmatter conventions, cross-referencing, and the three operations (Ingest, Query, Lint)."
            if append_section_if_missing "$CLAUDE_MD" "${SCHEMA_NS}.md" "$SCHEMA_LINE"; then
                CLAUDE_UPDATED+=("Namespaced SCHEMA reference")
            fi
        fi
    fi

    if ! grep -qF "### Knowledge Graph" "$CLAUDE_MD"; then
        printf '\n%s\n' "$KG_SUBSECTION" >> "$CLAUDE_MD"
        CLAUDE_UPDATED+=("Knowledge Graph subsection")
    fi
else
    cat > "$CLAUDE_MD" << CLAUDEEOF
# CLAUDE.md

> Context file for AI assistants working on this project.

$WIKI_SECTION

$KG_SUBSECTION
CLAUDEEOF
    CLAUDE_UPDATED+=("Created CLAUDE.md with Wiki + Knowledge Graph sections")
fi

if [[ ${#CLAUDE_UPDATED[@]} -gt 0 ]]; then
    echo "Updated CLAUDE.md:"
    for s in "${CLAUDE_UPDATED[@]}"; do
        echo "  + $s"
    done
else
    echo "CLAUDE.md already up to date."
fi

# --- Commit changes in wiki repo ---
cd "$WIKI_DIR"
git add -A
if git diff --cached --quiet 2>/dev/null; then
    echo ""
    echo "No wiki changes to commit."
else
    if [[ "$MODE" == "create" ]]; then
        git commit -m "Initialize wiki with llm-wiki pattern (namespaced)" --quiet 2>/dev/null || true
    else
        git commit -m "Update wiki schema: frontmatter + KG support" --quiet 2>/dev/null || true
    fi
fi

# --- Log entry (update mode only) ---
if [[ "$MODE" == "update" ]]; then
    # Find the log file (namespaced or bare)
    if [[ -f "$WIKI_DIR/${LOG_NS}.md" ]]; then
        LOG_FILE="$WIKI_DIR/${LOG_NS}.md"
    elif [[ -f "$WIKI_DIR/log.md" ]]; then
        LOG_FILE="$WIKI_DIR/log.md"
    else
        LOG_FILE=""
    fi

    if [[ -n "$LOG_FILE" ]] && ! grep -qF "frontmatter convention" "$LOG_FILE"; then
        cat >> "$LOG_FILE" << EOF

## [$(date +%Y-%m-%d)] update | Added frontmatter convention
- Schema updated with standard YAML frontmatter format
- Lint rules now check for missing frontmatter
- Knowledge graph pipeline support added
EOF
        cd "$WIKI_DIR"
        git add "$(basename "$LOG_FILE")"
        git commit -m "Log: frontmatter convention update" --quiet 2>/dev/null || true
    fi
fi

# --- Summary ---
echo ""
if [[ "$MODE" == "create" ]]; then
    echo "✓ Wiki initialized at $WIKI_DIR"
    echo ""
    echo "Navigation files:"
    echo "  Home:   ${HOME_NS}.md (redirect: Home.md)"
    echo "  Index:  ${INDEX_NS}.md"
    echo "  Log:    ${LOG_NS}.md"
    echo "  Schema: ${SCHEMA_NS}.md"
    echo ""
    echo "Next steps:"
    echo "  1. Start a conversation with your LLM in this repo"
    echo "  2. Ask it to ingest your key documents into the wiki"
    echo "  3. The wiki will grow from there"
else
    echo "✓ Wiki updated at $WIKI_DIR"
    echo ""
    echo "Next steps:"
    echo "  1. Run a lint pass to add frontmatter to existing pages:"
    echo "     Tell your LLM: \"Lint the wiki — focus on adding frontmatter to pages that are missing it\""
    echo "  2. After frontmatter is in place, build the knowledge graph:"
    echo "     ./scripts/kg/build-graph.sh"
fi
echo ""
echo "If using GitHub wiki, push with:"
echo "  cd $WIKI_DIR && git push origin master"
