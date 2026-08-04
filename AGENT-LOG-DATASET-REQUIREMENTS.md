# UALF Capture and Dataset Requirements

**Scope:** All AI-agent projects using the shared logging layer.  
**Status:** Draft v1.3 — 2026-08-03

**Normative format:** `UNIFIED-AGENT-LOG-FORMAT.md`

Requirements use the key words defined by BCP 14, RFC 2119 and RFC 8174 only
when they appear in all capitals, and use stable `DLOG-NNN` identifiers.

## 1. Operational capture — P0

- **DLOG-001.** Every run MUST have a globally unique `run_id` and `trace_id`.
- **DLOG-002.** Every event MUST use the common envelope, gapless materialized
  sequence, unique event ID, actor, wall timestamp, and monotonic offset.
- **DLOG-003.** Nested and parallel work MUST use spans and causal references;
  sequence alone MUST NOT represent causality.
- **DLOG-004.** Every run MUST close with one outcome. A janitor MAY close an
  interrupted run as `aborted`; that record remains a conforming operational trace.
- **DLOG-005.** Every model and tool operation in a closed trace MUST record a
  start and exactly one terminal completion sharing a call ID. Terminal status
  MUST distinguish success, error, cancellation, timeout, and interruption. A
  recovery closer MUST NOT invent unavailable output, usage, cost, or latency.
- **DLOG-006.** Errors, retries, abandoned branches, and human interventions MUST
  be retained.
- **DLOG-007.** The logging boundary MUST redact secrets before persistence and
  MUST make any truncation, omission, or redaction explicit.

## 2. Model and action context — P0

- **DLOG-010.** A model call MUST record provider, exact model ID, parameters,
  usage, latency, cost where available, finish reason, and exact ordered context.
- **DLOG-011.** Exact model-visible messages and tool definitions MUST be stored
  inline or by resolvable content reference. Summaries and placeholders do not
  satisfy completeness.
- **DLOG-012.** Every tool call MUST record complete arguments and completion
  status plus output or structured error.
- **DLOG-013.** Every environment input that can influence an action MUST be an
  observation, model-context item, or referenced initial-state artifact.
- **DLOG-014.** File/state changes MUST record the target, hashes, and a
  diff or structured delta.
- **DLOG-015.** The complete available action space MUST be captured as actual
  tool definitions, not hashes alone.
- **DLOG-016.** Reference positions MUST enforce their semantic content role,
  and inline captured content MUST retain the same origin classification as a
  blob-backed value.
- **DLOG-017.** Multi-agent runs MUST represent agent lifecycle, delegation,
  handoff, agent messages, guardrails, retrieval, and memory access as typed
  events with parent/child run and trace correlation where applicable.
- **DLOG-018.** Unknown, unavailable, and not-applicable measurements MUST remain
  distinct from measured zero. File and state events MUST distinguish create,
  modify, and delete operations.

## 3. Testing and performance — P0/P1

- **DLOG-020 (P0).** Outcomes MUST be supported by evaluator records. Self-report,
  artifact, signed-external, and reproduced evidence MUST remain distinguishable.
- **DLOG-021 (P0).** Totals MUST be derived from events and checked rather than
  trusted from an agent-authored summary.
- **DLOG-022 (P1).** Performance analysis SHOULD be sliceable by project, domain,
  task category, agent version, prompt version, model, toolset, environment, and
  evaluator version.
- **DLOG-023 (P1).** CI SHOULD retain positive and negative conformance
  vectors and
  SHOULD prevent schema/verifier regressions.

## 4. Replay — P1/P2

- **DLOG-030 (P1).** Every trace MUST declare a replay capability level from the
  controlled hierarchy; it MUST NOT use an unqualified Boolean.
- **DLOG-031 (P1).** Stubbed replay SHOULD be supported by retaining exact model
  and tool responses plus call correlation.
- **DLOG-032 (P2).** Tool/full replay SHOULD capture initial state, dependency
  versions, seeds, clocks and other nondeterministic inputs, and external-effect
  boundaries.
- **DLOG-033 (P2).** A replay capability higher than `trace` MUST include a
  successful verification record and evidence of a matching replay.

## 5. Integrity and resilience — P0/P1

- **DLOG-040 (P0).** Live capture MUST tolerate concurrent agents and process
  failure without corrupting earlier events.
- **DLOG-041 (P0).** Materialization MUST reject blank lines, invalid UTF-8,
  duplicate IDs, sequence gaps, invalid causal references, and starts without a
  terminal completion. Recovery MAY add an attributable `interrupted` terminal
  event but MUST NOT fabricate successful completion data.
- **DLOG-042 (P1).** Closed traces selected for archival or export MUST be
  exact-byte hash-chained and Ed25519 sealed using RFC 8785 JCS.
- **DLOG-043 (P1).** Signing keys MUST be managed in a registry; header and seal
  identities MUST match. Private keys MUST never enter traces or blobs.
- **DLOG-044 (P1).** Content references MUST verify digest and declared byte count.
  Machine-detectable media types and archive usability SHOULD be checked.
- **DLOG-045 (P0).** Every event MUST identify producer, process, clock domain,
  producer-local sequence, event time, and observation time. Local monotonic
  offsets MUST be ordered only within the same clock domain. Materialization
  MUST define deterministic tie-breaking and MUST NOT impose a false global
  clock order. Call completion MUST follow its matching start and preserve span
  identity and causality.

## 6. Rights and hygiene — export P0

- **DLOG-050.** Every retained content item MUST have an origin classification:
  project, human, model, tool, third party, or external system.
- **DLOG-051.** Model-generated content MUST name provider/model and remain
  filterable without deleting structural events.
- **DLOG-052.** Every export candidate MUST have documented ownership or license
  provenance for prompts, code, tool results, observations, and human content.
- **DLOG-053.** PII, confidential data, client data, credentials, and secrets MUST
  be scanned before export. Unresolved findings make the trace ineligible.
- **DLOG-054.** Intended uses and prohibited uses MUST be recorded in the dataset
  manifest. Rights clearance MUST consider the buyer's downstream use.
- **DLOG-055.** A declaration inside a trace is metadata, not proof of rights.
  Supporting records MUST be retained outside the public dataset where necessary.

## 7. Dataset qualification — export P0

- **DLOG-060.** Raw traces MUST NOT be sold merely because they conform to the
  operational schema.
- **DLOG-061.** The export pipeline MUST independently compute schema validity,
  integrity, context completeness, evidence quality, replay quality, rights,
  hygiene, and eligibility.
- **DLOG-062.** Any commercial tier MUST be derived from the quality dimensions.
  The producer agent MUST NOT select its own tier.
- **DLOG-063.** Dataset packages MUST include a manifest, quality report,
  datasheet, immutable traces, required blobs, splits, and deduplication results.
- **DLOG-064.** Exports SHOULD include transformations for conversation SFT,
  tool-use episodes, preference pairs, RL episodes, and benchmark tasks.
- **DLOG-065.** A content-filtered export MUST be tested for dangling references
  and loss of model-visible state. "Distillation-safe" MUST describe the exact
  filter policy and MUST NOT imply legal clearance by itself.
- **DLOG-066.** The verifier MUST validate every manifest trace, require disjoint
  complete splits, reject duplicate trace and quality IDs, and recompute each
  quality row from verified facts rather than trusting producer-stamped fields.
- **DLOG-067.** Dataset paths MUST be contained normalized relative paths. Archive
  members MUST reject traversal, links, devices, and unsupported types.
- **DLOG-068.** A dataset export MUST inventory every referenced blob and bind
  trace membership, splits, artifact digests, rights metadata, and intended uses
  with an RFC 8785 canonical Ed25519 manifest seal.
- **DLOG-069.** Every dataset trace entry MUST bind capture evidence or explicit
  synthetic origin, amendment head and cutoff, retention policy, revocation
  state, signed rights, hygiene, and replay evidence, plus every external
  dependency and its availability commitment. Qualification MUST also record
  exact and near-duplicate methods, benchmark contamination, semantic split
  leakage, and a machine-readable datasheet; `not_run` MUST NOT be interpreted
  as no findings.

## 8. External interoperability — P1

- **DLOG-070.** External compatibility claims MUST identify the exact standard,
  draft, profile, and version. Internet-Drafts MUST NOT be represented as IETF
  standards, endorsements, or regulatory certifications.
- **DLOG-071.** An AAT draft-00 export MUST be a derived audit projection from a
  closed, verified UALF trace. It MUST NOT replace the UALF source record.
- **DLOG-072.** AAT input, output, parameter, response, context, and reasoning
  hashes MUST be derived from exact UALF content through a documented,
  deterministic privacy transformation.
- **DLOG-073.** The export pipeline MUST record source and destination digests,
  exporter and validator versions, record mappings, omitted semantics, and the
  identity responsible for any trust-level assertion in a schema-valid, signed
  transformation manifest.
- **DLOG-074.** UALF and AAT integrity mechanisms MUST be verified independently.
  Exact-byte Ed25519 UALF seals MUST NOT be relabeled as RFC 8785 ECDSA AAT
  signatures or vice versa.
- **DLOG-075.** Parallel UALF spans MUST be deterministically serialized or mapped
  to linked AAT sessions. The export MUST retain source span and causal mappings.
- **DLOG-076.** The AAT draft-00 projection MUST remain frozen and optional.
  UALF maintainers have no obligation to track later AAT revisions. A future
  target requires explicit governance approval, a new profile, a mapping and
  behavior-change report, conformance vectors, and a named maintenance owner.
  Frozen status and scope MUST be published in the machine-readable projection
  target catalog and regression-tested.
- **DLOG-077.** AAT content hashes MUST use RFC 8785 JCS bytes for JSON, exact
  UTF-8 bytes without normalization for text, and decoded octets for binary.
- **DLOG-078.** Sensitive or personal content MUST NOT be stored inline in an
  immutable UALF trace unless separately managed encryption keys support
  cryptographic erasure. Hashes MUST be treated as potentially personal data.

## 9. Production capture and lifecycle — P0

- **DLOG-080.** Sampling MUST be decided at root-trace scope and MUST record the
  effective probability, policy, and reason. Partial child-span sampling MUST
  NOT be represented as a complete trace.
- **DLOG-081.** Every content category MUST use a controlled state that
  distinguishes captured, unavailable, intentionally omitted, redacted,
  truncated, capture-failed, sampled-out, and not-applicable content.
- **DLOG-082.** Privacy transformations MUST occur before the first unauthorized
  persistence or network boundary. The boundary and policy MUST be recorded.
- **DLOG-083.** Asynchronous capture MUST expose accepted, delivered, retried,
  dropped, and terminal-failure counts plus queue, spool, and flush status.
- **DLOG-084.** Collector retries MUST be idempotent. Conflicting content for an
  existing `(run_id, event_id)` MUST be rejected.
- **DLOG-085.** Capture MUST identify wall and monotonic clock sources,
  synchronization status, and detected drift. Materialization MUST tolerate
  late delivery without inferring causality from delivery order.
- **DLOG-086.** Recovery MUST record the last durable checkpoint and known or
  suspected record loss. A janitor closure MUST NOT invent missing results.
- **DLOG-087.** Capture reports used for qualification MUST be scoped to
  organization, project, and environment; bind the source trace digest; and be
  canonically hashed and signed by an authorized capture identity.

## 10. Amendments, retention, and trust — P0/P1

- **DLOG-090 (P0).** A sealed trace MUST NOT be rewritten for later evaluation,
  annotation, feedback, correction, retention, or deletion activity.
- **DLOG-091 (P0).** Post-run evaluations MUST use an append-only amendment
  stream with target, source, evaluator and rubric versions, typed result,
  severity, confidence, evidence, timestamp, and supersession history.
- **DLOG-092 (P1).** Amendment streams selected for export MUST be hash-chained
  and signed, and signing identities MUST resolve through an external registry.
- **DLOG-093 (P0).** Retention policy MUST bind an immutable subject digest to
  expiry, legal hold, dependency mode, erasure method, and dangling-reference
  behavior.
- **DLOG-094 (P0).** Qualified packages MUST be self-contained or explicitly
  declare each external dependency and availability commitment.
- **DLOG-095 (P1).** Signing-key registries SHOULD publish validity, rotation,
  revocation, organization, and signer-role metadata. Embedded public keys alone
  MUST NOT be treated as proof of organizational identity.
- **DLOG-096 (P0).** Retention records MUST be scoped, policy-versioned,
  canonically hashed, and signed. Revocation or erasure MUST use a signed
  statement that exposes propagation across canonical objects, projections,
  caches, backups, and exports.

## 11. Ecosystem projections and analytics — P1/P2

- **DLOG-100 (P1).** UALF SHOULD provide version-pinned OpenTelemetry GenAI and
  OpenInference projections with deterministic identifier mappings and
  privacy-safe defaults.
- **DLOG-101 (P1).** Dataset production SHOULD emit OpenLineage provenance and
  Croissant discovery metadata without treating either as the authoritative
  membership or rights record.
- **DLOG-102 (P1).** Qualification MAY be wrapped in an in-toto Statement v1 and
  DSSE signature. Consumers MUST verify the subject digest and predicate policy
  and MUST fail closed when a required attestation is absent.
- **DLOG-103 (P1).** Every derived artifact MUST use a projection manifest that
  binds source/output digests, exporter and validator versions, mappings,
  omissions, privacy transformation, and loss class.
- **DLOG-104 (P1).** Analytical tables and indexes MUST identify their source
  trace digest and projection version and MUST remain non-authoritative.
- **DLOG-105 (P2).** Python, TypeScript, and Go SDKs SHOULD generate types and
  constants from the normative schemas and share the same conformance vectors.
- **DLOG-106 (P2).** A compact or segment/Merkle integrity profile MUST preserve
  exact reconstruction or declare itself lossy and MUST NOT be relabeled as the
  v1 exact-byte chain.

## 12. Storage and ingestion architecture — P0/P1

- **DLOG-110 (P0).** A production design MUST identify one logical authoritative
  artifact set per security and lifecycle boundary as the recovery,
  verification, replay, and export authority. The set MAY use replicated or
  physically separate archives without creating competing sources of truth.
- **DLOG-111 (P0).** SQL catalogs, analytical databases, Parquet tables,
  indexes, search systems, and dashboards MUST be treated as rebuildable
  projections and MUST identify their authoritative source digests.
- **DLOG-112 (P0).** Durable acceptance MUST have an explicit receipt boundary.
  An SDK queue acknowledgement alone MUST NOT be represented as archive
  durability.
- **DLOG-113 (P0).** Retry and recovery MUST use a stable idempotency key.
  Byte-identical duplicates MAY be accepted; conflicting content for the same
  identity MUST be rejected, quarantined, and surfaced as an integrity incident.
- **DLOG-114 (P0).** Agents and SDKs MUST NOT independently dual-write canonical
  and analytical stores. One ingestion path MUST own fan-out and reconciliation.
- **DLOG-115 (P0).** Every ingest request, catalog or analytical row, object key,
  policy decision, and management action MUST be scoped to an organization or
  storage namespace, project, and environment. Development, staging, and
  production MUST use separate storage boundaries and credentials.
- **DLOG-121 (P0).** The same organization, project, and environment scope MUST
  be carried by portable authoritative trace, capture, retention, dataset, and
  management-audit artifacts rather than existing only in transport metadata.
- **DLOG-116 (P0).** Content deduplication MUST remain within a declared privacy,
  encryption, rights, retention, and residency boundary. Knowledge of a content
  digest MUST NOT grant or imply access to the content.
- **DLOG-117 (P1).** The architecture SHOULD support dedicated deployment when
  residency, regulated operation, customer isolation, scale, or contract terms
  require it, while preserving a unified logical model.
- **DLOG-118 (P1).** Encoded objects SHOULD bind stored-byte and decoded-content
  digests where both transport integrity and semantic identity are required.
- **DLOG-119 (P1).** Replay and dataset qualification MUST be reconstructable
  from canonical artifacts without depending on the continued availability of
  an analytical database.
- **DLOG-120 (P1).** Commercial dataset publication MUST remain a separate,
  rights-qualified export path rather than a direct query over operational
  storage.

## 13. Management, observability, and continuity — P0/P1

- **DLOG-130 (P0).** The management plane MUST be operationally independent from
  the data path it observes and MUST expose its own health.
- **DLOG-131 (P0).** Every critical processing hop MUST expose positive progress,
  negative failure, stalled work, and absent-signal detection.
- **DLOG-132 (P0).** Production designs MUST include a harmless signed canary on
  a defined cadence that traverses the real producer, spool, gateway, archive,
  catalog, analytics, and replay path. It MUST use deterministic content, a
  short retention class, an exact producer identity, and an expected replay
  result that unrelated traces cannot satisfy.
- **DLOG-133 (P0).** An independent watchdog MUST detect failure or silence in
  the monitoring and alert-delivery path itself.
- **DLOG-134 (P0).** Alerting MUST preserve a durable internal alert record and
  use a separate external paging path for human notification.
- **DLOG-135 (P0).** Metrics MUST use bounded-cardinality dimensions. Run, trace,
  event, prompt, and raw error identifiers MUST remain in logs, traces, or
  analytical stores rather than metric labels.
- **DLOG-136 (P1).** Privileged management actions and policy changes SHOULD
  produce attributable, tamper-evident audit records.
- **DLOG-137 (P1).** Retention and erasure workflows SHOULD expose propagation
  state across canonical objects, projections, caches, backups, and exports.
- **DLOG-138 (P1).** Backup and restore design MUST include tested recovery
  objectives and integrity verification, not backup creation alone.
- **DLOG-139 (P1).** Management views SHOULD separately cover platform
  operations; project and agent performance; capture quality and data integrity;
  privacy, retention, access, and security; and dataset readiness and commercial
  inventory.
- **DLOG-140 (P1).** UALF SHOULD standardize SLO measurement semantics while
  allowing deployment profiles to select targets. Alert requirements SHOULD use
  ratio-based conditions, minimum-traffic guards, explicit absent-signal arms,
  and multi-window error-budget evaluation where applicable.

These requirements define the approved design target. Planned receipt, storage,
management-audit, semantic-convention, dashboard, and alert artifacts are not
part of current schema conformance until published.

## 14. Design adoption order

This order describes design and capability maturity, not development or
deployment instructions.

1. Ship the shared event envelope, run lifecycle, model/tool calls, redaction,
   terminal outcomes, and configuration versions.
2. Add derived performance metrics, evaluator events, and conformance tests.
3. Add stubbed replay, then state restoration and replay verification where useful.
4. Materialize signed traces and build the rights/hygiene qualification pipeline.
5. Publish buyer-specific exports only from qualified dataset packages.
6. Add production capture reports, durable spool/flush behavior, amendment
   streams, and retention bindings.
7. Add version-pinned telemetry, lineage, discovery, attestation, and analytical
   projections without weakening or replacing the operational source record.
8. Specify the canonical archive, durable receipt, projection, namespace, and
   deployment-profile contracts before selecting or deploying products.
9. Specify independent management telemetry, hop and canary semantics, bounded
   metrics, watcher health, alert evidence, and management audit contracts.

The operational trace is the durable source record. Commercial inventory is a
verified view over that record, not the default status of every run.
