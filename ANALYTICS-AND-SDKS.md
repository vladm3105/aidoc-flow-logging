# UALF Analytics, Storage, and SDK Profile

**Profile:** `ualf-analytics/v1`

**Status:** Draft v1.2 — 2026-08-03

UALF JSONL remains the authoritative interchange and evidence representation.
Indexes, compressed containers, database rows, and Parquet files are derived
views and MUST identify their source trace digest and transformation version.

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
