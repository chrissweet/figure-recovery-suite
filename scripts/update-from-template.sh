#!/usr/bin/env bash
#
# update-from-template.sh — pull updates from the llm-wiki template repo into
# an existing project, without touching project-specific content.
#
# Usage:
#   ./scripts/update-from-template.sh [--dry-run] [--template-url=<url>]
#
# Flags:
#   --dry-run        Print what would change without writing anything.
#   --template-url   Override the template remote URL. Defaults to the
#                    crcresearch/llm-wiki-memory-template repo. Pass this only if
#                    your org maintains a fork.
#
# What gets updated:
#   ALWAYS_UPDATE (generic, shared content)
#     llm-wiki.md
#     wiki/init-wiki.sh
#     wiki/agents/README.md
#     wiki/agents/discipline-gates.md
#     wiki/agents/verification-gate.md
#     scripts/update-from-template.sh
#     scripts/check-template-version.sh
#     .gitignore
#
#   NEVER SYNCED (one-shot, self-deleting; see wiki/agents/README.md)
#     scripts/instantiate.sh   - removed by the script itself at end of run
#
#   IF .claude/ EXISTS (Claude Code overlay active in this project)
#     .claude/commands/wiki-{experiment,source,lint}.md    (substitute {{REPO_NAME}})
#     .claude/skills/wiki-{experiment,source,lint}.md      (substitute {{REPO_NAME}})
#     wiki/agents/claude-code/setup.sh
#     wiki/agents/claude-code/README.md
#     wiki/agents/claude-code/templates/*
#
#   IF .cursor/ EXISTS (Cursor overlay active in this project)
#     .cursor/rules/wiki-{as-memory,experiment,source,lint}.mdc   (substitute {{REPO_NAME}})
#     wiki/agents/cursor/setup.sh
#     wiki/agents/cursor/README.md
#     wiki/agents/cursor/templates/*
#
# What does NOT get touched (project-specific):
#   CLAUDE.md
#   README.md
#   .cursorrules                              (project's own Cursor config)
#   .claude/settings.json                     (project's permissions allowlist)
#   .claude/settings.local.json               (per-user, gitignored)
#   .claude/hooks/                            (per-machine, opt-in)
#   wiki/<repo>.wiki/                         (separate git sub-repo)
#   Any file under your project's source tree
#
# After each successful run, an entry is appended to .llm-wiki-template-log.md
# at the repo root, recording the template commit SHA and the files changed.
# Push: this script does NOT push. It stages changes locally (unless --dry-run).
#

set -euo pipefail

DRY_RUN=false
TEMPLATE_URL="git@github.com:crcresearch/llm-wiki-memory-template.git"

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)            DRY_RUN=true; shift ;;
        --template-url=*)     TEMPLATE_URL="${1#*=}"; shift ;;
        -h|--help)
            sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) \
    || { echo "Error: not in a git repository." >&2; exit 1; }
REPO_NAME=$(basename "$REPO_ROOT")
cd "$REPO_ROOT"

# --- Ensure 'template' remote exists ---
if ! git remote get-url template >/dev/null 2>&1; then
    echo "Adding remote 'template' -> $TEMPLATE_URL"
    git remote add template "$TEMPLATE_URL"
fi

echo "Fetching template@main ..."
git fetch --quiet template main

TEMPLATE_SHA=$(git rev-parse --short template/main)
echo "Template HEAD: $TEMPLATE_SHA"

# --- Build the file list ---
ALWAYS_FILES=(
    "llm-wiki.md"
    "wiki/init-wiki.sh"
    "wiki/agents/README.md"
    "wiki/agents/discipline-gates.md"
    "wiki/agents/verification-gate.md"
    "wiki/agents/wiki-write-protocol.md"
    "scripts/update-from-template.sh"
    "scripts/check-template-version.sh"
    "scripts/lib/install-feature.sh"
    "scripts/enable-feature.sh"
    "scripts/disable-feature.sh"
    "scripts/wiki-write-protocol/README.md"
    "scripts/wiki-write-protocol/protocol.sh"
    "scripts/wiki-write-protocol/sandbox.sh"
    "scripts/wiki-write-protocol/run-all.sh"
    "scripts/wiki-write-protocol/scenarios/01-different-pages/run.sh"
    "scripts/wiki-write-protocol/scenarios/02-different-sections/run.sh"
    "scripts/wiki-write-protocol/scenarios/03-same-section/run.sh"
    "scripts/wiki-write-protocol/scenarios/04-index-union/run.sh"
    "scripts/wiki-write-protocol/scenarios/05-log-append/run.sh"
    "scripts/wiki-write-protocol/scenarios/06-push-race/run.sh"
    "scripts/wiki-write-protocol/scenarios/07-livelock-retry/run.sh"
    "scripts/wiki-write-protocol/scenarios/08-session-start-auto-pull/run.sh"
    "scripts/wiki-write-protocol/scenarios/09-session-start-divergent/run.sh"
    "features/README.md"
    ".gitignore"
)

# One-shot files are deliberately excluded from sync. They are either
# self-deleting scripts (run once, remove themselves) or one-shot template
# files consumed and removed by instantiate.sh during bootstrap. After
# bootstrap they do not exist in the derived project. Listed here for
# documentation only; the sync logic does not iterate over this array.
ONE_SHOT_FILES=(
    "scripts/instantiate.sh"
    "CLAUDE.md.template"
    "README.md.template"
    ".claude/settings.json.template"
    ".cursorrules.template"
)

CLAUDE_FILES=(
    ".claude/commands/wiki-experiment.md"
    ".claude/commands/wiki-source.md"
    ".claude/commands/wiki-lint.md"
    ".claude/skills/wiki-experiment.md"
    ".claude/skills/wiki-source.md"
    ".claude/skills/wiki-lint.md"
    "wiki/agents/claude-code/setup.sh"
    "wiki/agents/claude-code/README.md"
    "wiki/agents/claude-code/templates/claude-md-snippet.md"
    "wiki/agents/claude-code/templates/memory-seed.md"
    "wiki/agents/claude-code/templates/session-start-hook.sh"
)

CURSOR_FILES=(
    ".cursor/rules/wiki-as-memory.mdc"
    ".cursor/rules/wiki-experiment.mdc"
    ".cursor/rules/wiki-source.mdc"
    ".cursor/rules/wiki-lint.mdc"
    "wiki/agents/cursor/setup.sh"
    "wiki/agents/cursor/README.md"
)

# Files where {{REPO_NAME}} must be substituted by $REPO_NAME after pulling
# from template/main. These ship with literal {{REPO_NAME}} in the template
# but were substituted at instantiate time in this project; the substitution
# must be re-applied each time we pull.
SUBSTITUTE_FILES=(
    ".claude/commands/wiki-experiment.md"
    ".claude/commands/wiki-source.md"
    ".claude/commands/wiki-lint.md"
    ".claude/skills/wiki-experiment.md"
    ".claude/skills/wiki-source.md"
    ".claude/skills/wiki-lint.md"
    ".cursor/rules/wiki-as-memory.mdc"
    ".cursor/rules/wiki-experiment.mdc"
    ".cursor/rules/wiki-source.mdc"
    ".cursor/rules/wiki-lint.mdc"
)

needs_substitution() {
    local f="$1"
    for s in "${SUBSTITUTE_FILES[@]}"; do
        [[ "$f" == "$s" ]] && return 0
    done
    return 1
}

# Assemble the active file list based on which overlays are present.
FILES=("${ALWAYS_FILES[@]}")
if [[ -d "$REPO_ROOT/.claude" ]] || [[ -d "$REPO_ROOT/wiki/agents/claude-code" ]]; then
    FILES+=("${CLAUDE_FILES[@]}")
fi
if [[ -d "$REPO_ROOT/.cursor" ]] || [[ -d "$REPO_ROOT/wiki/agents/cursor" ]]; then
    FILES+=("${CURSOR_FILES[@]}")
fi

# --- Diff and apply ---
CHANGED=()
SKIPPED=()
MISSING_IN_TEMPLATE=()

for f in "${FILES[@]}"; do
    # Does the file exist in template/main?
    if ! git cat-file -e "template/main:$f" 2>/dev/null; then
        MISSING_IN_TEMPLATE+=("$f")
        continue
    fi

    # Materialize the template version to a temp file so the byte-exact
    # comparison preserves trailing newlines. Using a bash variable + sha256sum
    # via pipe would strip the trailing \n and produce false "changed" reports.
    TEMPLATE_TMP=$(mktemp)
    git show "template/main:$f" > "$TEMPLATE_TMP"
    if needs_substitution "$f"; then
        # GNU sed: -i without backup. macOS sed needs -i ''. Use a portable
        # form via the .bak suffix and clean up after.
        sed -i.bak "s|{{REPO_NAME}}|$REPO_NAME|g" "$TEMPLATE_TMP"
        rm -f "${TEMPLATE_TMP}.bak"
    fi

    TEMPLATE_HASH=$(sha256sum "$TEMPLATE_TMP" | awk '{print $1}')
    if [[ -f "$f" ]]; then
        LOCAL_HASH=$(sha256sum "$f" | awk '{print $1}')
    else
        LOCAL_HASH="<missing>"
    fi

    if [[ "$LOCAL_HASH" == "$TEMPLATE_HASH" ]]; then
        SKIPPED+=("$f")
        rm -f "$TEMPLATE_TMP"
        continue
    fi

    CHANGED+=("$f")
    if ! $DRY_RUN; then
        mkdir -p "$(dirname "$f")"
        mv "$TEMPLATE_TMP" "$f"
        # Preserve executable bit for shell scripts that should be executable.
        case "$f" in
            *.sh) chmod +x "$f" ;;
        esac
    else
        rm -f "$TEMPLATE_TMP"
    fi
done

# --- Report ---
echo ""
echo "================ update-from-template ================"
echo "Repo:     $REPO_ROOT"
echo "Template: $TEMPLATE_URL @ $TEMPLATE_SHA"
echo "Mode:     $($DRY_RUN && echo 'DRY RUN' || echo 'APPLIED')"
echo "------------------------------------------------------"
echo "Changed (${#CHANGED[@]}):"
if [[ ${#CHANGED[@]} -gt 0 ]]; then
    for f in "${CHANGED[@]}"; do echo "  + $f"; done
fi
echo ""
echo "Skipped, identical to template (${#SKIPPED[@]}):"
if [[ ${#SKIPPED[@]} -gt 0 ]]; then
    for f in "${SKIPPED[@]}"; do echo "  = $f"; done
fi
if [[ ${#MISSING_IN_TEMPLATE[@]} -gt 0 ]]; then
    echo ""
    echo "Not present in template/main (${#MISSING_IN_TEMPLATE[@]}):"
    for f in "${MISSING_IN_TEMPLATE[@]}"; do echo "  ? $f"; done
fi
echo "======================================================"

if $DRY_RUN; then
    echo ""
    echo "Dry run only. Re-run without --dry-run to apply."
    exit 0
fi

if [[ ${#CHANGED[@]} -eq 0 ]]; then
    echo ""
    echo "Nothing to apply. Repo is in sync with template/main @ $TEMPLATE_SHA."
    exit 0
fi

# --- Append log entry ---
LOG_FILE="$REPO_ROOT/.llm-wiki-template-log.md"
TODAY=$(date +%Y-%m-%d)
{
    [[ -f "$LOG_FILE" ]] || echo "# llm-wiki template sync log"
    [[ -f "$LOG_FILE" ]] || echo ""
    echo "## [$TODAY] pulled template @${TEMPLATE_SHA} - ${#CHANGED[@]} file(s) updated"
    for f in "${CHANGED[@]}"; do echo "- $f"; done
    echo ""
} >> "$LOG_FILE"

echo ""
echo "Logged in .llm-wiki-template-log.md."
echo ""
echo "Next steps:"
echo "  Review the changes:    git diff"
echo "  Stage and commit:      git add -A && git commit -m \"chore: pull llm-wiki template @${TEMPLATE_SHA}\""
echo "  (Do NOT push unless the team has reviewed.)"
