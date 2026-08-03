# UALF Specification Governance

UALF is a draft open specification. Maintainers publish profile identifiers,
schemas, mappings, fixtures, verifiers, and release notes together.

## Normative precedence

For a named profile, its immutable JSON Schema defines structural validity,
`UNIFIED-AGENT-LOG-FORMAT.md` defines cross-record semantics, and
`AGENT-LOG-DATASET-REQUIREMENTS.md` defines deployment and qualification
requirements. Profile-specific documents refine those rules. A contradiction is
an erratum: validators fail closed for the affected claim until the maintainers
publish a resolution.

## Change rules

- Profile identifiers and published schema `$id` values are immutable.
- Structural or semantic changes require a new profile identifier.
- Every new profile includes a compatibility matrix, migration mapping, positive
  and adversarial vectors, verifier support, and changelog entry.
- Historical schemas and verifiers remain available for sealed artifacts.
- Editorial clarifications that do not alter accepted artifacts may be published
  as errata and must identify affected releases.
- External standards and drafts are pinned by version plus immutable release or
  commit URL. Moving targets such as `main` or `latest` are not normative.

## Review and release

Normative changes require a public pull request, passing conformance tests, and
maintainer approval. Security, privacy, wire compatibility, and commercial-data
effects must be explicit in the pull request. Releases are tagged and their
schemas are published at versioned paths.

Contributions are licensed under Apache-2.0. Contributors must have the right to
submit their material and certify that right using the Developer Certificate of
Origin sign-off described in `CONTRIBUTING.md`.
