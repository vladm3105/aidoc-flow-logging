# UALF Production Capture and Lifecycle Profile

**Profile:** `ualf-capture/v1`

**Status:** Draft v1.2 — 2026-08-03

**Trace profiles:** `ualf-trace/v1` and later compatible revisions

This profile specifies how a live agent runtime records enough information to
determine whether a materialized UALF trace is complete. It does not replace the
trace. A capture report is operational evidence about sampling, buffering,
delivery, clock quality, privacy transformations, recovery, and closure.

## 1. Capture boundary

Redaction, omission, and truncation MUST occur before content crosses the first
persistence or network boundary that is not authorized to receive the original
content. A server-side redaction policy is insufficient when an untrusted server
has already received the value.

Each content category MUST have one controlled state:

- `captured`: retained without a known loss;
- `not_applicable`: the category did not exist for this run;
- `not_available`: the source did not expose it;
- `not_captured`: policy intentionally disabled capture;
- `redacted`: some or all content was replaced under a named policy;
- `truncated`: a deterministic size or count limit was applied;
- `capture_failed`: capture was required but failed; or
- `sampled_out`: the run was excluded by a declared sampling decision.

A placeholder MUST NOT be represented as complete content. Redacted and
truncated values SHOULD retain a digest of the pre-transformation value only
when the privacy policy permits it.

## 2. Sampling

Sampling decisions are made at the root trace. A retained trace MUST retain all
required child spans and events. Implementations MUST NOT retain arbitrary child
events, discard their ancestors, and then claim a complete trace.

The report records the decision, probability, policy and reason. A sampled-out
run MAY emit only a capture report and aggregate metrics. It MUST NOT be used as
complete-context training inventory.

Priority sampling MAY always retain errors, policy denials, human overrides,
high-cost calls, or explicitly selected cohorts. The policy and effective
probability MUST remain queryable to prevent biased performance analysis.

## 3. Durable delivery

Asynchronous capture MUST define:

- queue capacity and high-water mark;
- accepted and dropped record counts;
- retry count and terminal delivery failures;
- backoff policy;
- local spool or write-ahead-journal status;
- flush status and deadline; and
- collector acknowledgement or durable local commit boundary.

Short-lived processes MUST explicitly flush or durably spool accepted records.
A successful application exit is not evidence that asynchronous telemetry was
delivered.

Collector retries MUST be idempotent. The tuple `(run_id, event_id)` is the
default idempotency key. Collectors MUST reject conflicting content for the same
key and MAY accept byte-identical duplicates.

## 4. Ordering and clocks

Producers record both UTC wall time and a monotonic offset. The report identifies
the wall-clock source, synchronization method and maximum detected drift.

Collectors MAY receive records late or out of order. Materialization assigns a
gapless file sequence without treating that sequence as causality. Causality
continues to be expressed by spans and `caused_by`.

## 5. Recovery and closure

Live writers SHOULD checkpoint accepted events to a durable spool. Recovery
records the last durable event and whether any accepted records were lost.

The controlled recovery states are:

- `clean`: the run closed normally without a recovery attempt;
- `recovered`: a prior spool or checkpoint was resumed without known loss;
- `incomplete`: the run was recovered or closed with known or suspected loss;
- `abandoned`: the run could not be reconstructed; or
- `not_supported`: the implementation has no recovery mechanism.

A janitor MAY append an `aborted` outcome to an interrupted run. It MUST identify
itself as the closer and MUST NOT invent missing results. Known loss makes the
capture report incomplete even when the resulting JSONL is structurally valid.

## 6. Retention and erasure

The separate `ualf-retention/v1` document binds a trace or dataset digest to its
retention class, expiry, legal hold, encryption-key identity, erasure method, and
reference policy.

Qualified dataset packages MUST either:

1. copy and digest-pin every required artifact into the package; or
2. declare each external dependency, its availability commitment, retention
   deadline, and expected failure behavior.

An expired source object MUST NOT silently leave a dangling qualified-dataset
reference. Deletion and cryptographic erasure are recorded through signed
statements; immutable historical artifacts are not rewritten in place.

## 7. Conformance

`ualf-production-capture.schema.json` is the normative capture-report schema.
`ualf-retention.schema.json` is the normative retention-record schema. A conforming
implementation validates both syntax and the cross-document requirements above.
