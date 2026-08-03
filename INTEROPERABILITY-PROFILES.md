# UALF Interoperability Profiles

**Manifest profile:** `ualf-projection-manifest/v1`

**Status:** Draft v1.2 — 2026-08-03

UALF is the authoritative evidence record. Every interoperability artifact is a
derived, version-pinned projection with a manifest that binds source and output
digests, exporter identity, mappings, omissions, privacy policy, and validation
results. Projection success does not imply conformance or certification by the
external project.

## 1. OpenTelemetry GenAI and OTLP

**Profile identifier:** `ualf-otel-genai/v1`

**Target:** OpenTelemetry Semantic Conventions `1.43.0` plus the exact GenAI
semantic-conventions revision recorded by the projection manifest.

The exporter uses W3C-compatible 16-byte trace IDs and 8-byte span IDs. When a
UALF identifier does not already satisfy those constraints, it derives an ID as
the leading bytes of SHA-256 over the UTF-8 string and records the reversible
source-to-output mapping in the manifest. A collision aborts export.

### Resource mapping

| UALF | OpenTelemetry |
| --- | --- |
| `project` | `service.namespace` |
| `agent.framework` | `gen_ai.agent.framework` extension attribute |
| `agent.agent_version` | `service.version` |
| `environment.source_revision` | `vcs.ref.head.revision` where supported |
| `run_id` | `session.id` and `ualf.run.id` |
| `trajectory_id` | `ualf.trajectory.id` |

### Span and event mapping

- The run becomes a root internal span.
- Paired model calls become GenAI client spans using the target revision's
  inference-operation conventions.
- Paired tool calls become tool execution spans. Remote tool transports MAY add
  a nested client span.
- Decisions, observations, retries, file/state changes, feedback, and
  evaluations become span events unless a target convention defines a more
  specific span.
- Interrupted started calls close with error status and `ualf.incomplete=true`.
- `parent_span_id` maps to parent context; `caused_by` that is not a parent maps
  to a span link or a `ualf.caused_by` event attribute.

Raw prompts, messages, outputs, tool arguments, results, reasoning, images,
audio, and embeddings are opt-in. Default OTLP export contains hashes,
references, sizes, roles, and completeness states. Capture policy is applied
before span creation, not only at the collector.

Sampling applies to the root trace. The projection carries the sampling policy,
probability and decision but MUST NOT present a sampled or incomplete trace as a
complete UALF archive.

## 2. OpenInference

**Profile identifier:** `ualf-openinference/v1`

OpenInference is an optional semantic projection layered on OpenTelemetry. It
does not change UALF's source event types.

| UALF operation | `openinference.span.kind` |
| --- | --- |
| Agent run or delegated agent | `AGENT` |
| Model call | `LLM` |
| Tool call | `TOOL` |
| Retrieval observation | `RETRIEVER` |
| Guard or policy decision | `GUARDRAIL` |
| Evaluation | `EVALUATOR` |
| Prompt rendering | `PROMPT` |
| Unclassified workflow step | `CHAIN` |

Exact ordered UALF context maps to indexed OpenInference messages and content
parts. Tool definitions map to the advertised-tool attributes. A value that was
redacted, truncated, unavailable, or not captured remains explicitly so; the
exporter MUST NOT replace it with a value that appears complete.

## 3. OpenLineage

**Profile identifier:** `ualf-openlineage/v1`

UALF trace materialization and dataset qualification are represented as jobs;
each execution is a run. Source traces, blobs, quality reports, manifests,
analytical tables, and buyer exports are datasets identified by canonical URI
and digest.

- Inputs: source traces, referenced blobs, evaluation evidence and policy files.
- Outputs: signed UALF package and declared derived exports.
- Run facets: UALF profile, exporter version, parent run, source revision and
  terminal status.
- Dataset facets: digest, schema, rights classification, intended/prohibited
  uses, retention class and quality assertions.

Custom facets use the prefix `ualf` and an immutable schema URL. Assertion
`success` is independent from `severity`; advisory failures may coexist with a
successful qualification run but remain visible.

## 4. MLCommons Croissant

**Profile identifier:** `ualf-croissant/v1`

A Croissant export describes the qualified dataset, not the live logging store.
It includes:

- name, version, description, license and publisher;
- trace and analytical record sets;
- file objects with digests and encodings;
- field definitions and source mappings;
- provenance and transformation references;
- intended and prohibited uses;
- sensitive-data and retention disclosures; and
- links to the UALF datasheet, manifest and quality report.

The Croissant document is a discovery and loading aid. The signed UALF manifest
remains authoritative for membership, rights qualification, and integrity.

## 5. in-toto and DSSE

**Profile identifier:** `ualf-in-toto-qualification/v1`

The UALF dataset manifest digest becomes an in-toto Statement v1 subject. The
predicate type is the immutable URI for the UALF qualification predicate. The
predicate contains the dataset ID, UALF profile, quality-report digest, rights
status, intended/prohibited uses, qualification-tool version, validation time,
and signer role.

An implementation MAY sign the Statement through DSSE and MAY publish Sigstore
identity and transparency evidence. Consumers MUST verify both subject digest
and predicate policy. Systems requiring an attestation MUST fail closed when it
is absent; a valid signature does not prove that an expected attestation was
delivered.

## 6. Analytical and buyer projections

Parquet, SFT conversations, preference pairs, RL episodes and benchmark tasks
use the same projection manifest. A projection declares whether it is lossless,
which UALF semantics were omitted or flattened, how content filtering was
performed, and whether model-visible context remains complete.

## 7. Manifest requirements

`ualf-projection-manifest.schema.json` requires:

- exact source and target profile identifiers;
- source artifact digest and byte count;
- one or more output artifacts and digests;
- exporter name, version and source revision;
- deterministic ID and record mappings;
- omissions and loss classification;
- privacy transformation and capture-policy identifier;
- validator identity and result; and
- generation time.

Compatibility claims are scoped to the exact target revision recorded in the
manifest. A target revision change produces a new mapping profile and new
positive and negative conformance vectors.
