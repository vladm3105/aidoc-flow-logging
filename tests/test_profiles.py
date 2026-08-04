from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


BASE = Path(__file__).resolve().parents[1]
VERIFY = BASE / "verify_profiles.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ualf_profiles", VERIFY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def validate(value: dict, schema_name: str) -> list:
    schema = json.loads((BASE / schema_name).read_text(encoding="utf-8"))
    return list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value))


class ProfileGoldenVectors(unittest.TestCase):
    def test_positive_examples(self) -> None:
        result = subprocess.run([sys.executable, str(VERIFY)], cwd=BASE, check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CONFORMING", result.stdout)

    def test_profile_cli_validates_supplied_capture(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(VERIFY),
                "--artifact-root",
                str(BASE),
                "--capture",
                str(BASE / "example-production-capture.json"),
            ],
            cwd=BASE,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_builder_is_deterministic(self) -> None:
        targets = [BASE / "example-amendments.jsonl", BASE / "example-index.json", BASE / "example-production-capture.json", BASE / "example-segment-manifest.json", BASE / "sdk" / "typescript" / "ualf-types.ts"]
        before = [path.read_bytes() for path in targets]
        result = subprocess.run([sys.executable, str(BASE / "build_profiles.py")], cwd=BASE, check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, [path.read_bytes() for path in targets])

    def test_schema_catalog_matches_schema_ids(self) -> None:
        catalog = json.loads((BASE / "schema-catalog.json").read_text(encoding="utf-8"))
        for entry in catalog["schemas"]:
            schema = json.loads((BASE / entry["path"]).read_text(encoding="utf-8"))
            self.assertEqual(entry["id"], schema["$id"], entry["path"])

    def test_projection_target_catalog_is_valid(self) -> None:
        catalog = json.loads(
            (BASE / "projection-target-catalog.json").read_text(encoding="utf-8")
        )
        self.assertFalse(
            validate(catalog, "ualf-projection-target-catalog.schema.json")
        )
        target = catalog["targets"][0]
        self.assertEqual(target["lifecycle"], "frozen")
        self.assertTrue(target["optional"])
        for artifact in target["artifacts"]:
            self.assertTrue((BASE / artifact).is_file(), artifact)

    def test_complete_capture_rejects_dropped_records(self) -> None:
        capture = json.loads((BASE / "example-production-capture.json").read_text(encoding="utf-8"))
        capture["delivery"]["dropped_records"] = 1
        self.assertTrue(validate(capture, "ualf-production-capture.schema.json"))

    def test_capture_signature_rejects_tampering(self) -> None:
        module = load_module()
        capture = json.loads(
            (BASE / "example-production-capture.json").read_text(encoding="utf-8")
        )
        capture["delivery"]["accepted_records"] += 1
        report = module.Report()
        module.verify_document_seal(capture, "capture report", report)
        self.assertIn("capture report digest", report.failures)

    def test_active_legal_hold_requires_authority(self) -> None:
        retention = json.loads(
            (BASE / "example-retention.json").read_text(encoding="utf-8")
        )
        retention["legal_hold"] = {"active": True}
        self.assertTrue(validate(retention, "ualf-retention.schema.json"))

    def test_sampled_out_capture_rejects_trace_digest(self) -> None:
        capture = json.loads((BASE / "example-production-capture.json").read_text(encoding="utf-8"))
        capture["sampling"]["decision"] = "drop"
        capture["completeness"] = "sampled_out"
        self.assertTrue(validate(capture, "ualf-production-capture.schema.json"))

    def test_sensitive_extension_must_be_opt_in(self) -> None:
        registry = json.loads((BASE / "extension-registry.json").read_text(encoding="utf-8"))
        registry["extensions"][1]["requirement_level"] = "recommended"
        self.assertTrue(validate(registry, "ualf-extension-registry.schema.json"))

    def test_projection_rejects_traversal(self) -> None:
        manifest = json.loads((BASE / "projections" / "example-otel-genai-manifest.json").read_text(encoding="utf-8"))
        manifest["outputs"][0]["path"] = "../secret.json"
        self.assertTrue(validate(manifest, "ualf-projection-manifest.schema.json"))

    def test_amendment_tampering_is_rejected(self) -> None:
        module = load_module()
        lines = (BASE / "example-amendments.jsonl").read_text(encoding="utf-8").splitlines()
        amendment = json.loads(lines[1])
        amendment["confidence"] = 0.5
        lines[1] = json.dumps(amendment, separators=(",", ":"))
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "bad-amendments.jsonl"
            candidate.write_text("\n".join(lines) + "\n", encoding="utf-8")
            report = module.Report()
            module.verify_amendments(candidate, report)
        self.assertIn("amendment exact-byte chain", report.failures)

    def test_index_tampering_is_rejected(self) -> None:
        module = load_module()
        index = json.loads((BASE / "example-index.json").read_text(encoding="utf-8"))
        candidate = deepcopy(index)
        candidate["records"][1]["offset"] += 1
        report = module.Report()
        module.verify_index(candidate, report)
        self.assertIn("index offsets and line digests", report.failures)

    def test_index_rejects_parent_traversal(self) -> None:
        index = json.loads((BASE / "example-index.json").read_text(encoding="utf-8"))
        index["source"]["path"] = "../example-trajectory.jsonl"
        self.assertTrue(validate(index, "ualf-index.schema.json"))

    def test_index_missing_source_is_rejected_cleanly(self) -> None:
        module = load_module()
        index = json.loads((BASE / "example-index.json").read_text(encoding="utf-8"))
        index["source"]["path"] = "missing.jsonl"
        report = module.Report()
        module.verify_index(index, report)
        self.assertIn("index source exists", report.failures)

    def test_segment_tampering_is_rejected(self) -> None:
        module = load_module()
        manifest = json.loads((BASE / "example-segment-manifest.json").read_text(encoding="utf-8"))
        manifest["segments"][0]["sha256"] = "0" * 64
        report = module.Report()
        module.verify_segments(manifest, report)
        self.assertIn("segment exact coverage", report.failures)

    def test_segment_rejects_parent_traversal(self) -> None:
        manifest = json.loads((BASE / "example-segment-manifest.json").read_text(encoding="utf-8"))
        manifest["source"]["path"] = "../example-trajectory.jsonl"
        self.assertTrue(validate(manifest, "ualf-segment-manifest.schema.json"))

    def test_segment_missing_source_is_rejected_cleanly(self) -> None:
        module = load_module()
        manifest = json.loads((BASE / "example-segment-manifest.json").read_text(encoding="utf-8"))
        manifest["source"]["path"] = "missing.jsonl"
        report = module.Report()
        module.verify_segments(manifest, report)
        self.assertIn("segment source exists", report.failures)

    def test_analytics_projection_has_stable_tables(self) -> None:
        expected = {"traces", "events", "model_calls", "tool_calls", "content_refs", "evaluations", "outcomes"}
        actual = {path.stem for path in (BASE / "analytics").glob("*.jsonl")}
        self.assertEqual(actual, expected)
        for path in (BASE / "analytics").glob("*.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.assertEqual(row["projection_version"], "ualf-analytics/v1")
                self.assertRegex(row["source_trace_sha256"], "^[a-f0-9]{64}$")

    def test_dsse_tampering_is_rejected(self) -> None:
        module = load_module()
        envelope = json.loads((BASE / "projections" / "example-in-toto.dsse.json").read_text(encoding="utf-8"))
        envelope["payload"] = envelope["payload"][:-2] + "AA"
        manifest = json.loads((BASE / "projections" / "example-in-toto-manifest.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "bad.dsse.json"
            candidate.write_text(json.dumps(envelope), encoding="utf-8")
            report = module.Report()
            module.verify_dsse(candidate, manifest, report)
        self.assertIn("DSSE Ed25519 signature", report.failures)

    def test_otel_projection_timestamps_match_source(self) -> None:
        module_path = BASE / "build_profiles.py"
        spec = importlib.util.spec_from_file_location("ualf_build_profiles", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        trace = [json.loads(line) for line in (BASE / "example-trajectory.jsonl").read_text(encoding="utf-8").splitlines()]
        otel = json.loads((BASE / "projections" / "example-otel-genai.json").read_text(encoding="utf-8"))
        span = otel["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(span["startTimeUnixNano"], module.unix_nano(trace[0]["started_at"]))
        self.assertEqual(span["endTimeUnixNano"], module.unix_nano(trace[-1]["timestamp"]))


if __name__ == "__main__":
    unittest.main()
