#!/usr/bin/env bash
# Assertions for the --agent=none regression smoke test (issue #9).
#
# Before the fix, instantiate.sh exited non-zero with
#   "INIT_AGENT_ARGS[@]: unbound variable"
# on bash 3.2 and init-wiki.sh never ran. After the fix, the script
# completes and produces CLAUDE.md + the wiki sub-repo.

T="$SANDBOX/template-none"

if [ ! -d "$T" ]; then
    skip "instantiate-agent-none assertions" "template not cloned (offline + no MVP_TEMPLATE_LOCAL)"
    return 0 2>/dev/null || true
fi

# Bootstrap exit + CLAUDE.md substitution
assert "instantiate.sh --agent=none produced CLAUDE.md" \
    "[ -f '$T/CLAUDE.md' ]"
assert_contains "CLAUDE.md has project name substituted" \
    "$T/CLAUDE.md" "Agent None Project"
assert "CLAUDE.md has no {{PROJECT_NAME}} leak" \
    "! grep -q '{{PROJECT_NAME}}' '$T/CLAUDE.md'"

# init-wiki.sh must have run (the regression killed it before it could fire)
REPO_NAME=$(basename "$T")
WIKI_SUB="$T/wiki/${REPO_NAME}.wiki"

assert "wiki sub-repo created at wiki/${REPO_NAME}.wiki/ (init-wiki.sh ran)" \
    "[ -d '$WIKI_SUB/.git' ]"
assert "Home_${REPO_NAME}.md exists" \
    "[ -f '$WIKI_SUB/Home_${REPO_NAME}.md' ]"
assert "SCHEMA_${REPO_NAME}.md exists" \
    "[ -f '$WIKI_SUB/SCHEMA_${REPO_NAME}.md' ]"

# --agent=none means no agent-overlay files should have been copied into
# the project root. The template ships agent overlays under wiki/agents/
# but instantiate.sh should NOT have created .claude/ or .cursor/ when
# --agent=none.
assert "no .claude/ overlay copied when --agent=none" \
    "[ ! -d '$T/.claude' ]"
assert "no .cursor/ overlay copied when --agent=none" \
    "[ ! -d '$T/.cursor' ]"
