# UALF Analytics, Storage, and SDK Profile

**Profile:** `ualf-analytics/v1`

**Status:** Draft v1.2 — 2026-08-03

UALF JSONL remains the authoritative interchange and evidence representation.
Indexes, compressed containers, database rows, and Parquet files are derived
views and MUST identify their source trace digest and transformation version.

This profile defines logical behavior and design requirements. It does not
select or ship a production database, archive, SDK package, dashboard, or
deployment topology.

## Storage architecture boundary

The approved design uses an immutable content-addressed object archive as the
canonical recovery, verification, replay, and export source. A SQL catalog,
ClickHouse-compatible hot analytical store, Parquet files, indexes, search
systems, and dashboards are derived projections that MUST be rebuildable from
canonical artifacts.

Replay, qualification, and audit verification MUST NOT depend on an analytical
database remaining available. SDKs write through one authenticated ingestion
path; they do not independently dual-write canonical and analytical stores. A
general-purpose NoSQL database is not required by the initial design, and no
specific storage product is normative.

## Logical analytical tables

The stable logical projection contains:

| Table | Grain |
| --- | --- |
| `traces` | One closed or interrupted run |
| `events` | One UALF event |
| `model_calls` | One paired or interrupted model call |
| `tool_calls` | One paired or interrupted tool call |
| `content_refs` | One content-addressed reference occurrence |
| `evaluations` | One original evaluation or amendment |
| `outcomes` | One terminal outcome |

Every row carries `source_trace_sha256`, `run_id`, `trace_id`, and the producing
projection version. Event-derived rows additionally carry `event_id`, `seq`,
`span_id`, `parent_span_id`, and `caused_by` where applicable.

Parquet exporters SHOULD use nested columns for structured values and MUST NOT
flatten arrays into delimiter-separated strings. Timestamps use UTC microseconds.
Decimal monetary amounts SHOULD use a decimal type rather than binary floating
point in analytical outputs.

## Index profile

`ualf-index/v1` provides header metadata, the exact source digest and byte count,
and per-record byte offsets and lengths. Readers MUST verify the source digest
before trusting offsets. The index is never included in the trace hash chain.

## Compact containers

A future compact container MAY combine compressed trace chunks, shared content
attachments, and indexes. It MUST preserve lossless reconstruction of the exact
authoritative JSONL bytes or explicitly declare itself a non-authoritative
analytical projection.

High-throughput implementations MAY use `ualf-segments/v1`, defined by
`ualf-segment-manifest.schema.json`. It binds ordered byte segments, record
ranges, exact source digest, duplicate-last SHA-256 Merkle root, external signing
identity, and an Ed25519-sealed canonical manifest. The example preserves exact
reconstruction and does not weaken or relabel the v1 exact-byte chain.

## SDK behavior

Python, TypeScript and Go SDKs SHOULD provide:

- typed event builders generated from the schemas;
- context propagation and span helpers;
- client-side capture policy enforcement;
- asynchronous buffering with durable-spool hooks;
- explicit flush and close operations;
- deterministic materialization;
- projection interfaces; and
- the shared positive and negative conformance vectors.

SDKs MUST surface dropped records and flush failures to the caller or an
independently monitored health signal. Silent loss is non-conforming.

The generated constants in this repository are a cross-language foundation,
not production runtime SDK packages. Runtime libraries, durable spool adapters,
and transport clients remain planned deliverables.

## Management analytics and cardinality

Management projections SHOULD support distinct views for platform health,
agent and model performance, quality and safety, commercial inventory, and
governance and cost. These views do not replace canonical evidence.

Metric labels MUST remain bounded. Environment, service, operation, model
family, tool class, outcome class, and policy version are suitable when their
value sets are governed. `run_id`, `trace_id`, `event_id`, prompt text, user
content, and raw error bodies MUST NOT be metric labels; they belong in logs,
traces, or high-cardinality analytical storage.

The management plane MUST expose its own health independently of the data path.
Detailed semantic conventions, SLO definitions, dashboards, alerts, and
watcher-canary contracts remain roadmap deliverables rather than implemented
parts of this profile.
