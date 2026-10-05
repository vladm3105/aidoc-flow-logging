# Agent Instructions & Governance Rules (`flow-trajectory-logging`)

Operational instructions, governance boundaries, and execution rules for autonomous agents operating within or integrating with `flow-trajectory-logging`.

**Precedence & Single Source of Truth:** This file (`AGENTS.md`) is the canonical source of truth for all autonomous agents and engineers working in this repository.

---

## 1. Scope & Mandate

`flow-trajectory-logging` defines the **Universal Agent Log Format (UALF)** and serves a **Dual Mandate**:

1. **Universal Operational Execution Floor (Internal Across All Projects):**  
   Every autonomous agent across every project (`aidoc-flow-engramory`, `aidoc-flow-interlog`, `aidoc-observability-monitoring`, `b-local-privy`, etc.) logs its step-by-step execution to UALF format. This includes prompts, tool calls, bash diffs, memory access, and outcomes for debugging, regression testing, and supervisory auditing.

2. **Qualified Commercial Dataset Refinery (Downstream):**  
   Transforms high-value closed trajectories into rights-cleared, replay-verified training assets (SFT JSONL, DPO preference pairs, Parquet) and regulated compliance vaults under EU AI Act mandates.

---

## 2. Multi-Agent Hierarchy & Roles

Agents interact with `flow-trajectory-logging` under strict role separation:

- **Project Executors (Headless Coding Agents in isolated worktrees):**
  - Execute assigned tasks within isolated project worktrees (e.g. `b-local-privy`).
  - Emit unsealed in-flight events to the local spool (`.ualf/spool/`) using `ualf.recorder.TrajectoryRecorder`.
  - Ensure canonical project slug conformance (`^proj-[a-z0-9-]{2,}$`).
  - Adhere to the **Autonomy Invariant**: logging must never block or crash execution if external collectors are unreachable.
  - No access to commercial dataset signing private keys; no cross-project read access.

- **Global Operations Assistant (Supervisory Auditor & Qualification Authority):**
  - Audits closed trajectories across all spoke projects via ClickHouse `ualf_analytics` and MinIO `ualf-archives/`.
  - Attaches non-destructive evaluations and test scores via signed append-only amendment streams (`ualf-amendments/v1`).
  - Triggers Engramory episodic memory distillation (L2 lessons and L3 knowledge graph) from verified runs.
  - Holds Ed25519 dataset signing keys to seal qualified commercial dataset packages (`ualf-dataset/v1.2`).

---

## 3. Environment & Tooling Commands

This repository standardizes on **uv** and **task**:

- **Setup Environment:** `task venv` (sets up `.venv` with `uv` and installs `requirements.txt`).
- **Verify Trajectory:** `task verify` (runs `verify.py` to validate schemas, exact-byte hash chains, blob references, and cryptographic Ed25519 seals).
- **Verify Dataset Manifest:** `task verify:dataset` (runs full dataset manifest validation).
- **Verify Profiles:** `task verify:profiles` (runs `verify_profiles.py` checking capture, retention, index, Merkle segments, DSSE envelopes, and OTel/Croissant projections).
- **Run Tests:** `task test` (runs python unittest suite in `tests/`).
- **Rebuild Profiles:** `task build:profiles` (deterministically regenerates profile examples).
- **Export Analytics:** `task export:analytics` (exports 7 relational analytical tables).
- **Full Verification Check:** `task check:all`

---

## 4. Strict Safety & Invariant Rules

1. **Project ID Regex Constraint:** Every `project` identifier must strictly match `^proj-[a-z0-9-]{2,}$`. Use `normalize_project_id()` to map spoke repository names (e.g. `aidoc-flow-interlog` $\rightarrow$ `proj-interlog`).
2. **Fail-Closed Privacy Boundary:** No trajectory containing unredacted API keys, credentials (`ghp_*`, `sk-*`, `Bearer *`), or private customer PII may ever be sealed or exported.
3. **Deterministic Replay Guarantee:** Tool invocations and model responses must be grounded in verified execution state (recorded in content-addressed `blobs/sha256:`). Synthetic hallucinations without execution grounding must never claim replay qualification.
4. **Proprietary IP Protection:** Never export trajectories from proprietary algorithm repos (e.g. `trading/` live trading logic). Commercial exports must strictly focus on generic software engineering, systems architecture, and IT operations workflows.
5. **Immutable Schemas:** Schemas defined in `*.schema.json` are version-pinned and canonical. Any schema extension must follow `EXTENSIONS-AND-EVOLUTION.md` and be registered in `extension-registry.json`.
