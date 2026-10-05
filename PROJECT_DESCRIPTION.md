# flow-trajectory-logging — Project Description

> **Status:** Active Core Platform & Commercialization Engine (2026-10). Position of Record.  
> **Core Architecture:** Dual Mandate: Universal Operational Trajectory Logging across all spoke projects (UALF v1.3) + Commercial Dataset Refinery & Compliance Packaging.

---

## 1. Charter & Mission

`flow-trajectory-logging` defines the **Universal Agent Log Format (UALF)** and serves a **Dual Mandate** across the multi-agent ecosystem:

1. **Universal Operational Execution Floor (Internal Across All Projects):**  
   Every autonomous agent across every project (`aidoc-flow-engramory`, `aidoc-flow-interlog`, `aidoc-observability-monitoring`, `aidoc-framework`, `aidoc-flow-support-desk`, `unified-test-suite`, and headless coding agents in isolated git worktrees like `b-local-privy`) produces step-by-step execution traces. UALF records these traces with gapless exact-byte SHA-256 hash chaining, content-addressed tool output grounding (`blobs/sha256:`), and local in-flight spooling (`.ualf/spool/`) for local debugging, regression testing, and supervisory auditing.

2. **Qualified Commercial Dataset Refinery & Compliance Vault (Downstream):**  
   Transforms high-value, closed, and verified agent trajectories into audit-grade, rights-cleared, replay-verified training assets for commercial AI data markets (Frontier Labs, enterprise fine-tuners) and non-repudiation audit archives under EU AI Act High-Risk AI mandates.

---

## 2. Ecosystem Triad & Architectural Pipeline

The multi-agent architecture operates as a tightly integrated triad:

- **Intra-Agent Execution (UALF / `flow-trajectory-logging`):** Records the microscopic steps of individual agents—prompts, reasoning steps, tool invocations, bash diffs, compiler errors, and local state transitions.
- **Inter-Agent Coordination (Interlog / `aidoc-flow-interlog`):** Records cross-agent collaboration, task handoffs, supervisor reviews, and cross-project decisions (Phase-A outbox / Phase-B exchange).
- **Episodic & Semantic Memory (Engramory / `aidoc-flow-engramory`):** Closed UALF trajectories serve as the raw gold source for Engramory's memory consolidation pipeline, distilling L2 episodic lessons and L3 knowledge graph entities.
- **Fleet Observability (`aidoc-observability-monitoring`):** Ingests live OTLP spans, populates ClickHouse `ualf_analytics` tables, and maintains immutable canonical JSONL files in MinIO `ualf-archives/`.

```text
                                  Spoke Autonomous Agents
                       (b-local-privy, engramory, interlog, framework)
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     │                                               │
                     ▼ (Hot Path: OTLP Spans)                        ▼ (Cold Path: Authoritative UALF)
         [ OpenTelemetry Collector ]                        Local In-Flight Spool
                     │                                      (.ualf/spool/<run_id>.jsonl)
                     ├──► Grafana Tempo (trace_id)                   │
                     ├──► Grafana Loki (logs/stdout)                 ▼
                     └──► Langfuse (live prompt view)      Closed Trajectory & Blobs
                                                                     │
                                     ┌───────────────────────────────┴───────────────────────────────┐
                                     │                                                               │
                                     ▼ (Fleet Storage & Analytics)                                   ▼ (Refinery & Commercial)
                     [ aidoc-observability-monitoring ]                             [ Dataset Refinery & Vault ]
                      • ClickHouse ualf_analytics (7 tables)                         • Secrets scrubbing & PII masking
                      • MinIO ualf-archives/ (immutable JSONL)                       • Replay verification (stubbed/tool)
                      • Engramory L2/L3 Distillation Worker                          • Ed25519 seal + DSSE envelope
                                                                                     • SFT, DPO, Croissant, Parquet
```

---

## 3. Multi-Agent Hierarchy & Governance Roles

UALF defines strict access boundaries across the fleet:

- **Project Executors (Headless Coding Agents in isolated worktrees):**
  - Execute within scoped project directories.
  - Emit unsealed in-flight events to the local spool (`.ualf/spool/`).
  - Write large tool inputs/outputs to local content-addressed blobs (`.ualf/blobs/`).
  - Maintain the **Autonomy Invariant**: logging never blocks or crashes the agent loop if external collectors are down.
  - Zero access to commercial dataset signing private keys; no cross-project read access.

- **Global Operations Assistant (Supervisory Auditor & Qualification Authority):**
  - Audits trajectories across all projects via ClickHouse `ualf_analytics` and MinIO.
  - Issues non-destructive evaluations and grades via signed append-only amendment streams (`ualf-amendments/v1`).
  - Holds Ed25519 dataset signing keys to seal qualified commercial packages (`ualf-dataset/v1.2`).
  - Triggers Engramory episodic memory distillation from high-value closed trajectories.

---

## 4. Commercial Product Lines (Downstream Refinery)

### Product A: Autonomous SWE & Bug-Fixing Trajectories (Tier 1 Flagship)

- **Source:** `operations-assistant` + `unified-test-suite`
- **Trajectory Shape:** Issue description $\rightarrow$ Worktree setup $\rightarrow$ Code search & editing $\rightarrow$ Compiler/Linter output $\rightarrow$ Test failure $\rightarrow$ Reasoning loop $\rightarrow$ Fix edit $\rightarrow$ Test pass $\rightarrow$ PR verification.
- **Target Buyers:** Frontier labs training coding & reasoning models (o1/o3, Claude Sonnet competitors, Devin alternatives).

### Product B: AI Systems Architect Trajectories (Differentiated Niche)

- **Source:** `aidoc-framework`
- **Trajectory Shape:** Product vision seed $\rightarrow$ Architecture decomposition $\rightarrow$ ADR generation $\rightarrow$ Technical SPEC $\rightarrow$ Implementation Plan (IPLAN) $\rightarrow$ Atomic Task definition.
- **Target Buyers:** Labs developing high-level architectural planning and reasoning capabilities.

### Product C: Autonomous IT Triage & Dispatch Trajectories

- **Source:** `aidoc-flow-support-desk`
- **Trajectory Shape:** Omnichannel ticket $\rightarrow$ Clarification dialogue $\rightarrow$ Sanitization & Quarantine $\rightarrow$ Repo dispatch.
- **Target Buyers:** Enterprise IT / Customer Operations automation vendors.

### Product D: Enterprise Compliance & Audit Vault

- **Format:** RFC 8785 sealed UALF v1.3 with DSSE envelope and exact-reconstruction Merkle trees.
- **Target Buyers:** Regulated enterprise clients needing tamper-proof, non-repudiation logs under EU AI Act High-Risk AI mandates or financial/defense compliance.

---

## 5. Repository Structure & Artifacts

| Component | Path / File | Purpose |
| :--- | :--- | :--- |
| **Spoke Onboarding** | `docs/SPOKE-INTEGRATION.md` | Practical developer & agent integration guide |
| **Python SDK** | `sdk/python/` (`ualf`) | Reusable `TrajectoryRecorder`, types, and project normalizers |
| **Normative Spec** | `UNIFIED-AGENT-LOG-FORMAT.md` | Core UALF v1.3 trace and dataset specification |
| **Dataset Requirements** | `AGENT-LOG-DATASET-REQUIREMENTS.md` | Commercial capture and qualification requirements |
| **Interoperability** | `INTEROPERABILITY-PROFILES.md` | Mappings to OTel GenAI, OpenInference, Croissant, OpenLineage |
| **Infrastructure Roadmap** | `INFRASTRUCTURE-AND-OPERATIONS-ROADMAP.md` | Storage, ingestion, and ClickHouse/S3 scaling strategy |
| **Extension Registry** | `extension-registry.json` | Registered schema extensions (`interlog`, `engramory`, `otel`) |
| **Schemas** | `*.schema.json` | Strict JSON schemas for trajectories, manifests, hygiene, rights |
| **Verifiers** | `verify.py`, `verify_profiles.py` | Standalone cryptographic and conformance verification |
| **Analytics Exporter** | `export_analytics.py` | Generates 7 relational/Parquet analytical tables |
