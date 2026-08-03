#!/usr/bin/env python3
"""Build deterministic UALF v1.3 profile examples and projections."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
NOW = "2026-08-03T12:00:00Z"


def compact(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(type_bytes)).encode() + b" " + type_bytes + b" " + str(len(payload)).encode() + b" " + payload


def unix_nano(value: str) -> str:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    delta = instant - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return str((delta.days * 86_400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1_000)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )


def digest(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    media = "application/jsonl" if path.suffix == ".jsonl" else "application/json"
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data).hexdigest(), "bytes": len(data), "media_type": media}


def signed_document(value: dict[str, Any], seed: bytes, key_id: str) -> dict[str, Any]:
    import rfc8785
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.from_private_bytes(sha256(seed).digest())
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    document_sha256 = sha256(rfc8785.dumps(value)).hexdigest()
    value["seal"] = {
        "key_id": key_id,
        "algorithm": "ed25519",
        "public_key": base64.b64encode(public).decode(),
        "document_sha256": document_sha256,
        "signature": base64.b64encode(
            private.sign(bytes.fromhex(document_sha256))
        ).decode(),
    }
    return value


def build_index(trace_path: Path) -> None:
    data = trace_path.read_bytes()
    records = []
    offset = 0
    for raw in data.splitlines(keepends=True):
        content = raw.rstrip(b"\r\n")
        obj = json.loads(content)
        row = {
            "seq": obj["seq"],
            "kind": obj["kind"],
            "offset": offset,
            "length": len(content),
            "sha256": sha256(content).hexdigest(),
        }
        if obj.get("event_id"):
            row["event_id"] = obj["event_id"]
        if obj.get("type"):
            row["event_type"] = obj["type"]
        records.append(row)
        offset += len(raw)
    write_json(
        ROOT / "example-index.json",
        {
            "profile": "ualf-index/v1",
            "source": {"path": trace_path.name, "sha256": sha256(data).hexdigest(), "bytes": len(data)},
            "created_at": NOW,
            "generator": {"name": "build_profiles.py", "version": "1.0.0"},
            "records": records,
        },
    )


def build_capture_and_retention(trace_path: Path) -> None:
    trace_digest = sha256(trace_path.read_bytes()).hexdigest()
    record_count = len(trace_path.read_bytes().splitlines())
    write_json(
        ROOT / "example-production-capture.json",
        signed_document({
            "profile": "ualf-capture/v1.1",
            "organization": "org-ualf-demo",
            "project": "proj-03",
            "environment": "test",
            "run_id": "run-2026-08-02-demo-001",
            "trace_id": "trace-2026-08-02-demo-001",
            "trace_sha256": trace_digest,
            "created_at": NOW,
            "sampling": {"decision": "keep", "probability": 1.0, "policy": "ualf-demo-sampling/v1", "reason": "manual", "scope": "root_trace"},
            "content_states": {
                "inputs": "captured", "outputs": "captured", "system_messages": "captured", "developer_messages": "not_applicable",
                "tool_definitions": "captured", "tool_arguments": "captured", "tool_results": "captured", "reasoning": "captured",
                "images": "not_applicable", "audio": "not_applicable", "embeddings": "not_applicable", "provider_payloads": "not_available",
            },
            "privacy": {"policy": "ualf-demo-redaction/v1", "boundary": "client", "pre_persistence": True, "secrets_scan": "clean"},
            "delivery": {"mode": "durable_spool", "queue_capacity": 1024, "queue_high_watermark": 8, "accepted_records": record_count, "delivered_records": record_count, "dropped_records": 0, "retry_count": 0, "terminal_failures": 0, "spool": "durable", "flush_status": "completed", "flush_deadline_ms": 5000},
            "clock": {"wall_source": "system_utc", "monotonic_source": "steady_clock", "synchronization": "synthetic-fixture", "synchronized": True, "max_drift_ms": 1.0},
            "recovery": {"status": "clean", "accepted_records_lost": 0, "closer": "example-agent"},
            "completeness": "complete",
        }, b"ualf-capture-demo-key", "ualf-capture-demo-1"),
    )
    write_json(
        ROOT / "example-retention.json",
        signed_document({
            "profile": "ualf-retention/v1.1",
            "organization": "org-ualf-demo",
            "project": "proj-03",
            "environment": "test",
            "subject": {"kind": "trace", "id": "traj-2026-08-02-demo-001", "sha256": trace_digest},
            "policy_id": "ualf-demo-retention/v1",
            "retention_class": "commercial-candidate",
            "created_at": NOW,
            "expires_at": "2033-08-03T12:00:00Z",
            "legal_hold": {"active": False},
            "artifact_policy": {"dependency_mode": "self_contained", "availability_commitment_until": "2033-08-03T12:00:00Z", "dangling_reference_behavior": "reject_package"},
            "encryption": {"at_rest": True, "algorithm": "AES-256-GCM", "key_id": "ualf-demo-storage-key", "key_registry": "https://example.invalid/keys"},
            "erasure": {"method": "cryptographic_shred", "statement_required": True, "statement_schema": "https://iplanic.ai/schemas/ualf/erasure-statement/v1/schema.json"},
        }, b"ualf-retention-demo-key", "ualf-retention-demo-1"),
    )


def build_amendments(trace_path: Path) -> None:
    try:
        import rfc8785
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise SystemExit(f"install requirements.txt dependencies: {exc}") from exc

    private = Ed25519PrivateKey.from_private_bytes(sha256(b"ualf-v1.2-amendment-demo-key").digest())
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    key_id = "ualf-amend-demo-1"
    header = {
        "kind": "amendment_header", "seq": 1, "profile": "ualf-amendments/v1", "stream_id": "amend-stream-demo-001",
        "source_trace_sha256": sha256(trace_path.read_bytes()).hexdigest(), "created_at": NOW,
        "signing": {"key_id": key_id, "algorithm": "ed25519", "public_key": base64.b64encode(public).decode(), "registry": "https://example.invalid/keys", "valid_from": "2026-08-03T00:00:00Z", "valid_until": "2027-08-03T00:00:00Z"},
    }
    header_raw = compact(header)
    evidence = "sha256:a3d2651957f21810eb833386c095e6151e65939b00ef9a7bc1f5809d0c055514"
    first = {
        "kind": "amendment", "seq": 2, "amendment_id": "amend-demo-001", "timestamp": "2026-08-03T12:00:01Z",
        "target": {"kind": "trace", "id": "traj-2026-08-02-demo-001", "sha256": header["source_trace_sha256"]},
        "source": "programmatic", "evaluator": {"id": "pytest", "version": "8.2.0", "organization": "UALF demo"},
        "rubric": {"id": "regression-suite", "version": "1.0.0", "policy": "all required tests pass"},
        "result": True, "severity": "blocking", "confidence": 1.0, "evidence": {"quality": "artifact", "ref": evidence},
        "prev_sha256": sha256(header_raw).hexdigest(),
    }
    first_raw = compact(first)
    second = {
        "kind": "amendment", "seq": 3, "amendment_id": "amend-demo-002", "timestamp": "2026-08-03T12:05:00Z",
        "target": {"kind": "trace", "id": "traj-2026-08-02-demo-001", "sha256": header["source_trace_sha256"]},
        "source": "human", "evaluator": {"id": "reviewer-demo", "version": "1", "organization": "UALF demo"},
        "rubric": {"id": "trajectory-quality", "version": "1.0.0", "policy": "manual evidence review"},
        "result": {"quality": "usable", "notes": "Synthetic conformance fixture only"}, "severity": "info", "confidence": 0.95,
        "evidence": {"quality": "artifact", "ref": evidence}, "prev_sha256": sha256(first_raw).hexdigest(),
    }
    second_raw = compact(second)
    seal_unsigned = {"kind": "amendment_seal", "seq": 4, "closed_at": "2026-08-03T12:05:01Z", "amendment_count": 2, "prev_sha256": sha256(second_raw).hexdigest()}
    chain = sha256(rfc8785.dumps(seal_unsigned)).hexdigest()
    seal = {**seal_unsigned, "chain_sha256": chain, "signature": {"key_id": key_id, "algorithm": "ed25519", "value": base64.b64encode(private.sign(bytes.fromhex(chain))).decode()}}
    (ROOT / "example-amendments.jsonl").write_bytes(b"\n".join([header_raw, first_raw, second_raw, compact(seal)]) + b"\n")


def projection_manifest(profile: str, spec: str, revision: str, source: Path, output: Path, mappings: list[dict[str, Any]], omissions: list[dict[str, Any]], loss: str, privacy: dict[str, str]) -> dict[str, Any]:
    return {
        "profile": "ualf-projection-manifest/v1", "projection_id": f"projection-{profile.split('/')[0]}-demo", "source_profile": "ualf-trace/v1.1" if source.suffix == ".jsonl" else "ualf-dataset/v1.2",
        "target": {"profile": profile, "specification": spec, "revision": revision}, "source": digest(source), "outputs": [digest(output)],
        "exporter": {"name": "build_profiles.py", "version": "1.1.0", "source_revision": "ualf-v1.3", "deterministic": True},
        "record_mappings": mappings, "omissions": omissions, "loss_class": loss, "privacy": privacy,
        "validator": {"name": "verify_profiles.py", "version": "1.0.0", "result": "passed", "validated_at": NOW}, "generated_at": NOW,
    }


def build_projections(trace_path: Path) -> None:
    objects = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    header, outcome = objects[0], objects[-1]
    trace_digest = sha256(trace_path.read_bytes()).hexdigest()
    projection_dir = ROOT / "projections"
    projection_dir.mkdir(exist_ok=True)
    otel = {
        "resourceSpans": [{"resource": {"attributes": [{"key": "service.namespace", "value": {"stringValue": header["project"]}}, {"key": "service.version", "value": {"stringValue": header["agent"]["agent_version"]}}, {"key": "ualf.source.sha256", "value": {"stringValue": trace_digest}}]},
        "scopeSpans": [{"scope": {"name": "ualf.exporter", "version": "1.0.0"}, "spans": [{"traceId": sha256(header["trace_id"].encode()).hexdigest()[:32], "spanId": sha256(b"span-run").hexdigest()[:16], "name": "agent run", "kind": 1, "startTimeUnixNano": unix_nano(header["started_at"]), "endTimeUnixNano": unix_nano(outcome["timestamp"]), "attributes": [{"key": "ualf.run.id", "value": {"stringValue": header["run_id"]}}, {"key": "ualf.outcome", "value": {"stringValue": outcome["status"]}}]}]}]}]
    }
    oi = {"profile": "ualf-openinference/v1", "source_trace_sha256": trace_digest, "spans": [{"name": "agent run", "kind": "AGENT", "attributes": {"openinference.span.kind": "AGENT", "session.id": header["run_id"]}}, {"name": "model call", "kind": "LLM", "attributes": {"openinference.span.kind": "LLM", "llm.model_name": "example-agent-model", "ualf.content.mode": "references"}}]}
    lineage = {"eventType": "COMPLETE", "eventTime": NOW, "producer": "https://github.com/vladm3105/aidoc-flow-logging", "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json", "run": {"runId": "0198a8c0-0000-7000-8000-000000000001", "facets": {"ualf_source": {"_producer": "https://github.com/vladm3105/aidoc-flow-logging", "_schemaURL": "https://iplanic.ai/schemas/ualf-openlineage-facet.json?version=1.0.0", "traceSha256": trace_digest}}}, "job": {"namespace": "ualf", "name": "dataset-qualification"}, "inputs": [{"namespace": "ualf", "name": trace_path.name, "facets": {}}], "outputs": [{"namespace": "ualf", "name": "example-manifest.json", "facets": {}}]}
    croissant = {"@context": {"@language": "en", "sc": "https://schema.org/", "cr": "http://mlcommons.org/croissant/"}, "@type": "sc:Dataset", "name": "UALF synthetic conformance dataset", "description": "Synthetic fixture for UALF validators; not representative training inventory.", "license": "https://www.apache.org/licenses/LICENSE-2.0", "version": "1.2.0", "url": "https://github.com/vladm3105/aidoc-flow-logging", "conformsTo": "http://mlcommons.org/croissant/1.0", "distribution": [{"@type": "cr:FileObject", "@id": "manifest", "name": "example-manifest.json", "contentUrl": "example-manifest.json", "sha256": sha256((ROOT / "example-manifest.json").read_bytes()).hexdigest(), "encodingFormat": "application/json"}]}
    statement = {"_type": "https://in-toto.io/Statement/v1", "subject": [{"name": "example-manifest.json", "digest": {"sha256": sha256((ROOT / "example-manifest.json").read_bytes()).hexdigest()}}], "predicateType": "https://iplanic.ai/attestations/ualf-qualification/v1", "predicate": {"datasetId": "dataset-ualf-demo-001", "profile": "ualf-dataset/v1.2", "qualityReportSha256": sha256((ROOT / "example-quality-report.json").read_bytes()).hexdigest(), "rightsStatus": "cleared", "intendedUses": ["format validation", "integration testing"], "prohibitedUses": ["representation as production training inventory"], "validator": "verify.py/1.2", "validatedAt": NOW, "signerRole": "dataset-producer"}}
    values = {
        "otel-genai": ("ualf-otel-genai/v1", "https://github.com/open-telemetry/semantic-conventions-genai/commit/9af08349db7e70b2528accde90bae81d4ebcfa1e", "core-semconv-1.43.0+genai@9af08349db7e70b2528accde90bae81d4ebcfa1e", otel, "semantically_lossy", {"policy": "ualf-otel-default/v1", "raw_content": "excluded", "transformation": "hash"}),
        "openinference": ("ualf-openinference/v1", "https://arize-ai.github.io/openinference/spec/", "59ea35e3b69c830a26c0560825dde00bd43e292d", oi, "semantically_lossy", {"policy": "ualf-openinference-default/v1", "raw_content": "excluded", "transformation": "hash"}),
        "openlineage": ("ualf-openlineage/v1", "https://openlineage.io/spec/", "1.50.0+8470ab1696ee5941d8d3a1e48c2238073eb1fe34", lineage, "semantically_lossy", {"policy": "ualf-lineage/v1", "raw_content": "excluded", "transformation": "hash"}),
        "croissant": ("ualf-croissant/v1", "https://mlcommons.org/croissant/", "1.0+401f6fff81db26a49c0d1704f02bffc4e4fa8fe2", croissant, "aggregate_only", {"policy": "ualf-dataset-discovery/v1", "raw_content": "excluded", "transformation": "aggregate"}),
        "in-toto": ("ualf-in-toto-qualification/v1", "https://in-toto.io/Statement/v1", "v1+6fad7157dfb216034e28223c6b5c6b0f9c41bf28", statement, "aggregate_only", {"policy": "ualf-attestation/v1", "raw_content": "excluded", "transformation": "hash"}),
    }
    for name, (profile, spec, revision, value, loss, privacy) in values.items():
        output = projection_dir / f"example-{name}.json"
        write_json(output, value)
        source = ROOT / "example-manifest.json" if name in {"croissant", "in-toto"} else trace_path
        mappings = [{"source": "trace", "targets": ["root-span"], "id_derivation": "sha256-prefix"}] if name in {"otel-genai", "openinference"} else [{"source": source.name, "targets": [output.name]}]
        omissions = [{"source_semantic": "model-visible content", "reason": "privacy", "effect": "content_loss", "details": "Default public example carries references and hashes only."}]
        manifest = projection_manifest(profile, spec, revision, source, output, mappings, omissions, loss, privacy)
        if name in {"croissant", "in-toto"}:
            manifest["source_profile"] = "ualf-dataset/v1.2"
        if name == "in-toto":
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            payload_type = "application/vnd.in-toto+json"
            payload = compact(value)
            private = Ed25519PrivateKey.from_private_bytes(sha256(b"ualf-v1.2-dsse-demo-key").digest())
            public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            envelope = {"payloadType": payload_type, "payload": base64.b64encode(payload).decode(), "signatures": [{"keyid": "ualf-dsse-demo-1", "sig": base64.b64encode(private.sign(dsse_pae(payload_type, payload))).decode()}], "verification": {"algorithm": "ed25519", "public_key": base64.b64encode(public).decode(), "registry": "https://example.invalid/keys"}}
            envelope_path = projection_dir / "example-in-toto.dsse.json"
            write_json(envelope_path, envelope)
            manifest["outputs"].append(digest(envelope_path))
        write_json(projection_dir / f"example-{name}-manifest.json", manifest)


def build_registry() -> None:
    write_json(ROOT / "extension-registry.json", {"profile": "ualf-extension-registry/v1", "updated_at": NOW, "extensions": [
        {"id": "iplanic.ai/capture/v1.1", "schema_url": "https://iplanic.ai/schemas/ualf/capture/v1.1/report.schema.json", "owner": "UALF maintainers", "contact": "https://github.com/vladm3105/aidoc-flow-logging/issues", "status": "experimental", "requirement_level": "recommended", "applies_to": ["header", "capture"], "privacy_risk": "low", "unknown_consumer_behavior": "preserve", "first_supported_profile": "ualf-trace/v1.1", "description": "Binds production sampling, delivery, privacy and recovery evidence."},
        {"id": "iplanic.ai/otel/semconv-genai/2026-08-03", "schema_url": "https://iplanic.ai/schemas/ualf/projection-manifest/v1/schema.json", "owner": "UALF maintainers", "contact": "https://github.com/vladm3105/aidoc-flow-logging/issues", "status": "experimental", "requirement_level": "opt_in", "applies_to": ["projection"], "privacy_risk": "sensitive", "unknown_consumer_behavior": "preserve", "first_supported_profile": "ualf-trace/v1.1", "description": "Version-pinned OpenTelemetry GenAI projection metadata."}
    ]})


def build_analytics(trace_path: Path) -> None:
    from export_analytics import project, write_jsonl

    output_dir = ROOT / "analytics"
    outputs = write_jsonl(output_dir, project(trace_path))
    manifest = {
        "profile": "ualf-projection-manifest/v1", "projection_id": "projection-ualf-analytics-demo", "source_profile": "ualf-trace/v1.1",
        "target": {"profile": "ualf-analytics/v1", "specification": "https://iplanic.ai/specs/ualf-analytics/v1", "revision": "1.0.0"},
        "source": digest(trace_path), "outputs": [digest(path) for path in outputs],
        "exporter": {"name": "export_analytics.py", "version": "1.1.0", "source_revision": "ualf-v1.3", "deterministic": True},
        "record_mappings": [{"source": "header", "targets": ["traces"]}, {"source": "events", "targets": ["events", "model_calls", "tool_calls", "evaluations", "content_refs"]}, {"source": "outcome", "targets": ["outcomes"]}],
        "omissions": [{"source_semantic": "raw referenced content", "reason": "privacy", "effect": "content_loss", "details": "Analytical rows retain content digests and provenance only."}],
        "loss_class": "semantically_lossy", "privacy": {"policy": "ualf-analytics-default/v1", "raw_content": "excluded", "transformation": "hash"},
        "validator": {"name": "verify_profiles.py", "version": "1.0.0", "result": "passed", "validated_at": NOW}, "generated_at": NOW,
    }
    write_json(output_dir / "example-analytics-manifest.json", manifest)


def merkle_root(leaves: list[bytes]) -> bytes:
    level = leaves
    while len(level) > 1:
        if len(level) % 2:
            level = [*level, level[-1]]
        level = [sha256(level[index] + level[index + 1]).digest() for index in range(0, len(level), 2)]
    return level[0]


def build_segments(trace_path: Path, records_per_segment: int = 5) -> None:
    try:
        import rfc8785
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise SystemExit(f"install requirements.txt dependencies: {exc}") from exc

    data = trace_path.read_bytes()
    lines = data.splitlines(keepends=True)
    segments = []
    offset = 0
    leaf_digests: list[bytes] = []
    for index, start in enumerate(range(0, len(lines), records_per_segment)):
        raw = b"".join(lines[start : start + records_per_segment])
        leaf = sha256(raw).digest()
        leaf_digests.append(leaf)
        segments.append({"index": index, "seq_start": start + 1, "seq_end": min(start + records_per_segment, len(lines)), "offset": offset, "bytes": len(raw), "sha256": leaf.hex()})
        offset += len(raw)
    private = Ed25519PrivateKey.from_private_bytes(sha256(b"ualf-v1.2-segment-demo-key").digest())
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    key_id = "ualf-segment-demo-1"
    unsigned = {
        "profile": "ualf-segments/v1", "source": {"path": trace_path.name, "sha256": sha256(data).hexdigest(), "bytes": len(data)}, "created_at": NOW,
        "segment_policy": {"records_per_segment": records_per_segment, "preserves_exact_bytes": True}, "segments": segments,
        "merkle": {"algorithm": "sha256", "leaf": "raw-segment-sha256", "odd_node": "duplicate_last", "root": merkle_root(leaf_digests).hex()},
        "signing": {"key_id": key_id, "algorithm": "ed25519", "public_key": base64.b64encode(public).decode(), "registry": "https://example.invalid/keys"},
    }
    manifest_hash = sha256(rfc8785.dumps(unsigned)).hexdigest()
    write_json(ROOT / "example-segment-manifest.json", {**unsigned, "seal": {"manifest_sha256": manifest_hash, "signature": {"key_id": key_id, "algorithm": "ed25519", "value": base64.b64encode(private.sign(bytes.fromhex(manifest_hash))).decode()}}})


def main() -> int:
    trace = ROOT / "example-trajectory.jsonl"
    build_index(trace)
    build_capture_and_retention(trace)
    build_amendments(trace)
    build_registry()
    build_projections(trace)
    build_analytics(trace)
    build_segments(trace)
    from generate_sdk_types import main as generate_sdk_types
    generate_sdk_types()
    print("Built UALF v1.3 profile examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
