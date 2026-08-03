# UALF — Unified Agent Log Format

**Trace profile:** `ualf-trace/v1.1`

**Dataset profile:** `ualf-dataset/v1.2`

**Status:** Draft v1.3 — 2026-08-03

UALF is an operations-first event format for AI-agent debugging, testing,
performance analysis, activity tracing, and replay. A commercial dataset is a
qualified, immutable export of selected traces; it is not the live logging
format and it is not created merely by stamping a grade on a run.

This document specifies the format and its design requirements. It does not
claim that the production infrastructure described in the roadmap is already
implemented. Existing schemas and verifiers define current artifact
conformance; planned infrastructure contracts become normative only when their
profiles and schemas are published.

## 1. Architecture

```text
agent runtimes
    -> operational event store (UALF Trace)
       -> debugging / tests / performance / replay
       -> dataset materializer
          -> rights + hygiene + completeness + evidence checks
          -> immutable signed package (UALF Dataset)
          -> buyer-specific SFT / preference / RL / benchmark exports
```

The trace profile answers: **what happened?** The dataset profile additionally
answers: **is the trace complete, rights-cleared, independently evidenced, and
fit for a declared downstream use?**

## 2. Trace file model

One closed trace is one UTF-8 JSONL file:

```text
line 1        header
lines 2..n-1  events
line n        outcome
```

Every physical line MUST contain exactly one JSON object. Blank lines, byte-order
marks, invalid UTF-8, partial lines, and trailing content are invalid. The header
has `seq: 1`; all following records form a gapless sequence. A materialized trace
MAY be hash-chained and signed. Live systems MAY buffer or index events before
closure, but the canonical immutable archive described in the roadmap remains
the recovery and replay authority after materialization.

### 2.1 Common event envelope

Every event contains:

| Field | Meaning |
| --- | --- |
| `kind` | `event` |
| `seq` | Gapless file sequence |
| `event_id` | Unique event identifier within the run |
| `organization` | Security and ownership scope |
| `project` | Project scope |
| `deployment_environment` | Lifecycle environment |
| `run_id` | Run correlation |
| `trace_id` | Distributed-trace correlation |
| `session_id` | Agent-session correlation |
| `conversation_id` | Optional conversation correlation |
| `turn_id` | Optional user-turn correlation |
| `span_id`, `parent_span_id` | Nested/parallel operation correlation |
| `caused_by` | Optional prior `event_id` that caused this event |
| `actor` | Agent, human, system, tool, or evaluator identity |
| `producer` | Producer, process, clock domain, and producer-local sequence |
| `timestamp` | Producer event time as a UTC RFC 3339 timestamp |
| `observed_at` | Collector or materializer observation time |
| `monotonic_ms` | Producer-local offset in its declared clock domain |
| `type` | Discriminated event type |
| `data` | Strict type-specific payload |
| `prev_sha256` | Exact-byte hash of the preceding physical line |

`seq` expresses deterministic materialization order. Causality is expressed by
spans and `caused_by`; consumers MUST NOT infer causality from sequence, wall
time, observation time, or offsets from different clock domains alone. Within a
producer clock domain, `producer.local_seq` is unique and increasing.

### 2.2 Core event types

- `agent.started` / `agent.completed`
- `delegation.started` / `delegation.completed`
- `agent_message.sent` / `agent_message.received`
- `guardrail.evaluated`, `retrieval.completed`, and `memory.accessed`
- `model_call.started` / `model_call.completed`
- `tool_call.started` / `tool_call.completed`
- `observation.received`
- `decision.recorded`
- `file_change.recorded` / `state_change.recorded`
- `error.recorded` / `retry.started`
- `human_feedback.recorded`
- `evaluation.completed`

Model and tool started/completed pairs share a `call_id`; agent and delegation
pairs share an `activity_id`. Every closed trace contains exactly one terminal
completion for every start. The completion follows its matching start, uses the
same span, and preserves the call or agent identity. Terminal
status is `ok`, `error`,
`cancelled`, `timed_out`, or `interrupted`. A recovery janitor emits
`interrupted` and identifies itself; it MUST NOT invent usage, cost, output, or
latency. An unexplained missing completion is non-conforming capture loss.

## 3. Header

The header identifies the run and captures immutable configuration:

- organization, project, deployment environment, domain, stable agent identity,
  agent version, and prompt version;
- task goal, category, acceptance criteria, and work order;
- environment fingerprint and source revision;
- the complete tool-definition snapshot or a resolvable reference;
- capture policy, redaction policy, and content retention mode;
- replay artifacts and capability level;
- signing identity for a materialized trace;
- ownership/source classification used later by dataset qualification.

Tool-definition hashes alone are insufficient for training or replay. The actual
definitions MUST be present inline or resolvable through a blob reference.

## 4. Content-addressed references

Large values and segregated content use strict references:

```json
{
  "$ref": "sha256:<64 lowercase hex characters>",
  "bytes": 1234,
  "media_type": "application/json",
  "encoding": "identity",
  "content_role": "model_output",
  "origin": {"type": "model", "source": "provider/model-id"}
}
```

Required fields are `$ref`, `bytes`, `media_type`, `encoding`, `content_role`, and
`origin`. The verifier checks the filename, digest, byte count, media type where
machine-detectable, and role-specific provenance.

Reference positions use role-specific schema types: for example, `tools_ref`
accepts only `tool_definitions`, model completion accepts only `model_output`,
and evaluator evidence accepts only `evidence`. Inline values use
`{"value": ..., "origin": ...}` so provenance is never lost merely because a
small value was embedded instead of placed in the blob store. Encodings are
`identity` and `gzip`; encoded bytes are decoded and validated rather than
accepted by label alone.

Content roles include:

- `authored_prompt`, `model_input`, `model_output`, `model_reasoning`;
- `tool_output`, `observation`, `diff`, `evidence`;
- `initial_state`, `tool_definitions`, `artifact`, `human_content`.

Model-generated roles require `origin.type: model` and a provider/model source.
This makes a model-text-filtered export deterministic. Redaction or truncation
MUST be explicit in the surrounding event and MUST NOT be represented by a
placeholder that appears complete.

## 5. Exact model-visible context

Each completed model call records:

- provider, model, terminal status, parameters, usage, cost, and latency;
- a `context` array in exact presentation order;
- role (`system`, `developer`, `user`, `assistant`, `tool`), content reference,
  and optional name/tool-call identifier for every context item;
- the exact tool-definition snapshot used for that call;
- output reference or explicit `no_output: true`;
- finish reason and request/response identifiers when available.

Unavailable usage or cost is represented by `usage_state` or `cost_state`; zero
MUST mean a measured zero rather than unknown. Failed terminal calls carry a
structured error and explicit `no_output: true`. File and state changes use an
operation of `create`, `modify`, or `delete`; absent pre- or post-state is JSON
`null` only where that operation makes it inapplicable.

A summary such as "system prompt + task context" is not complete context. If
policy prevents retention, the call is marked `context_complete: false` with a
controlled reason. Such traces remain operationally useful but cannot qualify as
complete-context training inventory.

## 6. Outcomes and evaluation

The outcome reports what happened; it does not self-assign commercial quality:

```json
{
  "kind": "outcome",
  "status": "success",
  "evaluations": [
    {
      "evaluator": "pytest",
      "method": "oracle:test",
      "status": "passed",
      "evidence_ref": {"$ref": "sha256:..."}
    }
  ],
  "totals": {},
  "seal": {}
}
```

Totals are derived from events and checked by the verifier. Evidence is
classified as `self_report`, `artifact`, `signed_external`, or `reproduced`.
A signature over the trace proves integrity and signer identity; it does not by
itself prove that an asserted test, trade, or external action occurred.

Aborted runs close with `status: aborted`; they can conform as traces. Dataset
qualification separately decides whether they are useful failure inventory.

## 7. Replay capability

Replay is a verified capability level, not a Boolean:

| Level | Meaning |
| --- | --- |
| `none` | No replay material |
| `trace` | Activity can be inspected in order |
| `stubbed` | Recorded model/tool responses can be replayed |
| `tool_reexecution` | Tools can be rerun from restored initial state |
| `full_reexecution` | Model and tool calls can be rerun |
| `outcome_reproduced` | Reexecution was attempted and the outcome matched |

The header records the available level, state snapshot, captured nondeterministic
inputs, and the latest replay-verification result. A quality report MUST NOT claim
a level higher than the artifacts and verification support. Levels above `trace`
require a successful verification record with evidence and a matching result;
tool reexecution and stronger levels also require initial state and captured
nondeterministic inputs.

## 8. Integrity

For an immutable trace:

1. Every event/outcome `prev_sha256` is SHA-256 of the previous physical line's
   exact UTF-8 bytes excluding the line terminator.
2. `seal.chain_sha256` is SHA-256 of RFC 8785 JCS bytes for the outcome with
   `seal` absent.
3. Ed25519 signs the 32 raw bytes represented by `chain_sha256`.
4. Header and seal key ID and algorithm MUST match.
5. Public keys and signatures use strict, padded standard Base64.

Hash chaining and signing are mandatory for `ualf-dataset/v1.2` exports and
optional for an unmaterialized live trace. HMAC is not an exportable signature.

## 9. Dataset profile

A dataset package contains:

```text
manifest.json
quality-report.json
traces/*.jsonl
blobs/<sha256>
datasheet.md
datasheet.json
evidence/*.json
```

`manifest.json` declares dataset ID, trace schema, creation time, export profile,
intended uses, prohibited uses, splits, trace IDs, licenses, rights summary,
deduplication, and quality-report digest. Paths MUST be contained normalized
relative paths. Tar members MUST reject absolute names, parent traversal, links,
devices, and unsupported member types. The manifest inventories every referenced
blob and MUST NOT omit or silently add package blobs. Each trace entry binds its
capture evidence or explicit synthetic origin, amendment-stream head and cutoff,
retention policy, revocation state, signed hygiene evidence, signed replay
evidence, and declared external dependencies.

The manifest is canonically hashed with RFC 8785 (with `seal` absent) and signed
with Ed25519. This dataset-level seal binds trace membership, splits, rights and
quality artifacts, blob inventory, and intended-use metadata. Every manifest
trace MUST be independently schema- and integrity-verified; verifying one sample
trace is not dataset verification.

`quality-report.json` contains independently derived dimensions. Rights,
hygiene, and replay status count as verified only when their signed evidence
documents pass schema, digest, signature, authority, subject, and policy checks:

- `schema_valid`
- `integrity_verified`
- `context_completeness`
- `evidence_quality`
- `replay_quality`
- `rights_status`
- `hygiene_status`
- `export_eligible`
- optional derived `commercial_tier`

The package also includes a machine-readable datasheet covering collection,
composition, transformations, privacy and rights, quality, limitations, and
revocation maintenance. Qualification records exact and near-duplicate methods,
benchmark contamination, and semantic split leakage. `not_run` is never treated
as equivalent to no findings.

The commercial tier is a view over these dimensions, never a value chosen by the
agent. Under `ualf-default-qualification/v1`, the verifier recomputes every
quality row from trace facts plus the dataset rights status and rejects stamped
values that differ. Buyers can apply their own tier function.

## 10. Validation levels

UALF validation reports three independent levels:

1. **Schema:** types, required fields, discriminated payloads, and closed objects.
2. **Trajectory:** ordering, call pairing, causality, references, totals, hashes,
   blobs, signatures, and cross-record consistency.
3. **Qualification:** context completeness, replay evidence, rights, hygiene,
   objective evidence, deduplication, and declared downstream use.

Base validation is domain-neutral. Domain plugins validate CI attestations, test
reports, P&L records, policy checks, or other oracle evidence.

## 11. External standards and audit projections

UALF SHOULD interoperate with established identifiers, timestamps,
canonicalization rules, distributed-tracing context, and audit transports where
that does not weaken its operational semantics. Compatibility is expressed as a
versioned projection from a closed UALF trace, not by relabeling UALF fields or
discarding its source artifacts.

The informative `AAT-COMPATIBILITY.md` profile targets
`draft-sharif-agent-audit-trail-00`. It defines a one-way audit projection,
controlled compatibility claims, privacy transformation, integrity separation,
and mappings for lifecycle, tool, decision, delegation, escalation, error, and
human-intervention records.

An export claim requires a source-context document conforming to
`ualf-aat-source.schema.json`. A validation claim additionally requires AAT JSONL
that passes `aat-draft-00.schema.json` and a signed transformation manifest that
passes `ualf-aat-export-manifest.schema.json`. The exact claim strings include
the complete Internet-Draft identifier.

The AAT target is an individual IETF Internet-Draft and work in progress. A UALF
implementation MUST identify the exact target version and MUST NOT describe the
draft as an IETF standard, IETF endorsement, or proof of regulatory compliance.
The UALF trace remains authoritative for debugging, replay, evaluation, and
dataset qualification because the AAT projection intentionally removes content
and UALF-only semantics.

## 12. Extensions and compatibility

Objects are closed by default. Extensions live only under an `extensions` object
whose keys use a namespaced form such as `example.com/feature`. A consumer may
preserve unknown extensions but MUST NOT interpret them as base-profile fields.

`aidoc-traj/v1` was an experimental draft and is not wire-compatible with
`ualf-trace/v1`. Projects SHOULD migrate before production capture rather than
carry ambiguous compatibility behavior.

The machine-readable extension registry and its lifecycle rules are defined by
`EXTENSIONS-AND-EVOLUTION.md` and `ualf-extension-registry.schema.json`.

## 13. Production capture evidence

A structurally valid closed trace does not prove that the live producer retained
everything it accepted. Production implementations SHOULD emit a separate
`ualf-capture/v1.1` report conforming to
`ualf-production-capture.schema.json`. The report binds the run to:

- root-trace sampling decision, probability, policy, and reason;
- granular content states;
- privacy-transformation boundary;
- accepted, delivered, retried, and dropped record counts;
- queue, spool, flush, and terminal delivery status;
- clock sources and detected drift;
- checkpoint and recovery status; and
- a controlled completeness claim.

Sampling is performed at root-trace scope. A sampled or lossy trace MUST NOT be
called complete merely because the records that remain form valid JSONL. The
normative lifecycle rules are in `PRODUCTION-CAPTURE-AND-LIFECYCLE.md`.

## 14. Post-run amendments

Sealed traces are never rewritten to add human review, user feedback, improved
scoring, or corrected evaluator results. Post-run information is stored in a
separate `ualf-amendments/v1` JSONL stream:

```text
line 1        amendment_header
lines 2..n-1  amendments
line n        amendment_seal
```

Every amendment identifies its target, source, evaluator and version, rubric and
version, typed result, severity, confidence, evidence, and optional prior
amendment that it supersedes. Supersession preserves the historical record; it
does not delete or mutate it.

Each amendment and the terminal seal contains the exact-byte SHA-256 digest of
the previous physical line. `chain_sha256` is SHA-256 of RFC 8785 JCS bytes for
the terminal seal with `chain_sha256` and `signature` absent. Ed25519 signs the
32 raw digest bytes. The signing key includes an external registry URI and may
include validity bounds. `ualf-amendment.schema.json` is normative.

Execution success and evaluation success are independent. Severity records the
consequence of an evaluation failure; an advisory failure can coexist with a
successful run.

## 15. Retention and erasure

`ualf-retention/v1.1` binds an immutable subject digest to its retention class,
expiry, legal-hold status, artifact dependency mode, encryption-key identity,
erasure method, and dangling-reference behavior. Qualified packages are
self-contained or explicitly declare externally pinned dependencies and their
availability commitments.

Deletion or cryptographic erasure is recorded with a signed external statement.
It does not rewrite a sealed trace. Embedded public keys prove signature
consistency but not organizational authority; production keys MUST be resolved
through an independently governed registry with rotation and revocation.
Capture and retention records are themselves canonically hashed and Ed25519
sealed. Erasure or revocation actions conform to
`ualf-erasure-statement/v1` and expose propagation across every declared copy.

## 16. Interoperability projections

`INTEROPERABILITY-PROFILES.md` defines projections for:

- OpenTelemetry GenAI and OTLP;
- OpenInference;
- OpenLineage;
- MLCommons Croissant;
- in-toto Statement v1 and optional DSSE/Sigstore envelopes; and
- analytical and buyer-specific formats.

Every projection conforms to `ualf-projection-manifest/v1`, pins the target
revision, binds source and output digests, records mappings and omissions, and
declares its privacy transformation and loss class. No projection replaces the
authoritative UALF source artifact.

## 17. Analytics, indexing, and SDKs

Parquet tables, database rows, indexes, and compact containers are derived
artifacts. `ualf-index/v1` supplies digest-bound byte offsets for random access.
The stable logical analytical tables and cross-language SDK requirements are
defined in `ANALYTICS-AND-SDKS.md`.

The `ualf-segments/v1` profile improves highly concurrent archival while
preserving exact reconstruction. It uses a distinct identifier and MUST NOT
weaken or relabel the v1 exact-byte chain.

## 18. Infrastructure design requirements

The approved infrastructure direction separates capture, authoritative storage,
and derived query systems:

- a shared SDK and local durable spool feed one authenticated ingestion path;
- one logical authoritative artifact set per security and lifecycle boundary is
  the canonical recovery, verification, replay, and export source; it may use
  replicated or physically separate object archives;
- SQL catalogs, ClickHouse-compatible analytical stores, Parquet tables,
  indexes, search systems, and dashboards are rebuildable derived views;
- SDKs and agents do not dual-write independently to archive and analytical
  stores;
- durable acceptance has an explicit receipt boundary, and retries use stable
  idempotency keys with conflict rejection;
- organization, project, and environment are mandatory logical isolation
  dimensions, with separate development, staging, and production boundaries;
- deduplication is restricted to declared privacy and lifecycle boundaries, and
  knowledge of a content digest never implies authorization; and
- dedicated deployments are available when residency, customer isolation,
  regulated operation, scale, or contractual controls require them.

The design does not require a general-purpose NoSQL database in the initial
platform. Product choices are non-normative unless a future profile explicitly
binds behavior to one. Storage manifests, ingestion receipts, deployment
profiles, and their conformance vectors are planned artifacts; their absence
from this draft MUST NOT be interpreted as an implementation claim.

## 19. Management-plane design requirements

The management plane is operationally independent from the data path it
observes. Its design covers five distinct views: platform operations; project
and agent performance; capture quality and data integrity; privacy, retention,
access, and security; and dataset readiness and commercial inventory.

Each critical hop reports positive progress as well as negative, stalled, and
absent states. A harmless signed far-end canary traverses the real path through
archive, catalog, analytics, and replay and validates an expected replay result.
An independent watchdog checks that the monitoring path itself is alive.
Durable internal alert records preserve evidence; external paging remains a
separate delivery path.

Metric labels MUST be bounded. High-cardinality identifiers such as `run_id`,
`trace_id`, `event_id`, prompt text, and error bodies belong in logs, traces, or
analytical stores rather than metric dimensions. Privileged management actions
and policy changes require attributable, tamper-evident audit records.

UALF standardizes SLO measurement semantics while deployment profiles select
targets. Detailed semantic conventions, SLO definitions, alert rules,
dashboards, and management audit schemas remain roadmap deliverables. This
section establishes design requirements without presenting those future
artifacts as implemented.

## 20. Versioning, conformance, and governance

UALF profile identifiers are immutable contracts. `ualf-trace/v1` and
`ualf-dataset/v1.1` remain historical profiles; the call-lifecycle, distributed
clock, tenancy, and evidence changes in this draft use `ualf-trace/v1.1` and
`ualf-dataset/v1.2`. Producers MUST NOT emit new semantics under an older
identifier.

Schemas use versioned immutable `$id` paths. Normative precedence is: the named
profile schema for structural rules, this document for cross-record semantics,
and `AGENT-LOG-DATASET-REQUIREMENTS.md` for deployment and qualification
requirements. A conflict is a specification defect and validators MUST fail
closed until a published erratum resolves it. Conformance classes and release
rules are defined in `CONFORMANCE.md` and `SPECIFICATION-GOVERNANCE.md`.
