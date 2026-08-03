#!/usr/bin/env python3
"""Verify a materialized UALF Trace v1.1 file and optional dataset metadata.

Usage:
  python verify.py TRACE.jsonl [--blobs DIR]
         [--manifest manifest.json] [--quality-report quality-report.json]

Exit 0 means that every requested validation passed. Qualification and legal
clearance remain separate from trace conformance.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import gzip
import hashlib
import json
import math
import tarfile
from datetime import datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        suffix = f" — {detail}" if detail and not ok else ""
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{suffix}")
        if not ok:
            self.failures.append(name)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_b64(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def collect_refs(value: Any, refs: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("$ref"), str) and value["$ref"].startswith("sha256:"):
            refs.append(value)
        for child in value.values():
            collect_refs(child, refs)
    elif isinstance(value, list):
        for child in value:
            collect_refs(child, refs)


def read_jsonl(path: Path, report: Report) -> tuple[list[bytes], list[dict[str, Any]]]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        report.check("trajectory readable", False, str(exc))
        return [], []

    report.check("non-empty trajectory", bool(payload))
    if not payload:
        return [], []
    report.check("no UTF-8 BOM", not payload.startswith(b"\xef\xbb\xbf"))

    physical = payload.splitlines()
    report.check("no blank physical lines", all(line.strip() for line in physical))

    raw: list[bytes] = []
    objects: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for number, line in enumerate(physical, 1):
        if not line.strip():
            continue
        try:
            text = line.decode("utf-8", errors="strict")
            value = json.loads(text)
            if not isinstance(value, dict):
                raise TypeError("line is not a JSON object")
            raw.append(line)
            objects.append(value)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            parse_errors.append(f"line {number}: {exc}")
    report.check(
        "UTF-8 JSON object per line", not parse_errors, "; ".join(parse_errors[:3])
    )
    return raw, objects


def validate_schema(
    objects: list[dict[str, Any]], schema_path: Path, report: Report
) -> bool:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError:
        report.check("schema validation", False, "install jsonschema")
        return False
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = [
            (line, error)
            for line, obj in enumerate(objects, 1)
            for error in validator.iter_errors(obj)
        ]
        detail = "; ".join(
            f"line {line} at {'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for line, error in errors[:5]
        )
        report.check("schema validation", not errors, detail)
        return not errors
    except (OSError, json.JSONDecodeError) as exc:
        report.check("schema validation", False, str(exc))
        return False


def verify_structure(
    raw: list[bytes], objects: list[dict[str, Any]], report: Report
) -> None:
    if not objects:
        return
    kinds = [obj.get("kind") for obj in objects]
    report.check(
        "one header first / one outcome last",
        kinds[0] == "header"
        and kinds[-1] == "outcome"
        and kinds.count("header") == 1
        and kinds.count("outcome") == 1,
    )
    report.check(
        "seq gapless",
        [obj.get("seq") for obj in objects] == list(range(1, len(objects) + 1)),
    )

    header = objects[0]
    run_id, trace_id = header.get("run_id"), header.get("trace_id")
    report.check(
        "run_id consistent", all(obj.get("run_id", run_id) == run_id for obj in objects)
    )
    report.check(
        "trace_id consistent",
        all(obj.get("trace_id", trace_id) == trace_id for obj in objects),
    )
    for field in ("organization", "project", "deployment_environment", "session_id"):
        expected = header.get(field)
        report.check(
            f"{field} consistent",
            all(obj.get(field, expected) == expected for obj in objects),
        )

    try:
        observed = [
            datetime.fromisoformat(obj["observed_at"].replace("Z", "+00:00"))
            for obj in objects[1:]
        ]
        report.check("observation timestamps ordered", observed == sorted(observed))
        per_clock: dict[tuple[str, str, str], list[tuple[int, int]]] = {}
        for obj in objects[1:]:
            producer = obj["producer"]
            key = (producer["id"], producer["process_id"], producer["clock_id"])
            per_clock.setdefault(key, []).append(
                (producer["local_seq"], obj["monotonic_ms"])
            )
        clocks_ok = all(
            values == sorted(values) and len({seq for seq, _ in values}) == len(values)
            for values in per_clock.values()
        )
        report.check("producer-local clocks ordered", clocks_ok)
    except (KeyError, TypeError, ValueError) as exc:
        report.check("producer-local clocks ordered", False, str(exc))

    breaks = [
        index + 1
        for index in range(1, min(len(raw), len(objects)))
        if objects[index].get("prev_sha256") != sha256(raw[index - 1])
    ]
    report.check("exact-byte hash chain", not breaks, f"broken at line(s) {breaks}")


def verify_events(
    objects: list[dict[str, Any]], blobs_dir: Path, report: Report
) -> dict[str, Any]:
    if len(objects) < 2:
        return {}
    header = objects[0]
    events = [obj for obj in objects[1:-1] if obj.get("kind") == "event"]

    event_ids = [event.get("event_id") for event in events]
    report.check("event IDs unique", len(event_ids) == len(set(event_ids)))
    seen: set[str] = set()
    bad_causes: list[str] = []
    bad_retries: list[str] = []
    for event in events:
        cause = event.get("caused_by")
        if cause is not None and cause not in seen:
            bad_causes.append(str(event.get("event_id")))
        if (
            event.get("type") == "retry.started"
            and event.get("data", {}).get("retry_of") not in seen
        ):
            bad_retries.append(str(event.get("event_id")))
        if isinstance(event.get("event_id"), str):
            seen.add(event["event_id"])
    report.check(
        "causal references point backward", not bad_causes, f"bad events {bad_causes}"
    )
    report.check(
        "retry references point backward", not bad_retries, f"bad events {bad_retries}"
    )

    spans_seen = {event.get("span_id") for event in events}
    bad_parents = [
        str(event.get("event_id"))
        for event in events
        if event.get("parent_span_id") is not None
        and event.get("parent_span_id") not in spans_seen
    ]
    report.check("parent spans resolve", not bad_parents, f"bad events {bad_parents}")
    span_parents: dict[str, str | None] = {}
    span_conflicts: list[str] = []
    for event in events:
        span = event.get("span_id")
        parent = event.get("parent_span_id")
        if span == parent:
            span_conflicts.append(str(span))
        if span in span_parents and span_parents[span] != parent:
            span_conflicts.append(str(span))
        elif isinstance(span, str):
            span_parents[span] = parent
    cyclic: list[str] = []
    for span in span_parents:
        cursor: str | None = span
        visited: set[str] = set()
        while cursor is not None and cursor in span_parents:
            if cursor in visited:
                cyclic.append(span)
                break
            visited.add(cursor)
            cursor = span_parents[cursor]
    report.check(
        "span hierarchy acyclic and consistent",
        not span_conflicts and not cyclic,
        f"conflicts {span_conflicts}, cycles {cyclic}",
    )

    starts: dict[tuple[str, str], dict[str, Any]] = {}
    completes: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_calls: list[str] = []
    for event in events:
        event_type = event.get("type", "")
        data = event.get("data", {})
        if event_type in {"model_call.started", "tool_call.started"}:
            family = event_type.split(".")[0]
            key = (family, str(data.get("call_id")))
            if key in starts:
                duplicate_calls.append(f"start:{key}")
            starts[key] = event
        elif event_type in {"model_call.completed", "tool_call.completed"}:
            family = event_type.split(".")[0]
            key = (family, str(data.get("call_id")))
            if key in completes:
                duplicate_calls.append(f"complete:{key}")
            completes[key] = event
    report.check(
        "call IDs unique per lifecycle", not duplicate_calls, str(duplicate_calls)
    )
    report.check(
        "calls paired",
        starts.keys() == completes.keys(),
        f"unpaired {sorted(starts.keys() ^ completes.keys())}",
    )

    mismatched: list[str] = []
    bad_lifecycle: list[str] = []
    for key in starts.keys() & completes.keys():
        start_event, end_event = starts[key], completes[key]
        start_data = start_event.get("data", {})
        end_data = end_event.get("data", {})
        if key[0] == "model_call" and (
            start_data.get("provider"),
            start_data.get("model"),
        ) != (end_data.get("provider"), end_data.get("model")):
            mismatched.append(key[1])
        if key[0] == "tool_call" and start_data.get("tool") != end_data.get("tool"):
            mismatched.append(key[1])
        same_clock = (
            start_event.get("producer", {}).get("clock_id")
            == end_event.get("producer", {}).get("clock_id")
        )
        elapsed = end_event.get("monotonic_ms", 0) - start_event.get("monotonic_ms", 0)
        latency_ok = "latency_state" in end_data or (
            same_clock and elapsed == end_data.get("latency_ms")
        )
        if (
            start_event.get("seq", 0) >= end_event.get("seq", 0)
            or start_event.get("span_id") != end_event.get("span_id")
            or end_event.get("caused_by") != start_event.get("event_id")
            or not latency_ok
        ):
            bad_lifecycle.append(key[1])
    report.check("call identity consistent", not mismatched, f"mismatched {mismatched}")
    report.check(
        "call lifecycle order and latency consistent",
        not bad_lifecycle,
        f"bad calls {bad_lifecycle}",
    )

    activity_starts: dict[tuple[str, str], dict[str, Any]] = {}
    activity_completes: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_activities: list[str] = []
    for event in events:
        event_type = event.get("type", "")
        if event_type not in {
            "agent.started",
            "agent.completed",
            "delegation.started",
            "delegation.completed",
        }:
            continue
        family, phase = event_type.split(".", 1)
        key = (family, str(event.get("data", {}).get("activity_id")))
        target = activity_starts if phase == "started" else activity_completes
        if key in target:
            duplicate_activities.append(f"{phase}:{key}")
        target[key] = event
    report.check(
        "agent activity IDs unique per lifecycle",
        not duplicate_activities,
        str(duplicate_activities),
    )
    report.check(
        "agent activities paired",
        activity_starts.keys() == activity_completes.keys(),
        f"unpaired {sorted(activity_starts.keys() ^ activity_completes.keys())}",
    )
    bad_activities: list[str] = []
    for key in activity_starts.keys() & activity_completes.keys():
        start_event = activity_starts[key]
        end_event = activity_completes[key]
        if (
            start_event.get("seq", 0) >= end_event.get("seq", 0)
            or start_event.get("span_id") != end_event.get("span_id")
            or start_event.get("data", {}).get("agent_id")
            != end_event.get("data", {}).get("agent_id")
        ):
            bad_activities.append(key[1])
    report.check(
        "agent activity lifecycle consistent",
        not bad_activities,
        f"bad activities {bad_activities}",
    )

    positions_bad: list[str] = []
    incomplete_context: list[str] = []
    for key, event in starts.items():
        if key[0] != "model_call":
            continue
        data = event.get("data", {})
        positions = [item.get("position") for item in data.get("context", [])]
        if positions != list(range(len(positions))):
            positions_bad.append(key[1])
        if not data.get("context_complete", False):
            incomplete_context.append(key[1])
    report.check(
        "model context positions gapless",
        not positions_bad,
        f"bad calls {positions_bad}",
    )
    report.check(
        "model context complete",
        not incomplete_context,
        f"incomplete calls {incomplete_context}",
    )

    tools: dict[str, str] = {}
    tools_ref = header.get("environment", {}).get("tools_ref")
    if isinstance(tools_ref, dict) and isinstance(tools_ref.get("$ref"), str):
        path = blobs_dir / tools_ref["$ref"][7:]
        try:
            from jsonschema import Draft202012Validator
            from jsonschema.exceptions import SchemaError
        except ImportError as exc:
            report.check(
                "tool definitions parse", False, f"install dependency: {exc.name}"
            )
        else:
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
                tool_schema = json.loads(
                    (
                        Path(__file__).resolve().parent
                        / "ualf-tool-definitions.schema.json"
                    ).read_text(encoding="utf-8")
                )
                tool_errors = list(
                    Draft202012Validator(tool_schema).iter_errors(document)
                )
                if tool_errors:
                    raise ValueError(tool_errors[0].message)
                for item in document["tools"]:
                    Draft202012Validator.check_schema(item["input_schema"])
                identities = [
                    (item["name"], item["version"]) for item in document["tools"]
                ]
                if len(identities) != len(set(identities)):
                    raise ValueError("duplicate tool name/version")
                tools = {
                    item["name"]: item["version"] for item in document.get("tools", [])
                }
                report.check("tool definitions parse", bool(tools))
            except (
                OSError,
                UnicodeDecodeError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
                SchemaError,
            ) as exc:
                report.check("tool definitions parse", False, str(exc))
    else:
        report.check("tool definitions parse", False, "missing tools_ref")

    undeclared_tools: list[str] = []
    for key, event in starts.items():
        if key[0] != "tool_call":
            continue
        data = event.get("data", {})
        if tools.get(data.get("tool")) != data.get("tool_version"):
            undeclared_tools.append(str(data.get("tool")))
    report.check(
        "tool calls match declared action space",
        not undeclared_tools,
        f"undeclared/version mismatch {undeclared_tools}",
    )

    model_tool_mismatch = [
        key[1]
        for key, event in starts.items()
        if key[0] == "model_call"
        and event.get("data", {}).get("tools_ref") != tools_ref
    ]
    report.check(
        "model calls use declared tool snapshot",
        not model_tool_mismatch,
        f"bad calls {model_tool_mismatch}",
    )

    bad_choices = [
        str(event.get("event_id"))
        for event in events
        if event.get("type") == "decision.recorded"
        and event.get("data", {}).get("chosen", -1)
        >= len(event.get("data", {}).get("options", []))
    ]
    report.check("decision indexes valid", not bad_choices, f"bad events {bad_choices}")

    evaluations = [
        event.get("data")
        for event in events
        if event.get("type") == "evaluation.completed"
    ]
    outcome_evaluations = objects[-1].get("evaluations", []) if objects else []
    report.check(
        "outcome evaluations derive from events", outcome_evaluations == evaluations
    )
    outcome_status = objects[-1].get("status")
    evaluation_statuses = [item.get("status") for item in outcome_evaluations]
    status_ok = (
        (outcome_status == "aborted")
        or (
            outcome_status == "success"
            and evaluation_statuses
            and all(x == "passed" for x in evaluation_statuses)
        )
        or (outcome_status == "failure" and "failed" in evaluation_statuses)
        or (
            outcome_status == "partial"
            and evaluation_statuses
            and ("partial" in evaluation_statuses or len(set(evaluation_statuses)) > 1)
        )
    )
    report.check(
        "outcome status matches evaluations",
        status_ok,
        f"outcome {outcome_status}, evaluations {evaluation_statuses}",
    )
    return {"events": events, "starts": starts, "completes": completes}


def safe_tar(data: bytes) -> bool:
    try:
        with tarfile.open(fileobj=BytesIO(data), mode="r:*") as archive:
            for member in archive.getmembers():
                name = PurePosixPath(member.name.replace("\\", "/"))
                if (
                    name.is_absolute()
                    or ".." in name.parts
                    or member.issym()
                    or member.islnk()
                    or member.isdev()
                    or not (member.isfile() or member.isdir())
                ):
                    return False
        return True
    except (OSError, tarfile.TarError):
        return False


def check_media(path: Path, ref: dict[str, Any]) -> bool:
    media_type = ref.get("media_type")
    encoding = ref.get("encoding")
    try:
        data = path.read_bytes()
        if encoding == "gzip":
            data = gzip.decompress(data)
        elif encoding != "identity":
            return False
        if media_type == "application/json":
            json.loads(data.decode("utf-8"))
        elif media_type == "application/x-tar":
            if not safe_tar(data):
                return False
        elif isinstance(media_type, str) and (
            media_type.startswith("text/") or media_type.endswith("+json")
        ):
            data.decode("utf-8")
        return True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, gzip.BadGzipFile):
        return False


def verify_blobs(
    objects: list[dict[str, Any]], blobs_dir: Path, report: Report
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for obj in objects:
        collect_refs(obj, refs)
    missing: list[str] = []
    mismatched: list[str] = []
    wrong_size: list[str] = []
    wrong_media: list[str] = []
    for ref in refs:
        digest = ref["$ref"][7:]
        path = blobs_dir / digest
        if not path.is_file():
            missing.append(digest[:12])
            continue
        data = path.read_bytes()
        if sha256(data) != digest:
            mismatched.append(digest[:12])
        if len(data) != ref.get("bytes"):
            wrong_size.append(digest[:12])
        if not check_media(path, ref):
            wrong_media.append(digest[:12])
    report.check(
        f"blob refs resolve ({len(refs)} refs)", not missing, f"missing {missing}"
    )
    report.check("blob hashes match", not mismatched, f"mismatched {mismatched}")
    report.check("blob byte counts match", not wrong_size, f"wrong sizes {wrong_size}")
    report.check(
        "blob media is usable", not wrong_media, f"invalid media {wrong_media}"
    )
    return refs


def verify_model_sources(
    objects: list[dict[str, Any]], refs: list[dict[str, Any]], report: Report
) -> None:
    if not objects:
        return
    declared = set(objects[0].get("rights", {}).get("model_sources", []))
    used = {
        ref.get("origin", {}).get("source")
        for ref in refs
        if ref.get("origin", {}).get("type") == "model"
    }
    used.discard(None)
    report.check(
        "model sources complete",
        used <= declared,
        f"undeclared {sorted(used - declared)}",
    )

    bad_outputs: list[str] = []
    for obj in objects:
        if obj.get("type") != "model_call.completed":
            continue
        data = obj.get("data", {})
        ref = data.get("output_ref")
        expected = f"{data.get('provider')}/{data.get('model')}"
        if ref is not None and (
            ref.get("content_role") != "model_output"
            or ref.get("origin", {}).get("type") != "model"
            or ref.get("origin", {}).get("source") != expected
        ):
            bad_outputs.append(str(data.get("call_id")))
    report.check(
        "model outputs carry exact provenance",
        not bad_outputs,
        f"bad calls {bad_outputs}",
    )


def verify_totals(
    objects: list[dict[str, Any]], event_state: dict[str, Any], report: Report
) -> None:
    if not objects or not event_state:
        return
    events = event_state["events"]
    model_completions = [
        event for event in events if event.get("type") == "model_call.completed"
    ]
    expected = {
        "events": len(events),
        "model_calls": len(model_completions),
        "tool_calls": sum(
            event.get("type") == "tool_call.completed" for event in events
        ),
        "errors": sum(event.get("type") == "error.recorded" for event in events),
        "retries": sum(event.get("type") == "retry.started" for event in events),
        "tokens_in": sum(
            (event.get("data", {}).get("usage") or {}).get("tokens_in", 0)
            for event in model_completions
        ),
        "tokens_out": sum(
            (event.get("data", {}).get("usage") or {}).get("tokens_out", 0)
            for event in model_completions
        ),
        "cost_usd": round(
            sum(
                event.get("data", {}).get("cost_usd") or 0 for event in model_completions
            ),
            12,
        ),
        "wall_ms": objects[-1].get("monotonic_ms"),
    }
    actual = objects[-1].get("totals", {})
    costs_equal = isinstance(actual.get("cost_usd"), (int, float)) and math.isclose(
        actual["cost_usd"], expected["cost_usd"], rel_tol=0, abs_tol=1e-12
    )
    equal = (
        all(
            actual.get(key) == value
            for key, value in expected.items()
            if key != "cost_usd"
        )
        and costs_equal
    )
    report.check(
        "outcome totals recompute", equal, f"stamped {actual}, computed {expected}"
    )


def verify_replay(objects: list[dict[str, Any]], report: Report) -> None:
    if not objects:
        return
    replay = objects[0].get("environment", {}).get("replay", {})
    level = replay.get("available_level")
    rank = {
        name: index
        for index, name in enumerate(
            [
                "none",
                "trace",
                "stubbed",
                "tool_reexecution",
                "full_reexecution",
                "outcome_reproduced",
            ]
        )
    }
    ok = level in rank
    if ok and rank[level] >= rank["stubbed"]:
        ok = (
            replay.get("model_responses_captured") is True
            and replay.get("tool_responses_captured") is True
        )
        verification = replay.get("verification", {})
        ok = (
            ok
            and verification.get("status") == "passed"
            and verification.get("result_match") is True
        )
    if ok and rank[level] >= rank["tool_reexecution"]:
        ok = (
            isinstance(replay.get("initial_state_ref"), dict)
            and replay.get("nondeterministic_inputs_captured") is True
        )
    report.check("replay claim supported", ok, f"unsupported level {level}")


def verify_seal(objects: list[dict[str, Any]], report: Report) -> None:
    if not objects:
        return
    try:
        import rfc8785
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        report.check("seal verification", False, f"install dependency: {exc.name}")
        return
    try:
        header = objects[0]
        outcome = dict(objects[-1])
        seal = outcome.pop("seal")
        signing = header["provenance"]["signing"]
        signature = seal["signature"]
        report.check(
            "seal identity matches header",
            signing["key_id"] == signature["key_id"]
            and signing["algorithm"] == signature["algorithm"],
        )
        canonical = rfc8785.dumps(outcome)
        expected = sha256(canonical)
        report.check(
            "seal chain_sha256",
            expected == seal["chain_sha256"],
            f"computed {expected}",
        )
        public_bytes = strict_b64(signing["public_key"])
        signature_bytes = strict_b64(signature["value"])
        report.check(
            "Ed25519 key/signature lengths",
            len(public_bytes) == 32 and len(signature_bytes) == 64,
        )
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(
            signature_bytes, bytes.fromhex(seal["chain_sha256"])
        )
        report.check("Ed25519 signature", True)
    except (
        KeyError,
        TypeError,
        ValueError,
        binascii.Error,
        InvalidSignature,
        rfc8785.CanonicalizationError,
    ) as exc:
        report.check("Ed25519 signature", False, str(exc))


def validate_optional_document(
    path: Path | None, schema_path: Path, label: str, report: Report
) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        from jsonschema import Draft202012Validator, FormatChecker

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = list(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
                document
            )
        )
        report.check(
            label, not errors, "; ".join(error.message for error in errors[:3])
        )
        return document if not errors else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ImportError) as exc:
        report.check(label, False, str(exc))
        return None


def safe_resolve(root: Path, relative: str) -> Path | None:
    try:
        candidate = (root / relative).resolve()
        return candidate if candidate.is_relative_to(root.resolve()) else None
    except (OSError, TypeError, ValueError):
        return None


def verify_trace(
    trajectory_path: Path,
    schema_path: Path,
    blobs_dir: Path,
    report: Report,
) -> dict[str, Any]:
    print(f"UALF trace: {trajectory_path}")
    before = len(report.failures)
    raw, objects = read_jsonl(trajectory_path, report)
    schema_valid = False
    refs: list[dict[str, Any]] = []
    if objects:
        schema_valid = validate_schema(objects, schema_path, report)
        verify_structure(raw, objects, report)
        refs = verify_blobs(objects, blobs_dir, report)
        event_state = verify_events(objects, blobs_dir, report)
        verify_model_sources(objects, refs, report)
        verify_totals(objects, event_state, report)
        verify_replay(objects, report)
        verify_seal(objects, report)

    new_failures = report.failures[before:]
    integrity_verified = bool(objects) and not any(
        name != "schema validation" for name in new_failures
    )
    model_starts = [obj for obj in objects if obj.get("type") == "model_call.started"]
    if not model_starts:
        context_completeness = "missing"
    elif all(
        obj.get("data", {}).get("context_complete") is True for obj in model_starts
    ):
        context_completeness = "complete"
    else:
        context_completeness = "partial"

    evidence_rank = {
        "none": 0,
        "self_report": 1,
        "artifact": 2,
        "signed_external": 3,
        "reproduced": 4,
    }
    evaluations = objects[-1].get("evaluations", []) if objects else []
    evidence_quality = (
        min(
            (item.get("evidence_quality", "none") for item in evaluations),
            key=lambda name: evidence_rank.get(name, 0),
        )
        if evaluations
        else "none"
    )
    header = objects[0] if objects else {}
    replay_quality = (
        header.get("environment", {}).get("replay", {}).get("available_level", "none")
    )
    if "replay claim supported" in new_failures:
        replay_quality = "none"
    return {
        "path": trajectory_path,
        "objects": objects,
        "header": header,
        "refs": refs,
        "trajectory_id": header.get("trajectory_id"),
        "trace_sha256": sha256(trajectory_path.read_bytes())
        if trajectory_path.is_file()
        else None,
        "schema_valid": bool(schema_valid),
        "integrity_verified": bool(integrity_verified),
        "context_completeness": context_completeness,
        "evidence_quality": evidence_quality,
        "replay_quality": replay_quality,
        "hygiene_status": header.get("rights", {})
        .get("secrets_scan", {})
        .get("verdict", "not_run"),
    }


def verify_artifact(
    root: Path, artifact: dict[str, Any], label: str, report: Report
) -> Path | None:
    path = safe_resolve(root, artifact.get("path"))
    report.check(f"{label} path contained", path is not None)
    if path is None:
        return None
    report.check(f"{label} exists", path.is_file())
    if not path.is_file():
        return None
    data = path.read_bytes()
    report.check(f"{label} digest", sha256(data) == artifact.get("sha256"))
    report.check(f"{label} byte count", len(data) == artifact.get("bytes"))
    return path


def verify_signed_evidence(
    path: Path | None, schema_path: Path, label: str, report: Report
) -> dict[str, Any] | None:
    document = validate_optional_document(path, schema_path, f"{label} schema", report)
    if document is None:
        return None
    try:
        import rfc8785
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        unsigned = dict(document)
        seal = unsigned.pop("seal")
        expected = sha256(rfc8785.dumps(unsigned))
        digest_ok = expected == seal["document_sha256"]
        report.check(f"{label} digest", digest_ok)
        Ed25519PublicKey.from_public_bytes(strict_b64(seal["public_key"])).verify(
            strict_b64(seal["signature"]), bytes.fromhex(seal["document_sha256"])
        )
        report.check(f"{label} signature", digest_ok)
        return document if digest_ok else None
    except (
        KeyError,
        TypeError,
        ValueError,
        binascii.Error,
        InvalidSignature,
        rfc8785.CanonicalizationError,
    ) as exc:
        report.check(f"{label} signature", False, str(exc))
        return None


def verify_manifest_seal(manifest: dict[str, Any], report: Report) -> None:
    try:
        import rfc8785
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        report.check("dataset manifest signature", False, f"install {exc.name}")
        return
    try:
        unsigned = dict(manifest)
        seal = unsigned.pop("seal")
        signing = manifest["provenance"]["signing"]
        signature = seal["signature"]
        report.check(
            "dataset seal identity matches",
            signing["key_id"] == signature["key_id"]
            and signing["algorithm"] == signature["algorithm"],
        )
        expected = sha256(rfc8785.dumps(unsigned))
        report.check(
            "dataset manifest_sha256",
            expected == seal["manifest_sha256"],
            f"computed {expected}",
        )
        public_bytes = strict_b64(signing["public_key"])
        signature_bytes = strict_b64(signature["value"])
        report.check(
            "dataset key/signature lengths",
            len(public_bytes) == 32 and len(signature_bytes) == 64,
        )
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(
            signature_bytes, bytes.fromhex(seal["manifest_sha256"])
        )
        report.check("dataset manifest signature", True)
    except (
        KeyError,
        TypeError,
        ValueError,
        binascii.Error,
        InvalidSignature,
        rfc8785.CanonicalizationError,
    ) as exc:
        report.check("dataset manifest signature", False, str(exc))


def derive_quality(trace: dict[str, Any], rights_status: str) -> dict[str, Any]:
    evidence_rank = {
        "none": 0,
        "self_report": 1,
        "artifact": 2,
        "signed_external": 3,
        "reproduced": 4,
    }
    replay_rank = {
        "none": 0,
        "trace": 1,
        "stubbed": 2,
        "tool_reexecution": 3,
        "full_reexecution": 4,
        "outcome_reproduced": 5,
    }
    eligible = (
        trace["schema_valid"]
        and trace["integrity_verified"]
        and trace["context_completeness"] == "complete"
        and evidence_rank[trace["evidence_quality"]] >= evidence_rank["artifact"]
        and replay_rank[trace["replay_quality"]] >= replay_rank["trace"]
        and rights_status == "cleared"
        and trace["hygiene_status"] == "clean"
        and trace.get("rights_evidence_verified") is True
        and trace.get("hygiene_evidence_verified") is True
        and trace.get("replay_evidence_verified") is True
        and trace.get("capture_completeness") in {"complete", "synthetic"}
        and trace.get("revocation_status") == "active"
    )
    if (
        not trace["schema_valid"]
        or not trace["integrity_verified"]
        or not trace.get("rights_evidence_verified")
        or not trace.get("hygiene_evidence_verified")
        or not trace.get("replay_evidence_verified")
        or trace.get("capture_completeness") not in {"complete", "synthetic"}
        or trace.get("revocation_status") != "active"
    ):
        tier = "reject"
    elif not eligible:
        tier = "C"
    elif (
        evidence_rank[trace["evidence_quality"]] >= evidence_rank["signed_external"]
        and replay_rank[trace["replay_quality"]] >= replay_rank["tool_reexecution"]
    ):
        tier = "A"
    else:
        tier = "B"

    findings: list[str] = []
    if not trace["schema_valid"]:
        findings.append("Trace schema validation failed.")
    if not trace["integrity_verified"]:
        findings.append("Trace integrity verification failed.")
    if trace["context_completeness"] != "complete":
        findings.append("Model-visible context is incomplete.")
    if evidence_rank[trace["evidence_quality"]] < evidence_rank["signed_external"]:
        findings.append("Evidence is not independently signed or reproduced.")
    if replay_rank[trace["replay_quality"]] < replay_rank["tool_reexecution"]:
        findings.append("Replay is below verified tool reexecution.")
    if rights_status != "cleared":
        findings.append("Rights are not cleared.")
    if trace["hygiene_status"] != "clean":
        findings.append("Hygiene verification is not clean.")
    if not trace.get("rights_evidence_verified"):
        findings.append("Rights evidence is not independently verified.")
    if not trace.get("hygiene_evidence_verified"):
        findings.append("Hygiene evidence is not independently verified.")
    if not trace.get("replay_evidence_verified"):
        findings.append("Replay evidence is not independently verified.")
    if trace.get("capture_completeness") not in {"complete", "synthetic"}:
        findings.append("Capture is incomplete or not qualified.")
    if trace.get("revocation_status") != "active":
        findings.append("Trace is revoked or erased.")
    return {
        "trajectory_id": trace["trajectory_id"],
        "trace_sha256": trace["trace_sha256"],
        "schema_valid": trace["schema_valid"],
        "integrity_verified": trace["integrity_verified"],
        "capture_completeness": trace.get("capture_completeness", "incomplete"),
        "context_completeness": trace["context_completeness"],
        "evidence_quality": trace["evidence_quality"],
        "replay_quality": trace["replay_quality"],
        "rights_status": rights_status,
        "hygiene_status": trace["hygiene_status"],
        "rights_evidence_verified": trace.get("rights_evidence_verified", False),
        "hygiene_evidence_verified": trace.get("hygiene_evidence_verified", False),
        "replay_evidence_verified": trace.get("replay_evidence_verified", False),
        "revocation_status": trace.get("revocation_status", "revoked"),
        "amendment_cutoff": trace.get("amendment_cutoff"),
        "export_eligible": eligible,
        "commercial_tier": tier,
        "findings": findings,
    }


def verify_dataset_package(
    manifest_path: Path,
    manifest: dict[str, Any],
    quality: dict[str, Any] | None,
    traces: list[dict[str, Any]],
    report: Report,
) -> None:
    root = manifest_path.resolve().parent
    verify_manifest_seal(manifest, report)
    report.check(
        "manifest and quality dataset IDs match",
        quality is not None and manifest.get("dataset_id") == quality.get("dataset_id"),
    )

    trace_entries = manifest.get("traces", [])
    trace_ids = [item.get("trajectory_id") for item in trace_entries]
    report.check(
        "manifest trajectory IDs unique", len(trace_ids) == len(set(trace_ids))
    )
    split_lists = list(manifest.get("splits", {}).values())
    split_flat = [item for split in split_lists for item in split]
    report.check("dataset splits are disjoint", len(split_flat) == len(set(split_flat)))
    report.check("dataset splits cover traces", set(split_flat) == set(trace_ids))

    trace_by_id = {item.get("trajectory_id"): item for item in traces}
    report.check("every manifest trace verified", set(trace_by_id) == set(trace_ids))
    for entry in trace_entries:
        trace = trace_by_id.get(entry.get("trajectory_id"))
        if trace is None:
            continue
        report.check(
            f"trace digest {entry['trajectory_id']}",
            trace.get("trace_sha256") == entry.get("sha256"),
        )
        report.check(
            f"trace byte count {entry['trajectory_id']}",
            trace["path"].stat().st_size == entry.get("bytes"),
        )

    artifact_paths: dict[str, Path | None] = {}
    for label, artifact in [
        ("quality report", manifest.get("quality_report", {})),
        ("datasheet", manifest.get("datasheet", {})),
        ("machine datasheet", manifest.get("machine_datasheet", {})),
        ("rights evidence", manifest.get("rights_summary", {}).get("evidence", {})),
        ("deduplication report", manifest.get("deduplication", {}).get("report", {})),
    ]:
        artifact_paths[label] = verify_artifact(root, artifact, label, report)

    machine_datasheet = validate_optional_document(
        artifact_paths.get("machine datasheet"),
        root / "ualf-datasheet.schema.json",
        "machine datasheet schema",
        report,
    )
    report.check(
        "machine datasheet dataset ID",
        machine_datasheet is not None
        and machine_datasheet.get("dataset_id") == manifest.get("dataset_id"),
    )
    rights_document = verify_signed_evidence(
        artifact_paths.get("rights evidence"),
        root / "ualf-rights-attestation.schema.json",
        "rights evidence",
        report,
    )
    rights_status = (
        rights_document.get("status", "unresolved")
        if rights_document is not None
        and rights_document.get("dataset_id") == manifest.get("dataset_id")
        else "unresolved"
    )
    report.check(
        "rights status matches verified evidence",
        manifest.get("rights_summary", {}).get("status") == rights_status,
    )
    report.check(
        "rights uses match manifest",
        rights_document is not None
        and rights_document.get("intended_uses") == manifest.get("intended_uses")
        and rights_document.get("prohibited_uses") == manifest.get("prohibited_uses"),
    )

    entries_by_id = {item.get("trajectory_id"): item for item in trace_entries}
    for trace in traces:
        entry = entries_by_id.get(trace.get("trajectory_id"), {})
        capture = entry.get("capture", {})
        if capture.get("mode") == "synthetic":
            header = trace.get("header", {})
            synthetic_ok = header.get("deployment_environment") in {"test", "development"}
            report.check("synthetic capture limited to non-production", synthetic_ok)
            trace["capture_completeness"] = "synthetic" if synthetic_ok else "incomplete"
        else:
            capture_path = verify_artifact(root, capture, "capture evidence", report)
            capture_doc = validate_optional_document(
                capture_path,
                root / "ualf-production-capture.schema.json",
                "capture evidence schema",
                report,
            )
            trace["capture_completeness"] = (
                capture_doc.get("completeness", "incomplete")
                if capture_doc is not None
                and capture_doc.get("trace_sha256") == trace.get("trace_sha256")
                and capture_doc.get("organization")
                == trace.get("header", {}).get("organization")
                and capture_doc.get("project") == trace.get("header", {}).get("project")
                and capture_doc.get("environment")
                == trace.get("header", {}).get("deployment_environment")
                else "incomplete"
            )
        amendments = entry.get("amendments", {})
        report.check(
            "amendment state coherent",
            (amendments.get("state") == "none" and amendments.get("count") == 0)
            or (
                amendments.get("state") == "present"
                and amendments.get("count", 0) > 0
                and "stream" in amendments
                and "terminal_sha256" in amendments
            ),
        )
        retention = entry.get("retention", {})
        if retention.get("mode") != "package":
            retention_path = verify_artifact(
                root, retention, "retention evidence", report
            )
            retention_doc = verify_signed_evidence(
                retention_path,
                root / "ualf-retention.schema.json",
                "retention evidence",
                report,
            )
            report.check(
                "retention subject matches trace",
                retention_doc is not None
                and retention_doc.get("subject", {}).get("sha256")
                == trace.get("trace_sha256"),
            )
        for dependency in entry.get("external_dependencies", []):
            verify_artifact(
                root, dependency.get("artifact", {}), "external dependency", report
            )
        hygiene_path = verify_artifact(
            root, entry.get("hygiene_evidence", {}), "hygiene evidence", report
        )
        hygiene = verify_signed_evidence(
            hygiene_path,
            root / "ualf-hygiene-report.schema.json",
            "hygiene evidence",
            report,
        )
        replay_path = verify_artifact(
            root, entry.get("replay_evidence", {}), "replay evidence", report
        )
        replay = verify_signed_evidence(
            replay_path,
            root / "ualf-replay-verification.schema.json",
            "replay evidence",
            report,
        )
        rights_scope = rights_document.get("scope", {}) if rights_document else {}
        header_scope = trace.get("header", {})
        trace["rights_evidence_verified"] = (
            rights_document is not None
            and rights_scope.get("organization") == header_scope.get("organization")
            and rights_scope.get("project") == header_scope.get("project")
            and rights_scope.get("environment")
            == header_scope.get("deployment_environment")
        )
        trace["hygiene_evidence_verified"] = (
            hygiene is not None
            and hygiene.get("subject", {}).get("sha256") == trace.get("trace_sha256")
            and {item.get("category") for item in hygiene.get("scanners", [])}
            >= {"pii", "secrets", "license", "malware"}
            and all(
                item.get("status") in {"clean", "findings_resolved"}
                for item in hygiene.get("scanners", [])
            )
        )
        trace["replay_evidence_verified"] = (
            replay is not None
            and replay.get("subject", {}).get("sha256") == trace.get("trace_sha256")
            and replay.get("result_match") is True
            and replay.get("declared_level") == trace.get("replay_quality")
            and replay.get("calls", {}).get("matched")
            == replay.get("calls", {}).get("model", 0)
            + replay.get("calls", {}).get("tool", 0)
        )
        if hygiene is not None:
            trace["hygiene_status"] = hygiene.get("overall", "not_run")
        if replay is not None and trace["replay_evidence_verified"]:
            trace["replay_quality"] = replay.get("verified_level", "none")
        trace["revocation_status"] = entry.get("revocation", {}).get(
            "status", "revoked"
        )
        trace["amendment_cutoff"] = entry.get("amendments", {}).get("as_of")

    manifest_blobs = manifest.get("blobs", [])
    blob_ids = [entry.get("sha256") for entry in manifest_blobs]
    report.check("manifest blob IDs unique", len(blob_ids) == len(set(blob_ids)))
    required_blob_ids = {
        ref["$ref"][7:] for trace in traces for ref in trace.get("refs", [])
    }
    report.check("manifest covers referenced blobs", set(blob_ids) == required_blob_ids)
    for entry in manifest_blobs:
        path = verify_artifact(
            root, entry, f"blob {entry.get('sha256', '')[:12]}", report
        )
        if path is not None:
            report.check(
                f"blob filename {entry['sha256'][:12]}",
                path.name == entry["sha256"],
            )
    blobs_root = root / "blobs"
    actual_blob_ids = (
        {path.name for path in blobs_root.iterdir() if path.is_file()}
        if blobs_root.is_dir()
        else set()
    )
    report.check("no unlisted package blobs", actual_blob_ids == set(blob_ids))

    duplicate_count = len(trace_entries) - len(
        {item.get("sha256") for item in trace_entries}
    )
    report.check("no exact duplicate traces", duplicate_count == 0)
    report.check(
        "deduplication count recomputes",
        manifest.get("deduplication", {}).get("exact_duplicates_remaining")
        == duplicate_count,
    )

    if quality is None:
        return
    quality_entries = quality.get("traces", [])
    quality_ids = [item.get("trajectory_id") for item in quality_entries]
    report.check(
        "quality trajectory IDs unique", len(quality_ids) == len(set(quality_ids))
    )
    report.check("quality report covers traces", set(quality_ids) == set(trace_ids))
    quality_by_id = {item.get("trajectory_id"): item for item in quality_entries}
    for trace in traces:
        expected = derive_quality(trace, rights_status)
        actual = quality_by_id.get(trace.get("trajectory_id"))
        report.check(
            f"quality derives for {trace.get('trajectory_id')}",
            actual == expected,
            f"stamped {actual}, computed {expected}",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--blobs", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--quality-report", type=Path)
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    schema_path = args.schema or base / "ualf-trajectory.schema.json"
    report = Report()
    manifest = validate_optional_document(
        args.manifest,
        base / "ualf-dataset-manifest.schema.json",
        "dataset manifest schema",
        report,
    )
    quality_path = args.quality_report
    if quality_path is None and manifest is not None and args.manifest is not None:
        quality_path = safe_resolve(
            args.manifest.resolve().parent,
            manifest.get("quality_report", {}).get("path"),
        )
    if quality_path is not None and manifest is not None and args.manifest is not None:
        expected_quality_path = safe_resolve(
            args.manifest.resolve().parent,
            manifest.get("quality_report", {}).get("path"),
        )
        report.check(
            "quality report path matches manifest",
            expected_quality_path is not None
            and quality_path.resolve() == expected_quality_path,
        )
    quality = validate_optional_document(
        quality_path,
        base / "ualf-quality-report.schema.json",
        "quality report schema",
        report,
    )

    trace_paths: list[Path] = []
    if manifest is not None and args.manifest is not None:
        root = args.manifest.resolve().parent
        for entry in manifest.get("traces", []):
            path = safe_resolve(root, entry.get("path"))
            report.check(
                f"trace path contained {entry.get('trajectory_id')}", path is not None
            )
            if path is not None:
                report.check(
                    f"trace exists {entry.get('trajectory_id')}", path.is_file()
                )
                if path.is_file():
                    trace_paths.append(path)
        report.check(
            "requested trajectory is in manifest",
            args.trajectory.resolve() in {path.resolve() for path in trace_paths},
        )
    else:
        trace_paths = [args.trajectory.resolve()]

    blobs_dir = args.blobs or (
        args.manifest.resolve().parent / "blobs"
        if args.manifest is not None
        else args.trajectory.resolve().parent / "blobs"
    )
    traces = [
        verify_trace(path, schema_path, blobs_dir, report)
        for path in dict.fromkeys(trace_paths)
    ]
    if manifest is not None and args.manifest is not None:
        verify_dataset_package(args.manifest, manifest, quality, traces, report)

    if report.failures:
        print(f"NON-CONFORMING ({len(report.failures)} failure(s))")
        return 1
    print("CONFORMING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
