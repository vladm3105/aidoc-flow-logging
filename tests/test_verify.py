from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

BASE = Path(__file__).resolve().parents[1]
VERIFY = BASE / "verify.py"
EXAMPLE = BASE / "example-trajectory.jsonl"
MANIFEST = BASE / "example-manifest.json"
QUALITY = BASE / "example-quality-report.json"
AAT_VERIFY = BASE / "verify_aat.py"
AAT_EXAMPLE = BASE / "example-aat.jsonl"
AAT_MANIFEST = BASE / "example-aat-manifest.json"
AAT_CONTEXT = BASE / "example-aat-source.json"


def load_verifier():
    spec = importlib.util.spec_from_file_location("ualf_verify", VERIFY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def example_records() -> list[dict]:
    return [
        json.loads(line) for line in EXAMPLE.read_text(encoding="utf-8").splitlines()
    ]


def run_verifier(path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFY),
            str(path),
            "--blobs",
            str(BASE / "blobs"),
            *extra,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def run_aat_verifier(
    path: Path, manifest: Path = AAT_MANIFEST
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(AAT_VERIFY),
            str(path),
            "--manifest",
            str(manifest),
            "--source-context",
            str(AAT_CONTEXT),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


class VerifierGoldenVectors(unittest.TestCase):
    def test_positive_example(self) -> None:
        result = run_verifier(EXAMPLE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CONFORMING", result.stdout)

    def test_failed_model_call_has_explicit_terminal_state(self) -> None:
        schema = json.loads(
            (BASE / "ualf-trajectory.schema.json").read_text(encoding="utf-8")
        )
        event = deepcopy(
            next(
                record
                for record in example_records()
                if record.get("type") == "model_call.completed"
            )
        )
        data = event["data"]
        data.update(
            {
                "status": "interrupted",
                "usage_state": "not_available",
                "cost_state": "not_available",
                "latency_state": "not_available",
                "no_output": True,
                "error": {
                    "class": "process_terminated",
                    "message": "Producer exited before a response was observed.",
                    "retryable": True,
                },
            }
        )
        for field in ("usage", "cost_usd", "latency_ms", "finish_reason", "output_ref"):
            data.pop(field, None)
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(event)))

    def test_file_create_and_delete_are_representable(self) -> None:
        schema = json.loads(
            (BASE / "ualf-trajectory.schema.json").read_text(encoding="utf-8")
        )
        event = deepcopy(
            next(
                record
                for record in example_records()
                if record.get("type") == "file_change.recorded"
            )
        )
        event["data"].update(
            {"operation": "create", "pre_sha256": None, "post_sha256": "0" * 64}
        )
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(event)))
        event["data"].update(
            {"operation": "delete", "pre_sha256": "0" * 64, "post_sha256": None}
        )
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(event)))

    def test_unpaired_agent_activity_is_detected(self) -> None:
        records = example_records()
        records = [
            record
            for record in records
            if record.get("type") != "agent.completed"
        ]
        verifier = load_verifier()
        report = verifier.Report()
        verifier.verify_events(records, BASE / "blobs", report)
        self.assertIn("agent activities paired", report.failures)

    def test_rights_evidence_tampering_is_rejected(self) -> None:
        document = json.loads(
            (BASE / "rights-attestation.json").read_text(encoding="utf-8")
        )
        document["status"] = "restricted"
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "rights.json"
            candidate.write_text(json.dumps(document), encoding="utf-8")
            report = verifier.Report()
            result = verifier.verify_signed_evidence(
                candidate,
                BASE / "ualf-rights-attestation.schema.json",
                "rights evidence",
                report,
            )
        self.assertIsNone(result)
        self.assertIn("rights evidence digest", report.failures)

    def test_positive_complete_dataset(self) -> None:
        result = run_verifier(
            EXAMPLE,
            "--manifest",
            str(MANIFEST),
            "--quality-report",
            str(QUALITY),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[PASS] dataset manifest signature", result.stdout)
        self.assertIn("[PASS] quality derives", result.stdout)

    def test_blank_physical_line_is_rejected(self) -> None:
        lines = EXAMPLE.read_bytes().splitlines()
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "blank-line.jsonl"
            candidate.write_bytes(lines[0] + b"\n\n" + b"\n".join(lines[1:]) + b"\n")
            result = run_verifier(candidate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] no blank physical lines", result.stdout)

    def test_malformed_json_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "malformed.jsonl"
            candidate.write_bytes(b'{"kind":"header"\n')
            result = run_verifier(candidate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] UTF-8 JSON object per line", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_modified_totals_are_detected(self) -> None:
        records = example_records()
        records[-1]["totals"]["tool_calls"] += 1
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "wrong-totals.jsonl"
            candidate.write_text(
                "\n".join(
                    json.dumps(record, separators=(",", ":")) for record in records
                )
                + "\n",
                encoding="utf-8",
            )
            result = run_verifier(candidate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] outcome totals recompute", result.stdout)

    def test_schema_rejects_inline_model_completion_extension(self) -> None:
        schema = json.loads(
            (BASE / "ualf-trajectory.schema.json").read_text(encoding="utf-8")
        )
        event = next(
            record
            for record in example_records()
            if record.get("type") == "model_call.completed"
        )
        event["data"]["completion"] = "inline model text"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(event)))

    def test_successful_outcome_requires_evaluation(self) -> None:
        schema = json.loads(
            (BASE / "ualf-trajectory.schema.json").read_text(encoding="utf-8")
        )
        outcome = example_records()[-1]
        outcome["evaluations"] = []
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(outcome)))

    def test_tools_ref_rejects_wrong_content_role(self) -> None:
        schema = json.loads(
            (BASE / "ualf-trajectory.schema.json").read_text(encoding="utf-8")
        )
        header = example_records()[0]
        header["environment"]["tools_ref"]["content_role"] = "model_output"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(header)))

    def test_manifest_rejects_parent_traversal_path(self) -> None:
        schema = json.loads(
            (BASE / "ualf-dataset-manifest.schema.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["traces"][0]["path"] = "../outside.jsonl"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(manifest)))

    def test_invalid_manifest_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "invalid-manifest.json"
            manifest.write_text('{"schema":"wrong"}\n', encoding="utf-8")
            result = run_verifier(EXAMPLE, "--manifest", str(manifest))
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] dataset manifest schema", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_fake_tar_is_rejected(self) -> None:
        module = load_verifier()
        ref = {"media_type": "application/x-tar", "encoding": "identity"}
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "fake.tar"
            fake.write_bytes(b"placeholder")
            self.assertFalse(module.check_media(fake, ref))

    def test_tar_parent_traversal_is_rejected(self) -> None:
        module = load_verifier()
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w") as archive:
            item = tarfile.TarInfo("../outside.txt")
            item.size = 1
            archive.addfile(item, io.BytesIO(b"x"))
        self.assertFalse(module.safe_tar(payload.getvalue()))

    def test_call_completion_before_start_is_detected(self) -> None:
        module = load_verifier()
        records = example_records()
        start = next(
            record for record in records if record.get("type") == "tool_call.started"
        )
        end = next(
            record for record in records if record.get("type") == "tool_call.completed"
        )
        end["seq"] = start["seq"] - 1
        report = module.Report()
        module.verify_events(records, BASE / "blobs", report)
        self.assertIn("call lifecycle order and latency consistent", report.failures)

    def test_qualification_is_derived_not_trusted(self) -> None:
        module = load_verifier()
        trace = {
            "trajectory_id": "trace-1",
            "trace_sha256": "0" * 64,
            "schema_valid": True,
            "integrity_verified": True,
            "context_completeness": "partial",
            "evidence_quality": "artifact",
            "replay_quality": "trace",
            "hygiene_status": "clean",
        }
        derived = module.derive_quality(trace, "cleared")
        self.assertFalse(derived["export_eligible"])
        self.assertEqual(derived["commercial_tier"], "reject")

    def test_dataset_requires_every_manifest_trace_to_be_verified(self) -> None:
        module = load_verifier()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        extra = deepcopy(manifest["traces"][0])
        extra["trajectory_id"] = "missing-trace"
        extra["path"] = "missing.jsonl"
        manifest["traces"].append(extra)
        manifest["splits"]["test"].append("missing-trace")
        report = module.Report()
        module.verify_dataset_package(MANIFEST, manifest, None, [], report)
        self.assertIn("every manifest trace verified", report.failures)

    def test_missing_dependencies_fail_without_traceback(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(VERIFY),
                str(EXAMPLE),
                "--blobs",
                str(BASE / "blobs"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("install dependency", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_aat_positive_example(self) -> None:
        result = run_aat_verifier(AAT_EXAMPLE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CONFORMING", result.stdout)

    def test_aat_modified_chain_is_rejected(self) -> None:
        records = [
            json.loads(line)
            for line in AAT_EXAMPLE.read_text(encoding="utf-8").splitlines()
        ]
        records[-1]["prev_hash"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "bad-aat.jsonl"
            candidate.write_text(
                "\n".join(
                    json.dumps(record, separators=(",", ":")) for record in records
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = json.loads(AAT_MANIFEST.read_text(encoding="utf-8"))
            manifest["export"]["path"] = candidate.name
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            for source in (EXAMPLE, AAT_CONTEXT):
                (root / source.name).write_bytes(source.read_bytes())
            result = run_aat_verifier(candidate, manifest_path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] AAT chains and session summaries", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_aat_raw_content_field_is_rejected(self) -> None:
        records = [
            json.loads(line)
            for line in AAT_EXAMPLE.read_text(encoding="utf-8").splitlines()
        ]
        records[0]["action_detail"]["input"] = "secret"
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "raw-aat.jsonl"
            candidate.write_text(
                "\n".join(
                    json.dumps(record, separators=(",", ":")) for record in records
                )
                + "\n",
                encoding="utf-8",
            )
            result = run_aat_verifier(candidate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] AAT privacy-minimized fields", result.stdout)


if __name__ == "__main__":
    unittest.main()
