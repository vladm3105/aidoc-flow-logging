#!/usr/bin/env python3
"""Validate the executable UALF v1.3 profile examples."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any


SCHEMA_ROOT = Path(__file__).resolve().parent
ROOT = SCHEMA_ROOT


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        print(f"[{'PASS' if condition else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
        if not condition:
            self.failures.append(name)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(path: Path, schema_path: Path, report: Report) -> Any:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        value = load_json(path)
        errors = list(Draft202012Validator(load_json(schema_path), format_checker=FormatChecker()).iter_errors(value))
        report.check(f"schema {path.name}", not errors, "; ".join(error.message for error in errors[:3]))
        return value
    except (ImportError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        report.check(f"schema {path.name}", False, str(exc))
        return None


def verify_document_seal(value: dict[str, Any], label: str, report: Report) -> None:
    try:
        import rfc8785
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        unsigned = dict(value)
        seal = unsigned.pop("seal")
        expected = sha256(rfc8785.dumps(unsigned)).hexdigest()
        report.check(f"{label} digest", expected == seal["document_sha256"])
        Ed25519PublicKey.from_public_bytes(strict_b64(seal["public_key"])).verify(
            strict_b64(seal["signature"]), bytes.fromhex(seal["document_sha256"])
        )
        report.check(f"{label} signature", True)
    except (KeyError, TypeError, ValueError, binascii.Error, InvalidSignature) as exc:
        report.check(f"{label} signature", False, str(exc))


def verify_capture(capture: dict[str, Any], report: Report) -> None:
    delivery = capture["delivery"]
    report.check("capture delivered accepted records", delivery["delivered_records"] == delivery["accepted_records"])
    lossy = {"not_captured", "sampled_out", "capture_failed", "redacted", "truncated"}
    states = [value if isinstance(value, str) else value["state"] for value in capture["content_states"].values()]
    if capture["completeness"] == "complete":
        report.check("complete capture has no lossy state", not lossy.intersection(states))
        report.check("complete capture privacy boundary", capture["privacy"]["pre_persistence"] is True and capture["privacy"]["boundary"] in {"client", "trusted_sidecar"})


def verify_index(index: dict[str, Any], report: Report) -> None:
    source = safe_path(index["source"]["path"])
    report.check("index source path contained", source is not None)
    if source is None:
        return
    report.check("index source exists", source.is_file())
    if not source.is_file():
        return
    data = source.read_bytes()
    report.check("index source digest", sha256(data).hexdigest() == index["source"]["sha256"])
    report.check("index source bytes", len(data) == index["source"]["bytes"])
    records = index["records"]
    report.check("index gapless sequence", [r["seq"] for r in records] == list(range(1, len(records) + 1)))
    expected_offset = 0
    ok = True
    metadata_ok = True
    for record in records:
        raw = data[record["offset"] : record["offset"] + record["length"]]
        ok = ok and record["offset"] == expected_offset and sha256(raw).hexdigest() == record["sha256"]
        try:
            source_record = json.loads(raw)
            metadata_ok = metadata_ok and source_record.get("seq") == record["seq"] and source_record.get("kind") == record["kind"]
            metadata_ok = metadata_ok and source_record.get("event_id") == record.get("event_id") and source_record.get("type") == record.get("event_type")
        except (UnicodeDecodeError, json.JSONDecodeError):
            metadata_ok = False
        terminator = data[record["offset"] + record["length"] : record["offset"] + record["length"] + 2]
        expected_offset = record["offset"] + record["length"] + (2 if terminator.startswith(b"\r\n") else 1)
    report.check("index offsets and line digests", ok)
    report.check("index metadata matches source", metadata_ok)
    report.check("index covers source", expected_offset == len(data))


def strict_b64(value: str) -> bytes:
    if len(value) % 4 != 0:
        raise ValueError("non-padded base64")
    return base64.b64decode(value, validate=True)


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(type_bytes)).encode() + b" " + type_bytes + b" " + str(len(payload)).encode() + b" " + payload


def verify_amendments(path: Path, report: Report) -> None:
    try:
        import rfc8785
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:
        report.check("amendment dependencies", False, str(exc))
        return
    raw_lines = path.read_bytes().splitlines()
    objects = [json.loads(line) for line in raw_lines]
    schema = load_json(ROOT / "ualf-amendment.schema.json")
    errors = [error for obj in objects for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(obj)]
    report.check("amendment line schemas", not errors, "; ".join(error.message for error in errors[:3]))
    report.check("amendment physical shape", objects[0].get("kind") == "amendment_header" and objects[-1].get("kind") == "amendment_seal")
    report.check("amendment gapless sequence", [o.get("seq") for o in objects] == list(range(1, len(objects) + 1)))
    chain_ok = all(objects[i].get("prev_sha256") == sha256(raw_lines[i - 1]).hexdigest() for i in range(1, len(objects)))
    report.check("amendment exact-byte chain", chain_ok)
    amendments = objects[1:-1]
    ids = [item["amendment_id"] for item in amendments]
    report.check("amendment IDs unique", len(ids) == len(set(ids)))
    report.check("amendment count", objects[-1]["amendment_count"] == len(amendments))
    known: set[str] = set()
    supersedes_ok = True
    for item in amendments:
        if "supersedes" in item and item["supersedes"] not in known:
            supersedes_ok = False
        known.add(item["amendment_id"])
    report.check("amendment supersedes prior record", supersedes_ok)
    try:
        seal = objects[-1]
        unsigned = {key: value for key, value in seal.items() if key not in {"chain_sha256", "signature"}}
        expected = sha256(rfc8785.dumps(unsigned)).hexdigest()
        report.check("amendment terminal digest", expected == seal["chain_sha256"])
        signing = objects[0]["signing"]
        report.check("amendment signing identity", signing["key_id"] == seal["signature"]["key_id"])
        Ed25519PublicKey.from_public_bytes(strict_b64(signing["public_key"])).verify(strict_b64(seal["signature"]["value"]), bytes.fromhex(seal["chain_sha256"]))
        report.check("amendment Ed25519 signature", True)
    except (KeyError, ValueError, TypeError, binascii.Error, InvalidSignature, rfc8785.CanonicalizationError) as exc:
        report.check("amendment Ed25519 signature", False, str(exc))


def safe_path(relative: str) -> Path | None:
    try:
        path = (ROOT / relative).resolve()
        return path if path.is_relative_to(ROOT.resolve()) else None
    except (OSError, TypeError, ValueError):
        return None


def verify_projection(manifest: dict[str, Any], report: Report) -> None:
    for label, artifact in [("source", manifest["source"]), *[("output", item) for item in manifest["outputs"]]]:
        path = safe_path(artifact["path"])
        report.check(f"projection {manifest['projection_id']} {label} contained", path is not None)
        if path is None:
            continue
        report.check(f"projection {manifest['projection_id']} {label} exists", path.is_file())
        if not path.is_file():
            continue
        data = path.read_bytes()
        report.check(f"projection {manifest['projection_id']} {label} digest", sha256(data).hexdigest() == artifact["sha256"])
        report.check(f"projection {manifest['projection_id']} {label} bytes", len(data) == artifact["bytes"])
    lossy_effects = {item["effect"] for item in manifest["omissions"] if item["effect"] != "none"}
    report.check(f"projection {manifest['projection_id']} loss declared", not lossy_effects or manifest["loss_class"] != "lossless")
    report.check(f"projection {manifest['projection_id']} version pinned", bool(manifest["target"]["revision"]) and manifest["target"]["revision"] not in {"latest", "main"})
    external_profiles = {"ualf-otel-genai/v1", "ualf-openinference/v1", "ualf-openlineage/v1", "ualf-croissant/v1", "ualf-in-toto-qualification/v1"}
    if manifest["target"]["profile"] in external_profiles:
        report.check(f"projection {manifest['projection_id']} immutable upstream revision", re.search(r"[a-f0-9]{40}", manifest["target"]["revision"]) is not None)
    if manifest["target"]["profile"] == "ualf-in-toto-qualification/v1":
        dsse_outputs = [safe_path(item["path"]) for item in manifest["outputs"] if item["path"].endswith(".dsse.json")]
        report.check("in-toto projection declares one DSSE envelope", len(dsse_outputs) == 1 and dsse_outputs[0] is not None)
        if len(dsse_outputs) == 1 and dsse_outputs[0] is not None:
            verify_dsse(dsse_outputs[0], manifest, report)


def verify_dsse(path: Path, manifest: dict[str, Any], report: Report) -> None:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from jsonschema import Draft202012Validator, FormatChecker
        envelope = load_json(path)
        errors = list(Draft202012Validator(load_json(ROOT / "ualf-dsse-envelope.schema.json"), format_checker=FormatChecker()).iter_errors(envelope))
        report.check("DSSE envelope schema", not errors, "; ".join(error.message for error in errors[:3]))
        payload = strict_b64(envelope["payload"])
        statement = json.loads(payload)
        report.check("DSSE in-toto statement type", statement.get("_type") == "https://in-toto.io/Statement/v1")
        statement_outputs = [safe_path(item["path"]) for item in manifest["outputs"] if item["path"].endswith(".json") and not item["path"].endswith(".dsse.json")]
        report.check("DSSE declares one statement artifact", len(statement_outputs) == 1 and statement_outputs[0] is not None)
        if len(statement_outputs) == 1 and statement_outputs[0] is not None:
            report.check("DSSE payload matches statement artifact", statement == load_json(statement_outputs[0]))
        subject_digest = statement["subject"][0]["digest"]["sha256"]
        report.check("DSSE subject binds projection source", subject_digest == manifest["source"]["sha256"])
        signature = envelope["signatures"][0]
        Ed25519PublicKey.from_public_bytes(strict_b64(envelope["verification"]["public_key"])).verify(strict_b64(signature["sig"]), dsse_pae(envelope["payloadType"], payload))
        report.check("DSSE Ed25519 signature", True)
    except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError, binascii.Error, InvalidSignature, ImportError) as exc:
        report.check("DSSE Ed25519 signature", False, str(exc))


def verify_registry(registry: dict[str, Any], report: Report) -> None:
    ids = [item["id"] for item in registry["extensions"]]
    urls = [item["schema_url"] for item in registry["extensions"]]
    report.check("extension identifiers unique", len(ids) == len(set(ids)))
    report.check("extension schema URLs unique", len(urls) == len(set(urls)))
    report.check("sensitive extensions opt in", all(item["requirement_level"] == "opt_in" for item in registry["extensions"] if item["privacy_risk"] in {"sensitive", "high"}))


def merkle_root(leaves: list[bytes]) -> bytes:
    level = leaves
    while len(level) > 1:
        if len(level) % 2:
            level = [*level, level[-1]]
        level = [sha256(level[index] + level[index + 1]).digest() for index in range(0, len(level), 2)]
    return level[0]


def verify_segments(manifest: dict[str, Any], report: Report) -> None:
    try:
        import rfc8785
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        report.check("segment dependencies", False, str(exc))
        return
    source = safe_path(manifest["source"]["path"])
    report.check("segment source path contained", source is not None)
    if source is None:
        return
    report.check("segment source exists", source.is_file())
    if not source.is_file():
        return
    data = source.read_bytes()
    report.check("segment source digest", sha256(data).hexdigest() == manifest["source"]["sha256"])
    report.check("segment source bytes", len(data) == manifest["source"]["bytes"])
    expected_offset = 0
    expected_seq = 1
    leaves: list[bytes] = []
    coverage_ok = True
    for index, segment in enumerate(manifest["segments"]):
        raw = data[segment["offset"] : segment["offset"] + segment["bytes"]]
        leaf = sha256(raw).digest()
        leaves.append(leaf)
        coverage_ok = coverage_ok and segment["index"] == index and segment["offset"] == expected_offset and segment["seq_start"] == expected_seq and leaf.hex() == segment["sha256"]
        try:
            source_records = [json.loads(line) for line in raw.splitlines()]
            coverage_ok = coverage_ok and bool(source_records) and source_records[0].get("seq") == segment["seq_start"] and source_records[-1].get("seq") == segment["seq_end"]
            coverage_ok = coverage_ok and [record.get("seq") for record in source_records] == list(range(segment["seq_start"], segment["seq_end"] + 1))
        except (UnicodeDecodeError, json.JSONDecodeError):
            coverage_ok = False
        expected_offset += segment["bytes"]
        expected_seq = segment["seq_end"] + 1
    report.check("segment exact coverage", coverage_ok and expected_offset == len(data))
    report.check("segment Merkle root", merkle_root(leaves).hex() == manifest["merkle"]["root"])
    try:
        unsigned = dict(manifest)
        seal = unsigned.pop("seal")
        expected = sha256(rfc8785.dumps(unsigned)).hexdigest()
        report.check("segment manifest digest", expected == seal["manifest_sha256"])
        signing = manifest["signing"]
        report.check("segment signing identity", signing["key_id"] == seal["signature"]["key_id"])
        Ed25519PublicKey.from_public_bytes(strict_b64(signing["public_key"])).verify(strict_b64(seal["signature"]["value"]), bytes.fromhex(seal["manifest_sha256"]))
        report.check("segment Ed25519 signature", True)
    except (KeyError, ValueError, TypeError, binascii.Error, InvalidSignature, rfc8785.CanonicalizationError) as exc:
        report.check("segment Ed25519 signature", False, str(exc))


def main() -> int:
    global ROOT
    parser = argparse.ArgumentParser(
        description="Validate UALF lifecycle, indexing, and projection profiles."
    )
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--retention", type=Path)
    parser.add_argument("--amendments", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--segments", type=Path)
    parser.add_argument("--projection", type=Path, action="append", default=[])
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=SCHEMA_ROOT,
        help="Root used to resolve contained paths inside supplied artifacts.",
    )
    args = parser.parse_args()
    ROOT = args.artifact_root.resolve()
    explicit = any(
        [
            args.capture,
            args.retention,
            args.amendments,
            args.registry,
            args.index,
            args.segments,
            args.projection,
        ]
    )
    capture_path = args.capture or (None if explicit else ROOT / "example-production-capture.json")
    retention_path = args.retention or (None if explicit else ROOT / "example-retention.json")
    registry_path = args.registry or (None if explicit else ROOT / "extension-registry.json")
    index_path = args.index or (None if explicit else ROOT / "example-index.json")
    segment_path = args.segments or (None if explicit else ROOT / "example-segment-manifest.json")
    amendment_path = args.amendments or (None if explicit else ROOT / "example-amendments.jsonl")
    projection_paths = args.projection or (
        []
        if explicit
        else [
            *(ROOT / "projections").glob("*-manifest.json"),
            ROOT / "analytics" / "example-analytics-manifest.json",
        ]
    )
    report = Report()
    capture = validate(capture_path, SCHEMA_ROOT / "ualf-production-capture.schema.json", report) if capture_path else None
    retention = validate(retention_path, SCHEMA_ROOT / "ualf-retention.schema.json", report) if retention_path else None
    registry = validate(registry_path, SCHEMA_ROOT / "ualf-extension-registry.schema.json", report) if registry_path else None
    index = validate(index_path, SCHEMA_ROOT / "ualf-index.schema.json", report) if index_path else None
    segments = validate(segment_path, SCHEMA_ROOT / "ualf-segment-manifest.schema.json", report) if segment_path else None
    if capture:
        verify_document_seal(capture, "capture report", report)
        verify_capture(capture, report)
    if retention:
        verify_document_seal(retention, "retention record", report)
        report.check("retention legal hold coherent", not retention["legal_hold"]["active"] or "authority" in retention["legal_hold"])
        if retention.get("expires_at"):
            report.check("retention expiry follows creation", retention["expires_at"] > retention["created_at"])
    if registry:
        verify_registry(registry, report)
    if index:
        verify_index(index, report)
    if segments:
        verify_segments(segments, report)
    if amendment_path:
        verify_amendments(amendment_path, report)
    for path in sorted(projection_paths):
        manifest = validate(path, SCHEMA_ROOT / "ualf-projection-manifest.schema.json", report)
        if manifest:
            verify_projection(manifest, report)
    if report.failures:
        print(f"NON-CONFORMING ({len(report.failures)} failure(s))")
        return 1
    print("CONFORMING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
