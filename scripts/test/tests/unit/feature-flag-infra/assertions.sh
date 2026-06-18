#!/usr/bin/env bash
# Assertions: exercise install_feature and uninstall_feature against the
# bundled test-feature fixture. Verifies the full contract from RFC #13
# Etapa 1: copy files, patch CLAUDE.md, copy CI workflow, record in
# .features-enabled, print deps; idempotency on re-install and re-uninstall;
# install + uninstall = identity (byte-equivalent CLAUDE.md).

PROJ="$SANDBOX/feature-flag-test-project"
# assertions.sh is sourced by run.sh, so $HERE here = run.sh's HERE =
# scripts/test/. Two levels up is the template repo root.
REPO_ROOT_FFINFRA="$(cd "$HERE/../.." && pwd)"
INSTALL_LIB="$REPO_ROOT_FFINFRA/scripts/lib/install-feature.sh"
ENABLE_SCRIPT="$REPO_ROOT_FFINFRA/scripts/enable-feature.sh"
DISABLE_SCRIPT="$REPO_ROOT_FFINFRA/scripts/disable-feature.sh"
FEATURES_README="$REPO_ROOT_FFINFRA/features/README.md"

# --- Sanity: the new infra files all exist and are syntactically valid ---
assert "scripts/lib/install-feature.sh exists" "[ -f '$INSTALL_LIB' ]"
assert "scripts/enable-feature.sh exists"      "[ -f '$ENABLE_SCRIPT' ]"
assert "scripts/disable-feature.sh exists"     "[ -f '$DISABLE_SCRIPT' ]"
assert "features/README.md exists"             "[ -f '$FEATURES_README' ]"

assert "install-feature.sh passes bash -n"  "bash -n '$INSTALL_LIB'"
assert "enable-feature.sh passes bash -n"   "bash -n '$ENABLE_SCRIPT'"
assert "disable-feature.sh passes bash -n"  "bash -n '$DISABLE_SCRIPT'"

assert "enable-feature.sh is executable"    "[ -x '$ENABLE_SCRIPT' ]"
assert "disable-feature.sh is executable"   "[ -x '$DISABLE_SCRIPT' ]"

# --- Helper: run a command in $PROJ with FEATURES_DIR set to the fixture ---
_ff_run_in_proj() {
    (cd "$PROJ" && FEATURES_DIR="$PROJ/_fixtures" bash -c "
        source '$INSTALL_LIB'
        $1
    ")
}

# --- Step 1: install_feature test-feature ---
_ff_run_in_proj "install_feature test-feature" >/dev/null 2>&1
INSTALL_RC=$?
assert "install_feature test-feature exits 0"            "[ '$INSTALL_RC' -eq 0 ]"
assert "scripts/test-feature/ created"                   "[ -d '$PROJ/scripts/test-feature' ]"
assert "scripts/test-feature/greet.sh present"           "[ -f '$PROJ/scripts/test-feature/greet.sh' ]"
assert ".features-enabled file created"                  "[ -f '$PROJ/.features-enabled' ]"
assert ".features-enabled lists test-feature"            "grep -qFx 'test-feature' '$PROJ/.features-enabled'"
assert "CLAUDE.md has opening marker"                    "grep -qF '<!-- feature:test-feature -->' '$PROJ/CLAUDE.md'"
assert "CLAUDE.md has closing marker"                    "grep -qF '<!-- /feature:test-feature -->' '$PROJ/CLAUDE.md'"
assert "CLAUDE.md section content present"               "grep -qF 'Test Feature (fixture)' '$PROJ/CLAUDE.md'"
assert ".github/workflows/test-feature.yml created"      "[ -f '$PROJ/.github/workflows/test-feature.yml' ]"
assert "baseline content preserved in CLAUDE.md"         "grep -qF 'Pre-existing content' '$PROJ/CLAUDE.md'"

# --- Step 2: idempotent install (re-run, should not duplicate) ---
LINES_BEFORE=$(wc -l < "$PROJ/.features-enabled")
_ff_run_in_proj "install_feature test-feature" >/dev/null 2>&1
RE_INSTALL_RC=$?
LINES_AFTER=$(wc -l < "$PROJ/.features-enabled")
OPEN_MARKERS=$(grep -cF '<!-- feature:test-feature -->' "$PROJ/CLAUDE.md")

assert "idempotent install: exits 0"                          "[ '$RE_INSTALL_RC' -eq 0 ]"
assert "idempotent install: .features-enabled not duplicated" "[ '$LINES_BEFORE' -eq '$LINES_AFTER' ]"
assert "idempotent install: CLAUDE.md marker not duplicated"  "[ '$OPEN_MARKERS' -eq 1 ]"

# --- Step 3: uninstall_feature test-feature ---
_ff_run_in_proj "uninstall_feature test-feature" >/dev/null 2>&1
UNINSTALL_RC=$?

assert "uninstall_feature exits 0"                                       "[ '$UNINSTALL_RC' -eq 0 ]"
assert "scripts/test-feature/ removed"                                   "[ ! -d '$PROJ/scripts/test-feature' ]"
assert ".features-enabled removed (was empty)"                           "[ ! -f '$PROJ/.features-enabled' ]"
assert "CLAUDE.md no longer contains opening marker"                     "! grep -qF '<!-- feature:test-feature -->' '$PROJ/CLAUDE.md'"
assert "CLAUDE.md no longer contains closing marker"                     "! grep -qF '<!-- /feature:test-feature -->' '$PROJ/CLAUDE.md'"
assert ".github/workflows/test-feature.yml removed"                      "[ ! -f '$PROJ/.github/workflows/test-feature.yml' ]"

# --- Step 4: install + uninstall = identity (byte-equivalent CLAUDE.md) ---
assert "CLAUDE.md byte-equivalent to baseline after install+uninstall"   "diff -q '$PROJ/CLAUDE.md' '$PROJ/CLAUDE.md.baseline' >/dev/null"

# --- Step 5: idempotent uninstall (re-run, no error) ---
_ff_run_in_proj "uninstall_feature test-feature" >/dev/null 2>&1
IDEMP_UNINSTALL_RC=$?
assert "idempotent uninstall: re-run exits 0"                            "[ '$IDEMP_UNINSTALL_RC' -eq 0 ]"

# --- Step 6: error handling — install_feature on non-existent feature ---
_ff_run_in_proj "install_feature nonexistent-feature-name" >/dev/null 2>&1
NOTFOUND_RC=$?
assert "install_feature on nonexistent feature exits non-zero"           "[ '$NOTFOUND_RC' -ne 0 ]"

# --- Step 7: error handling — install_feature called with no args ---
_ff_run_in_proj "install_feature" >/dev/null 2>&1
NOARG_RC=$?
assert "install_feature with no name exits non-zero"                     "[ '$NOARG_RC' -ne 0 ]"
