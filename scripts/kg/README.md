# scripts/kg/

Single-entry-point pipeline that builds a typed-edge knowledge graph
from the wiki's YAML frontmatter and body links. Implements what the
template's wiki page
[Knowledge-Graph-Pipeline](../../wiki/Knowledge-Graph-Pipeline)
previously documented as **NOT YET IMPLEMENTED**.

## Quick start

```bash
./scripts/kg/build-graph.sh                  # build against wiki/<repo>.wiki/
./scripts/kg/build-graph.sh --wiki=PATH      # custom wiki
./scripts/kg/build-graph.sh --refresh-spec   # re-fetch spec from LA3D
./scripts/kg/build-graph.sh --stats          # extractor stats
./scripts/kg/build-graph.sh --help           # full flag list
```

Outputs go to `scripts/kg/build/` (gitignored):

| File                    | Contents                                                  |
|-------------------------|-----------------------------------------------------------|
| `graph.jsonld`          | JSON-LD extracted from frontmatter + body links          |
| `graph.ttl`             | Turtle translation (with RDF-star weights appended)      |
| `graph-weights.ttl`     | RDF-star weighted `mentions` (from the extractor)        |
| `graph-full.ttl`        | `graph.ttl` plus materialised inverses, hubs, area inh.  |
| `validation-report.ttl` | SHACL conformance report                                 |

## Architecture

The pipeline distinguishes **spec** (canonical, fetched from the
published LA3D URL) from **code** (local, modifiable) from **queries**
(curated subset that this template actually uses):

| Source of truth | Files |
|---|---|
| `https://la3d.github.io/llm-wiki-colab/` (fetched at build, cached in `.cache/`) | `ontology.ttl`, `shapes.ttl`, `context.jsonld` |
| Local to this template | `build-graph.sh`, `build-graph.py`, `wiki-to-jsonld.py`, `sparql/*.rq` |
| Test fixtures | `fixtures/mini-wiki/` |

The published spec's IRIs (e.g. `llm-wiki-colab:Concept`,
`llm-wiki-colab:extends`) resolve under
`https://la3d.github.io/llm-wiki-colab/ontology#`. The cache is
gitignored.

The pipeline runs in-process Python using **rdflib + pyshacl**:

- JSON-LD parsing and Turtle serialisation: rdflib's standard parsers
- Materialisation (inverses, area inheritance, hub flag): SPARQL CONSTRUCT
  queries via `rdflib.Graph.query()`, in-process, no subprocess
- SHACL validation: `pyshacl.validate()`, in-process

This shape is deliberate. The agent-tool layer that builds on the KG
(typed-parameter wrappers around canned queries, eventually a memory
substrate) stays in Python; calls into the graph are in-process method
calls, not subprocess invocations of CLI tools.

## Dependencies

- Bash 4+
- Python 3 with `PyYAML` (used by `wiki-to-jsonld.py`)
- `rdflib` and `pyshacl` Python packages

That is the whole list. No Java, no Apache Jena, no system-level
package install beyond pip.

Tests assert presence and fail on missing deps; the CI workflow at
`.github/workflows/test-harness.yml` installs them on both
`ubuntu-latest` (`apt-get install python3-yaml` + `pip install rdflib
pyshacl`) and `macos-latest` (`pip install --break-system-packages
pyyaml rdflib pyshacl`).

## SPARQL endpoint

The pipeline's default mode is **in-process**: queries run against the
loaded graph object directly. No server, no HTTP, no separate process.

For scenarios that need a live SPARQL endpoint (multi-client query,
agent-write via SPARQL UPDATE, federated queries across wikis, web
dashboards), Apache Jena Fuseki can host the produced
`graph-full.ttl` and rdflib will talk to it via `SPARQLStore`. This is
opt-in. The agent-memory feature, when shipped, is expected to depend
on the Fuseki path because cross-session writes need SPARQL UPDATE and
an HTTP surface.

## Layout

```
scripts/kg/
├── README.md
├── build-graph.sh       thin shell entry point
├── build-graph.py       pipeline in Python (rdflib + pyshacl)
├── wiki-to-jsonld.py    frontmatter + body extractor (LA3D-derived)
├── .gitignore           ignores .cache/ and build/
├── sparql/              11 canned queries (curated from LA3D set)
└── fixtures/mini-wiki/  5 fixture pages used by the harness assertions
```

Runtime-only (not committed):

```
scripts/kg/
├── .cache/              fetched spec (ontology.ttl, shapes.ttl, context.jsonld)
└── build/               graph.jsonld, graph.ttl, graph-full.ttl, validation-report.ttl
```

## Tests

The harness wraps a single assertion-set at
`scripts/test/tests/unit/kg-frontmatter-graph/assertions.sh`. Run
either:

```bash
./scripts/test/run.sh --category=unit
./scripts/test/run.sh kg-frontmatter-graph
```

The assertions run `build-graph.sh --wiki=scripts/kg/fixtures/mini-wiki`
and check the produced JSON-LD and Turtle for expected pages, type
mappings, frontmatter typed-edge resolution, and materialised inverse
edges.

## Scope today

- **Frontmatter typed edges**: fully exercised by the assertions
  (`up`, `extends`, `supports`, `criticizes`, `related`, `source`,
  plus all other LA3D forward predicates the extractor recognises).
- **Body link mentions**: extracted as `mentions` edges; the extractor
  also recognises Variant 1 inline annotations and HTML-comment
  attributes. These work today but are not the focus of the v1
  assertions.
- **SHACL validation**: runs against the fetched `shapes.ttl`. The
  build script does not abort on validation failures; it writes the
  report and surfaces a summary line.
- **Federation / multi-wiki**: out of scope for this script. The IRIs
  the extractor mints use the LA3D base; federation would happen at the
  Fuseki layer if needed.

## Attribution

`build-graph.py` and `wiki-to-jsonld.py` are derived from prior work at
[`LA3D/llm-wiki-colab`](https://github.com/LA3D/llm-wiki-colab) (MIT).
File headers reference the source. They live here as local code, not as
a tracked upstream dependency, so they evolve with the template.
