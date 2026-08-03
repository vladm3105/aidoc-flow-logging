#!/usr/bin/env python3
"""Build the UALF example fixture with fresh demo-only signing material."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import rfc8785
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BASE = Path(__file__).resolve().parent
BLOBS = BASE / "blobs"
RUN_ID = "run-2026-08-02-demo-001"
TRACE_ID = "trace-2026-08-02-demo-001"
TRAJECTORY_ID = "traj-2026-08-02-demo-001"
START = datetime(2026, 8, 2, 18, 0, 0, tzinfo=timezone.utc)


def compact(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def origin(
    origin_type: str, source: str, license_name: str | None = None
) -> dict[str, str]:
    value = {"type": origin_type, "source": source}
    if license_name:
        value["license"] = license_name
    return value


def blob(
    data: bytes, media_type: str, role: str, blob_origin: dict[str, str]
) -> dict[str, Any]:
    value_hash = digest(data)
    (BLOBS / value_hash).write_bytes(data)
    return {
        "$ref": f"sha256:{value_hash}",
        "bytes": len(data),
        "media_type": media_type,
        "encoding": "identity",
        "content_role": role,
        "origin": blob_origin,
    }


def text_blob(text: str, role: str, blob_origin: dict[str, str]) -> dict[str, Any]:
    return blob(text.encode("utf-8"), "text/plain", role, blob_origin)


def inline(value: Any, content_origin: dict[str, str]) -> dict[str, Any]:
    return {"value": value, "origin": content_origin}


def write_artifact(name: str, data: bytes) -> dict[str, Any]:
    path = BASE / name
    path.write_bytes(data)
    return {"path": name, "sha256": digest(data), "bytes": len(data)}


def tar_snapshot(files: dict[str, str]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name in sorted(files):
            data = files[name].encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


def timestamp(ms: int) -> str:
    return (
        (START + timedelta(milliseconds=ms))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def main() -> None:
    if BLOBS.exists():
        for child in BLOBS.iterdir():
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
    BLOBS.mkdir(exist_ok=True)

    project = origin("project", "proj-03", "Apache-2.0")
    model = origin("model", "example-ai/example-agent-model")
    tool = origin("tool", "ualf-demo-tools")
    evaluator = origin("external_system", "pytest-demo")

    goal_ref = text_blob(
        "Fix test_lease_renewal_extends_expiry without changing the test, then run the complete test suite.",
        "authored_prompt",
        project,
    )
    system_ref = text_blob(
        "You are a software-maintenance agent. Inspect evidence before editing, make the smallest correct change, and verify the full test suite.",
        "authored_prompt",
        project,
    )
    user_ref = text_blob(
        "Fix test_lease_renewal_extends_expiry without changing the test. Acceptance: the target test passes and no other test regresses.",
        "model_input",
        project,
    )
    failing_ref = text_blob(
        "FAILED tests/test_ledger.py::test_lease_renewal_extends_expiry - AssertionError: expected 2026-07-30T15:02:00Z, got 2026-07-30T14:32:00Z",
        "tool_output",
        tool,
    )
    model_output_ref = text_blob(
        "The 30-minute delta matches RENEWAL_WINDOW. Inspect renew() to confirm whether expiry is anchored to granted_at instead of the renewal time.",
        "model_output",
        model,
    )
    rationale_ref = text_blob(
        "Reading the narrow implementation is cheaper and more diagnostic than a repository-wide search because the observed delta already identifies the likely arithmetic anchor.",
        "model_reasoning",
        model,
    )

    tools_document = {
        "schema": "ualf-tools/v1",
        "tools": [
            {
                "name": "read_file",
                "version": "1.0",
                "input_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
            },
            {
                "name": "edit_file",
                "version": "1.0",
                "input_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["path", "old", "new"],
                    "properties": {
                        "path": {"type": "string"},
                        "old": {"type": "string"},
                        "new": {"type": "string"},
                    },
                },
            },
            {
                "name": "run_tests",
                "version": "1.2",
                "input_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["target"],
                    "properties": {"target": {"type": "string"}},
                },
            },
        ],
    }
    tools_ref = blob(
        compact(tools_document), "application/json", "tool_definitions", project
    )

    source_before = (
        "from datetime import timedelta\n\n"
        "RENEWAL_WINDOW = timedelta(minutes=30)\n\n"
        "class Lease:\n"
        "    def __init__(self, granted_at):\n"
        "        self.granted_at = granted_at\n"
        "        self.expires_at = granted_at + RENEWAL_WINDOW\n\n"
        "    def renew(self, now):\n"
        "        self.expires_at = self.granted_at + RENEWAL_WINDOW\n"
    )
    source_after = source_before.replace(
        "self.expires_at = self.granted_at + RENEWAL_WINDOW\n",
        "self.expires_at = now + RENEWAL_WINDOW\n",
        1,
    )
    test_source = (
        "from datetime import datetime, timedelta, timezone\n"
        "from src.ledger.lease import Lease, RENEWAL_WINDOW\n\n"
        "def test_lease_renewal_extends_expiry():\n"
        "    granted = datetime(2026, 7, 30, 14, 2, tzinfo=timezone.utc)\n"
        "    now = granted + timedelta(minutes=30)\n"
        "    lease = Lease(granted)\n"
        "    lease.renew(now)\n"
        "    assert lease.expires_at == now + RENEWAL_WINDOW\n"
    )
    snapshot = tar_snapshot(
        {
            "src/ledger/lease.py": source_before,
            "tests/test_ledger.py": test_source,
            "README.txt": "Self-contained UALF example replay fixture.\n",
        }
    )
    initial_state_ref = blob(snapshot, "application/x-tar", "initial_state", project)
    workspace_hash = digest(snapshot)

    diff_text = (
        "--- a/src/ledger/lease.py\n"
        "+++ b/src/ledger/lease.py\n"
        "@@ -8,4 +8,4 @@ class Lease:\n"
        "     def renew(self, now):\n"
        "-        self.expires_at = self.granted_at + RENEWAL_WINDOW\n"
        "+        self.expires_at = now + RENEWAL_WINDOW\n"
    )
    diff_ref = text_blob(diff_text, "diff", project)
    evidence_document = {
        "kind": "test-report",
        "runner": "pytest",
        "runner_version": "8.2.0",
        "command": "pytest tests/",
        "exit_code": 0,
        "summary": {"passed": 128, "failed": 0, "skipped": 0},
        "run_id": RUN_ID,
        "source_revision": "example-pre-fix+ualf-demo-change",
    }
    evidence_ref = blob(
        compact(evidence_document), "application/json", "evidence", evaluator
    )
    replay_document = {
        "kind": "stubbed-replay-report",
        "runner": "ualf-replay",
        "runner_version": "1.0",
        "run_id": RUN_ID,
        "status": "passed",
        "model_calls_replayed": 1,
        "tool_calls_replayed": 4,
        "result_match": True,
    }
    replay_evidence_ref = blob(
        compact(replay_document), "application/json", "evidence", evaluator
    )

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = f"ualf-demo-{digest(public_key)[:16]}"

    header = {
        "kind": "header",
        "seq": 1,
        "schema": "ualf-trace/v1",
        "run_id": RUN_ID,
        "trace_id": TRACE_ID,
        "trajectory_id": TRAJECTORY_ID,
        "project": "proj-03",
        "domain": "software_dev",
        "agent": {
            "framework": "aidoc-flow",
            "framework_version": "2.4.1",
            "role": "implementation-agent",
            "agent_version": "agent-3.1.0",
            "prompt_version": "prompt-17",
        },
        "task": {
            "goal": goal_ref,
            "category": "bugfix",
            "acceptance": ["target test passes", "complete suite has no regression"],
            "difficulty": 2,
        },
        "environment": {
            "workspace_sha256": workspace_hash,
            "source_revision": "example-pre-fix",
            "os": "linux-6.8",
            "runtime_versions": {"python": "3.12.4", "pytest": "8.2.0"},
            "tools_ref": tools_ref,
            "replay": {
                "available_level": "stubbed",
                "initial_state_ref": initial_state_ref,
                "model_responses_captured": True,
                "tool_responses_captured": True,
                "nondeterministic_inputs_captured": False,
                "verification": {
                    "status": "passed",
                    "verified_at": timestamp(10480),
                    "result_match": True,
                    "evidence_ref": replay_evidence_ref,
                },
            },
        },
        "capture": {
            "context_policy": "complete",
            "redaction_policy": "ualf-demo-redaction/v1",
            "retention_mode": "full",
        },
        "rights": {
            "owner": "UALF example author",
            "classification": "cleared",
            "model_sources": ["example-ai/example-agent-model"],
            "pii": "none",
            "secrets_scan": {
                "tool": "example-secret-scan",
                "version": "1.0",
                "verdict": "clean",
            },
        },
        "provenance": {
            "signing": {
                "key_id": key_id,
                "algorithm": "ed25519",
                "public_key": base64.b64encode(public_key).decode("ascii"),
            }
        },
        "started_at": timestamp(0),
    }

    events: list[dict[str, Any]] = []

    def add(
        event_id: str,
        event_type: str,
        ms: int,
        span: str,
        actor_type: str,
        actor_id: str,
        data: dict[str, Any],
        *,
        parent: str | None = "span-run",
        caused_by: str | None = None,
    ) -> None:
        event = {
            "kind": "event",
            "seq": len(events) + 2,
            "event_id": event_id,
            "run_id": RUN_ID,
            "trace_id": TRACE_ID,
            "span_id": span,
            "parent_span_id": parent,
            "actor": {"type": actor_type, "id": actor_id},
            "timestamp": timestamp(ms),
            "monotonic_ms": ms,
            "type": event_type,
            "data": data,
        }
        if caused_by:
            event["caused_by"] = caused_by
        events.append(event)

    add(
        "evt-run-observation",
        "observation.received",
        10,
        "span-run",
        "system",
        "runtime",
        {
            "source": "task-queue",
            "value": inline(
                {"task_received": True},
                origin("external_system", "task-queue"),
            ),
        },
        parent=None,
    )
    add(
        "evt-test-start-1",
        "tool_call.started",
        100,
        "span-test-1",
        "agent",
        "implementation-agent-1",
        {
            "call_id": "call-test-1",
            "tool": "run_tests",
            "tool_version": "1.2",
            "arguments": inline(
                {"target": "tests/test_ledger.py::test_lease_renewal_extends_expiry"},
                project,
            ),
        },
        caused_by="evt-run-observation",
    )
    add(
        "evt-test-end-1",
        "tool_call.completed",
        1940,
        "span-test-1",
        "tool",
        "run_tests",
        {
            "call_id": "call-test-1",
            "tool": "run_tests",
            "status": "error",
            "latency_ms": 1840,
            "output_ref": failing_ref,
            "error": {"class": "test_failure", "message": "1 failed"},
        },
        caused_by="evt-test-start-1",
    )
    add(
        "evt-test-error",
        "error.recorded",
        1941,
        "span-test-1",
        "system",
        "runtime",
        {"class": "tool_failure", "message": "Target test failed"},
        caused_by="evt-test-end-1",
    )
    add(
        "evt-model-start",
        "model_call.started",
        2000,
        "span-model-1",
        "agent",
        "implementation-agent-1",
        {
            "call_id": "call-model-1",
            "provider": "example-ai",
            "model": "example-agent-model",
            "parameters": {"temperature": 0},
            "context": [
                {"position": 0, "role": "system", "content_ref": system_ref},
                {"position": 1, "role": "user", "content_ref": user_ref},
                {
                    "position": 2,
                    "role": "tool",
                    "name": "run_tests",
                    "tool_call_id": "call-test-1",
                    "content_ref": failing_ref,
                },
            ],
            "tools_ref": tools_ref,
            "context_complete": True,
        },
        caused_by="evt-test-error",
    )
    add(
        "evt-model-end",
        "model_call.completed",
        3650,
        "span-model-1",
        "system",
        "model-gateway",
        {
            "call_id": "call-model-1",
            "provider": "example-ai",
            "model": "example-agent-model",
            "usage": {"tokens_in": 410, "tokens_out": 55},
            "cost_usd": 0.0012,
            "latency_ms": 1650,
            "finish_reason": "stop",
            "output_ref": model_output_ref,
            "request_id": "req-demo-001",
        },
        caused_by="evt-model-start",
    )
    add(
        "evt-decision",
        "decision.recorded",
        3660,
        "span-model-1",
        "agent",
        "implementation-agent-1",
        {
            "options": [
                {
                    "summary": "Read the lease renewal implementation",
                    "tool": "read_file",
                },
                {"summary": "Search for all renewal-window uses", "tool": "read_file"},
            ],
            "chosen": 0,
            "rationale_ref": rationale_ref,
        },
        caused_by="evt-model-end",
    )
    add(
        "evt-read-start",
        "tool_call.started",
        3700,
        "span-read-1",
        "agent",
        "implementation-agent-1",
        {
            "call_id": "call-read-1",
            "tool": "read_file",
            "tool_version": "1.0",
            "arguments": inline({"path": "src/ledger/lease.py"}, project),
        },
        caused_by="evt-decision",
    )
    add(
        "evt-read-end",
        "tool_call.completed",
        3795,
        "span-read-1",
        "tool",
        "read_file",
        {
            "call_id": "call-read-1",
            "tool": "read_file",
            "status": "ok",
            "latency_ms": 95,
            "output": inline(source_before, tool),
        },
        caused_by="evt-read-start",
    )
    add(
        "evt-edit-start",
        "tool_call.started",
        3900,
        "span-edit-1",
        "agent",
        "implementation-agent-1",
        {
            "call_id": "call-edit-1",
            "tool": "edit_file",
            "tool_version": "1.0",
            "arguments": inline(
                {
                    "path": "src/ledger/lease.py",
                    "old": "self.expires_at = self.granted_at + RENEWAL_WINDOW",
                    "new": "self.expires_at = now + RENEWAL_WINDOW",
                },
                project,
            ),
        },
        caused_by="evt-read-end",
    )
    add(
        "evt-edit-end",
        "tool_call.completed",
        3960,
        "span-edit-1",
        "tool",
        "edit_file",
        {
            "call_id": "call-edit-1",
            "tool": "edit_file",
            "status": "ok",
            "latency_ms": 60,
            "output": inline({"replacements": 1}, tool),
        },
        caused_by="evt-edit-start",
    )
    add(
        "evt-file-change",
        "file_change.recorded",
        3961,
        "span-edit-1",
        "system",
        "workspace-monitor",
        {
            "path": "src/ledger/lease.py",
            "pre_sha256": digest(source_before.encode()),
            "post_sha256": digest(source_after.encode()),
            "diff_ref": diff_ref,
        },
        caused_by="evt-edit-end",
    )
    add(
        "evt-retry",
        "retry.started",
        4000,
        "span-test-2",
        "agent",
        "implementation-agent-1",
        {
            "retry_of": "evt-test-end-1",
            "strategy": "rerun complete suite after targeted fix",
        },
        caused_by="evt-file-change",
    )
    add(
        "evt-test-start-2",
        "tool_call.started",
        4010,
        "span-test-2",
        "agent",
        "implementation-agent-1",
        {
            "call_id": "call-test-2",
            "tool": "run_tests",
            "tool_version": "1.2",
            "arguments": inline({"target": "tests/"}, project),
        },
        caused_by="evt-retry",
    )
    add(
        "evt-test-end-2",
        "tool_call.completed",
        10360,
        "span-test-2",
        "tool",
        "run_tests",
        {
            "call_id": "call-test-2",
            "tool": "run_tests",
            "status": "ok",
            "latency_ms": 6350,
            "output": inline({"passed": 128, "failed": 0}, tool),
        },
        caused_by="evt-test-start-2",
    )

    evaluation = {
        "evaluator": "pytest",
        "evaluator_version": "8.2.0",
        "method": "oracle:test",
        "status": "passed",
        "score": 1.0,
        "evidence_quality": "artifact",
        "evidence_ref": evidence_ref,
    }
    add(
        "evt-evaluation",
        "evaluation.completed",
        10400,
        "span-eval-1",
        "evaluator",
        "pytest",
        evaluation,
        caused_by="evt-test-end-2",
    )

    records: list[dict[str, Any]] = [header] + events
    lines: list[bytes] = []
    for record in records:
        if lines:
            record["prev_sha256"] = digest(lines[-1])
        lines.append(compact(record))

    outcome = {
        "kind": "outcome",
        "seq": len(records) + 1,
        "run_id": RUN_ID,
        "trace_id": TRACE_ID,
        "timestamp": timestamp(10450),
        "monotonic_ms": 10450,
        "prev_sha256": digest(lines[-1]),
        "status": "success",
        "evaluations": [evaluation],
        "totals": {
            "events": len(events),
            "model_calls": 1,
            "tool_calls": 4,
            "errors": 1,
            "retries": 1,
            "tokens_in": 410,
            "tokens_out": 55,
            "cost_usd": 0.0012,
            "wall_ms": 10450,
        },
    }
    chain_sha256 = digest(rfc8785.dumps(outcome))
    signature = private_key.sign(bytes.fromhex(chain_sha256))
    outcome["seal"] = {
        "chain_sha256": chain_sha256,
        "signature": {
            "key_id": key_id,
            "algorithm": "ed25519",
            "value": base64.b64encode(signature).decode("ascii"),
        },
    }
    lines.append(compact(outcome))
    trajectory_path = BASE / "example-trajectory.jsonl"
    trajectory_path.write_bytes(b"\n".join(lines) + b"\n")

    quality = {
        "schema": "ualf-quality/v1.1",
        "dataset_id": "ualf-example-dataset-001",
        "generated_at": timestamp(11000),
        "generator": "ualf-example-builder/v1",
        "qualification_policy": "ualf-default-qualification/v1",
        "traces": [
            {
                "trajectory_id": TRAJECTORY_ID,
                "trace_sha256": digest(trajectory_path.read_bytes()),
                "schema_valid": True,
                "integrity_verified": True,
                "context_completeness": "complete",
                "evidence_quality": "artifact",
                "replay_quality": "stubbed",
                "rights_status": "cleared",
                "hygiene_status": "clean",
                "export_eligible": True,
                "commercial_tier": "B",
                "findings": [
                    "Evidence is not independently signed or reproduced.",
                    "Replay is below verified tool reexecution.",
                ],
            }
        ],
    }
    quality_bytes = (
        json.dumps(quality, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    )
    quality_artifact = write_artifact("example-quality-report.json", quality_bytes)

    datasheet_bytes = (
        b"# UALF Example Dataset Datasheet\n\n"
        b"This package contains one synthetic software-maintenance trajectory for\n"
        b"format and pipeline testing. It is not representative training inventory.\n\n"
        b"## Collection and labels\n\n"
        b"The fixture is generated locally by `build_example.py`. Test evidence and\n"
        b"stubbed replay evidence are self-contained artifacts. No personal, client,\n"
        b"or production data is included.\n\n"
        b"## Limitations\n\n"
        b"The evaluator evidence is not externally signed, and replay does not\n"
        b"reexecute tools. The single trace is not representative training inventory\n"
        b"and should be used only as a format and integration fixture.\n"
    )
    datasheet_artifact = write_artifact("datasheet.md", datasheet_bytes)

    rights_bytes = (
        json.dumps(
            {
                "schema": "ualf-rights-attestation/v1",
                "dataset_id": "ualf-example-dataset-001",
                "reviewed_by": "example-human-reviewer",
                "reviewed_at": timestamp(10900),
                "status": "cleared",
                "basis": "All fixture content is synthetic and generated by the example author.",
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        + b"\n"
    )
    rights_artifact = write_artifact("rights-attestation.json", rights_bytes)

    dedup_bytes = (
        json.dumps(
            {
                "schema": "ualf-dedup-report/v1",
                "method": "exact-sha256/v1",
                "trace_count": 1,
                "unique_trace_count": 1,
                "exact_duplicates_remaining": 0,
            },
            indent=2,
        ).encode("utf-8")
        + b"\n"
    )
    dedup_artifact = write_artifact("dedup-report.json", dedup_bytes)

    blob_entries = [
        {
            "path": f"blobs/{path.name}",
            "sha256": path.name,
            "bytes": path.stat().st_size,
        }
        for path in sorted(BLOBS.iterdir(), key=lambda item: item.name)
        if path.is_file()
    ]

    manifest = {
        "schema": "ualf-dataset/v1.1",
        "dataset_id": "ualf-example-dataset-001",
        "created_at": timestamp(11000),
        "trace_schema": "ualf-trace/v1",
        "export_profile": "full",
        "intended_uses": ["format evaluation", "tool-use pipeline integration testing"],
        "prohibited_uses": [],
        "traces": [
            {
                "trajectory_id": TRAJECTORY_ID,
                "path": "example-trajectory.jsonl",
                "sha256": digest(trajectory_path.read_bytes()),
                "bytes": trajectory_path.stat().st_size,
            }
        ],
        "blobs": blob_entries,
        "splits": {"train": [TRAJECTORY_ID], "validation": [], "test": []},
        "rights_summary": {
            "status": "cleared",
            "owners": ["UALF example author"],
            "license": "Apache-2.0",
            "reviewed_by": "example-human-reviewer",
            "reviewed_at": timestamp(10900),
            "evidence": rights_artifact,
        },
        "deduplication": {
            "method": "exact-sha256/v1",
            "exact_duplicates_remaining": 0,
            "report": dedup_artifact,
        },
        "quality_report": quality_artifact,
        "datasheet": datasheet_artifact,
        "provenance": {
            "signing": {
                "key_id": key_id,
                "algorithm": "ed25519",
                "public_key": base64.b64encode(public_key).decode("ascii"),
            }
        },
    }
    manifest_hash = digest(rfc8785.dumps(manifest))
    manifest["seal"] = {
        "manifest_sha256": manifest_hash,
        "signature": {
            "key_id": key_id,
            "algorithm": "ed25519",
            "value": base64.b64encode(
                private_key.sign(bytes.fromhex(manifest_hash))
            ).decode("ascii"),
        },
    }
    (BASE / "example-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
