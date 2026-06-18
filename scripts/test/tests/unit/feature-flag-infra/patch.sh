#!/usr/bin/env bash
# Patch: set up a tmp project root inside the sandbox with a baseline
# CLAUDE.md and a parallel _fixtures/ directory so install_feature can
# find the test-feature fixture via FEATURES_DIR.
#
# Inputs:  SANDBOX env var (from run.sh) pointing at the sandbox root.
# Effects:
#   - Creates $SANDBOX/feature-flag-test-project/ with CLAUDE.md and
#     CLAUDE.md.baseline (snapshot for byte-equivalence check after
#     install + uninstall).
#   - Copies _fixtures/test-feature into the project's _fixtures/ so
#     FEATURES_DIR=$PROJ/_fixtures resolves to it.

set -uo pipefail

PROJ="$SANDBOX/feature-flag-test-project"
# patch.sh is invoked (not sourced), so compute the fixture path from this
# file's own location. Layout: <test>/tests/unit/feature-flag-infra/patch.sh
# -> fixture at <test>/_fixtures/test-feature
HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE_SRC="$HERE_DIR/../../../_fixtures/test-feature"

if [[ ! -d "$FIXTURE_SRC" ]]; then
    echo "  ERROR: fixture not found at $FIXTURE_SRC" >&2
    exit 1
fi

mkdir -p "$PROJ/_fixtures"
cp -R "$FIXTURE_SRC" "$PROJ/_fixtures/"

# Baseline CLAUDE.md (small but realistic, with content the install must preserve)
cat > "$PROJ/CLAUDE.md" <<'EOF'
# Test Project

> Baseline CLAUDE.md for feature-flag infra testing.

## Notes

Pre-existing content that must be preserved across install + uninstall.
EOF

# Snapshot the baseline so the uninstall assertion can compare
cp "$PROJ/CLAUDE.md" "$PROJ/CLAUDE.md.baseline"

echo "  feature-flag-infra patch applied: project root at $PROJ"
