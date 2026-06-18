#!/usr/bin/env bash
#
# Claude Code PostToolUse hook (command type): after a Write or Edit to a
# wiki page, remind the agent to run the Verification Gate before
# committing. Installed by setup.sh --posttooluse-hook into
# .claude/hooks/posttooluse-hook.sh, then referenced from
# .claude/settings.json with matcher "Write|Edit".
#
# Why a command hook and not a prompt hook:
#   A command hook that exits 0 is purely advisory. The tool action
#   proceeds, and whatever the script writes to stdout is added to the
#   agent's context as a note. A prompt hook cannot do this: it is a
#   sandboxed single-turn model call with no filesystem or transcript
#   access, and its only outcomes are allow or block. An earlier version
#   of this hook used a prompt hook that asked the evaluator to check
#   index/log/back-reference state; the evaluator could not access those,
#   returned "not ok", and wrongly stopped the agent mid-ingest.
#
# This script does not evaluate the wiki itself (a shell hook has no way
# to). It only reminds the agent, which has tools, to run the gate. The
# canonical criteria live in wiki/agents/verification-gate.md.
#
# Reads the PostToolUse event JSON on stdin; always exits 0.

INPUT=$(cat)

# Extract the path of the file just written or edited. Empty if absent or
# if jq is unavailable; either way the script simply does not nudge.
FILE_PATH=""
if command -v jq >/dev/null 2>&1; then
    FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
fi

# Nudge only for a write/edit to a wiki page: wiki/<repo>.wiki/*.md.
case "$FILE_PATH" in
    *wiki/*.wiki/*.md)
        cat <<'EOF'
A wiki page was just written or edited. Before committing in the wiki
repo, run the Verification Gate at wiki/agents/verification-gate.md over
every page created or edited this session: every numerical claim tagged
with its corpus, every projection marked as such, back-references
bidirectional, and index_${REPO_NAME}.md plus log_${REPO_NAME}.md
updated. This is an advisory reminder and does not block.
EOF
        ;;
esac

exit 0
