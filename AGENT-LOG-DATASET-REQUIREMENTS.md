# UALF Capture and Dataset Requirements

**Scope:** All AI-agent projects using the shared logging layer.  
**Status:** Draft v1.1 — 2026-08-02  
**Normative format:** `UNIFIED-AGENT-LOG-FORMAT.md`

Requirements use RFC 2119 keywords and stable `DLOG-NNN` identifiers.

## 1. Operational capture — P0

- **DLOG-001.** Every run MUST have a globally unique `run_id` and `trace_id`.
- **DLOG-002.** Every event MUST use the common envelope, gapless materialized
  sequence, unique event ID, actor, wall timestamp, and monotonic offset.
- **DLOG-003.** Nested and parallel work MUST use spans and causal references;
  sequence alone MUST NOT represent causality.
- **DLOG-004.** Every run MUST close with one outcome. A janitor MAY close an
  interrupted run as `aborted`; that record remains a conforming operational trace.
- **DLOG-005.** Every model and tool operation MUST record start and completion
  events sharing a call ID. Interrupted calls remain visible.
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
  duplicate IDs, sequence gaps, invalid causal references, and unpaired calls.
- **DLOG-042 (P1).** Closed traces selected for archival or export MUST be
  exact-byte hash-chained and Ed25519 sealed using RFC 8785 JCS.
- **DLOG-043 (P1).** Signing keys MUST be managed in a registry; header and seal
  identities MUST match. Private keys MUST never enter traces or blobs.
- **DLOG-044 (P1).** Content references MUST verify digest and declared byte count.
  Machine-detectable media types and archive usability SHOULD be checked.
- **DLOG-045 (P0).** Wall timestamps MUST be ordered and reconcile with the run
  start plus monotonic offsets. Call completion MUST follow its matching start,
  preserve span identity and causality, and have recomputable latency.

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

## 8. Adoption order

1. Ship the shared event envelope, run lifecycle, model/tool calls, redaction,
   terminal outcomes, and configuration versions.
2. Add derived performance metrics, evaluator events, and conformance tests.
3. Add stubbed replay, then state restoration and replay verification where useful.
4. Materialize signed traces and build the rights/hygiene qualification pipeline.
5. Publish buyer-specific exports only from qualified dataset packages.

The operational trace is the durable source record. Commercial inventory is a
verified view over that record, not the default status of every run.
