#!/usr/bin/env bash
#
# setup.sh — Cursor overlay on top of an llm-wiki project.
#
# This script is the Cursor-specific layer of the llm-wiki pattern, parallel
# to wiki/agents/claude-code/setup.sh. wiki/init-wiki.sh stays agent-agnostic.
#
# Usage:
#   ./wiki/agents/cursor/setup.sh                 # base: verify rules and CLAUDE.md patch
#   ./wiki/agents/cursor/setup.sh --legacy        # also install legacy .cursorrules
#                                                 # (for Cursor builds that don't read .mdc rules)
#
# What it does:
#   Base mode:
#     1. Verifies the wiki is present (else points to init-wiki.sh).
#     2. Patches CLAUDE.md with the "Wiki maintenance behavior" subsection,
#        if not already present. Same marker as the Claude Code overlay; if
#        both overlays are active, only the first one to run patches.
#     3. Reports presence/absence of .cursor/rules/wiki-*.mdc. These ship
#        with the repository and the script only verifies them.
#
#   --legacy:
#     4. Copies .cursorrules.template -> .cursorrules at the repo root,
#        substituting ${REPO_NAME}. Skipped if .cursorrules already exists.
#
# Cursor has no SessionStart hook equivalent and no per-user memory directory
# managed by the IDE, so the Claude Code overlay's --hook and --seed-memory
# flags have no analog here. The always-applied rule wiki-as-memory.mdc
# carries the same persistent intent.
#
# Does not commit anything. Does not push.
#

set -euo pipefail

WITH_LEGACY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --legacy) WITH_LEGACY=true; shift ;;
        -h|--help)
            sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# --- Detect project layout ---
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
REPO_NAME=$(basename "$REPO_ROOT")
WIKI_DIR="$REPO_ROOT/wiki/${REPO_NAME}.wiki"
SCHEMA_FILE="$WIKI_DIR/SCHEMA_${REPO_NAME}.md"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"

OVERLAY_DIR="$REPO_ROOT/wiki/agents/cursor"
TEMPLATES_DIR="$OVERLAY_DIR/templates"
RULES_DIR="$REPO_ROOT/.cursor/rules"
CURSORRULES_DEST="$REPO_ROOT/.cursorrules"
CURSORRULES_TEMPLATE="$REPO_ROOT/.cursorrules.template"

REPORT=()

# --- Step 1: verify wiki present ---
if [[ ! -f "$SCHEMA_FILE" ]]; then
    echo "ERROR: wiki not found at $WIKI_DIR" >&2
    echo "       (expected $SCHEMA_FILE)" >&2
    echo "" >&2
    echo "Run wiki/init-wiki.sh first, then re-run this script." >&2
    exit 1
fi

# --- Step 2: patch CLAUDE.md (shared with Claude Code overlay) ---
# The same marker "### Wiki maintenance behavior" is used by both overlays.
# If either overlay has already patched, this is a no-op.
SNIPPET_FILE="$REPO_ROOT/wiki/agents/claude-code/templates/claude-md-snippet.md"
MARKER="### Wiki maintenance behavior"

if [[ ! -f "$CLAUDE_MD" ]]; then
    REPORT+=("CLAUDE.md: not found (skipped). Run instantiate.sh to generate it.")
elif grep -qF "$MARKER" "$CLAUDE_MD"; then
    REPORT+=("CLAUDE.md: 'Wiki maintenance behavior' already present (skipped)")
elif [[ ! -f "$SNIPPET_FILE" ]]; then
    REPORT+=("CLAUDE.md: template snippet not found at $SNIPPET_FILE (skipped)")
else
    # Inject snippet before "### Knowledge Graph" if present, else append.
    SNIPPET_BODY=$(grep -v '^<!--' "$SNIPPET_FILE" | grep -v '^-->' | sed "s/\${REPO_NAME}/$REPO_NAME/g")
    if grep -qF "### Knowledge Graph" "$CLAUDE_MD"; then
        TMP=$(mktemp)
        awk -v snippet="$SNIPPET_BODY" '
            /^### Knowledge Graph/ && !done { print snippet; print ""; done = 1 }
            { print }
        ' "$CLAUDE_MD" > "$TMP"
        mv "$TMP" "$CLAUDE_MD"
        REPORT+=("CLAUDE.md: injected 'Wiki maintenance behavior' before '### Knowledge Graph'")
    else
        printf '\n%s\n' "$SNIPPET_BODY" >> "$CLAUDE_MD"
        REPORT+=("CLAUDE.md: appended 'Wiki maintenance behavior' at end")
    fi
fi

# --- Step 3: verify .cursor/rules/wiki-*.mdc present ---
RULES_MISSING=()
for rule in wiki-as-memory wiki-experiment wiki-source wiki-lint; do
    if [[ ! -f "$RULES_DIR/${rule}.mdc" ]]; then
        RULES_MISSING+=("$rule")
    fi
done

if [[ ${#RULES_MISSING[@]} -eq 0 ]]; then
    REPORT+=(".cursor/rules/: all four present (wiki-as-memory, wiki-experiment, wiki-source, wiki-lint)")
else
    REPORT+=(".cursor/rules/: MISSING — ${RULES_MISSING[*]} (these should be committed in the repo)")
fi

# --- Step 4: install legacy .cursorrules (--legacy) ---
if $WITH_LEGACY; then
    if [[ -f "$CURSORRULES_DEST" ]]; then
        REPORT+=(".cursorrules: already present (skipped)")
    elif [[ ! -f "$CURSORRULES_TEMPLATE" ]]; then
        REPORT+=(".cursorrules: template not found at $CURSORRULES_TEMPLATE (skipped)")
    else
        sed "s/{{REPO_NAME}}/$REPO_NAME/g" "$CURSORRULES_TEMPLATE" > "$CURSORRULES_DEST"
        REPORT+=(".cursorrules: created from template (legacy single-file Cursor format)")
    fi
fi

# --- Summary ---
echo ""
echo "================ Cursor overlay setup ================"
echo "Repo:        $REPO_ROOT"
echo "Wiki:        $WIKI_DIR"
echo "Flags:       --legacy=$WITH_LEGACY"
echo "------------------------------------------------------"
for line in "${REPORT[@]}"; do
    echo " - $line"
done
echo "======================================================"
echo ""

CHANGES_MADE=false
for line in "${REPORT[@]}"; do
    case "$line" in
        *injected*|*appended*|*created*) CHANGES_MADE=true; break ;;
    esac
done
if $CHANGES_MADE; then
    echo "Next steps:"
    echo "  Review the changes above, then stage and commit:"
    echo "    git add CLAUDE.md .cursor/ ${WITH_LEGACY:+.cursorrules}"
    echo "    git commit -m \"cursor: apply Cursor overlay (setup.sh)\""
    echo ""
fi
