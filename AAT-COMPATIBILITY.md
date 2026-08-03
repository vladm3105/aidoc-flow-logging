# UALF Compatibility with the Agent Audit Trail Internet-Draft

**Status:** Informative compatibility profile  
**Target:** `draft-sharif-agent-audit-trail-00`  
**Target date:** 2026-03-29  
**UALF source profile:** `ualf-trace/v1`

## 1. Status and scope

The Agent Audit Trail (AAT) document is an individual IETF Internet-Draft. It is
work in progress, is not endorsed by the IETF, and has no formal standing in the
IETF standards process. This profile therefore pins every compatibility claim to
`draft-sharif-agent-audit-trail-00`. A later AAT draft is a different target and
MUST be reviewed before a producer updates its claim.

UALF is the authoritative, operations-first source record. An AAT document is a
privacy-minimized audit projection derived from a closed UALF trace:

```text
UALF trace
    -> debugging, testing, evaluation, replay, and dataset qualification
    -> version-pinned AAT audit projection
       -> regulatory review and conventional audit-log integrations
```

This profile does not make AAT the UALF wire format. It does not claim that AAT
publication, UALF conformance, or this mapping proves compliance with any law,
certification program, or management-system standard.

## 2. Compatibility claims

Implementations MUST use one of these precise claims:

- `aat-aligned/draft-00`: UALF captures the source facts needed by the
  documented mapping.
- `aat-exported/draft-00`: a closed UALF trace was transformed into AAT JSONL
  using this profile.
- `aat-validated/draft-00`: the exported AAT JSONL passed a validator pinned to
  draft-00.

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
| W3C Trace Context | Correlation with distributed trace and span identifiers |

UALF's exact-byte SHA-256 chain and Ed25519 trace seal remain authoritative for
the UALF artifact. An AAT exporter builds a separate RFC 8785 chain and, when
configured, separate ECDSA P-256 signatures. It MUST NOT relabel one integrity
mechanism as the other.

## 4. Required export context

Before export, the producer MUST resolve or explicitly configure:

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

## 5. Record mapping

Export occurs after trace closure so paired operations and their final outcomes
are known. The exporter creates a new linear AAT record sequence and records a
mapping from every AAT `record_id` to its source UALF record or records.

- Header -> `lifecycle/session_start`: hash configuration and enabled tools; do
  not expose retained content.
- `tool_call.started` -> `tool_call`: hash canonical arguments and derive its
  outcome only after pairing.
- `tool_call.completed` -> `tool_response`: link to the exported call record and
  hash the response or structured error.
- `decision.recorded` -> `decision`: map option count and hash retained rationale
  when policy permits.
- Model start/completion pair: enrich a linked `decision` with `model_id`, input
  and output hashes, cost, and latency. A model call without a decision has no
  lossless AAT draft-00 action type and MUST NOT be misclassified.
- `error.recorded` -> `error`: map category and recoverability through a
  documented policy.
- `human_feedback.recorded` -> `human_override` only when it records an actual
  intervention. Use `escalation` only when the UALF event documents an
  escalation; otherwise preserve the feedback only in UALF.
- Child-agent handoff extension -> `delegation`: require the delegate URI, trust
  assertion, and task-description hash.
- Outcome -> `lifecycle/session_end`: map final status and derive AAT session
  summary fields.

UALF observations, file changes, state changes, retries, evaluations, replay
evidence, and dataset qualification have no lossless draft-00 equivalent. The
exporter MUST retain their UALF source and MUST document whether they were
summarized, hashed into another record, or omitted.

## 6. Privacy transformation

AAT draft-00 prohibits raw inputs, outputs, tool parameters, responses, and
reasoning in audit records. The exporter therefore:

1. resolves the exact UALF inline value or content-addressed artifact;
2. hashes the decoded logical content using the exporter's documented procedure;
3. writes only the AAT hash and permitted metadata;
4. keeps the UALF content in a separately controlled system when retention is
   allowed; and
5. records the source content digest in the transformation manifest.

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

## 8. Integrity and deletion

The UALF trace and AAT projection are independently verifiable artifacts. Their
digests and signatures MUST be stored together in the transformation manifest.

UALF immutable traces and dataset packages MUST NOT be rewritten in place to
implement an AAT tombstone. Erasure is handled by deleting or restricting the
separately retained content under the applicable policy and recording a signed
redaction or deletion statement. An AAT tombstone projection MAY be produced
only when the implementation documents and validates the draft-00 chain-break
exception; it does not retroactively modify the UALF source artifact.

## 9. Versioning and evolution

The draft-00 mapping is isolated from the base UALF schema. Implementations SHOULD
place optional source metadata under a namespaced UALF extension such as
`ietf.org/draft-sharif-agent-audit-trail-00` until fields demonstrate stable,
general operational value.

When AAT changes, maintainers MUST:

1. add a new compatibility profile instead of silently changing draft-00;
2. publish a mapping and behavior-change report;
3. add positive and negative conformance vectors;
4. preserve the old exporter for reproducible historical audits; and
5. reconsider promotion of stable, broadly useful fields into a future UALF
   base-profile version.

## 10. References

- [IETF Datatracker status page](https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/)
- [Agent Audit Trail draft-00](https://www.ietf.org/archive/id/draft-sharif-agent-audit-trail-00.html)
- [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339)
- [RFC 5424](https://www.rfc-editor.org/rfc/rfc5424)
- [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)
- [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
