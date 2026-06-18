#!/usr/bin/env bash
# Sandbox lifecycle for the MVP test harness.

sandbox_setup() {
    local d
    d=$(mktemp -d -t llm-wiki-mvp-test.XXXXXX)
    echo "$d"
}

sandbox_teardown() {
    local d="$1"
    if [ -n "$d" ] && [ -d "$d" ]; then
        # Safety: only delete if path looks like a mktemp dir
        case "$d" in
            /tmp/llm-wiki-mvp-test.*|/var/folders/*/llm-wiki-mvp-test.*)
                rm -rf "$d"
                ;;
            *)
                echo "Refusing to delete unexpected sandbox path: $d" >&2
                return 1
                ;;
        esac
    fi
}
