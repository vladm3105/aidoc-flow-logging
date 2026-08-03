#!/usr/bin/env python3
"""Verify an AAT draft-00 JSONL projection and its UALF transformation manifest."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

PROFILE = "draft-sharif-agent-audit-trail-00"
VERSION = "ualf-aat-validator/0.1.0"
RAW_KEYS = {
    "input",
    "output",
    "parameters",
    "response",
    "reasoning",
    "prompt",
    "completion",
    "original_action",
}


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


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def load_json(path: Path, report: Report, label: str) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError("root is not an object")
        report.check(f"{label} readable", True)
        return value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        report.check(f"{label} readable", False, str(exc))
        return None


def validate_document(
    value: Any, schema_path: Path, report: Report, label: str
) -> bool:
    try:
        from jsonschema import Draft202012Validator, FormatChecker

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = list(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
                value
            )
        )
        detail = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors[:5]
        )
        report.check(label, not errors, detail)
        return not errors
    except (ImportError, OSError, json.JSONDecodeError) as exc:
        report.check(label, False, str(exc))
        return False


def read_jsonl(path: Path, report: Report) -> tuple[list[bytes], list[dict[str, Any]]]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        report.check("AAT artifact readable", False, str(exc))
        return [], []
    report.check("AAT artifact non-empty", bool(payload))
    report.check("AAT UTF-8 without BOM", not payload.startswith(b"\xef\xbb\xbf"))
    lines = payload.splitlines()
    report.check(
        "AAT no blank lines", bool(lines) and all(line.strip() for line in lines)
    )
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for number, line in enumerate(lines, 1):
        try:
            value = json.loads(line.decode("utf-8", errors="strict"))
            if not isinstance(value, dict):
                raise TypeError("line is not an object")
            records.append(value)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            errors.append(f"line {number}: {exc}")
    report.check("AAT JSON object per line", not errors, "; ".join(errors[:3]))
    return lines, records


def contains_raw_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in RAW_KEYS or contains_raw_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(contains_raw_key(child) for child in value)
    return False


def verify_record_signatures(
    records: list[dict[str, Any]], context: dict[str, Any], report: Report
) -> None:
    signed = [record for record in records if "signature" in record]
    report.check(
        "AAT signatures all-or-none", not signed or len(signed) == len(records)
    )
    if not signed:
        return
    identity = context.get("signing_identity")
    if not isinstance(identity, dict):
        report.check("AAT signing identity present", False)
        return
    try:
        import rfc8785
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    except ImportError as exc:
        report.check("AAT P-256 signatures", False, f"install dependency: {exc.name}")
        return
    try:
        key = serialization.load_pem_public_key(identity["public_key"].encode("ascii"))
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(
            key.curve, ec.SECP256R1
        ):
            raise TypeError("public key is not ECDSA P-256")
        for record in records:
            unsigned = dict(record)
            signature = b64url_decode(unsigned.pop("signature"))
            if len(signature) != 64:
                raise ValueError("signature is not 64-byte IEEE P1363")
            der = encode_dss_signature(
                int.from_bytes(signature[:32], "big"),
                int.from_bytes(signature[32:], "big"),
            )
            key.verify(der, rfc8785.dumps(unsigned), ec.ECDSA(hashes.SHA256()))
        report.check("AAT P-256 signatures", True)
    except (
        KeyError,
        TypeError,
        ValueError,
        binascii.Error,
        InvalidSignature,
        UnsupportedAlgorithm,
        rfc8785.CanonicalizationError,
    ) as exc:
        report.check("AAT P-256 signatures", False, str(exc))


def verify_aat(
    records: list[dict[str, Any]],
    lines: list[bytes],
    schema_path: Path,
    context: dict[str, Any],
    report: Report,
) -> dict[str, str]:
    try:
        import rfc8785
    except ImportError as exc:
        report.check("AAT chain dependency", False, str(exc))
        return {}
    for number, record in enumerate(records, 1):
        validate_document(record, schema_path, report, f"AAT schema line {number}")
    report.check(
        "AAT record size limit", all(len(line) <= 256 * 1024 for line in lines)
    )
    report.check(
        "AAT recommended record size", all(len(line) <= 64 * 1024 for line in lines)
    )
    report.check(
        "AAT privacy-minimized fields",
        not any(contains_raw_key(record) for record in records),
    )

    ids = [record.get("record_id") for record in records]
    report.check("AAT record IDs unique", len(ids) == len(set(ids)))
    report.check(
        "AAT identity and trust match source context",
        all(
            record.get("agent_id") == context.get("agent_id")
            and record.get("agent_version") == context.get("agent_version")
            and record.get("trust_level")
            == context.get("trust_assertion", {}).get("level")
            for record in records
        ),
    )

    session_hashes: dict[str, str] = {}
    sessions: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        sessions.setdefault(str(record.get("session_id")), []).append(record)
    record_by_id = {record.get("record_id"): record for record in records}
    bad_links: list[str] = []
    for record in records:
        detail = record.get("action_detail", {})
        if record.get("action_type") == "tool_response":
            parent = record_by_id.get(detail.get("parent_call_id"))
            if parent is None or parent.get("action_type") != "tool_call":
                bad_links.append(f"{record.get('record_id')}: bad parent_call_id")
        if (
            record.get("action_type") == "delegation"
            and str(detail.get("child_session_id")) not in sessions
        ):
            bad_links.append(f"{record.get('record_id')}: bad child_session_id")
    report.check("AAT action cross-references", not bad_links, "; ".join(bad_links[:5]))
    chain_errors: list[str] = []
    for session_id, session in sessions.items():
        first, last = session[0], session[-1]
        if not (
            first.get("parent_record_id") is None
            and first.get("prev_hash") is None
            and first.get("action_type") == "lifecycle"
            and first.get("action_detail", {}).get("event") == "session_start"
        ):
            chain_errors.append(f"{session_id}: invalid genesis")
        try:
            timestamps = [
                datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                for record in session
            ]
            if timestamps != sorted(timestamps):
                chain_errors.append(f"{session_id}: timestamps regress")
        except (KeyError, TypeError, ValueError):
            chain_errors.append(f"{session_id}: invalid timestamp")
        for previous, current in pairwise(session):
            expected = sha256(rfc8785.dumps(previous))
            if (
                current.get("parent_record_id") != previous.get("record_id")
                or current.get("prev_hash") != expected
            ):
                chain_errors.append(
                    f"{session_id}: broken before {current.get('record_id')}"
                )
        if not (
            last.get("action_type") == "lifecycle"
            and last.get("action_detail", {}).get("event") == "session_end"
        ):
            chain_errors.append(f"{session_id}: missing close")
            continue
        try:
            digest_bytes = b"".join(
                bytes.fromhex(record["prev_hash"]) for record in session[1:]
            )
            expected_session_hash = sha256(digest_bytes)
            session_hashes[session_id] = expected_session_hash
            if last["action_detail"].get("session_hash") != expected_session_hash:
                chain_errors.append(f"{session_id}: bad session_hash")
            if last["action_detail"].get("record_count") != len(session):
                chain_errors.append(f"{session_id}: bad record_count")
        except (KeyError, TypeError, ValueError):
            chain_errors.append(f"{session_id}: invalid close summary")
    report.check(
        "AAT chains and session summaries",
        not chain_errors,
        "; ".join(chain_errors[:5]),
    )
    verify_record_signatures(records, context, report)
    return session_hashes


def artifact_ok(
    root: Path, artifact: dict[str, Any], report: Report, label: str
) -> Path | None:
    try:
        path = (root / artifact["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("path escapes manifest directory")
        data = path.read_bytes()
        report.check(f"{label} digest", sha256(data) == artifact.get("sha256"))
        report.check(f"{label} byte count", len(data) == artifact.get("bytes"))
        return path
    except (OSError, KeyError, TypeError, ValueError) as exc:
        report.check(f"{label} artifact", False, str(exc))
        return None


def verify_manifest(
    manifest_path: Path,
    manifest: dict[str, Any],
    requested_aat_path: Path,
    requested_context_path: Path,
    records: list[dict[str, Any]],
    session_hashes: dict[str, str],
    report: Report,
) -> None:
    base = Path(__file__).resolve().parent
    validate_document(
        manifest,
        base / "ualf-aat-export-manifest.schema.json",
        report,
        "AAT manifest schema",
    )
    root = manifest_path.resolve().parent
    source = artifact_ok(root, manifest.get("source", {}), report, "source UALF")
    context_path = artifact_ok(
        root, manifest.get("source_context", {}), report, "AAT source context"
    )
    export_path = artifact_ok(root, manifest.get("export", {}), report, "AAT export")
    if export_path is not None:
        report.check(
            "requested AAT matches manifest",
            requested_aat_path.resolve() == export_path,
        )
        report.check(
            "manifest record count",
            manifest["export"].get("record_count") == len(records),
        )
    expected_ids = {record.get("record_id") for record in records}
    mapped_ids = {item.get("record_id") for item in manifest.get("record_mappings", [])}
    report.check("manifest maps every AAT record", mapped_ids == expected_ids)
    report.check(
        "manifest session hashes",
        manifest.get("integrity", {}).get("aat_session_hashes") == session_hashes,
    )
    if source is not None:
        try:
            from verify import Report as UalfReport
            from verify import verify_trace

            ualf_report = UalfReport()
            ualf_state = verify_trace(
                source,
                base / "ualf-trajectory.schema.json",
                source.parent / "blobs",
                ualf_report,
            )
            report.check(
                "source UALF independently verified",
                not ualf_report.failures
                and ualf_state.get("schema_valid") is True
                and ualf_state.get("integrity_verified") is True,
            )
            source_records = [
                json.loads(line)
                for line in source.read_text(encoding="utf-8").splitlines()
                if line
            ]
            report.check(
                "manifest UALF terminal seal",
                source_records[-1]["seal"]["chain_sha256"]
                == manifest.get("integrity", {}).get("ualf_chain_sha256"),
            )
            source_ids = {
                record.get("event_id", f"seq:{record['seq']}")
                for record in source_records
            }
            disposed = {
                source_id
                for mapping in manifest.get("record_mappings", [])
                for source_id in mapping.get("source_records", [])
            } | {
                omission.get("source_record")
                for omission in manifest.get("omissions", [])
            }
            report.check("manifest disposes every UALF record", disposed == source_ids)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
            ImportError,
        ) as exc:
            report.check("manifest UALF terminal seal", False, str(exc))
    if context_path is not None:
        report.check(
            "requested context matches manifest",
            requested_context_path.resolve() == context_path,
        )
        context = load_json(context_path, report, "manifest source context")
        if context is not None:
            validate_document(
                context,
                base / "ualf-aat-source.schema.json",
                report,
                "manifest source context schema",
            )
    report.check(
        "manifest validator identity",
        manifest.get("validator") == {"name": "ualf-aat-validator", "version": "0.1.0"},
    )
    try:
        import rfc8785
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        report.check("AAT manifest signature", False, f"install dependency: {exc.name}")
        return
    try:
        unsigned = dict(manifest)
        seal = unsigned.pop("seal")
        expected = sha256(rfc8785.dumps(unsigned))
        report.check("AAT manifest hash", expected == seal["manifest_sha256"])
        Ed25519PublicKey.from_public_bytes(b64url_decode(seal["public_key"])).verify(
            b64url_decode(seal["signature"]), bytes.fromhex(expected)
        )
        report.check("AAT manifest signature", True)
    except (
        KeyError,
        TypeError,
        ValueError,
        binascii.Error,
        InvalidSignature,
        rfc8785.CanonicalizationError,
    ) as exc:
        report.check("AAT manifest signature", False, str(exc))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("aat", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-context", type=Path, required=True)
    parser.add_argument("--schema", type=Path)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    report = Report()
    context = load_json(args.source_context, report, "AAT source context") or {}
    validate_document(
        context,
        base / "ualf-aat-source.schema.json",
        report,
        "AAT source context schema",
    )
    lines, records = read_jsonl(args.aat, report)
    session_hashes = (
        verify_aat(
            records,
            lines,
            args.schema or base / "aat-draft-00.schema.json",
            context,
            report,
        )
        if records
        else {}
    )
    manifest = load_json(args.manifest, report, "AAT transformation manifest")
    if manifest is not None:
        verify_manifest(
            args.manifest,
            manifest,
            args.aat,
            args.source_context,
            records,
            session_hashes,
            report,
        )
    if report.failures:
        print(f"NON-CONFORMING ({len(report.failures)} failure(s))")
        return 1
    print(f"CONFORMING ({VERSION}, {PROFILE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
