#!/usr/bin/env bash
# Assertion helpers for the MVP test harness.
# All helpers update the globals PASS, FAIL, SKIP, FAILED_TESTS from run.sh.

assert() {
    local desc="$1"
    local cmd="$2"
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  PASS: $desc"
        PASS=$((PASS+1))
    else
        echo "  FAIL: $desc"
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$desc")
    fi
}

assert_contains() {
    local desc="$1"
    local file="$2"
    local pattern="$3"
    if [ -f "$file" ] && grep -qE "$pattern" "$file"; then
        echo "  PASS: $desc"
        PASS=$((PASS+1))
    else
        echo "  FAIL: $desc"
        echo "    (file=$file pattern=$pattern)"
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$desc")
    fi
}

assert_not_contains() {
    local desc="$1"
    local file="$2"
    local pattern="$3"
    if [ ! -f "$file" ] || ! grep -qE "$pattern" "$file"; then
        echo "  PASS: $desc"
        PASS=$((PASS+1))
    else
        echo "  FAIL: $desc"
        echo "    (file=$file pattern=$pattern was unexpectedly present)"
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$desc")
    fi
}

assert_eq() {
    local desc="$1"
    local expected="$2"
    local actual="$3"
    if [ "$expected" = "$actual" ]; then
        echo "  PASS: $desc"
        PASS=$((PASS+1))
    else
        echo "  FAIL: $desc"
        echo "    expected: $expected"
        echo "    actual:   $actual"
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$desc")
    fi
}

assert_ne() {
    local desc="$1"
    local left="$2"
    local right="$3"
    if [ "$left" != "$right" ]; then
        echo "  PASS: $desc"
        PASS=$((PASS+1))
    else
        echo "  FAIL: $desc"
        echo "    both values were: $left"
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$desc")
    fi
}

skip() {
    local desc="$1"
    local reason="${2:-no reason given}"
    echo "  SKIP: $desc ($reason)"
    SKIP=$((SKIP+1))
}
