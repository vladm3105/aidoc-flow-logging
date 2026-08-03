# UALF — Unified Agent Logging and Dataset Format

UALF provides one operations-first trace format for AI projects and a separate
qualification profile for commercial trajectory datasets.

## Project maturity and scope

UALF is currently a design-stage logging standard and reference-artifact
package. The schemas, examples, generators, exporters, and verifiers in this
repository demonstrate format behavior and conformance; they are not a
production logging platform.

`INFRASTRUCTURE-AND-OPERATIONS-ROADMAP.md` records the approved direction for
storage, ingestion, isolation, observability, replay, and operations. The
repository does not yet provide or claim a production ingestion gateway,
managed archive, SQL or ClickHouse deployment, monitoring stack, runtime SDK,
dashboard package, or operational runbook. Those deliverables remain planned
until their designs and conformance contracts are completed.

## Goals

1. Debug, test, measure, and trace AI agents consistently across projects.
2. Support useful replay levels, beginning with recorded-response replay.
3. Preserve enough provenance and context to create valuable training datasets.
4. Export only rights-cleared, complete, independently qualified traces.

## Profiles

- **`ualf-trace/v1.1`** records scoped, distributed operational activity: agent
  lifecycle and delegation, model calls, tool calls,
  observations, decisions, changes, errors, feedback, evaluations, and outcomes.
- **`ualf-dataset/v1.2`** packages selected traces with signed rights, hygiene,
  replay, capture, amendment-cutoff, retention, revocation, evidence,
  replay, deduplication, splits, quality dimensions, and an Ed25519 seal.
- **AAT draft-00 compatibility** documents a one-way, privacy-minimized audit
  projection to `draft-sharif-agent-audit-trail-00` without replacing UALF's
  richer operational source record.
- **`ualf-capture/v1.1`** records production sampling, content states, privacy
  boundary, delivery loss, clocks, recovery, and closure evidence.
- **`ualf-amendments/v1`** preserves signed post-run evaluation and annotation
  history without rewriting sealed traces.
- **Interoperability profiles** project verified UALF artifacts to OpenTelemetry
  GenAI, OpenInference, OpenLineage, Croissant, in-toto, and analytical formats.

UALF JSONL is the immutable source/interchange representation. Buyers may use
derived Parquet, SFT conversation, preference-pair, RL episode, or benchmark-task
exports.

## Bundle contents

<!-- markdownlint-disable MD013 -->

| File | Purpose |
| --- | --- |
| `UNIFIED-AGENT-LOG-FORMAT.md` | Normative trace and dataset specification |
| `AGENT-LOG-DATASET-REQUIREMENTS.md` | Capture and export requirements |
| `AAT-COMPATIBILITY.md` | Version-pinned AAT draft-00 mapping and claim rules |
| `PRODUCTION-CAPTURE-AND-LIFECYCLE.md` | Sampling, buffering, privacy, recovery, retention, and erasure |
| `INTEROPERABILITY-PROFILES.md` | OTel, OpenInference, lineage, Croissant, attestation, and buyer projections |
| `EXTENSIONS-AND-EVOLUTION.md` | Namespaced extensions, registry, promotion, and deprecation |
| `ANALYTICS-AND-SDKS.md` | Logical tables, indexing, compact storage, and cross-language SDK behavior |
| `INFRASTRUCTURE-AND-OPERATIONS-ROADMAP.md` | Approved storage, deployment, management-plane, and implementation roadmap |
| `CONFORMANCE.md` | Conformance classes, evidence rules, and claim language |
| `SPECIFICATION-GOVERNANCE.md` | Versioning, precedence, errata, and change process |
| `aat-draft-00.schema.json` | Pinned AAT record schema |
| `ualf-aat-source.schema.json` | AAT identity and policy context |
| `ualf-aat-export-manifest.schema.json` | Signed transformation manifest |
| `ualf-production-capture.schema.json` | Production capture evidence |
| `ualf-amendment.schema.json` | Signed append-only amendment lines |
| `ualf-retention.schema.json` | Retention, dependency, encryption, and erasure policy |
| `ualf-extension-registry.schema.json` | Extension registry entries |
| `ualf-projection-manifest.schema.json` | Digest-bound external and analytical projections |
| `ualf-dsse-envelope.schema.json` | DSSE envelope for qualification attestations |
| `ualf-index.schema.json` | Digest-bound random-access byte index |
| `ualf-segment-manifest.schema.json` | Exact-reconstruction segments, Merkle root, and signature |
| `ualf-trajectory.schema.json` | Header, event, and outcome schema |
| `ualf-tool-definitions.schema.json` | Captured action-space schema |
| `ualf-dataset-manifest.schema.json` | Dataset package manifest schema |
| `ualf-quality-report.schema.json` | Derived qualification report schema |
| `ualf-rights-attestation.schema.json` | Signed rights-review evidence |
| `ualf-hygiene-report.schema.json` | Signed PII, secrets, license, and malware scan evidence |
| `ualf-replay-verification.schema.json` | Signed replay execution and comparison evidence |
| `ualf-datasheet.schema.json` | Machine-readable dataset disclosure schema |
| `ualf-erasure-statement.schema.json` | Signed revocation and erasure propagation evidence |
| `schema-catalog.json` | Profile, immutable schema identifier, and draft file resolution map |
| `example-trajectory.jsonl` | Complete signed example trace |
| `example-manifest.json` | Example dataset manifest |
| `example-quality-report.json` | Example derived quality report |
| `datasheet.md` | Example dataset documentation |
| `rights-attestation.json` | Example rights-review evidence |
| `dedup-report.json` | Example exact-deduplication evidence |
| `blobs/` | Content-addressed example artifacts |
| `verify.py` | Schema, trajectory, blob, totals, and signature verifier |
| `verify_aat.py` | AAT projection, chain, privacy, and manifest verifier |
| `build_example.py` | Regenerates the example with a fresh demo key |
| `build_aat_example.py` | Regenerates the synthetic AAT example |
| `build_profiles.py` | Deterministically regenerates the v1.3 profile examples |
| `verify_profiles.py` | Validates capture, amendments, retention, indexes, and projections |
| `export_analytics.py` | Exports stable JSONL tables and optional Parquet tables |
| `generate_sdk_types.py` | Generates shared Python, TypeScript, and Go constants |
| `example-aat*.json*` | Synthetic AAT projection artifacts |
| `example-production-capture.json` | Complete production-capture fixture |
| `example-amendments.jsonl` | Signed post-run amendment fixture |
| `example-retention.json` | Retention and erasure fixture |
| `example-index.json` | Byte-offset index for the example trajectory |
| `example-segment-manifest.json` | Signed exact-reconstruction segment/Merkle fixture |
| `extension-registry.json` | Machine-readable extension registry fixture |
| `projections/` | OTel, OpenInference, OpenLineage, Croissant, in-toto, and DSSE examples |
| `analytics/` | Seven stable analytical JSONL tables plus projection manifest |
| `sdk/` | Generated Python, TypeScript, and Go profile/event constants |
| `tests/test_verify.py` | Positive and adversarial golden-vector tests |
| `tests/test_profiles.py` | v1.3 profile and tamper-resistance tests |
| `requirements-analytics.txt` | Optional Parquet exporter dependency |

<!-- markdownlint-enable MD013 -->

## Trace shape

```text
line 1        header
lines 2..n-1  events with correlation + exact-byte hash chain
line n        outcome with evaluations + totals + Ed25519 seal
```

Events share a common envelope with run/trace IDs, spans, actor, wall and
monotonic time, causal reference, discriminated type, and strict `data` payload.

## Replay levels

`none < trace < stubbed < tool_reexecution < full_reexecution < outcome_reproduced`

The example contains a safe initial-state tar archive and qualifies for verified
`stubbed` replay: exact model and tool responses are captured, and the replay
result is recorded as evidence. It does not claim deterministic hosted-model
reexecution.

## Verify the example

Install dependencies:

```bash
python -m pip install jsonschema cryptography rfc8785
```

Run:

```bash
python verify.py example-trajectory.jsonl
```

Verify the complete dataset package, including every listed trace:

```bash
python verify.py example-trajectory.jsonl --manifest example-manifest.json
```

Verify the pinned AAT projection and signed transformation manifest:

```bash
python verify_aat.py example-aat.jsonl \
  --manifest example-aat-manifest.json \
  --source-context example-aat-source.json
```

Regenerate and verify all v1.3 profiles:

```bash
python build_profiles.py
python verify_profiles.py
python -m unittest discover -s tests -v
```

Validate supplied lifecycle or projection artifacts instead of the bundled
fixtures:

```bash
python verify_profiles.py \
  --artifact-root /path/to/bundle \
  --capture /path/to/bundle/capture-report.json \
  --retention /path/to/bundle/retention.json \
  --projection /path/to/bundle/projection-manifest.json
```

The verifier validates strict schemas, physical JSONL structure, gapless sequence,
  IDs, tenant scope, producer clocks, causality, terminal call pairing, tool
  declarations, exact-byte chain, RFC 8785 seal,
strict Ed25519 identity, blob hashes and byte counts, model-source provenance,
event-derived totals, context completeness markers, and replay artifacts. With a
manifest, it additionally validates safe contained paths, every trace, the full
blob inventory, artifact digests, splits, exact deduplication, a dataset-level
  seal, signed rights/hygiene/replay evidence, lifecycle bindings,
  machine-readable datasheets, and recomputed qualification fields.

## Design adoption sequence

This sequence describes capability adoption and requirements maturity. It is
not a deployment guide.

1. Emit the operational floor from a shared library.
2. Store large/sensitive content in the content-addressed blob store.
3. Add evaluator events and derived performance dashboards.
4. Add stubbed replay, then stronger replay only where it creates operational value.
5. Materialize and sign closed traces selected for archival or export.
6. Run dataset qualification and generate buyer-specific formats.
7. Generate privacy-minimized audit projections only from closed, verified
   traces, and pin every external compatibility claim to an exact specification
   version.
8. Emit production capture and retention evidence, keep post-run annotations in
   signed amendment streams, and publish derived ecosystem projections with
   digest-bound projection manifests.

## Roadmap implementation status

<!-- markdownlint-disable MD013 -->

| Capability | Status |
| --- | --- |
| Production sampling, privacy boundary, delivery, recovery, and flush evidence | Implemented profile, schema, fixture, and verifier |
| Append-only evaluator amendments | Implemented signed JSONL profile, fixture, and verifier |
| Retention, erasure, and dangling-reference policy | Implemented schema and fixture |
| OpenTelemetry GenAI and OpenInference | Version-pinned mapping and example projections |
| OpenLineage, Croissant, in-toto, and DSSE | Mapping, example projections, signed envelope, and manifests |
| Analytical tables and random access | Executable JSONL/optional Parquet exporter and verified byte index |
| Extension governance | Registry schema, lifecycle rules, and fixture |
| Segment/Merkle integrity | Implemented exact-reconstruction manifest, signature, fixture, and verifier |
| Cross-language SDK foundation | Generated Python, TypeScript, and Go constants; runtime SDK libraries remain separate packages |
| Infrastructure, archive, and management plane | Approved design roadmap; normative contracts and reference artifacts are planned |

<!-- markdownlint-enable MD013 -->

## Status

Draft v1.3 specification and reference-artifact package (2026-08-03). The
current profiles are `ualf-trace/v1.1` and `ualf-dataset/v1.2`; historical
`ualf-trace/v1` and `ualf-dataset/v1.1` identifiers remain immutable. v1.3 adds
scoped distributed clocks, terminal call states, multi-agent events, signed
qualification evidence, lifecycle-bound packages, and machine-readable dataset
disclosures. `aidoc-traj/v1` was
experimental and is superseded by the operations-first `ualf-trace/v1.1` design.
The AAT compatibility document is informative and targets an individual IETF
Internet-Draft; it is not an IETF endorsement or a regulatory certification.

## License

The specification, schemas, verifier, tests, and synthetic example fixture are
licensed under the Apache License 2.0. The example trajectory is intended for
format validation and integration testing; it is not representative training
inventory.
