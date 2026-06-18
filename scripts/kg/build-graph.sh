#!/usr/bin/env bash
# scripts/kg/build-graph.sh
#
# Thin shell entry point. Delegates to scripts/kg/build-graph.py, which
# runs the full pipeline (fetch spec, extract, materialise, validate)
# in-process using rdflib + pyshacl.
#
# All CLI flags are passed through to the Python script. See
# scripts/kg/build-graph.py --help for the full list.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/build-graph.py" "$@"
