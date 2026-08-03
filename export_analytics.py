#!/usr/bin/env python3
"""Export stable UALF analytical tables as JSONL or optional Parquet."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any


PROJECTION_VERSION = "ualf-analytics/v1"


def refs(value: Any, location: str = "$") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if isinstance(value.get("$ref"), str) and value["$ref"].startswith("sha256:"):
            found.append({"location": location, **value})
        for key, child in value.items():
            found.extend(refs(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(refs(child, f"{location}[{index}]"))
    return found


def common(source_digest: str, header: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_trace_sha256": source_digest,
        "projection_version": PROJECTION_VERSION,
        "run_id": header["run_id"],
        "trace_id": header["trace_id"],
        "trajectory_id": header["trajectory_id"],
    }


def project(trace_path: Path) -> dict[str, list[dict[str, Any]]]:
    data = trace_path.read_bytes()
    source_digest = sha256(data).hexdigest()
    objects = [json.loads(line) for line in data.splitlines()]
    header, outcome = objects[0], objects[-1]
    base = common(source_digest, header)
    events = objects[1:-1]
    tables: dict[str, list[dict[str, Any]]] = {
        "traces": [{**base, "project": header["project"], "domain": header["domain"], "agent_framework": header["agent"]["framework"], "agent_version": header["agent"]["agent_version"], "prompt_version": header["agent"]["prompt_version"], "started_at": header["started_at"], "status": outcome["status"]}],
        "events": [], "model_calls": [], "tool_calls": [], "content_refs": [], "evaluations": [],
        "outcomes": [{**base, "status": outcome["status"], "timestamp": outcome["timestamp"], **outcome["totals"]}],
    }
    started: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        event_base = {**base, "seq": event["seq"], "event_id": event["event_id"], "event_type": event["type"], "span_id": event["span_id"], "parent_span_id": event.get("parent_span_id"), "caused_by": event.get("caused_by"), "timestamp": event["timestamp"], "monotonic_ms": event["monotonic_ms"], "actor_type": event["actor"]["type"], "actor_id": event["actor"]["id"]}
        tables["events"].append(event_base)
        call_id = event.get("data", {}).get("call_id")
        if call_id and event["type"].endswith(".started"):
            started[(event["type"].split("_")[0], call_id)] = event
        elif call_id and event["type"] == "model_call.completed":
            begin = started.get(("model", call_id), {})
            tables["model_calls"].append({**base, "call_id": call_id, "span_id": event["span_id"], "provider": event["data"]["provider"], "model": event["data"]["model"], "started_event_id": begin.get("event_id"), "completed_event_id": event["event_id"], "context_complete": begin.get("data", {}).get("context_complete"), "tokens_in": event["data"]["usage"]["tokens_in"], "tokens_out": event["data"]["usage"]["tokens_out"], "cost_usd": str(event["data"]["cost_usd"]), "latency_ms": event["data"]["latency_ms"], "finish_reason": event["data"]["finish_reason"]})
        elif call_id and event["type"] == "tool_call.completed":
            begin = started.get(("tool", call_id), {})
            tables["tool_calls"].append({**base, "call_id": call_id, "span_id": event["span_id"], "tool": event["data"]["tool"], "started_event_id": begin.get("event_id"), "completed_event_id": event["event_id"], "status": event["data"]["status"], "latency_ms": event["data"]["latency_ms"]})
        if event["type"] == "evaluation.completed":
            value = event["data"]
            tables["evaluations"].append({**base, "source": "runtime", "target_kind": "trace", "target_id": header["trajectory_id"], "evaluator": value["evaluator"], "evaluator_version": value["evaluator_version"], "method": value["method"], "status": value["status"], "score": value.get("score"), "severity": "blocking", "event_id": event["event_id"]})
    for index, ref in enumerate(refs(objects)):
        tables["content_refs"].append({**base, "occurrence": index, "location": ref["location"], "sha256": ref["$ref"][7:], "bytes": ref["bytes"], "media_type": ref["media_type"], "encoding": ref["encoding"], "content_role": ref["content_role"], "origin_type": ref["origin"]["type"], "origin_source": ref["origin"]["source"]})
    return tables


def write_jsonl(directory: Path, tables: dict[str, list[dict[str, Any]]]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, rows in tables.items():
        path = directory / f"{name}.jsonl"
        path.write_bytes(
            "".join(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in rows
            ).encode("utf-8")
        )
        outputs.append(path)
    return outputs


def write_parquet(directory: Path, tables: dict[str, list[dict[str, Any]]]) -> list[Path]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SystemExit("Parquet export requires optional dependency: pip install pyarrow") from exc
    directory.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, rows in tables.items():
        path = directory / f"{name}.parquet"
        pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd")
        outputs.append(path)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path, default=Path("analytics"))
    parser.add_argument("--format", choices=["jsonl", "parquet"], default="jsonl")
    args = parser.parse_args()
    tables = project(args.trace)
    outputs = write_jsonl(args.output, tables) if args.format == "jsonl" else write_parquet(args.output, tables)
    print(f"Wrote {len(outputs)} {args.format} tables to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
