#!/usr/bin/env bash
# Template-clone helper for the MVP test harness.
#
# clone_template clones (or copies from local) the real template repo. Used
# by smoke tests that exercise the template's actual bootstrap, including
# init-wiki.sh in create and update modes.
#
# Two env vars control template resolution, in order of precedence:
#   MVP_TEMPLATE_LOCAL=/path/to/clone  use a local clone (offline, fast)
#   MVP_TEMPLATE_REPO=<url>            clone from this URL (default: the
#                                       canonical crcresearch template)

DEFAULT_TEMPLATE_REPO="https://github.com/crcresearch/llm-wiki-memory-template.git"

# Clone the real template into TARGET. Prefers MVP_TEMPLATE_LOCAL if set
# (offline mode), falls back to MVP_TEMPLATE_REPO (or DEFAULT_TEMPLATE_REPO).
# Returns 0 on success, 1 if both modes fail (e.g. no network and no local)
# OR if MVP_TEMPLATE_LOCAL points at a derived project rather than the
# canonical template (see the derived-project guard below; issue #15).
clone_template() {
    local target="$1"
    local repo="${MVP_TEMPLATE_REPO:-$DEFAULT_TEMPLATE_REPO}"
    local local_clone="${MVP_TEMPLATE_LOCAL:-}"

    if [ -n "$local_clone" ] && [ -d "$local_clone" ]; then
        # Derived-project guard (issue #15).
        #
        # The shipped test-harness.yml workflow sets
        # MVP_TEMPLATE_LOCAL=${{ github.workspace }} so the template's own CI
        # tests its local checkout. The workflow file is also shipped to
        # derived projects via "Use this template"; in the derived's CI,
        # github.workspace points at the derived, not at the template.
        # Copying a derived project into the sandbox would carry its
        # instantiated state (real CLAUDE.md, wiki/<repo>.wiki/, etc.) and
        # make the bootstrap assertions meaningless (16 fails, all spurious).
        #
        # Heuristic: the canonical template ships CLAUDE.md.template and
        # has no CLAUDE.md; a derived project has CLAUDE.md and (after
        # instantiate.sh self-deletes the one-shot template) typically no
        # CLAUDE.md.template either. The discriminator is the presence of
        # CLAUDE.md.template.
        if [ -f "$local_clone/CLAUDE.md" ] && [ ! -f "$local_clone/CLAUDE.md.template" ]; then
            echo "  Note: MVP_TEMPLATE_LOCAL=$local_clone looks like a derived" >&2
            echo "        project (has CLAUDE.md, lacks CLAUDE.md.template)." >&2
            echo "        Template-bootstrap smoke tests apply to the template" >&2
            echo "        repo only; declining to clone here. Smoke assertions" >&2
            echo "        will skip cleanly. See issue #15." >&2
            return 1
        fi

        # Local-clone mode: copy the working tree (preserving .git would
        # confuse instantiate.sh which expects to commit fresh state).
        # We re-init git so the derivative looks like a fresh checkout.
        cp -R "$local_clone" "$target"
        rm -rf "$target/.git"
        (
            cd "$target"
            git -c init.defaultBranch=main init --quiet
            git config user.email "smoke-test@example.test"
            git config user.name "Smoke Test"
            git add -A
            git commit -q -m "imported from local template clone for smoke test"
        )
        return 0
    fi

    # Network-clone mode
    if git clone --quiet "$repo" "$target" 2>/dev/null; then
        # Reset git config so commits made during the smoke test have a
        # known author.
        (
            cd "$target"
            git config user.email "smoke-test@example.test"
            git config user.name "Smoke Test"
        )
        return 0
    fi

    return 1
}
