#!/usr/bin/env python3
"""Build the synthetic AAT draft-00 projection and signed transformation manifest."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import rfc8785
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "example-trajectory.jsonl"
CONTEXT = BASE / "example-aat-source.json"
EXPORT = BASE / "example-aat.jsonl"
MANIFEST = BASE / "example-aat-manifest.json"
SESSION_ID = "44caeacd-3416-4e4f-a226-f47ff21f605d"
GENESIS_ID = "9bb1a83c-b5ac-4c94-b143-4b53e9db4cc7"
CLOSE_ID = "eeb190b7-72ce-46a5-9d89-af97c131dc39"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def artifact(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.name, "sha256": digest(data), "bytes": len(data)}


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def main() -> None:
    source_records = [
        json.loads(line)
        for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line
    ]
    header, outcome = source_records[0], source_records[-1]
    context = {
        "schema": "ualf-aat-source/draft-sharif-agent-audit-trail-00",
        "agent_id": "urn:agent:iplanic.ai:ualf-example-agent",
        "agent_version": "3.1.0",
        "trust_assertion": {
            "level": "L0",
            "authority": "ualf-example-owner",
            "basis": "no_verification",
            "asserted_at": "2026-08-02T18:00:10.460Z",
        },
        "outcome_policy": "ualf-to-aat-outcomes/draft-00-v1",
        "error_policy": "ualf-to-aat-errors/draft-00-v1",
        "privacy_policy": {
            "id": "ualf-aat-example-privacy/v1",
            "sensitive_inline_content": "forbidden",
            "low_entropy_hashes_are_personal_data": True,
        },
    }
    CONTEXT.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")

    genesis = {
        "record_id": GENESIS_ID,
        "timestamp": header["started_at"],
        "agent_id": context["agent_id"],
        "agent_version": context["agent_version"],
        "session_id": SESSION_ID,
        "action_type": "lifecycle",
        "action_detail": {
            "event": "session_start",
            "new_state": "active",
            "trigger": "ualf_projection",
            "config_hash": digest(
                rfc8785.dumps(
                    {"agent": header["agent"], "environment": header["environment"]}
                )
            ),
        },
        "outcome": "success",
        "trust_level": context["trust_assertion"]["level"],
        "parent_record_id": None,
        "prev_hash": None,
    }
    previous_hash = digest(rfc8785.dumps(genesis))
    session_hash = digest(bytes.fromhex(previous_hash))
    close = {
        "record_id": CLOSE_ID,
        "timestamp": outcome["timestamp"],
        "agent_id": context["agent_id"],
        "agent_version": context["agent_version"],
        "session_id": SESSION_ID,
        "action_type": "lifecycle",
        "action_detail": {
            "event": "session_end",
            "previous_state": "active",
            "new_state": "closed",
            "trigger": "ualf_trace_closed",
            "session_hash": session_hash,
            "record_count": 2,
            "duration_ms": outcome["monotonic_ms"],
        },
        "outcome": "success",
        "trust_level": context["trust_assertion"]["level"],
        "parent_record_id": GENESIS_ID,
        "prev_hash": previous_hash,
    }
    EXPORT.write_bytes(compact(genesis) + b"\n" + compact(close) + b"\n")

    omissions = [
        {
            "source_record": record.get("event_id", f"seq:{record['seq']}"),
            "reason": "No lossless AAT draft-00 action record in the minimal lifecycle projection.",
        }
        for record in source_records[1:-1]
    ]
    manifest = {
        "schema": "ualf-aat-export-manifest/v1",
        "profile": "draft-sharif-agent-audit-trail-00",
        "claim": "aat-validated/draft-sharif-agent-audit-trail-00",
        "transformed_at": "2026-08-02T18:00:10.470Z",
        "source": artifact(SOURCE),
        "source_context": artifact(CONTEXT),
        "export": {**artifact(EXPORT), "record_count": 2, "session_ids": [SESSION_ID]},
        "exporter": {"name": "ualf-example-projection-builder", "version": "0.1.0"},
        "validator": {"name": "ualf-aat-validator", "version": "0.1.0"},
        "hashing": {
            "algorithm": "sha256-lowercase-hex",
            "json": "rfc8785-jcs",
            "text": "utf8-exact-no-normalization",
            "binary": "decoded-octets",
            "content_encoding": "decode-identity-or-gzip-before-hashing",
        },
        "identity": {
            "agent_id": context["agent_id"],
            "agent_version": context["agent_version"],
            "trust_level": context["trust_assertion"]["level"],
            "trust_authority": context["trust_assertion"]["authority"],
            "trust_basis": context["trust_assertion"]["basis"],
        },
        "record_mappings": [
            {
                "record_id": GENESIS_ID,
                "session_id": SESSION_ID,
                "source_records": ["seq:1"],
            },
            {
                "record_id": CLOSE_ID,
                "session_id": SESSION_ID,
                "source_records": [f"seq:{outcome['seq']}"],
            },
        ],
        "omissions": omissions,
        "integrity": {
            "ualf_chain_sha256": outcome["seal"]["chain_sha256"],
            "aat_session_hashes": {SESSION_ID: session_hash},
        },
    }
    seed = hashlib.sha256(
        b"UALF AAT example manifest signing key - public fixture only"
    ).digest()
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    manifest_hash = digest(rfc8785.dumps(manifest))
    manifest["seal"] = {
        "manifest_sha256": manifest_hash,
        "key_id": f"ualf-aat-example-{digest(public_key)[:16]}",
        "algorithm": "ed25519",
        "public_key": b64url(public_key),
        "signature": b64url(private_key.sign(bytes.fromhex(manifest_hash))),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
