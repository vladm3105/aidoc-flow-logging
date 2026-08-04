# Frozen UALF Projection to the Agent Audit Trail Internet-Draft

**Status:** Frozen, optional, informative projection

**Target:** `draft-sharif-agent-audit-trail-00`  
**Target date:** 2026-03-29  
**UALF source profile:** `ualf-trace/v1.1`

## 1. Status and scope

The Agent Audit Trail (AAT) document is an individual IETF Internet-Draft. It is
work in progress, is not endorsed by the IETF, and has no formal standing in the
IETF standards process. This profile therefore pins every compatibility claim to
`draft-sharif-agent-audit-trail-00`. This repository does not track later AAT
revisions and makes no commitment to implement them. A later draft is a
different target and MUST NOT silently change this frozen profile.

UALF is the authoritative, operations-first source record. An AAT document is a
privacy-minimized audit projection derived from a closed UALF trace:

```text
UALF trace
    -> debugging, testing, evaluation, replay, and dataset qualification
    -> version-pinned AAT audit projection
       -> customer-requested historical audit integrations (non-certifying)
```

This profile does not make AAT the UALF wire format. It does not claim that AAT
publication, UALF conformance, or this mapping proves compliance with any law,
certification program, or management-system standard.

The profile is retained for reproducible historical exports and for buyers or
integrators that explicitly request this exact draft target. It is not part of
UALF base-profile conformance, and an implementation MAY omit it entirely.
`projection-target-catalog.json` is the machine-readable authority for this
target's source profile, lifecycle, optionality, claims, and maintenance scope.

### 1.1 Concepts incorporated into UALF

UALF has independently incorporated the useful general design ideas evaluated
through the AAT review: explicit agent and session identity, lifecycle and
action classification, outcome tracking, tamper-evident chains, signed export
evidence, privacy-minimized audit projections, retention and erasure records,
and exact-version compatibility claims. Their UALF definitions are authoritative
and do not depend on continued AAT compatibility.

## 2. Compatibility claims

Implementations MUST use one of these precise, fully scoped claims:

- `aat-exported/draft-sharif-agent-audit-trail-00`: a closed, verified UALF
  trace and valid AAT source-context document were transformed into AAT JSONL
  using this profile.
- `aat-validated/draft-sharif-agent-audit-trail-00`: the exported AAT JSONL and
  signed transformation manifest passed `verify_aat.py` or an equivalent
  validator pinned to the exact draft.

`AAT compliant`, `IETF compliant`, and `IETF standard` MUST NOT be used for this
Internet-Draft. A validation claim MUST identify the exporter version, validator
version, source trace digest, exported artifact digest, and transformation time.

## 3. Standards alignment

The compatibility projection preserves or derives these established building
blocks where applicable:

| Standard | Use |
| --- | --- |
| RFC 3339 | UTC wall timestamps |
| RFC 5424 | Optional Syslog transport for the AAT projection |
| RFC 8785 | AAT JSON canonicalization and record chaining |
| RFC 9562 | UUIDv4 record and session identifiers required by draft-00 |

W3C Trace Context correlation is not claimed by this profile. A future profile
may define it only after specifying exact conversion and validation rules for
UALF identifiers.

UALF's exact-byte SHA-256 chain and Ed25519 trace seal remain authoritative for
the UALF artifact. An AAT exporter builds a separate RFC 8785 chain and, when
configured, separate ECDSA P-256 signatures. It MUST NOT relabel one integrity
mechanism as the other.

## 4. Required export context

Before export, the producer MUST provide a document conforming to
`ualf-aat-source.schema.json`. It resolves:

- a persistent agent URI for AAT `agent_id`;
- a semantic agent version;
- a UUIDv4 AAT `session_id` and UUIDv4 for each exported record;
- a trust-level assertion and the authority that produced it;
- mappings from UALF outcomes and errors to the AAT controlled vocabularies;
- a privacy policy governing hashing, pseudonymization, and external content;
- an optional P-256 signing identity when AAT record signatures are emitted.

Missing required context makes the trace non-exportable under this profile. An
exporter MUST NOT invent a trust level, jurisdiction, authorization mechanism,
risk score, human identity, or regulatory classification.

The trust assertion records its authority, basis, assertion time, and optional
evidence reference. `L0` is used only when the source context explicitly asserts
that no cryptographic identity was verified; it is not an implicit default.

## 5. Record mapping

Export occurs after trace closure so paired operations and their final outcomes
are known. The exporter creates a new linear AAT record sequence and records a
mapping from every AAT `record_id` to its source UALF record or records.

- Header -> `lifecycle/session_start`: hash configuration and enabled tools; do
  not expose retained content.
- `tool_call.started` -> `tool_call`: hash canonical arguments and derive its
  outcome only after pairing. Map `ok` to `success`, policy rejection to
  `denied`, deadline exhaustion to `timeout`, and all other terminal errors to
  `failure`.
- `tool_call.completed` -> `tool_response`: link to the exported call record and
  hash the response or structured error.
- `decision.recorded` -> `decision`: map option count and hash retained rationale
  when policy permits. Use `success` only for a completed decision;
  policy-blocked and escalated decisions use `denied` and `escalated`.
- Model start/completion pair: enrich a linked `decision` with `model_id`, input
  and output hashes, cost, and latency. A model call without a decision has no
  lossless AAT draft-00 action type and MUST NOT be misclassified.
- `error.recorded` -> `error`: map category and recoverability through a
  documented policy. Its outcome is `timeout` for timeout errors and `failure`
  otherwise.
- `human_feedback.recorded` -> `human_override` only when it records an actual
  intervention. Use `escalation` only when the UALF event documents an
  escalation; otherwise preserve the feedback only in UALF. Escalation records
  use outcome `escalated`.
- `delegation.started` / `delegation.completed` -> `delegation`: require the
  delegate URI, trust
  assertion, task-description hash, and `child_session_id`. A completed handoff
  uses `success`; a refused handoff uses `denied`; failures use `failure`.
- Outcome -> `lifecycle/session_end`: map final status and derive AAT session
  summary fields. Map UALF `success` to `success`; cancellation or policy blocks
  to `denied`; time limits to `timeout`; and every other unsuccessful terminal
  state to `failure`.

UALF observations, agent messages, guardrail evaluations, retrieval and memory
events, file changes, state changes, retries, evaluations, replay evidence, and
dataset qualification have no lossless draft-00 equivalent. The
exporter MUST retain their UALF source and MUST document whether they were
summarized, hashed into another record, or omitted.

## 6. Privacy transformation

AAT draft-00 prohibits raw inputs, outputs, tool parameters, responses, and
reasoning in audit records. The exporter therefore applies these exact rules:

1. resolves the exact UALF inline value or content-addressed artifact;
2. decodes `identity` or `gzip` content encoding before hashing;
3. hashes JSON values as RFC 8785 JCS bytes, text as exact UTF-8 bytes without
   Unicode or newline normalization, and other media as decoded octets;
4. encodes SHA-256 as 64 lowercase hexadecimal characters;
5. writes only the AAT hash and permitted metadata;
6. keeps the UALF content in a separately controlled system when retention is
   allowed; and
7. records the source content digest in the transformation manifest.

Hashing is pseudonymization, not anonymization. Low-entropy inputs can be guessed
and hashes can remain personal data. They remain subject to access, retention,
and erasure controls.

Because the projection discards content and UALF-only event semantics, AAT to
UALF round trips are impossible. An AAT export MUST NOT replace the source UALF
trace for replay, debugging, evaluation, or dataset qualification.

## 7. Concurrency and causality

UALF represents parallel operations with spans, parent spans, and causal event
references. AAT draft-00 permits only a linear chain and directs parallel paths
to separate sessions.

An exporter MUST apply a deterministic policy:

- serialize events only when doing so preserves their meaning; or
- create a child AAT session for each parallel branch and emit a delegation
  record from the parent session.

The transformation manifest MUST retain the UALF trace, span, parent-span, and
causal identifiers so an auditor can reconstruct the richer source graph.

Every export MUST conform to `ualf-aat-export-manifest.schema.json`. The manifest
binds the source trace and context, exporter and validator versions, generated
UUID mappings, omissions, hashing policy, trust authority, signing-key binding,
UALF terminal seal, AAT session hashes, and exported artifact digest. It is
canonicalized with RFC 8785 and sealed with Ed25519.

A new export generates fresh UUIDv4 values. Reproduction of an existing export
MUST reuse the stored JSONL and signed manifest; rerunning an exporter without
the original mapping creates a new export instance and MUST NOT claim identical
artifact reproduction.

## 8. Integrity and deletion

The UALF trace and AAT projection are independently verifiable artifacts. Their
digests and signatures MUST be stored together in the transformation manifest.

UALF immutable traces and dataset packages MUST NOT be rewritten in place to
implement an AAT tombstone. Sensitive or personal content MUST NOT be retained
inline unless it is encrypted with separately erasable keys. Deployments SHOULD
use content-addressed, access-controlled encrypted artifacts so erasure can use
deletion or cryptographic shredding. A signed redaction or deletion statement
records the action. An AAT tombstone projection MAY be produced
only when the implementation documents and validates the draft-00 chain-break
exception; it does not retroactively modify the UALF source artifact.

## 9. Frozen support and re-evaluation

The draft-00 mapping is isolated from the base UALF schema. Implementations SHOULD
place optional source metadata under a namespaced UALF extension such as
`iplanic.ai/aat/draft-sharif-agent-audit-trail-00` until fields demonstrate stable,
general operational value.

Maintenance of this profile is limited to security fixes, verifier correctness,
and preservation of deterministic behavior for `ualf-trace/v1.1` against the
pinned draft-00 text. Later AAT or UALF revisions do not create implementation
work for this projection, and future UALF profiles are not required to export to
AAT.

A behavior-preserving implementation fix MUST increment the affected component
version and record the change. A fix that changes schemas, mapping semantics, or
the accepted artifact set MUST use a new projection identifier or withdraw the
affected claim; it MUST NOT silently redefine this frozen target.

Maintainers MAY propose a new, separately versioned target only after an explicit
governance decision triggered by at least one of these conditions:

1. adoption by an IETF working group or publication as an RFC;
2. material customer, buyer, or ecosystem demand;
3. a demonstrated interoperability requirement not met by UALF or another
   maintained projection; or
4. a security or regulatory development that makes a new target materially
   useful.

Approval of a new target requires a new profile identifier, mapping and
behavior-change report, positive and negative conformance vectors, and an
explicit maintenance owner. The frozen draft-00 exporter remains available for
reproducible historical audits unless a security issue requires withdrawal.

The supplied `aat-draft-00.schema.json` and `verify_aat.py` additionally enforce
UUIDv4 syntax, required action fields, monotonic timestamps, the 256 KB hard
record limit and 64 KB recommendation, linear chains, session closure and
summary hashes, privacy-prohibited raw fields, manifest mappings and digests,
and manifest signatures. Positive and negative vectors live in the example
artifacts and `tests/test_verify.py`.

## 10. References

- [IETF Datatracker status page](https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/)
- [Agent Audit Trail draft-00](https://www.ietf.org/archive/id/draft-sharif-agent-audit-trail-00.html)
- [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339)
- [RFC 5424](https://www.rfc-editor.org/rfc/rfc5424)
- [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)
- [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
