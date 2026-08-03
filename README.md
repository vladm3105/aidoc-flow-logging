# UALF — Unified Agent Logging and Dataset Format

UALF provides one operations-first trace format for AI projects and a separate
qualification profile for commercial trajectory datasets.

## Goals

1. Debug, test, measure, and trace AI agents consistently across projects.
2. Support useful replay levels, beginning with recorded-response replay.
3. Preserve enough provenance and context to create valuable training datasets.
4. Export only rights-cleared, complete, independently qualified traces.

## Profiles

- **`ualf-trace/v1`** records operational activity: model calls, tool calls,
  observations, decisions, changes, errors, feedback, evaluations, and outcomes.
- **`ualf-dataset/v1.1`** packages selected traces with rights, hygiene, evidence,
  replay, deduplication, splits, quality dimensions, and an Ed25519 seal.
- **AAT draft-00 compatibility** documents a one-way, privacy-minimized audit
  projection to `draft-sharif-agent-audit-trail-00` without replacing UALF's
  richer operational source record.

UALF JSONL is the immutable source/interchange representation. Buyers may use
derived Parquet, SFT conversation, preference-pair, RL episode, or benchmark-task
exports.

## Bundle contents

| File | Purpose |
| --- | --- |
| `UNIFIED-AGENT-LOG-FORMAT.md` | Normative trace and dataset specification |
| `AGENT-LOG-DATASET-REQUIREMENTS.md` | Capture and export requirements |
| `AAT-COMPATIBILITY.md` | Version-pinned AAT draft-00 mapping and claim rules |
| `aat-draft-00.schema.json` | Pinned AAT record schema |
| `ualf-aat-source.schema.json` | AAT identity and policy context |
| `ualf-aat-export-manifest.schema.json` | Signed transformation manifest |
| `ualf-trajectory.schema.json` | Header, event, and outcome schema |
| `ualf-tool-definitions.schema.json` | Captured action-space schema |
| `ualf-dataset-manifest.schema.json` | Dataset package manifest schema |
| `ualf-quality-report.schema.json` | Derived qualification report schema |
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
| `example-aat*.json*` | Synthetic AAT projection artifacts |
| `tests/test_verify.py` | Positive and adversarial golden-vector tests |

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

The verifier validates strict schemas, physical JSONL structure, gapless sequence,
IDs and causality, call pairing, tool declarations, exact-byte chain, RFC 8785 seal,
strict Ed25519 identity, blob hashes and byte counts, model-source provenance,
event-derived totals, context completeness markers, and replay artifacts. With a
manifest, it additionally validates safe contained paths, every trace, the full
blob inventory, artifact digests, splits, exact deduplication, a dataset-level
seal, and recomputed qualification fields.

## Adoption

1. Emit the operational floor from a shared library.
2. Store large/sensitive content in the content-addressed blob store.
3. Add evaluator events and derived performance dashboards.
4. Add stubbed replay, then stronger replay only where it creates operational value.
5. Materialize and sign closed traces selected for archival or export.
6. Run dataset qualification and generate buyer-specific formats.
7. Generate privacy-minimized audit projections only from closed, verified
   traces, and pin every external compatibility claim to an exact specification
   version.

## Status

Draft v1.1 reference implementation (2026-08-02). `aidoc-traj/v1` was
experimental and is superseded by the operations-first `ualf-trace/v1` design.
The AAT compatibility document is informative and targets an individual IETF
Internet-Draft; it is not an IETF endorsement or a regulatory certification.

## License

The specification, schemas, verifier, tests, and synthetic example fixture are
licensed under the Apache License 2.0. The example trajectory is intended for
format validation and integration testing; it is not representative training
inventory.
