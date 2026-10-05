from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sdk.python.recorder import TrajectoryRecorder, normalize_project_id


class TestTrajectoryRecorder(unittest.TestCase):
    def test_normalize_project_id(self) -> None:
        self.assertEqual(normalize_project_id("proj-interlog"), "proj-interlog")
        self.assertEqual(normalize_project_id("aidoc-flow-interlog"), "proj-aidoc-flow-interlog")
        self.assertEqual(normalize_project_id("engramory"), "proj-engramory")
        self.assertEqual(normalize_project_id("b_local_privy"), "proj-b-local-privy")

    def test_recorder_gapless_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            spool_dir = Path(tmp_dir) / "spool"
            blobs_dir = Path(tmp_dir) / "blobs"

            recorder = TrajectoryRecorder(
                organization="org-aidoc",
                project="aidoc-flow-interlog",
                deployment_environment="development",
                agent_id="test-agent",
                spool_dir=spool_dir,
                blobs_dir=blobs_dir,
                task_goal="Verify UALF recorder functionality",
            )

            # Record tool call and completion
            call_id = recorder.record_tool_call(
                tool="bash",
                tool_version="1.0",
                arguments={"command": "pytest tests/"},
                interlog_event_id="evt-test-123",
            )
            recorder.record_tool_completion(
                call_id=call_id,
                tool="bash",
                status="ok",
                output="15 passed in 0.45s",
                latency_ms=450,
            )

            # Record memory access
            recorder.record_memory_access(
                memory_id="mem-99",
                layer="L2",
                action="read",
                query="test query",
                similarity=0.95,
            )

            # Record delegation
            recorder.record_delegation(
                child_run_id="run-child-456",
                child_trace_id="trace-child-456",
                child_agent_id="agent-child",
                task_description="Execute sub-task",
            )

            # Close trajectory
            spool_file = recorder.close(status="completed", score=1.0)
            self.assertTrue(spool_file.exists())

            # Verify line-by-line exact-byte hash chain
            lines = spool_file.read_bytes().splitlines()
            self.assertEqual(len(lines), 6)  # header + 4 events + outcome

            header = json.loads(lines[0])
            self.assertEqual(header["kind"], "header")
            self.assertEqual(header["seq"], 1)
            self.assertEqual(header["project"], "proj-aidoc-flow-interlog")

            for i in range(1, len(lines)):
                record = json.loads(lines[i])
                self.assertEqual(record["seq"], i + 1)
                expected_prev_sha = hashlib.sha256(lines[i - 1]).hexdigest()
                self.assertEqual(record["prev_sha256"], expected_prev_sha)

            outcome = json.loads(lines[-1])
            self.assertEqual(outcome["kind"], "outcome")
            self.assertEqual(outcome["status"], "completed")
            self.assertEqual(outcome["totals"]["events"], 4)
            self.assertEqual(outcome["totals"]["tool_calls"], 1)


if __name__ == "__main__":
    unittest.main()
