#!/usr/bin/env bash
# Patch: build two fake project roots so assertions.sh can exercise
# clone_template's derived-project guard (issue #15).
#
# Inputs:  SANDBOX env var.
# Effects: $SANDBOX/clone-template-guard/ contains
#            fake-template/   (has CLAUDE.md.template, no CLAUDE.md)
#            fake-derived/    (has CLAUDE.md, no CLAUDE.md.template)
#
# Idempotent.

set -uo pipefail

ROOT="$SANDBOX/clone-template-guard"
TEMPL="$ROOT/fake-template"
DERIVED="$ROOT/fake-derived"

mkdir -p "$TEMPL" "$DERIVED"

# A fake template: the discriminator is CLAUDE.md.template present,
# CLAUDE.md absent. We do not need real template contents; clone_template's
# guard only looks at these two filenames.
echo "{{PROJECT_NAME}} placeholder" > "$TEMPL/CLAUDE.md.template"

# A fake derived project: CLAUDE.md present, CLAUDE.md.template absent.
# This is what instantiate.sh leaves behind after self-deleting the
# one-shot template.
echo "# CLAUDE.md (derived project state)" > "$DERIVED/CLAUDE.md"

echo "  clone-template-guard: fake roots ready at $ROOT"
