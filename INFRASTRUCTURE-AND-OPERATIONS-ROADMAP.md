# UALF Infrastructure and Operations Roadmap

**Status:** Approved direction, implementation planned

**Date:** 2026-08-03

This roadmap defines how UALF should move from a portable log and dataset
standard to an operational logging platform that supports debugging, testing,
performance management, replay, lifecycle governance, and qualified commercial
dataset exports.

It distinguishes normative behavior from replaceable implementation choices.
UALF will specify durability, integrity, isolation, monitoring, and lifecycle
semantics. It will not require a particular cloud provider, database, queue, or
dashboard product.

## 1. Approved architectural direction

UALF will use a layered storage model rather than selecting one database or file
format for every purpose:

```text
AI projects and agents
  -> UALF SDK and local durable spool
  -> authenticated ingestion gateway
  -> immutable canonical object archive
  -> PostgreSQL-compatible operational catalog
  -> ClickHouse-compatible hot analytical projection
  -> Parquet analytical and dataset projections
  -> replay, evaluation, management, and qualified export services
```

The authoritative source is the closed, verified UALF artifact and its required
blobs, manifests, amendments, and lifecycle bindings. Database rows, indexes,
dashboards, search documents, and Parquet tables are derived and reproducible.

This follows patterns visible in established open-source systems:

- [Langfuse](https://github.com/langfuse/langfuse) separates PostgreSQL,
  ClickHouse, Redis, and object storage responsibilities.
- [Helicone](https://github.com/Helicone/helicone) uses an application database,
  ClickHouse, and MinIO for distinct workloads.
- [OpenLIT](https://github.com/openlit/openlit) uses OpenTelemetry collection and
  ClickHouse analytics.
- [Phoenix](https://github.com/Arize-ai/phoenix) supports a simple local SQL
  deployment and a PostgreSQL production path.
- [Grafana Tempo](https://github.com/grafana/tempo) demonstrates an
  object-storage-first trace backend.
- [Grafana Loki](https://github.com/grafana/loki) demonstrates local write-ahead
  state, object-backed chunks, indexes, retention, and operational canaries.

These products are evidence for the architecture, not normative dependencies.

## 2. Storage responsibilities

<!-- markdownlint-disable MD013 -->

| Responsibility | Reference technology | Authority |
| --- | --- | --- |
| Closed traces and exact-reconstruction segments | S3-compatible object store | Authoritative |
| Content-addressed blobs | S3-compatible object store | Authoritative |
| Signed manifests, amendments, and lifecycle records | Object store plus catalog index | Authoritative object |
| Projects, access, policies, jobs, and run state | PostgreSQL-compatible SQL | Operational |
| Recent events, calls, costs, and quality metrics | ClickHouse-compatible OLAP | Derived |
| Long-term analytical tables and buyer exports | Parquet in object storage | Derived |
| Local and ad hoc analysis | DuckDB-compatible engine over Parquet | Derived |
| Delivery buffering | Local spool, outbox, or durable broker | Transport only |
| Full-text search | Optional search projection | Derived |
| Cache | Optional Redis-compatible cache | Disposable |

<!-- markdownlint-enable MD013 -->

General-purpose NoSQL storage is not planned for the initial reference
architecture. Transactional governance fits SQL, high-volume analysis fits a
columnar database, and canonical evidence fits immutable objects.

## 3. Archive and object layout

The reference layout will partition by security boundary before project or
date:

```text
ualf/<environment>/<organization>/<project>/<date>/<run-id>/
  source-manifest.json
  segment-*.jsonl.zst
  capture-report.json
  retention.json
  amendments/
  projections/
```

Content-addressed blobs will be namespaced by an encryption, rights, retention,
and residency boundary. Cross-organization global deduplication will not be a
default because it complicates isolation, erasure, existence privacy, and key
management.

Stored compressed objects must bind both representations:

- stored-object digest and byte count;
- content encoding and media type;
- decoded UALF digest and byte count;
- reconstruction order and sequence range;
- encryption and key identity;
- retention and residency binding.

The current `ualf-segments/v1` profile proves byte ranges and reconstruction but
does not bind independently stored segment objects or their compression. A new
storage profile will close that gap without changing the meaning of existing
segment manifests.

## 4. Unified storage and project isolation

The default deployment will be one shared platform with logical isolation:

```text
organization -> project -> environment -> run and trace
```

Every ingest request, catalog row, object key, analytical row, policy decision,
and management action must be scoped to an organization or storage namespace
and the existing UALF project identifier.

Dedicated infrastructure is reserved for projects that require contractual
isolation, separate residency, incompatible retention, dedicated encryption
keys, or materially different scale. Development, staging, and production must
at least use separate storage and credentials.

Deduplication is permitted only within a declared privacy and lifecycle
boundary. Authorization checks must not infer permission from knowledge of a
content digest.

## 5. Cloud, on-premises, and hybrid profiles

UALF will define portable deployment profiles:

### Local developer

- local files or an S3-compatible emulator;
- SQLite or PostgreSQL catalog;
- DuckDB over JSONL or Parquet;
- single-process collector and verifier;
- short synthetic retention.

### Team deployment

- S3-compatible object storage;
- PostgreSQL catalog;
- optional ClickHouse analytics;
- durable local spool and processing outbox;
- shared dashboards and access controls.

### Production deployment

- managed or replicated object storage;
- highly available PostgreSQL and ClickHouse equivalents;
- durable processing queue when justified by fan-out or backlog;
- KMS-backed envelope encryption;
- independent monitoring and external paging;
- tested backup, restore, retention, and erasure operations.

### Regulated or hybrid deployment

- client-side redaction before an unauthorized persistence or network boundary;
- local or on-premises canonical archive for restricted content;
- privacy-minimized cloud projections where permitted;
- region and residency enforcement;
- dedicated encryption and signed management audit.

The initial reference deployment will target one environment or cloud. A
multi-cloud active-active design is deferred until a demonstrated requirement.

## 6. Ingestion and processing semantics

The SDK must not dual-write independently to the archive and analytical
database. The approved sequence is:

1. Apply capture, redaction, and size policy at the producer boundary.
2. Write accepted records to a durable local spool when direct durable delivery
   is unavailable.
3. Authenticate and authorize organization, project, and environment.
4. Validate the envelope and idempotency identity.
5. Commit an immutable segment or durable queue record.
6. Return a durability-qualified receipt.
7. Close, materialize, and verify the trace asynchronously.
8. Build catalog, analytical, interoperability, and dataset projections.

The default idempotency scope is:

```text
organization + project + run_id + event_id
```

Byte-identical retries may be accepted. Conflicting content under the same
identity must be quarantined and surfaced as an integrity incident.

The catalog state model will include at least:

```text
received -> durably_committed -> closed -> verified -> projected
         -> replay_qualified -> dataset_qualified
         -> expired or erased
```

`quarantined` is an exceptional state reachable from any validation or
integrity boundary.

## 7. Management and observability plane

Platform monitoring must remain useful when UALF ingestion, storage, or
analytics is failing. Management telemetry therefore uses OpenTelemetry and an
independent metrics, logs, traces, alerting, and dashboard backend. It is not
stored exclusively through the canonical UALF pipeline.

High-value management actions use a separate signed audit stream. CPU metrics
and scrape results do not become recursive agent trajectories.

The management plane will provide five views:

1. platform operations;
2. project and agent performance;
3. capture quality and data integrity;
4. privacy, retention, access, and security;
5. dataset readiness and commercial inventory.

### 7.1 Pipeline-hop monitoring

Each durable hop must expose positive, negative, stalled, and missing-signal
states. The minimum monitored sequence is:

```text
SDK accepted
  -> SDK spooled
  -> gateway received
  -> gateway durably committed
  -> object stored
  -> trace closed
  -> trace verified
  -> analytics projected
  -> replay verified
```

For each applicable hop, expose:

- accepted, completed, failed, dropped, retried, and conflicted counts;
- queue or spool depth and capacity;
- oldest pending item age;
- last successful completion time;
- processing and end-to-end latency;
- absence of the expected self-telemetry series.

Process liveness alone is insufficient. A running exporter that is not
attempting delivery and a healthy receiver receiving nothing are independent
failure states.

### 7.2 Far-end synthetic canary

Every production environment will emit a harmless signed canary trace on a
defined cadence. The canary must be observed at the far end of the real path:

```text
producer -> spool -> gateway -> archive -> catalog -> analytics -> replay
```

It will use an exact producer identity, deterministic content, a short retention
class, and an expected replay result. A test stub or unrelated trace must not be
able to satisfy the presence check.

The canary lookback must exceed the production cadence and remain below every
applicable query and retention ceiling.

### 7.3 Watch the watcher

The reference alerts will detect:

- monitoring target absent as well as explicitly down;
- rule group missing or empty;
- rule evaluations stalled or repeatedly failing;
- configuration reload failure;
- notifier absent, failing, queueing, or dropping messages;
- required self-telemetry renamed or absent;
- dashboard datasource unavailable;
- external dead-man receiver not receiving a heartbeat.

Silence in a broken monitoring system must not be interpreted as health.

### 7.4 Alert record and paging

UALF will distinguish:

1. a durable internal alert record; and
2. an external paging destination outside the monitored failure domain.

Routing an alert back through only the path it monitors is useful for recovery
evidence but is not a complete paging design.

### 7.5 Cardinality rules

Metrics may use bounded dimensions such as organization, project, environment,
region, component, operation, status, failure class, and retention class.

`run_id`, `trace_id`, `event_id`, blob digests, prompts, user identities, and
arbitrary error text must not be metric labels. They remain available through
logs, traces, ClickHouse projections, and exemplar or drill-down links.

### 7.6 Initial SLO semantics

UALF will standardize the definition of SLOs but allow deployment profiles to
select targets. The production reference will initially demonstrate:

| SLO | Reference target |
| --- | --- |
| Ingestion API availability | 99.9 percent |
| Accepted event durably committed | p99 under 5 seconds |
| Unreported dropped records | Zero |
| Closed trace verified | 99 percent within 5 minutes |
| Hot analytical projection lag | p95 under 60 seconds |
| Integrity or signature failure | Zero tolerated |
| Synthetic end-to-end success | 99.9 percent |
| Retention and erasure completion | 100 percent within policy SLA |
| Backup recovery point | Defined per deployment profile |
| Restore verification | At least quarterly for production |

Reference alerting will use ratio-based conditions, minimum-traffic guards,
explicit absent-series arms, and multi-window error-budget burn alerts. A
cumulative counter greater than zero must not be used as a current-state alert.

## 8. Reusable findings from `llm-router`

The review of
[`vladm3105/llm-router`](https://github.com/vladm3105/llm-router/tree/main/monitoring)
approved these patterns for UALF:

- monitor each hop, not only component processes;
- combine failed-send counters with positive sent and received signals;
- alert when expected telemetry is absent;
- evaluate sparse heartbeats at the far end where the record lands;
- bind a heartbeat to the real producer so test artifacts cannot satisfy it;
- monitor rule evaluation and notification delivery;
- persist shipping positions and processing checkpoints;
- keep request-controlled values out of stream and metric labels;
- store monitoring configuration and dashboards in version control;
- test relationships across configs, mounts, rules, emitters, and receivers;
- verify configuration by observed effect, not only syntax or config readback;
- distinguish durable alert history from an actual pager.

The following router-specific choices are not adopted as UALF defaults:

- Promtail, which is already scheduled for migration to Grafana Alloy;
- unauthenticated, single-tenant Loki;
- filesystem-only, single-replica storage;
- Jaeger or rotated OTLP files as the canonical UALF archive;
- traffic-dependent absolute error-rate alerts;
- readiness inferred from a cumulative request counter;
- cumulative budget-overrun counters used as current-state alerts;
- recording rules presented as complete SLO alerting without paging rules.

The UALF reference stack may use OpenTelemetry Collector, Prometheus, Grafana,
Alertmanager, Alloy, Loki, and Tempo, but conformance depends on behavior rather
than those products.

## 9. Replay and dataset management

Replay will resolve and verify the canonical archive rather than relying on an
analytical database. It will restore initial state into an isolated sandbox,
default to recorded model and tool responses, and require explicit policy for
external tool re-execution.

Commercial data delivery will use a separate qualification pipeline:

```text
operational archive
  -> eligibility and rights filtering
  -> privacy transformation
  -> quality and replay qualification
  -> deterministic dataset snapshot
  -> signed package and datasheet
  -> buyer-specific encrypted delivery
```

Buyers will not receive access to the live operational archive. Every export has
independent membership, rights, retention, lineage, quality, and integrity
evidence.

## 10. Planned standards and schemas

The roadmap adds these deliverables without changing existing artifact meaning:

<!-- markdownlint-disable MD013 -->

| Deliverable | Purpose |
| --- | --- |
| `INFRASTRUCTURE-REFERENCE-ARCHITECTURE.md` | Normative boundaries and reference deployments |
| `OPERATIONS-AND-MANAGEMENT.md` | Metrics, SLOs, alerts, dashboards, canary, backup, and incident behavior |
| `ualf-storage-manifest.schema.json` | Stored objects, compression, decoded digest, encryption, replication, and reconstruction |
| `ualf-ingest-receipt.schema.json` | Received versus durably committed acknowledgements |
| `ualf-management-audit.schema.json` | Signed access, policy, export, legal-hold, retention, erasure, and key events |
| Operational semantic conventions | Stable `ualf.*` OpenTelemetry metrics and attributes |
| Reference dashboards and alert rules | Executable management-plane examples |
| Infrastructure conformance vectors | Crash, retry, conflict, absence, reconstruction, retention, and restore tests |

<!-- markdownlint-enable MD013 -->

Storage locations will use contained relative object keys in portable manifests.
Provider-specific URIs, credentials, and ephemeral object-store metadata will
remain deployment state rather than portable evidence.

## 11. Implementation phases

### Phase 1: normative infrastructure and operations profiles

Deliver:

- infrastructure reference architecture;
- operations and management profile;
- storage manifest, ingest receipt, and management audit schemas;
- positive and negative fixtures;
- verifier extensions;
- operational metric semantic conventions;
- reference dashboards, alerts, canary, and runbooks;
- configuration-contract and exact-reconstruction tests.

Exit criteria:

- compressed segments reconstruct exact authoritative bytes;
- conflicting idempotency content is rejected;
- every archive object is digest, encryption, and retention bound;
- a synthetic trace verifies the full reference path;
- breaking the evaluator or notifier produces an independent alert;
- deletion propagation across every declared projection is testable.

### Phase 2: minimal reference implementation

Deliver:

- SDK durable spool hooks;
- authenticated ingestion gateway;
- S3-compatible canonical archive;
- PostgreSQL catalog and processing outbox;
- DuckDB and Parquet analytical projection;
- verified stubbed replay;
- local and team deployment profiles.

Exit criteria:

- acknowledged records survive process and host restart within the declared
  durability level;
- database projections rebuild from the canonical archive;
- backup restore produces the same verified trace digest;
- dashboard and alert examples operate without high-cardinality labels.

### Phase 3: multi-project production

Deliver:

- organization and project authorization;
- ClickHouse-compatible hot analytical projection;
- durable broker only when required by measured backlog or consumer fan-out;
- KMS-backed per-boundary envelope encryption;
- lifecycle, legal-hold, and erasure controller;
- external paging and dead-man receiver;
- highly available deployment guidance;
- disaster-recovery drills and evidence.

Exit criteria:

- project isolation is penetration and conformance tested;
- loss, backlog, integrity, privacy, and erasure incidents page correctly;
- retention never leaves an undeclared dangling qualified-dataset dependency;
- recovery-point and recovery-time objectives are measured rather than assumed.

### Phase 4: qualified dataset product

Deliver:

- eligibility and rights rules;
- privacy and de-identification transformations;
- reproducible dataset snapshots;
- buyer-specific formats and encryption;
- quality, coverage, deduplication, lineage, and replay reports;
- delivery receipt and revocation workflow.

Exit criteria:

- every exported member resolves to qualified evidence;
- operationally ineligible or erased data cannot enter a new snapshot;
- buyers can verify package identity and integrity without live-system access;
- export and access actions appear in the signed management audit trail.

## 12. Scale triggers and deferred complexity

A durable broker, lakehouse transaction layer, distributed search cluster, or
dedicated per-project deployment will be added only when measurements justify
it.

Useful triggers include:

- sustained queue age or inability to meet the durable-commit SLO;
- more than two independent consumers requiring replayable delivery;
- analytical query or ingest contention exceeding the hot-store SLO;
- concurrent data-lake writers requiring snapshot isolation;
- contractual, residency, or encryption requirements requiring physical
  separation;
- object counts or file sizes making compaction operationally necessary.

This avoids making the first reference implementation as operationally complex
as a mature multi-tenant observability product while preserving a compatible
path to that scale.

## 13. Immediate next action

Implement Phase 1 as a sequence of reviewable changes:

1. infrastructure architecture and storage manifest;
2. ingest receipts and idempotency conformance;
3. operations profile and OpenTelemetry semantic conventions;
4. canary, watchdog, dashboards, alerts, and management audit;
5. lifecycle propagation, backup, restore, and disaster-recovery tests.

Each change must include fixtures and executable validation before its roadmap
status moves from planned to implemented.
