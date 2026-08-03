# Contributing to UALF

Open an issue before proposing a new base event, wire field, integrity mechanism,
qualification rule, or compatibility claim. Normative changes must include:

- the operational and privacy problem being solved;
- the proposed immutable profile or extension identifier;
- schema and documentation changes;
- positive and adversarial conformance vectors;
- migration and compatibility impact; and
- updates to generated examples and language constants.

Run `python build_example.py`, `python build_profiles.py`, all three verifiers,
and `python -m unittest discover -s tests -v` before submitting.

Commits must include a Developer Certificate of Origin sign-off using
`Signed-off-by: Name <email>`. By contributing, you certify that you created the
contribution or have the right to submit it under Apache-2.0.

Do not submit real client records, credentials, personal data, proprietary model
outputs, or production logs as test fixtures. Fixtures must be synthetic or
explicitly rights-cleared.
