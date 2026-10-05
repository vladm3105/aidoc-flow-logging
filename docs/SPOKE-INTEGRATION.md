# UALF Spoke Integration Guide

**Platform:** Universal Agent Log Format (UALF v1.3)  
**Target Audience:** Spoke service developers, coding agents in isolated worktrees (`b-local-privy`), and operations orchestrators across `aidoc-flow-engramory`, `aidoc-flow-interlog`, `aidoc-observability-monitoring`, and specialized agent workspaces.

---

## 1. Architectural Role & The Dual Mandate

UALF serves a **Dual Mandate** across the multi-agent ecosystem:

1. **Operational Execution Floor (Internal):** High-fidelity, intra-agent step logging (prompts, tool calls, bash commands, file diffs, test runs, memory reads/writes, evaluations, and outcomes) for local debugging, performance profiling, regression testing, and supervisory auditing.
2. **Qualified Dataset Refinery (Downstream):** A rigorous qualification and cryptographic sealing pipeline (`ualf-dataset/v1.2`) that transforms selected operational runs into tamper-evident commercial AI training assets (SFT JSONL, DPO preference pairs, Parquet) and regulated AI audit archives (EU AI Act).

---

## 2. The Dual-Path Telemetry Invariant

Every autonomous agent in the ecosystem emits telemetry along two complementary paths:

```text
                           Autonomous Spoke Agent
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         │                                                       │
         ▼ (Live Hot Path)                                       ▼ (Authoritative Cold Path)
   OpenTelemetry OTLP                                      UALF JSONL Spool
   (http://localhost:4318)                                 (.ualf/spool/<run_id>.jsonl)
         │                                                       │
         ▼                                                       ▼
[ aidoc-observability-monitoring ]                         [ Authoritative Archive & Refinery ]
 • OTel Collector                                           • Gapless SHA-256 exact-byte chain
 • Grafana Tempo (trace_id)                                 • Content-addressed blobs (blobs/sha256:…)
 • Grafana Loki (logs & stdout)                             • MinIO ualf-archives/
 • Langfuse (live prompt inspection)                        • ClickHouse ualf_analytics (7 tables)
                                                            • Engramory L2/L3 Distillation Pipeline
```

- **Live Hot Path:** Low-latency, non-blocking OTLP spans and logs streamed to the local OpenTelemetry Collector for real-time observability in Grafana and Langfuse.
- **Authoritative Cold Path:** Local file spool containing the gapless, exact-byte hash-chained JSONL records (`prev_sha256`) and content-addressed blobs. This file is the legal and technical source of truth for replay, memory synthesis, and audits.

---

## 3. Canonical Project Slug Mapping

UALF schemas strictly mandate that every `project` identifier matches the regular expression:

```text
^proj-[a-z0-9-]{2,}$
```

Top-level properties set `additionalProperties: false`. If a spoke emits an un-prefixed project name (e.g. `aidoc-flow-interlog`), **the schema verifier will reject the trace**.

Spoke services must map their repository names to compliant project slugs:

| Repository / Spoke | Canonical UALF Project Slug |
| :--- | :--- |
| `aidoc-flow-interlog` | `proj-interlog` (or `proj-aidoc-flow-interlog`) |
| `aidoc-flow-engramory` | `proj-engramory` |
| `aidoc-observability-monitoring` | `proj-observability` |
| `b-local-privy` (coding worktree) | `proj-privy` |
| `aidoc-flow-support-desk` | `proj-support-desk` |
| `unified-test-suite` | `proj-test-suite` |

The Python SDK automatically applies this normalization via `normalize_project_id()`.

---

## 4. Python SDK Integration (`ualf.recorder`)

### 4.1 Installation

In spoke projects, install the package in editable mode or reference it via dependencies:

```bash
pip install -e /mnt/e/dev/flow-trajectory-logging
```

### 4.2 Standard Lifecycle Instrumentation

```python
from ualf.recorder import TrajectoryRecorder

# 1. Initialize recorder at agent turn/run start
recorder = TrajectoryRecorder(
    organization="org-aidoc",
    project="aidoc-flow-interlog",  # Automatically normalized to proj-aidoc-flow-interlog
    deployment_environment="development",
    agent_id="coding-agent-01",
    agent_role="software_engineer",
    task_goal="Fix database connection leak in worker pool",
    spool_dir=".ualf/spool",
    blobs_dir=".ualf/blobs",
)

# 2. Record tool invocation
call_id = recorder.record_tool_call(
    tool="bash",
    tool_version="1.0",
    arguments={"command": "git diff src/db.py"},
)

# 3. Record tool completion (large outputs automatically stored as content-addressed blobs)
recorder.record_tool_completion(
    call_id=call_id,
    tool="bash",
    status="ok",
    output="diff --git a/src/db.py b/src/db.py...",
    latency_ms=145,
)

# 4. Record cross-ecosystem interactions (Interlog / Engramory)
# Recording an Engramory memory retrieval:
recorder.record_memory_access(
    memory_id="mem-4421-pool-leak",
    layer="L2",
    action="read",
    query="worker connection timeout handling",
    similarity=0.91,
)

# 5. Record cross-agent handoff or Interlog event publishing
interlog_call_id = recorder.record_tool_call(
    tool="interlog_publish",
    tool_version="1.0",
    arguments={"event_type": "decision.recorded", "decision": "Implemented connection pool retry"},
    interlog_event_id="evt-interlog-99824",
)
recorder.record_tool_completion(
    call_id=interlog_call_id,
    tool="interlog_publish",
    status="ok",
    output={"status": "published", "seq": 14},
    latency_ms=32,
)

# 6. Close the trajectory upon task outcome
spool_file = recorder.close(
    status="completed",
    score=1.0,
)
print(f"Trajectory safely spooled to {spool_file}")
```

---

## 5. Ecosystem Triad Integration

### 5.1 Interlog Correlation (`aidoc-flow-interlog`)

- **Intra-Agent vs. Inter-Agent:** `Interlog` governs coordination, handoffs, supervisor reviews, and cross-project decisions (Phase-A outbox / Phase-B exchange). `UALF` records the intra-agent execution steps (the detailed chain of thought, model calls, bash executions, file diffs, tool retries).
- **Binding Convention:** When invoking Interlog, the UALF event envelope populates the registered extension `aidoc.io/interlog/v1`:

  ```json
  "extensions": {
    "aidoc.io/interlog/v1": {
      "interlog_event_id": "evt-interlog-99824"
    }
  }
  ```

  Reciprocally, the Interlog event payload carries `source.run_id`, `trace_id`, and `source_trace_sha256` linking back to the UALF trajectory for deep forensic replay.

### 5.2 Engramory Distillation Pipeline (`aidoc-flow-engramory`)

- **Execution Tracing:** When an agent queries or writes to Engramory, UALF emits `memory.accessed` and `retrieval.completed` events with the `aidoc.io/engramory/v1` extension:

  ```json
  "extensions": {
    "aidoc.io/engramory/v1": {
      "memory_id": "mem-4421-pool-leak",
      "layer": "L2",
      "action": "read",
      "similarity_score": 0.91
    }
  }
  ```

- **Episodic Distillation:** Closed UALF trajectories stored in MinIO (`ualf-archives/`) serve as the primary raw gold source for Engramory's memory distillation pipeline. The Global Operations Assistant or an offline distiller processes closed runs to synthesize:
  1. **L2 Episodic Lessons:** Task goal, failure modes, root causes, and successful resolution patterns.
  2. **L3 Semantic Graph:** Code entities modified, architectural dependencies, and project constraints.

---

## 6. Multi-Agent Hierarchy & Supervisory Amendments

UALF formalizes strict access boundaries across the multi-agent hierarchy:

```text
┌────────────────────────────────────────────────────────┐
│      Global Operations Assistant (Supervisory Role)    │
│  • Reads closed trajectories across all spoke projects │
│  • Evaluates runs & issues signed ualf-amendments/v1   │
│  • Triggers Engramory episodic memory distillation     │
│  • Holds Ed25519 dataset keys to seal commercial packs │
└───────────────────────────┬────────────────────────────┘
                            │ Delegates tasks (child_run_id)
                            ▼
┌────────────────────────────────────────────────────────┐
│     Project Executors (Headless Coding Agents)         │
│  • Isolated in project worktree (b-local-privy)        │
│  • Emits local UALF trace events to .ualf/spool/       │
│  • Stores local file diffs in .ualf/blobs/             │
│  • No cross-project read access; no commercial signing │
└────────────────────────────────────────────────────────┘
```

### 6.1 Supervisory Evaluation via `ualf-amendments/v1`

Sealed UALF traces are immutable. To attach supervisory grades, test verification results, or human review scores without altering the original trace bytes, the Global Operations Assistant issues a **signed amendment stream**:

1. Project Executor seals run `run-xyz` with hash `source_trace_sha256`.
2. Operations Assistant runs regression tests and code audits.
3. Operations Assistant emits an append-only `ualf-amendments/v1` stream binding to `source_trace_sha256`:

   ```json
   {
     "kind": "amendment",
     "seq": 2,
     "amendment_id": "amend-eval-001",
     "target": {
       "kind": "trace",
       "id": "traj-run-xyz",
       "sha256": "7f4a640390689408230b251ac5ca838b1b731face9f331dab140a482229dede8"
     },
     "evaluator": {"id": "operations-assistant", "version": "1.0"},
     "rubric": {"id": "regression-suite", "policy": "all tests pass"},
     "result": true,
     "severity": "blocking",
     "confidence": 1.0
   }
   ```

---

## 7. Privacy & Fail-Closed Sanitization

To ensure data integrity without breaking debuggability, agents operate under two distinct privacy boundaries:

1. **Perimeter 1: Runtime Credential Hygiene (Operational Spool):**
   - Environment variables: Strip authorization headers, API keys (`sk-*`, `ghp_*`), and private tokens before writing events.
   - Large outputs: Large stdout/stderr blocks and code patches are written to content-addressed blobs (`.ualf/blobs/sha256:...`) with local filesystem access controls.
   - Preserves exact code diffs and compiler outputs required for stubbed replay and debugging.
2. **Perimeter 2: Commercial Dataset Qualification (Refinery):**
   - Executed only during `ualf-dataset/v1.2` export.
   - Automated fail-closed scanning for customer PII, internal hostnames, and proprietary trading algorithms.

---

## 8. Offline Autonomy Invariant

**Spoke execution must never block or crash due to logging infrastructure.**

- If the OpenTelemetry Collector is unreachable, OTel SDKs drop spans in-memory without throwing exceptions to the agent loop.
- If remote object storage or ClickHouse is offline, the agent writes strictly to the local spool (`.ualf/spool/<run_id>.jsonl`).
- Spooled files are asynchronously harvested and projected by the observability pipeline once connectivity is restored.
