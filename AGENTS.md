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

<!-- agents-canon:begin -->
<!-- managed by aiops-harness (aidoc-flow-agents-config) — edits inside this block are overwritten on deploy -->
## Agent working agreement (aiops-harness / aidoc-flow-agents-config)

This repository follows canonical AI agent rules, skills, and governance deployed from **aiops-harness** (`$AIOPS_HARNESS_ROOT/.agents`, consolidating `aidoc-flow-agents-config`). `AGENTS.md` is the single authoritative agent instruction file (`CLAUDE.md` is deprecated and forbidden).

### Operating rules

- **Instruction discovery:** Read the applicable `AGENTS.md` and `.agents/rules/` before editing. More specific rules take precedence. Reusable workflows live in `.agents/skills/`.
- **Worktree state:** Inspect worktree state before editing (`git status`). Never silently stage or overwrite unrelated changes.
- **Split-Forge Topology & Git Governance Mandate (`dev` on Gitea -> `staging`/`main` on GitHub):** Across all repositories in the ecosystem, the **default upstream tracking branch MUST be `gitea/dev`** for all active development, local CI, and machine-speed integration (`BASE_BRANCH=dev`). Development commits on `dev` land via feature PRs shipped with `task review` + `task autoship` (or `task ship` for protected config files) and merge automatically on green via server-side `.gitea/workflows/auto-merge.yml` (shared ephemeral `runsc` runners), then synchronize to GitHub (`github/dev`) with exact SHA parity via `task mirror` (never force-pushed). Both **staging (`staging`) and production (`main`) live on GitHub** and promote one hop at a time (`dev -> staging -> main`, `PROMOTION_AUTONOMOUS="staging main"`) via `task autopromote -- <branch>`, merging automatically with `--merge` (never `--squash`, never deleting `dev`/`staging`) via `.github/workflows/auto-merge.yml` once required checks pass — zero manual merge confirmation required (`v*` tags release). Never commit directly to `dev`, `staging`, or `main`; never invoke raw `gh pr merge`; clean up task worktrees (`git worktree remove` before `git branch -D`) and prune remotes after merge.
- **Minimal edits:** Make the smallest defensible change. Read source before changing it. Verify assumptions against authoritative files.
- **Documentation-First & SDD-First (`Seed -> Module -> SDD -> Code`):** Start new projects and subsystems with Tier-1 Seed docs (`docs/seed/00_index.md`, `architecture/`, `adr/`, `agent-surface/`) before writing code. Follow the canonical 4-stage flow for every post-seed change: **Stage 0** Classify (`sdd-chg-flow`: `HOTFIX`/`CODE2S`/`CODE2C`/`SEED2C`/`DIR2C` [strictly `C1`]/`SDD2C`, or `GATE-SPEC` for `.aidoc/framework/`); **Stage 1** Upstream Design (`plans/PLAN-NNN_<slug>.md` via `verified-planning` + `check_plan.py`; optional for trivial `C1` tracked via issue + `C1 CHG` + scoped `IPLAN`; never replaces `CHG`+`IPLAN` in SDD repos); **Stage 2** Authorize via `docs/sdd/09_CHG/CHG-NN_*.yaml` (`chg_lint.py`, zero code steps; run Phase 0 SDD cascade for `SEED2C`/`SDD2C`); **Stage 3** Execute via `In Progress` `docs/sdd/08_IPLAN/IPLAN-NN_*.swf.yaml` + `docs/sdd/graph/SLICE-NN_*.graph.yaml` (`iplan verify` 3-way YAML parity across `CHG`/`IPLAN`/`SLICE`); **Stage 4** Code, update `docs/` atomically (`docs-lint` and `docs-drift` must pass), and close out. When an operator requests documentation generation (e.g. "Create a full set of documentation for the project as discussed"), follow the 4-step on-demand protocol: (1) **Context & Scope Intake:** Determine whether the request targets Plane-A SDD specifications (`01_BRD` through `09_CHG`), Plane-B operator/developer runbooks (`docs/*.md`), or both; (2) **Tool Selection:** Invoke `docs_scaffold` / `aiops-harness docs scaffold` for Plane-B scaffolding, `sdd_scaffold` for Plane-A SDD layers, `docs_validate` / `aiops-harness docs lint --strict` for AST and chunk linting, `docs_check_drift` for git drift audits, `docs_export_llms` for LLM representation, and `docs_build_portal` for Starlight+Scalar portal staging; (3) **Frontmatter & Chunk Invariant:** Enforce mandatory 9-key frontmatter (`DOC-FM-000`), <=450 words per H2/H3 section, no deictics, and explicit host:port addresses (`127.0.0.1:<port>` or `10.250.0.1:<port>`); (4) **Autonomous Execution & Verification:** Run `task check` and strict doc linting (`uv run aiops-harness docs lint --strict --json`) before reporting completion.
- **Verification:** Run the narrowest relevant check after every edit, then full gate (`task check` / `task ci`) before reporting completion. Never claim success without read-back or state verification.
- **Durable records:** Keep factual claims, test evidence, and architecture decisions in machine-verifiable files (plans, ADRs, test results).
- **Recommendations on open questions:** Whenever the agent has open questions or generates recommendations on open questions: (1) provide **3 distinct recommendations** per question with clear rationale and trade-offs; (2) critically review the generated recommendations and **score each from `1` to `5`** based on **best practices** (platform standards, security, SDD/EaC compliance, maintainability) and **practical use** (operational simplicity, execution feasibility, blast radius), where a higher score is better (`5` = best), highlighting the top-scored recommendation; (3) **use the recommendation with the highest score and continue without asking an operator**.
- **Plan convergence & CHG chains (`plan-gate: v2`):** Opt into `.agents/skills/verified-planning/check_plan.py --v2` (`<!-- plan-gate: v2 -->`) for hash-pinned 4-pillar `## Task convergence` locking (`LOCKED`/`FIX`/`STALE`/`PROBE`/`REDESIGN`), `<= 3`-pass split gating, and `CHG`-governed Pass-2 auto-chains (`CHG-L021`, `SWF-L010`, `iplan evaluate-split`).
- **Subagent delegation:** Delegate independent, bounded, read-heavy analysis to custom agents (`.agents/agents/`). Read back at least 3 specific changes after any write.
- **Three-Layer One-Way Plane Boundary (`L1 Stewards/Operator -> L2 Agents/IDE -> L3 Agent's Harness`):** Enforce strict downward-only dependencies across the three architectural planes: **Layer 1 (`aiops-synchora` / Human Operator, formerly `aiops-saas-stewards`)** owns fleet supervision, tenant lifecycle, declarative NATS JetStream pipeline subscriptions (`CANONICAL_STEWARD_PIPELINES`), and warranted workflow dispatch; **Layer 2 (`aiops-agent-support`, `aiops-agent-pm`, `aiops-agent-dev`, IDE/CLI Agents, `aiops-edge-runner`)** owns cognitive reasoning and domain execution (requiring a Layer-1 Steward `X-Agent-Warrant` in `stage`/`prod` via `SecurityGatePlugin.pre_task_execute`, with direct CLI/IDE `warrant-local` calls restricted to `dev`/`test`), consuming Layer 3 via MCP/skills (Mode A) or `HarnessKernel.from_consumer()` SDK + `consumer_hook` callbacks (Mode B); **Layer 3 (`aiops-harness`)** is the deterministic Execution, Tooling, SDK & 8-Canon Governance Harness ("The Agent's Harness", providing 10 built-in capability plugins) with zero upward imports of Layer 1 or Layer 2 packages.
- **Platform security & orchestration planes:** Deliver runtime secrets exclusively via OpenBao `/dev/shm` (`0600`) sinks (never plaintext `.env` on disk); enforce `platform-security` (`platform_security.authz` & `platform_security.identity` / Security Gate `:8095`/`:18095`/UDS with Ed25519 `X-Agent-Warrant` and namespace repo isolation), Paperclip v0.4.2 lease-epoch fencing (`X-Paperclip-Lease-Epoch`, `SpendTripwire`), and NATS JetStream (`EVENTS_PAPERCLIP`, `INBOX_AIOPS_PM`) + Temporal (`ExecutePaperclipTaskWorkflow`) across agent workflows.
- **External actions:** Use approval gates before deleting, overwriting, force-pushing, or publishing outside the workspace. Never self-approve.
<!-- agents-canon:end -->

## Per-repo governance — where state lives

| Surface | Path |
|---|---|
| Handoff | Not adopted — GitHub issues + `docs/sdd/08_IPLAN/*.swf.yaml` |
| TODO / backlog | Not adopted — GitHub issues |
| Decisions | docs/sdd/05_ADR/ |
| Design Plans (Upstream) | plans/ (`PLAN-NNN_<slug>.md` via `verified-planning`; optional for trivial C1, never replaces `09_CHG`/`08_IPLAN`) |
| Execution Plans (08_IPLAN) | docs/sdd/08_IPLAN/ (`IPLAN-NN_<slug>.swf.yaml`) |
| Change Requests (09_CHG) | docs/sdd/09_CHG/ (`CHG-NN_<slug>.yaml`) |
| Changelog | Not adopted — GitHub Releases + docs/sdd/09_CHG/archive/ |
| Roadmap | Not adopted — GitHub Milestones / Issues + `docs/sdd/08_IPLAN/` |
| SDD Graph | `docs/sdd/graph/` (`SLICE-NN_<slug>.graph.yaml`; validated via `task sdd:graph-check` and `iplan verify`) |

<!-- aidoc-local-flow-ci:begin -->
<!-- managed by aidoc-local-flow-ci 1.1.0 — edits inside this block are overwritten by .ci/bin/update -->
## CI protocol (aiops-harness / aidoc-hybrid-ci)

This repository uses the **aiops-harness** hybrid CI framework (`$AIOPS_HARNESS_ROOT/.ci`, consolidating `aidoc-hybrid-ci`). Commands, output format and
rules are identical in every repository and every language. Follow this protocol exactly.

### Commands

| Command | When |
|---|---|
| `task doctor` | First thing in a new repo or worktree. Fix every `FAIL` before coding. |
| `task --list` | Discover tasks. Service tasks are named `<service>:<task>`. |
| `task fmt` | Auto-fix formatting (code, whitespace, final newlines, Markdown). Run freely. |
| `task check` | Fast gate (format, lint, types, Markdown/YAML/shell/workflow lint). After every meaningful edit. |
| `task <service>:test -- <filter>` | Targeted tests while iterating. |
| `task ci` | Full gate. Must end with `RESULT: pass` before you report work as done. |
| `task review -- --issue <N>` | Self-review: Pass 1 (`task ci`) + Pass 2 (independent reviewer) on your committed change. |
| `task ship` | Human-approved. Request it only after `task ci` (and `task review`, if required) pass. |
| `task autoship` | Only where `.ci-config` lists the base branch in `SHIP_AUTONOMOUS_BRANCHES`: ship + auto-merge. |
| `task sync` | Update your branch with the base branch; resolves conflicts per the conflict protocol below. |
| `task -x pr-status -- --watch` | Poll the forge's view of your PR until it merges (github: re-arms `--auto` if protected; gitea: merges on green). Exit 10 = conflicts → `task sync`; exit 12 = `conflict:human` → stop. |
| `task cleanup -- <branch>` | After the PR is merged: remove worktree and branches (run from the main checkout). |
| `task autopromote -- <branch>` | Autonomous promotion PR (`staging`/`main`, `PROMOTION_AUTONOMOUS="staging main"`); server `.github/workflows/auto-merge.yml` merges on green. |

### Reading results

- `.ci-out/summary.json` — machine-readable result of the last `check`/`ci` run:
  `status`, `failed[]`, `warnings[]`, and `checks[]` with `status` (`pass`/`fail`/`timeout`/`warn`/`cached`/`skipped`) and `log`.
  `warn` = a report-only check failed: it does not block, but mention it in your report.
- `.ci-out/logs/<service>__<task>.log` — full output of one check.
- Read these files instead of re-running commands to see output. `cached` means inputs are unchanged since the last pass.
- Exit codes named in this protocol are raw codes: read them with `task -x <task>` (`--exit-code`); plain `task` reports 201 for any failure.

### Work loop

1. Edit → `task check` → fix.
2. Run targeted tests for the area you changed. Add or update tests for every behaviour change.
3. `task ci` → on failure: read `summary.json`, open the failing log, fix the **root cause**, re-run.
4. If the same check still fails after **3 genuine fix attempts**: stop. Report the failing check,
   the relevant log excerpt, your hypotheses and what you tried. Do not keep guessing.
5. Author audit & self-review: run `author-self-review` skill + `task check` before committing.
   When `.ci-config` has `REVIEW=required`: commit, then `task review -- --issue <N>` (or
   `--requirements <file>`). Pass 0 runs static heuristics before Pass 1/2. Reviewer is independent:
   never paste reasoning into requirements. `REVISE` → fix & review; `BLOCK` → stop & report.
   Otherwise, if `AUDIT_TRAIL=required`: pushed commits need `Multi-agent self-review per OPS-0065
   (<agents>): <verdict summary>`. Never write founder-override (`Self-review skipped per founder OK`)
   unless the human explicitly authorized it in this session. Read status: `task review -- --status`.
6. Done = `task ci` passes (and `task review` is PASS when required). Report "ready to ship" with
   changes, tests, and any `warnings`. Run `task autoship` (or operator-authorized `task ship`), then
   `task mirror` and `task autopromote -- <branch>` (`staging`/`main`), and `task cleanup -- <branch>`.

### Merge conflicts ("This branch has conflicts that must be resolved")

You resolve conflicts on your own feature branch without a human, within the limits of
the conflict protocol (canon `docs/CONFLICT_RESOLUTION.md`:
`https://github.com/vladm3105/aidoc-hybrid-ci/blob/main/docs/CONFLICT_RESOLUTION.md` —
this repo vendors only `.ci/`, not the canon docs). Merge-only: never rebase pushed
commits, never force-push.

1. Before `ship`/`autoship`, and whenever `task -x pr-status` exits 10: `task -x sync -- --check`, then `task -x sync`.
2. Exit 0 → merged (class A clean / class B lockfile or changelog handled automatically). Continue at step 5.
3. Exit 20 → class C files await you. `task sync -- --brief` shows what the base side changed and why.
   Edit each file so **both** intents survive, remove every marker, `git add` it, then
   `task sync -- --continue`. Never take a side wholesale (`checkout/restore --ours/--theirs`,
   `merge -X ours/theirs`, `-s ours`). If one side is genuinely superseded, keep the other and pass
   the reason: `task sync -- --continue -m "<why>"`.
4. Exit 30 → escalated (CI/governance config, migrations, delete/rename/binary/submodule, too
   many files or attempts). The merge was aborted; the PR is labelled `conflict:human`. Stop and report.
5. `task ci`, then `task review -- --issue <N>` again (the diff changed; the reviewer sees the
   conflict record), then `task ship`/`task autoship`. Ship refuses while the branch conflicts.

### Hard rules

- Always follow platform standards based on the approved technology stack (`technology-stack` canon; local checkout at `$TECHNOLOGY_STACK_ROOT`).
  Do not offer or use insecure, deprecated, or unapproved options (such as open public ports without
  NetBird mesh / Cloudflare tunnels, unauthenticated Docker socket mounts without `docker-socket-proxy`,
  un-sandboxed untrusted execution outside gVisor `runsc`, or in-memory mock databases instead of real PostgreSQL).
  All templates and tooling must be verified against that technology stack checkout. If a required tool or
  library is missing from the technology stack, you MUST explicitly halt, inform the operator, and request
  instructions on what tool or software to use before proceeding.
- Never bypass hooks or checks: no `--no-verify`, `git commit -n`, `LEFTHOOK=0`, `SKIP=`,
  `core.hooksPath` changes, `ALLOW_TEST_DELETION`, or changing `CI_BASE_BRANCH` / `GITLEAKS_LOG_OPTS`.
- Never edit `.ci/` (vendored framework, integrity-checked by `task doctor`).
- Never weaken checks: do not edit `Taskfile.yml`, `.ci-config`, `.ci-local/`, `lefthook.yml`, `mise.toml`,
  `.github/`, `AGENTS.md`, linter/type/coverage configs or thresholds unless the task explicitly asks for it.
- Use only tools from the approved technology stack (`$TECHNOLOGY_STACK_ROOT`,
  authoritative list: `09-authoritative-platform-technology-stack.md`). Never offer or use insecure
  options. If a needed tool is missing from the stack, stop and ask the operator what tool or
  software to use — never substitute an unapproved tool on your own. In autonomous sessions,
  always file a GitHub issue on the repo recording the missing tool and the blocked work.
- Suppressions (`noqa`, `type: ignore`, `nolint`, `#[allow]`, `biome-ignore`, `@ts-ignore`, `nosec`, …)
  only as a last resort and always with an inline `reason: <why>` on the same line. Prefer fixing the code.
- Never delete, skip or `.only` tests to get green. A skip needs an inline `reason:`.
- Change dependencies only through the package manager (`uv add`, `cargo add`, `go get`, `pnpm add`)
  and commit the updated lockfile.
- Never commit to the base branch. Never post merge statuses yourself (`signoff` via `gh signoff` or
  `gh api …/statuses`, `review`), `gh pr merge`, `gh pr review --approve`. Never touch `.git/aidoc-ci/`
  (review/sync state), and never run `task review -- --reset` or `task sync -- --reset` (human decisions).
  Carve-out: `task pr-status -- --watch` may re-arm auto-merge (github) or merge on
  observed green (gitea) once the required checks are green — you still never merge by hand.
- Never force-push (`--force`, `--force-with-lease`, `+refspec`) or rewrite pushed history.
- Never write real credentials anywhere in the repository.
- Name branches `feature/<topic>` or `fix/<topic>`: integration PRs are accepted only from `feature/*`,
  `fix/*`, `dependabot/*`, `renovate/*` and the `staging` back-merge (`chore/`, `docs/`, `ci/` are refused;
  `task ship` and `task review` check it before pushing).
- When working in parallel with other agents, use your own git worktree
  (`git worktree add ../<repo>-<task> -b feature/<task>`), then run `task setup` there.
<!-- aidoc-local-flow-ci:end -->
