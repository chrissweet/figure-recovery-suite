#!/usr/bin/env bash
# Smoke test: instantiate with --agent=none.
#
# Regression coverage for issue #9: instantiate.sh tripped `set -u` on
# bash 3.2 (macOS default) when INIT_AGENT_ARGS expanded empty for
# --agent=none, killing the bootstrap before init-wiki.sh could run.
#
# This test exercises the no-overlay path end-to-end so the bug cannot
# return silently. Runs against the macOS matrix where bash 3.2 actually
# reproduces the original failure.
#
# Inputs:  SANDBOX env var. lib/template.sh's clone_template.
# Effects: $SANDBOX/template-none/ contains a derivative bootstrapped
#          without any agent overlay.
#
# Idempotent.

set -euo pipefail

HARNESS_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../lib" && pwd)"
# shellcheck source=../../../lib/template.sh
source "$HARNESS_LIB/template.sh"

T="$SANDBOX/template-none"

if [ -d "$T" ]; then
    echo "  Template-none already cloned at $T (idempotent re-run)."
elif clone_template "$T"; then
    echo "  Cloned template to $T."
else
    # clone_template declined: either no network + no MVP_TEMPLATE_LOCAL,
    # or MVP_TEMPLATE_LOCAL points at a derived project (issue #15).
    echo "  Smoke instantiate-agent-none assertions will skip (see above for reason)." >&2
    exit 0
fi

if [ -f "$T/scripts/instantiate.sh" ]; then
    (
        cd "$T"
        if [ ! -f CLAUDE.md ]; then
            bash scripts/instantiate.sh "Agent None Project" \
                --agent=none \
                --description="Regression test for issue #9 (set -u + empty array)." \
                >/tmp/instantiate-none.log 2>&1 || {
                    echo "  WARN: instantiate.sh --agent=none failed; assertions will surface the cause." >&2
                    cat /tmp/instantiate-none.log | sed 's/^/    /' >&2
                }
        fi
    )
fi

echo "  Smoke instantiate-agent-none patch applied: template at $T."
