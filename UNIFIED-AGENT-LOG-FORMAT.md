# UALF — Unified Agent Log Format

**Trace profile:** `ualf-trace/v1`  
**Dataset profile:** `ualf-dataset/v1.1`  
**Status:** Draft v1.1 — 2026-08-02

UALF is an operations-first event format for AI-agent debugging, testing,
performance analysis, activity tracing, and replay. A commercial dataset is a
qualified, immutable export of selected traces; it is not the live logging
format and it is not created merely by stamping a grade on a run.

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
MAY be hash-chained and signed. Live systems MAY first write events to a database
and materialize the immutable file after closure.

### 2.1 Common event envelope

Every event contains:

| Field | Meaning |
| --- | --- |
| `kind` | `event` |
| `seq` | Gapless file sequence |
| `event_id` | Unique event identifier within the run |
| `run_id`, `trace_id` | Run and distributed-trace correlation |
| `span_id`, `parent_span_id` | Nested/parallel operation correlation |
| `caused_by` | Optional prior `event_id` that caused this event |
| `actor` | Agent, human, system, tool, or evaluator identity |
| `timestamp` | UTC RFC 3339 timestamp |
| `monotonic_ms` | Milliseconds from run start |
| `type` | Discriminated event type |
| `data` | Strict type-specific payload |
| `prev_sha256` | Exact-byte hash of the preceding physical line |

`seq` expresses serialization order. Causality is expressed by spans and
`caused_by`; consumers MUST NOT infer causality from sequence alone.

### 2.2 Core event types

- `model_call.started` / `model_call.completed`
- `tool_call.started` / `tool_call.completed`
- `observation.received`
- `decision.recorded`
- `file_change.recorded` / `state_change.recorded`
- `error.recorded` / `retry.started`
- `human_feedback.recorded`
- `evaluation.completed`

Started/completed pairs share a `call_id`. A missing completion is observable as
an interrupted operation rather than an invented latency or result.

## 3. Header

The header identifies the run and captures immutable configuration:

- project, domain, agent identity, agent version, and prompt version;
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

- provider, model, parameters, usage, cost, and latency;
- a `context` array in exact presentation order;
- role (`system`, `developer`, `user`, `assistant`, `tool`), content reference,
  and optional name/tool-call identifier for every context item;
- the exact tool-definition snapshot used for that call;
- output reference or explicit `no_output: true`;
- finish reason and request/response identifiers when available.

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

Hash chaining and signing are mandatory for `ualf-dataset/v1.1` exports and
optional for an unmaterialized live trace. HMAC is not an exportable signature.

## 9. Dataset profile

A dataset package contains:

```text
manifest.json
quality-report.json
traces/*.jsonl
blobs/<sha256>
datasheet.md
```

`manifest.json` declares dataset ID, trace schema, creation time, export profile,
intended uses, prohibited uses, splits, trace IDs, licenses, rights summary,
deduplication, and quality-report digest. Paths MUST be contained normalized
relative paths. Tar members MUST reject absolute names, parent traversal, links,
devices, and unsupported member types. The manifest inventories every referenced
blob and MUST NOT omit or silently add package blobs.

The manifest is canonically hashed with RFC 8785 (with `seal` absent) and signed
with Ed25519. This dataset-level seal binds trace membership, splits, rights and
quality artifacts, blob inventory, and intended-use metadata. Every manifest
trace MUST be independently schema- and integrity-verified; verifying one sample
trace is not dataset verification.

`quality-report.json` contains independently derived dimensions:

- `schema_valid`
- `integrity_verified`
- `context_completeness`
- `evidence_quality`
- `replay_quality`
- `rights_status`
- `hygiene_status`
- `export_eligible`
- optional derived `commercial_tier`

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

## 11. Extensions and compatibility

Objects are closed by default. Extensions live only under an `extensions` object
whose keys use a namespaced form such as `example.com/feature`. A consumer may
preserve unknown extensions but MUST NOT interpret them as base-profile fields.

`aidoc-traj/v1` was an experimental draft and is not wire-compatible with
`ualf-trace/v1`. Projects SHOULD migrate before production capture rather than
carry ambiguous compatibility behavior.
