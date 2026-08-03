# UALF Extensions and Evolution

**Registry profile:** `ualf-extension-registry/v1`

**Status:** Draft v1.3 — 2026-08-03

UALF extensions allow experimentation without placing vendor-specific or
unstable fields in the base trace schema.

## Extension identifiers

An extension identifier uses a DNS-controlled prefix and a path, for example:

```text
iplanic.ai/otel/semconv-genai/2026-08-03
example.com/agent/safety/v2
```

The identifier is immutable. A behavior or schema change creates a new
identifier. Extension values appear only in an object's `extensions` member.

## Registry requirements

Every registered extension declares:

- an immutable canonical JSON Schema URL containing a release tag or commit;
- owner and contact;
- status: `experimental`, `stable`, `deprecated`, or `retired`;
- requirement level: `required`, `recommended`, or `opt_in`;
- applicable UALF objects and profiles;
- privacy risk: `none`, `low`, `sensitive`, or `high`;
- first and last supported base-profile versions;
- replacement identifier when deprecated; and
- whether unknown consumers may preserve, ignore, or must reject the extension.

Branches such as `main` or `latest` are not immutable schema references. An
extension with sensitive, expensive, or high-cardinality data SHOULD be
`opt_in`. An implementation that cannot configure opt-in capture MUST NOT emit
such an extension by default.

## Promotion and deprecation

An extension may be promoted into a future base profile only after:

1. at least two independent implementations;
2. stable semantics and conformance vectors;
3. documented privacy and retention behavior;
4. a migration mapping; and
5. a compatibility review against existing projections.

Deprecation MUST name a replacement or explain why none exists. Validators MUST
continue to recognize historical identifiers needed to reproduce old artifacts.
Retirement does not invalidate already sealed traces.

Base-profile evolution follows the same immutability rule. A structural or
semantic change uses a new profile identifier, publishes a compatibility matrix
and migration mapping, and preserves the prior schema and verifier for historical
artifacts. Mutable branches and unversioned schema URLs MUST NOT be used as
normative `$id` values.

## Generated libraries

The registry and JSON Schemas are the source for generated constants and types.
Python, TypeScript and Go packages SHOULD expose the same identifiers, enums and
validation vectors. Hand-maintained language-specific names MUST NOT silently
change normative JSON field names.

`ualf-extension-registry.schema.json` defines the machine-readable registry.
