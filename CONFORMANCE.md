# UALF Conformance

UALF conformance is scoped to an immutable profile identifier and a named
conformance class. Implementations MUST state the exact profile and verifier
version used. A schema-valid artifact alone is not a complete conformance claim.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**,
and **MAY** are interpreted as described by BCP 14, RFC 2119, and RFC 8174 when
they appear in all capitals.

## Classes

1. **Record schema conformance** validates one JSON object against its immutable
   profile schema.
2. **Closed trace conformance** validates physical JSONL, scope, ordering,
   producer clocks, causality, terminal call lifecycles, content references,
   totals, and integrity.
3. **Capture conformance** validates signed sampling, delivery, privacy,
   recovery, and completeness evidence bound to the trace digest.
4. **Dataset package conformance** validates every member, blob inventory,
   splits, lifecycle bindings, machine datasheet, and package seal.
5. **Commercial qualification conformance** additionally validates signed rights,
   hygiene, replay, revocation, amendment-cutoff, deduplication, contamination,
   and split-leakage evidence under a named policy.
6. **Projection conformance** validates source/output digests, immutable target
   revision, mappings, omissions, privacy transformation, and loss class.

Projection conformance is target-specific and does not make an optional
projection part of base UALF conformance. In particular, the frozen AAT
draft-00 projection may be omitted by a conforming UALF implementation.

Claims MUST NOT promote a lower class to a higher one. In particular,
`schema-valid`, `package-valid`, and `commercially qualified` are different
claims. Missing required evidence fails closed; `not_run` is not equivalent to a
clean result.

## Evidence authority

A valid signature proves key possession and artifact integrity. Organizational
or reviewer authority requires resolution through the declared external key or
authority registry, including validity and revocation checks. Demo keys and
embedded public keys are sufficient only for synthetic conformance fixtures.

## Legacy profiles

`ualf-trace/v1` and `ualf-dataset/v1.1` remain historical immutable profiles.
They do not gain v1.1/v1.2 semantics. Migration creates new artifacts under the
new identifiers and records a digest-bound transformation manifest.
