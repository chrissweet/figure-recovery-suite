# Test Harness for llm-wiki-memory-template

Structural CI for the template. Clones the template, runs `instantiate.sh`,
and asserts the bootstrap produces the right files. Runs on every push and
PR via `.github/workflows/test-harness.yml`, matrixed across `ubuntu-latest`
and `macos-latest`. Addresses template issue #5.

## What it tests

Currently one category. The harness auto-discovers any new categories under
`tests/<category>/`; the canonical order is `smoke`, `unit`, `integration`,
`e2e`, `regression`, then anything else alphabetically.

### Smoke (real template, fast structural checks)

| Test | Assertions | What it checks |
|---|---|---|
| `template-bootstrap` | 14 | Clones the real template, runs `instantiate.sh`, asserts: bash syntax of all shipping scripts, CLAUDE.md generated with substituted placeholders, wiki sub-repo created, namespaced nav files present, `init-wiki.sh` is idempotent |
| `instantiate-agent-none` | 8 | Regression for issue #9: runs `instantiate.sh --agent=none`, asserts bootstrap completes, CLAUDE.md is written, `init-wiki.sh` runs, and no `.claude/` or `.cursor/` overlay is copied |

## Usage

```bash
# Run all categories
./scripts/test/run.sh

# Filter by category
./scripts/test/run.sh --category=smoke
./scripts/test/run.sh --category smoke

# Filter by test name
./scripts/test/run.sh template-bootstrap

# Keep the sandbox dir after the run (for inspection)
./scripts/test/run.sh --no-cleanup
```

Exit code = number of failed assertions. 0 = all green.

## Template source

Smoke tests need a real template clone. Two ways to provide one:

```bash
# Offline mode (preferred for fast iteration; cheapest)
export MVP_TEMPLATE_LOCAL=/path/to/llm-wiki-memory-template
./scripts/test/run.sh

# Network mode (defaults to the upstream fork)
./scripts/test/run.sh

# Network mode with a different fork / branch
export MVP_TEMPLATE_REPO=https://github.com/your-fork/llm-wiki-memory-template.git
./scripts/test/run.sh
```

If neither is reachable, smoke tests `skip` gracefully.

## Structure

```
scripts/test/
├── README.md           # this file
├── run.sh              # main entry point (categories, filtering, reporting)
├── lib/
│   ├── assert.sh       # assertion helpers (assert, assert_contains, assert_eq, assert_ne, skip)
│   ├── sandbox.sh      # sandbox lifecycle (mktemp + cleanup)
│   └── template.sh     # clone_template (offline or network)
└── tests/
    └── smoke/
        └── template-bootstrap/
            ├── patch.sh       # clones template, runs instantiate.sh
            └── assertions.sh  # syntax + bootstrap-output assertions
```

## Adding a test

1. Pick a category: `smoke` (fast/structural), `unit` (single-script), `integration` (multi-script), `e2e` (full sandbox), `regression` (test for a fixed bug).
2. `mkdir -p tests/<category>/<test-name>`
3. Write `patch.sh`: applies setup to the sandbox. Should be idempotent. Source `lib/template.sh` etc. if you need helpers (run.sh runs each `patch.sh` in a subshell).
4. Write `assertions.sh`: uses `assert` / `assert_contains` / `assert_eq` / `assert_ne` / `skip` helpers. Sourced by run.sh (so shares PASS/FAIL/FAILED_TESTS globals).
5. The harness auto-discovers by directory.

## CI

`.github/workflows/test-harness.yml` runs the harness on every push and pull
request, matrixed across `ubuntu-latest` and `macos-latest`. macOS in the
matrix is important: bash 3.2 (the macOS default) accepts and rejects
syntax differently from bash 5+, and macOS-specific path-canonicalization
behavior surfaces here.

## Design notes

- **Bash 3.2 compatible**: macOS default bash. No `mapfile`, careful with `set -u` and empty arrays.
- **Sandboxed**: each run uses a `mktemp -d` sandbox; cleaned up on exit unless `--no-cleanup` is passed.
- **Adding a test is one directory**: no harness changes needed.
- **What can't be tested here**: live Claude Code session behavior (whether an agent actually invokes hooks at the right moment). That requires an LLM in the loop, out of scope for structural CI.
