#!/usr/bin/env bash
#
# install-feature.sh — Shared feature install/uninstall logic for the
# llm-wiki-memory-template feature-flag architecture (RFC #13, Etapa 1).
#
# This file is sourced by:
#   scripts/instantiate.sh      (the declarative entry point: --features=)
#   scripts/enable-feature.sh   (the retroactive entry point)
#   scripts/disable-feature.sh  (the symmetric removal)
#
# Do not invoke this file directly. It defines two functions:
#
#   install_feature <name>     install the named feature into the current
#                              project root (idempotent)
#   uninstall_feature <name>   symmetric removal (idempotent)
#
# Both functions expect the current working directory to be a derived
# project root (containing CLAUDE.md, scripts/, and either an existing
# features/ directory or a path provided via the FEATURES_DIR env var).
#
# The FEATURES_DIR override exists for tests, where the fixture lives
# outside the conventional features/ tree. In production install_feature
# defaults to ./features/ relative to the caller's cwd.
#
# The marker convention for CLAUDE.md sections is PAIRED HTML comments:
#
#   <!-- feature:<name> -->
#   ... section content from features/<name>/CLAUDE.section.md ...
#   <!-- /feature:<name> -->
#
# Paired markers are deliberate: they support both idempotent install
# (skip if opening marker present) AND clean uninstall (delete between
# the pair). A single-marker pattern like the existing
# wiki/agents/claude-code/setup.sh would not support uninstall.
#
# Requires: bash 3.2+, jq, python3 (for safe CLAUDE.md section removal).
# Bash 3.2 compatibility means no mapfile and no associative arrays;
# arrays are explicitly initialised before any expansion under `set -u`.

# --- Internal helpers ------------------------------------------------------

_feature_require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Error: '$1' is required but not on PATH (used by install_feature)." >&2
        return 1
    fi
}

_feature_features_dir() {
    if [[ -n "${FEATURES_DIR:-}" ]]; then
        echo "$FEATURES_DIR"
    else
        echo "./features"
    fi
}

_feature_list_available() {
    local features_dir; features_dir=$(_feature_features_dir)
    local d
    if [[ ! -d "$features_dir" ]]; then
        return 0
    fi
    for d in "$features_dir"/*/; do
        [[ -d "$d" ]] || continue
        [[ -f "$d/feature.json" ]] || continue
        echo "  $(basename "$d")"
    done
}

_feature_is_enabled() {
    local name="$1"
    [[ -f ".features-enabled" ]] && grep -qFx "$name" .features-enabled 2>/dev/null
}

# --- Public: install_feature -----------------------------------------------

install_feature() {
    local name="${1:-}"
    if [[ -z "$name" ]]; then
        echo "Error: install_feature requires a feature name." >&2
        return 1
    fi

    local features_dir feature_dir feature_json
    features_dir=$(_feature_features_dir)
    feature_dir="$features_dir/$name"
    feature_json="$feature_dir/feature.json"

    # Validate the feature exists
    if [[ ! -d "$feature_dir" ]]; then
        echo "Error: feature '$name' not found in $features_dir/." >&2
        echo "Available features:" >&2
        _feature_list_available >&2
        return 1
    fi
    if [[ ! -f "$feature_json" ]]; then
        echo "Error: feature '$name' is missing feature.json at $feature_json." >&2
        return 1
    fi

    _feature_require_cmd jq || return 1

    # Idempotency: if already in .features-enabled, no-op success
    if _feature_is_enabled "$name"; then
        echo "Feature '$name' already enabled; skipping."
        return 0
    fi

    echo "Installing feature '$name' from $feature_dir/ ..."

    # Step 1: copy code files (files.source -> files.destination)
    local files_src files_dst
    files_src=$(jq -r '.files.source // empty' "$feature_json")
    files_dst=$(jq -r '.files.destination // empty' "$feature_json")
    if [[ -n "$files_src" && -n "$files_dst" ]]; then
        local src_path="$feature_dir/$files_src"
        if [[ ! -d "$src_path" ]]; then
            echo "Error: files.source '$files_src' does not exist in $feature_dir." >&2
            return 1
        fi
        if [[ -e "$files_dst" ]]; then
            echo "Error: destination '$files_dst' already exists." >&2
            echo "       Refusing to overwrite. Resolve the conflict and re-run." >&2
            return 1
        fi
        mkdir -p "$(dirname "$files_dst")"
        cp -R "$src_path" "$files_dst"
        echo "  + copied $files_src/* -> $files_dst/"
    fi

    # Step 2: copy tests (tests.source -> tests.destination), if declared
    local tests_src tests_dst
    tests_src=$(jq -r '.tests.source // empty' "$feature_json")
    tests_dst=$(jq -r '.tests.destination // empty' "$feature_json")
    if [[ -n "$tests_src" && -n "$tests_dst" ]]; then
        local tests_src_path="$feature_dir/$tests_src"
        if [[ -d "$tests_src_path" ]]; then
            if [[ -e "$tests_dst" ]]; then
                echo "Error: tests destination '$tests_dst' already exists." >&2
                return 1
            fi
            mkdir -p "$(dirname "$tests_dst")"
            cp -R "$tests_src_path" "$tests_dst"
            echo "  + copied tests -> $tests_dst/"
        fi
    fi

    # Step 3: copy CI workflow file, if declared
    local ci_wf
    ci_wf=$(jq -r '.ci.workflow_file // empty' "$feature_json")
    if [[ -n "$ci_wf" ]]; then
        local ci_src="$feature_dir/$ci_wf"
        if [[ -f "$ci_src" ]]; then
            mkdir -p .github/workflows
            local ci_dst=".github/workflows/$(basename "$ci_wf")"
            cp "$ci_src" "$ci_dst"
            echo "  + copied CI workflow -> $ci_dst"
        fi
    fi

    # Step 4: patch CLAUDE.md with the feature's section between paired markers
    local marker section_file
    marker=$(jq -r '.claude_md.marker // empty' "$feature_json")
    section_file=$(jq -r '.claude_md.section_file // empty' "$feature_json")
    if [[ -n "$marker" && -n "$section_file" ]]; then
        local section_path="$feature_dir/$section_file"
        if [[ -f "$section_path" && -f "CLAUDE.md" ]]; then
            local open_marker="<!-- $marker -->"
            local close_marker="<!-- /$marker -->"
            if grep -qF "$open_marker" CLAUDE.md 2>/dev/null; then
                echo "  = CLAUDE.md already contains '$open_marker'; skipping patch."
            else
                {
                    printf '\n%s\n' "$open_marker"
                    cat "$section_path"
                    printf '%s\n' "$close_marker"
                } >> CLAUDE.md
                echo "  + patched CLAUDE.md with marker '$marker'"
            fi
        fi
    fi

    # Step 5: record in .features-enabled (plain text, one name per line)
    echo "$name" >> .features-enabled
    echo "  + recorded '$name' in .features-enabled"

    # Step 6: print system_deps install instructions (declarative, never auto-run)
    local n_deps
    n_deps=$(jq -r '.system_deps | length' "$feature_json" 2>/dev/null || echo 0)
    if [[ "$n_deps" -gt 0 ]]; then
        echo ""
        echo "System dependencies required for feature '$name':"
        local i=0
        while [[ "$i" -lt "$n_deps" ]]; do
            local dep_name dep_ver dep_inst_ubuntu dep_inst_macos dep_inst_manual
            dep_name=$(jq -r ".system_deps[$i].name // \"\"" "$feature_json")
            dep_ver=$(jq -r ".system_deps[$i].version // \"\"" "$feature_json")
            dep_inst_ubuntu=$(jq -r ".system_deps[$i].install.ubuntu // \"\"" "$feature_json")
            dep_inst_macos=$(jq -r ".system_deps[$i].install.macos // \"\"" "$feature_json")
            dep_inst_manual=$(jq -r ".system_deps[$i].install.manual // \"\"" "$feature_json")
            echo "  - $dep_name${dep_ver:+ ($dep_ver)}"
            [[ -n "$dep_inst_ubuntu" ]] && echo "      Ubuntu/Debian: $dep_inst_ubuntu"
            [[ -n "$dep_inst_macos" ]]  && echo "      macOS:         $dep_inst_macos"
            [[ -n "$dep_inst_manual" ]] && echo "      Manual:        $dep_inst_manual"
            i=$((i + 1))
        done
        echo ""
        echo "Note: install_feature does NOT run these commands."
        echo "      Install dependencies yourself before using the feature."
    fi

    echo ""
    echo "Feature '$name' installed."
    return 0
}

# --- Public: uninstall_feature ---------------------------------------------

uninstall_feature() {
    local name="${1:-}"
    if [[ -z "$name" ]]; then
        echo "Error: uninstall_feature requires a feature name." >&2
        return 1
    fi

    if ! _feature_is_enabled "$name"; then
        echo "Feature '$name' is not enabled; nothing to remove."
        return 0
    fi

    local features_dir feature_dir feature_json
    features_dir=$(_feature_features_dir)
    feature_dir="$features_dir/$name"
    feature_json="$feature_dir/feature.json"

    echo "Uninstalling feature '$name' ..."

    # If feature.json is missing, do minimal cleanup (just .features-enabled).
    # The user's deployment may have lost the feature definition; we still
    # honour the request to remove the bookkeeping entry.
    if [[ ! -f "$feature_json" ]]; then
        echo "Warning: feature.json missing at $feature_json." >&2
        echo "         Removing '$name' from .features-enabled only;" >&2
        echo "         manual cleanup of installed files may be needed." >&2
    else
        _feature_require_cmd jq || return 1

        # Step 1: remove files destination
        local files_dst
        files_dst=$(jq -r '.files.destination // empty' "$feature_json")
        if [[ -n "$files_dst" && -e "$files_dst" ]]; then
            rm -rf "$files_dst"
            echo "  - removed $files_dst"
        fi

        # Step 2: remove tests destination
        local tests_dst
        tests_dst=$(jq -r '.tests.destination // empty' "$feature_json")
        if [[ -n "$tests_dst" && -e "$tests_dst" ]]; then
            rm -rf "$tests_dst"
            echo "  - removed $tests_dst"
        fi

        # Step 3: remove CI workflow file
        local ci_wf
        ci_wf=$(jq -r '.ci.workflow_file // empty' "$feature_json")
        if [[ -n "$ci_wf" ]]; then
            local ci_dst=".github/workflows/$(basename "$ci_wf")"
            if [[ -f "$ci_dst" ]]; then
                rm -f "$ci_dst"
                echo "  - removed $ci_dst"
            fi
        fi

        # Step 4: remove CLAUDE.md section between paired markers
        local marker
        marker=$(jq -r '.claude_md.marker // empty' "$feature_json")
        if [[ -n "$marker" && -f "CLAUDE.md" ]]; then
            local open_marker="<!-- $marker -->"
            if grep -qF "$open_marker" CLAUDE.md 2>/dev/null; then
                # Use Python for safe re-based deletion; sed across newlines
                # is fragile and bash 3.2 lacks reliable in-place multiline
                # handling. The pattern eats blank lines surrounding the
                # markers so the file does not accumulate empty lines.
                _feature_require_cmd python3 || return 1
                MARKER_NAME="$marker" python3 <<'PY_EOF'
import os, re, sys
marker = os.environ["MARKER_NAME"]
with open("CLAUDE.md", "r") as f:
    text = f.read()
open_re  = re.escape(f"<!-- {marker} -->")
close_re = re.escape(f"<!-- /{marker} -->")
pat = re.compile(r"\n*" + open_re + r".*?" + close_re + r"\n*", re.DOTALL)
new_text = pat.sub("\n", text)
with open("CLAUDE.md", "w") as f:
    f.write(new_text)
PY_EOF
                echo "  - removed CLAUDE.md '$marker' section"
            fi
        fi
    fi

    # Step 5: remove from .features-enabled
    if [[ -f ".features-enabled" ]]; then
        local tmp
        tmp=$(mktemp)
        grep -vFx "$name" .features-enabled > "$tmp" 2>/dev/null || true
        if [[ -s "$tmp" ]]; then
            mv "$tmp" .features-enabled
        else
            rm -f "$tmp" .features-enabled
        fi
        echo "  - removed '$name' from .features-enabled"
    fi

    echo ""
    echo "Feature '$name' uninstalled."
    return 0
}
