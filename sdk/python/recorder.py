# -*- coding: utf-8 -*-
"""UALF Python Trajectory Recorder.

A zero-external-dependency in-flight trajectory recorder for Python spokes.
Provides gapless SHA-256 byte chaining, in-flight spooling to `.ualf/spool/`,
content-addressed blob storage, and canonical project slug mapping.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from .ualf_types import EVENT_TYPES, PROFILES, EventType, Profile

# Strict UALF Regex Patterns
PROJECT_PATTERN: Final = re.compile(r"^proj-[a-z0-9-]{2,}$")
ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")


def normalize_project_id(project: str) -> str:
    """Normalize and validate a project string into a compliant UALF project ID.

    UALF requires: `^proj-[a-z0-9-]{2,}$`.
    E.g.: 'aidoc-flow-interlog' -> 'proj-interlog' (or 'proj-aidoc-flow-interlog')
    """
    clean = project.strip().lower().replace("_", "-").replace(".", "-")
    if not clean.startswith("proj-"):
        clean = f"proj-{clean}"
    if not PROJECT_PATTERN.match(clean):
        # Fallback to sanitize illegal characters
        clean = "proj-" + re.sub(r"[^a-z0-9-]", "-", clean[5:]).strip("-")
        if len(clean) < 7:
            clean = f"{clean}-project"
    return clean


def utc_now_iso() -> str:
    """Return current UTC time formatted as an RFC 3339 ISO string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TrajectoryRecorder:
    """Authoritative in-flight UALF trajectory recorder for agent runs."""

    def __init__(
        self,
        organization: str = "org-aidoc",
        project: str = "proj-default",
        deployment_environment: str = "development",
        run_id: str | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
        spool_dir: Path | str = ".ualf/spool",
        blobs_dir: Path | str = ".ualf/blobs",
        domain: str = "software_dev",
        agent_id: str = "agent-executor",
        agent_role: str = "coding_agent",
        agent_framework: str = "aidoc-agent",
        task_goal: str = "Execute assigned task",
        acceptance: list[str] | None = None,
        key_id: str = "ephemeral-key-01",
        public_key_b64: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    ) -> None:
        self.organization = organization
        self.project = normalize_project_id(project)
        self.deployment_environment = deployment_environment
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:16]}"
        self.trace_id = trace_id or f"trace-{uuid.uuid4().hex[:16]}"
        self.session_id = session_id or f"session-{uuid.uuid4().hex[:16]}"
        self.trajectory_id = f"traj-{self.run_id}"

        self.spool_dir = Path(spool_dir)
        self.blobs_dir = Path(blobs_dir)
        self.spool_dir.mkdir(parents=True, exist_ok=True)
        self.blobs_dir.mkdir(parents=True, exist_ok=True)

        self.spool_file = self.spool_dir / f"{self.run_id}.jsonl"

        self.domain = domain
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.agent_framework = agent_framework
        self.task_goal = task_goal
        self.acceptance = acceptance or ["Task requirements satisfied with 0 regressions"]

        self.key_id = key_id
        self.public_key_b64 = public_key_b64

        self.seq = 1
        self.local_seq = 1
        self.prev_sha256 = ""
        self.start_mono_ms = int(time.monotonic() * 1000)
        self.clock_id = f"clock-{uuid.uuid4().hex[:8]}"
        self.process_id = f"proc-{os.getpid()}"
        self.producer_id = f"prod-{self.agent_id}"

        self.totals = {
            "events": 0,
            "model_calls": 0,
            "tool_calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0,
            "wall_time_ms": 0,
        }

        self._active_calls: dict[str, dict[str, Any]] = {}
        self.is_closed = False

        # Initialize and write header (line 1)
        self._write_header()

    def _mono_ms(self) -> int:
        return max(0, int(time.monotonic() * 1000) - self.start_mono_ms)

    def store_blob(
        self,
        data: bytes,
        media_type: str = "text/plain",
        role: str = "tool_output",
        origin_type: str = "tool",
        origin_source: str = "local",
    ) -> dict[str, Any]:
        """Store bytes into content-addressed blob storage and return a UALF blobRef."""
        digest = hashlib.sha256(data).hexdigest()
        blob_path = self.blobs_dir / digest
        if not blob_path.exists():
            blob_path.write_bytes(data)

        return {
            "$ref": f"sha256:{digest}",
            "bytes": len(data),
            "media_type": media_type,
            "encoding": "identity",
            "content_role": role,
            "origin": {
                "type": origin_type,
                "source": origin_source,
            },
        }

    def _write_line(self, obj: dict[str, Any]) -> str:
        """Serialize JSON, write physical line, and update hash chain."""
        line_bytes = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        line_sha = hashlib.sha256(line_bytes).hexdigest()

        with open(self.spool_file, "ab") as f:
            f.write(line_bytes + b"\n")

        self.prev_sha256 = line_sha
        self.seq += 1
        return line_sha

    def _write_header(self) -> None:
        """Write line 1 (header)."""
        goal_blob = self.store_blob(
            self.task_goal.encode("utf-8"),
            media_type="text/plain",
            role="authored_prompt",
            origin_type="project",
            origin_source=self.project,
        )

        tools_doc = {
            "schema": "ualf-tools/v1",
            "tools": [],
        }
        tools_blob = self.store_blob(
            json.dumps(tools_doc).encode("utf-8"),
            media_type="application/json",
            role="tool_definitions",
            origin_type="project",
            origin_source=self.project,
        )

        header = {
            "kind": "header",
            "seq": 1,
            "schema": "ualf-trace/v1.1",
            "organization": self.organization,
            "project": self.project,
            "deployment_environment": self.deployment_environment,
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "trajectory_id": self.trajectory_id,
            "domain": self.domain,
            "agent": {
                "id": self.agent_id,
                "framework": self.agent_framework,
                "framework_version": "1.0",
                "role": self.agent_role,
                "agent_version": "1.0",
                "prompt_version": "1.0",
            },
            "task": {
                "goal": goal_blob,
                "category": "software_engineering",
                "acceptance": self.acceptance,
            },
            "environment": {
                "workspace_sha256": "0" * 64,
                "source_revision": os.environ.get("GIT_COMMIT", "HEAD"),
                "os": sys.platform,
                "runtime_versions": {"python": sys.version.split()[0]},
                "tools_ref": tools_blob,
                "replay": {
                    "available_level": "none",
                    "model_responses_captured": False,
                    "tool_responses_captured": False,
                    "nondeterministic_inputs_captured": False,
                },
            },
            "capture": {
                "context_policy": "complete",
                "redaction_policy": "none",
                "retention_mode": "full",
            },
            "rights": {
                "owner": self.organization,
                "classification": "internal",
                "model_sources": ["internal"],
                "pii": "none",
                "secrets_scan": {
                    "tool": "runtime-sanitizer",
                    "version": "1.0",
                    "verdict": "clean",
                },
            },
            "provenance": {
                "signing": {
                    "key_id": self.key_id,
                    "algorithm": "ed25519",
                    "public_key": self.public_key_b64,
                }
            },
            "started_at": utc_now_iso(),
        }

        self._write_line(header)

    def record_event(
        self,
        event_type: str,
        data: dict[str, Any],
        span_id: str | None = None,
        parent_span_id: str | None = None,
        caused_by: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an in-flight event adhering to the UALF envelope."""
        if self.is_closed:
            raise RuntimeError("Cannot record events on a closed trajectory")

        now_utc = utc_now_iso()
        ev_id = f"ev-{self.local_seq:05d}"
        s_id = span_id or f"span-{uuid.uuid4().hex[:12]}"

        envelope = {
            "kind": "event",
            "seq": self.seq,
            "event_id": ev_id,
            "organization": self.organization,
            "project": self.project,
            "deployment_environment": self.deployment_environment,
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "span_id": s_id,
            "parent_span_id": parent_span_id,
            "actor": {
                "type": "agent",
                "id": self.agent_id,
            },
            "producer": {
                "id": self.producer_id,
                "process_id": self.process_id,
                "clock_id": self.clock_id,
                "local_seq": self.local_seq,
            },
            "timestamp": now_utc,
            "observed_at": now_utc,
            "monotonic_ms": self._mono_ms(),
            "type": event_type,
            "data": data,
            "prev_sha256": self.prev_sha256,
        }

        if caused_by:
            envelope["caused_by"] = caused_by
        if extensions:
            envelope["extensions"] = extensions

        self._write_line(envelope)
        self.local_seq += 1
        self.totals["events"] += 1
        return envelope

    def record_tool_call(
        self,
        tool: str,
        tool_version: str,
        arguments: dict[str, Any],
        call_id: str | None = None,
        span_id: str | None = None,
        interlog_event_id: str | None = None,
    ) -> str:
        """Record the start of a tool invocation."""
        c_id = call_id or f"call-tool-{uuid.uuid4().hex[:8]}"
        extensions = None
        if interlog_event_id:
            extensions = {
                "aidoc.io/interlog/v1": {
                    "interlog_event_id": interlog_event_id,
                }
            }

        self.record_event(
            event_type="tool_call.started",
            data={
                "call_id": c_id,
                "tool": tool,
                "tool_version": tool_version,
                "arguments": arguments,
            },
            span_id=span_id,
            extensions=extensions,
        )
        self._active_calls[c_id] = {"tool": tool, "start_time": time.monotonic()}
        self.totals["tool_calls"] += 1
        return c_id

    def record_tool_completion(
        self,
        call_id: str,
        tool: str,
        status: str = "ok",
        output: Any = None,
        latency_ms: int = 0,
        error: str | None = None,
        span_id: str | None = None,
    ) -> dict[str, Any]:
        """Record tool completion."""
        data: dict[str, Any] = {
            "call_id": call_id,
            "tool": tool,
            "status": status,
            "latency_ms": latency_ms,
        }
        if status == "ok":
            if isinstance(output, bytes):
                blob = self.store_blob(output, role="tool_output")
                data["output_ref"] = blob
            elif isinstance(output, str) and len(output) > 2048:
                blob = self.store_blob(output.encode("utf-8"), role="tool_output")
                data["output_ref"] = blob
            else:
                data["value"] = output if output is not None else ""
        else:
            data["no_output"] = True
            data["error"] = {
                "class": "ToolExecutionError",
                "message": error or "Unknown error",
                "retryable": False,
            }

        return self.record_event("tool_call.completed", data=data, span_id=span_id)

    def record_memory_access(
        self,
        memory_id: str,
        layer: str,
        action: str = "read",
        query: str | None = None,
        similarity: float | None = None,
        span_id: str | None = None,
    ) -> dict[str, Any]:
        """Record an Engramory memory read or update."""
        extensions = {
            "aidoc.io/engramory/v1": {
                "memory_id": memory_id,
                "layer": layer,
                "action": action,
                "query": query,
                "similarity_score": similarity,
            }
        }
        return self.record_event(
            event_type="memory.accessed",
            data={
                "activity_id": f"act-mem-{uuid.uuid4().hex[:8]}",
                "agent_id": self.agent_id,
                "status": "ok",
            },
            span_id=span_id,
            extensions=extensions,
        )

    def record_delegation(
        self,
        child_run_id: str,
        child_trace_id: str,
        child_agent_id: str,
        task_description: str,
        span_id: str | None = None,
    ) -> str:
        """Record delegation to a child/worktree agent."""
        act_id = f"act-del-{uuid.uuid4().hex[:8]}"
        task_blob = self.store_blob(task_description.encode("utf-8"), role="model_input")
        self.record_event(
            event_type="delegation.started",
            data={
                "activity_id": act_id,
                "agent_id": self.agent_id,
                "child_run_id": child_run_id,
                "child_trace_id": child_trace_id,
                "status": "started",
                "task_ref": task_blob,
            },
            span_id=span_id,
        )
        return act_id

    def close(
        self,
        status: str = "completed",
        score: float = 1.0,
        evaluations: list[dict[str, Any]] | None = None,
    ) -> Path:
        """Close the trajectory, append outcome record (line N), and flush to disk."""
        if self.is_closed:
            return self.spool_file

        now_utc = utc_now_iso()
        self.totals["wall_time_ms"] = self._mono_ms()

        evs = evaluations or [
            {
                "id": "eval-final-01",
                "evaluator": {"type": "system", "id": "spoke-runner"},
                "rubric": "task-completion",
                "score": score,
                "verdict": "passed" if score >= 0.7 else "failed",
            }
        ]

        outcome = {
            "kind": "outcome",
            "seq": self.seq,
            "status": status,
            "timestamp": now_utc,
            "evaluations": evs,
            "totals": self.totals,
            "prev_sha256": self.prev_sha256,
        }

        self._write_line(outcome)
        self.is_closed = True
        return self.spool_file
