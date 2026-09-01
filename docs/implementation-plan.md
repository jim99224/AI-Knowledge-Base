# AI Knowledge Base Implementation Plan

This document is the detailed implementation plan for the architecture and M0-M5 milestones defined in the project README.

## 1. Product Goal

Build a Python-first team engineering knowledge platform that makes repository knowledge, prior engineering experience, and live operational context available to AI while keeping those context types logically separate.

The three context layers are:

- **Knowledge** — durable engineering facts and source content extracted from repositories and verified sources.
- **Memory** — decisions and prior engineering experience that should persist across AI sessions.
- **Runtime** — live operational state such as Kubernetes workloads, Pods, status, and logs.

The implementation order is intentionally incremental. The project must first prove the core path:

```text
GitHub
  -> PostgreSQL
  -> pgvector
  -> Retrieval
  -> General LLM
  -> Grounded Engineering Answer
```

Only after this path is useful and measurable should the platform add graph traversal, Kubernetes runtime context, long-term memory, and agent orchestration.

## 2. Architecture Principles

1. PostgreSQL is the durable source of truth for repository content, chunks, metadata, indexing state, and later simple memory records.
2. pgvector is a semantic retrieval projection and must be rebuildable from canonical content.
3. Apache AGE is a graph projection and must be rebuildable from canonical content and retain evidence for every graph fact.
4. Knowledge, Memory, and Runtime have different lifecycles and must remain logically separate.
5. Runtime state is fetched live where practical rather than persisted as durable engineering knowledge.
6. Application services depend on ports/protocols rather than PostgreSQL, AGE, Kubernetes, GitHub, or model SDKs directly.
7. Deterministic parsers are preferred over LLM extraction for structured formats.
8. Every grounded answer must preserve evidence such as repository, path, commit SHA, and heading/chunk identity.
9. Indexing must be idempotent and support both incremental updates and full rebuilds.
10. Graph extraction, Memory frameworks, and LangGraph are not prerequisites for the first usable RAG product.

## 3. Target Architecture

```text
                         User / AI Client
                                |
                                v
                         Context Builder
                                |
                 +--------------+--------------+
                 |              |              |
                 v              v              v
            Knowledge        Memory         Runtime
            Retriever        Retriever      Retriever
                 |              |              |
        +--------+--------+     |              v
        |        |        |     |        Kubernetes API
        v        v        v     |
   PostgreSQL pgvector Apache   |
                      AGE       |
        |        |        |     |
        +--------+--------+-----+
                 |
                 v
            General LLM
```

The initial M0-M2 implementation uses the Knowledge path only. AGE becomes product-critical in M3, Kubernetes in M4, and Memory/LangGraph in M5.

## 4. Technology Strategy

| Area | Initial choice | Introduced |
| --- | --- | --- |
| Language | Python 3.12+ | M0 |
| HTTP API | FastAPI | M0 |
| Validation/config | Pydantic / pydantic-settings / PyYAML | M0 |
| Canonical database | PostgreSQL | M0 |
| Vector search | pgvector | M0-M2 |
| Graph | Apache AGE | bootstrap M0, product use M3 |
| Embedding | Existing embedding model behind `EmbeddingProvider` | M0-M1 |
| Generation | Existing general LLM behind `LLMProvider` | M0-M2 |
| Runtime integration | Kubernetes Python client | M4 |
| Agent orchestration | LangGraph | M5 |
| Memory | PostgreSQL behind `MemoryStore` | M5 |
| Metrics | Prometheus | progressively |
| MCP | Python MCP SDK / FastMCP | M5 |

## 5. Configuration Contract

All non-sensitive service configuration belongs in the central YAML configuration. Sensitive values belong only in `.env` or process environment variables.

### `config/app.yml`

```yaml
app:
  name: ai-knowledge-base

database:
  driver: postgresql+asyncpg
  host: localhost
  port: 5432
  name: ai_knowledge_base
  echo: false
  pool_size: 10
  max_overflow: 20
  pool_pre_ping: true

pgvector:
  enabled: true

age:
  enabled: true
  graph_name: ai_knowledge_graph

embedding:
  model_id: text-embedding-model
  dimension: 1024
  index_version: embedding-v1

llm:
  model_id: general-llm

kubernetes:
  runtime_enabled: false
```

### `.env`

```env
POSTGRES_USER=ai_kb_user
POSTGRES_PASSWORD=change-me
# GITHUB_TOKEN=
# EMBEDDING_API_KEY=
# GENERAL_LLM_API_KEY=
```

A full `DATABASE_URL` containing credentials is intentionally not stored. The application builds the DSN at startup from YAML configuration plus secrets. Future integrations must use this same central settings mechanism rather than introducing service-specific configuration loaders.

M0 must also resolve two schema/config invariants: `embedding.dimension` must match the deployed pgvector schema/index dimension, and `age.graph_name` must match the AGE graph created by bootstrap/migrations.

## 6. Core Domain and Ports

Existing domain models:

- `Repository`
- `Document`
- `Chunk`
- `IndexJob`

Existing storage boundaries:

- `DocumentStore`
- `VectorStore`
- `GraphStore`
- `MemoryStore`

M0 must add explicit provider boundaries before ingestion begins:

```python
from typing import Protocol, Sequence

class EmbeddingProvider(Protocol):
    async def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...

class LLMProvider(Protocol):
    async def generate(self, prompt: str) -> str: ...
```

Additional boundaries are introduced only when required: `SourceRepository` in M1, `Reranker` in M2, and `RuntimeProvider` in M4. The LLM and future agent must never directly use database or Kubernetes clients.

## 7. PostgreSQL Data Model

The initial canonical tables are `repositories`, `documents`, `chunks`, and `index_jobs`.

`repositories` stores repository identity, enabled state, default branch, and last successfully indexed commit.

`documents` stores canonical extracted content with repository ID, path, type, branch, commit SHA, content hash, raw text, metadata, indexing state, and deletion timestamp.

`chunks` stores retrieval units with document/repository IDs, chunk index, heading path, content, token count, content hash, commit SHA, embedding, embedding model/index version, metadata, and timestamps.

`index_jobs` records repository, target commit, status, processing counters, errors, and execution timestamps.

A `memories` table is introduced in M5 with scope, memory type, content, metadata, validity period, and timestamps. Initial long-term memory should focus on decision and episodic memory rather than creating an uncontrolled duplicate of canonical Knowledge.

## 8. Indexing Consistency Model

Canonical PostgreSQL rows are authoritative. Embeddings and graph facts are derived state.

M1 indexing state can remain simple:

```text
pending
  -> parsing
  -> persisted
  -> embedding
  -> indexed

any stage -> failed -> retry
```

M3 graph extraction is a separate downstream projection and must not block successful M1 indexing.

Required rules:

- use `content_hash` to avoid unnecessary parsing and embedding;
- preserve commit SHA on documents/chunks;
- use stable chunk identity where possible;
- record embedding model and index version;
- invalidate deleted documents/chunks during incremental indexing;
- update `last_indexed_commit` only after successful indexing;
- support operator-triggered and later periodic full rebuilds;
- keep vector and graph projections reconstructable from canonical content.

## 9. M0 — Foundation

### Objective

Make the current foundation truly runnable and verifiable against an externally supplied PostgreSQL environment.

### Already implemented

- Python project/package structure;
- central YAML + secret environment configuration;
- async SQLAlchemy lifecycle;
- Repository/Document/Chunk/IndexJob models;
- initial PostgreSQL bootstrap/schema SQL;
- pgvector embedding column and HNSW index;
- AGE extension/graph bootstrap SQL;
- DocumentStore/VectorStore/GraphStore/MemoryStore boundaries;
- PostgreSQL DocumentStore adapter;
- pgvector VectorStore adapter;
- initial unit-test scaffolding.

### Remaining tasks

- [ ] Define `EmbeddingProvider` and `LLMProvider` ports.
- [ ] Make config path resolution robust and protect secret values from accidental logging.
- [ ] Establish the migration strategy.
- [ ] Reconcile configured embedding dimension with pgvector schema/index dimension.
- [ ] Reconcile configured AGE graph name with bootstrap/migrations.
- [ ] Validate PostgreSQL, `vector`, `age`, and configured graph during readiness.
- [ ] Add FastAPI `/health/live` and `/health/ready`.
- [ ] Add PostgreSQL integration test.
- [ ] Add pgvector insert/search integration test and vector dimension validation.
- [ ] Add AGE bootstrap/query integration test.
- [ ] Expand DocumentStore write/update boundaries required by ingestion.
- [ ] Define indexing transaction semantics.

### Acceptance

Given valid external database configuration and credentials, the application starts, reports liveness, verifies PostgreSQL/pgvector/AGE readiness, verifies the configured AGE graph, and completes a real vector insert/search integration test. Configuration/schema mismatches must fail clearly.

## 10. M1 — Knowledge Ingestion MVP

### Objective

Build the first end-to-end repository ingestion path. Limit initial parsing to Markdown and text so ingestion and incremental semantics are proven before language-specific AST and infrastructure extraction.

### Flow

```text
GitHub Repository
  -> Repository Registration
  -> Git Fetch / Sync
  -> File Scanner
  -> Markdown / Text Parser
  -> Chunker
  -> PostgreSQL
  -> EmbeddingProvider
  -> pgvector
```

### Initial API

```text
POST /v1/repositories
GET  /v1/repositories
POST /v1/repositories/{repository_id}/index
GET  /v1/index-jobs/{job_id}
```

Webhook support is added after manual indexing is reliable.

### Full indexing

1. Resolve branch and target commit.
2. Enumerate eligible Markdown/text files.
3. Parse and create/update canonical Document rows.
4. Chunk parsed text and persist canonical Chunk rows.
5. Embed changed/new chunks in batches.
6. Persist vectors and embedding version.
7. Mark IndexJob successful.
8. Advance `last_indexed_commit`.

### Incremental indexing

```text
commit A indexed
       |
       v
compare A..B
       |
       +-> added
       +-> modified
       +-> deleted
       |
       v
parse/re-chunk changed files only
       |
       v
content_hash comparison
       |
       +-> unchanged: skip embedding
       +-> changed: embed/update
       +-> removed: invalidate/delete
```

A failed job must not advance `last_indexed_commit`.

### Chunking v1

Use Markdown headings as semantic boundaries where possible, retain `heading_path`, split oversized sections by paragraph/token limit, and store path/commit metadata on every chunk. Cross-chunk questions are handled later by retrieving multiple relevant/neighboring chunks and combining them in the Context Builder.

### Tasks

- [ ] Implement repository registration and GitHub/git source adapter.
- [ ] Implement manual full indexing and commit comparison.
- [ ] Implement eligible-file scanner.
- [ ] Implement Markdown and plain-text parsers.
- [ ] Implement chunker and metadata builder.
- [ ] Implement Document/Chunk write/upsert operations.
- [ ] Implement batch embedding and embedding version persistence.
- [ ] Implement content-hash skip logic.
- [ ] Implement deleted-file/chunk invalidation.
- [ ] Implement IndexJob status/counters/errors and retry semantics.
- [ ] Implement full rebuild operation.
- [ ] Add full/incremental indexing tests.

### Acceptance

The initial test repositories can be registered and indexed end-to-end. Full and incremental scans work, deleted content disappears from retrieval state, and unchanged chunks are not embedded again.

## 11. M2 — Search and RAG MVP

### Objective

Turn indexed repository content into measurable, grounded engineering answers.

### Flow

```text
Question
  -> Query Embedding
  -> pgvector Top-K
  -> Repository / Metadata Filter
  -> Reranker
  -> Canonical Chunk Fetch
  -> Context Builder
  -> General LLM
  -> Answer + Evidence
```

AGE is not required in the M2 critical path.

### API

```text
POST /v1/search
POST /v1/answer
GET  /v1/documents/{document_id}
```

Evidence should include repository identity, path, commit SHA, heading path, and chunk identity.

The answer service must use retrieved/authorized evidence as factual context, preserve source references, avoid unsupported repository claims, and communicate when evidence is insufficient.

Define a `Reranker` boundary even if the first implementation is simple.

### Evaluation

Create roughly 30-50 manually curated engineering questions from the initial repositories. Each question defines expected evidence, not only expected prose.

Track Recall@5, Recall@10, MRR, irrelevant chunk rate, citation correctness, faithfulness, unsupported-claim rate, and latency.

### Tasks

- [ ] Implement query embedding and repository/metadata filters.
- [ ] Add authorization-filter boundary.
- [ ] Implement Reranker port and initial adapter.
- [ ] Fetch canonical chunks after vector retrieval.
- [ ] Implement Context Builder.
- [ ] Implement grounded answer service.
- [ ] Return repo/path/commit evidence.
- [ ] Implement insufficient-evidence behavior.
- [ ] Build evaluation dataset and benchmark harness.
- [ ] Establish retrieval and answer-quality baseline.

### Acceptance

Known engineering questions retrieve expected evidence and generated answers contain traceable repository references. A reproducible retrieval baseline exists.

M2 is the first complete product MVP: **GitHub -> Knowledge -> AI Answer**.

## 12. M3 — Engineering Knowledge Graph

### Objective

Add relationship-aware engineering knowledge after M2 proves the core retrieval product.

Graph extraction remains downstream from canonical ingestion:

```text
PostgreSQL Canonical Knowledge
        -> Graph Extraction
        -> Normalize / Validate / Deduplicate
        -> Apache AGE
```

### Initial model

Entities: Repository, Service, API, Database, Deployment, Technology.

Relationships: `CONTAINS`, `DEPENDS_ON`, `CALLS`, `USES`, `EXPOSES`, `DEPLOYED_BY`.

Start with deterministic extractors for `pom.xml`, `requirements.txt`, `package.json`, Dockerfile, Kubernetes YAML, Helm, and OpenAPI. Use the general LLM only for semantic relationships that deterministic parsers cannot reliably infer.

Every graph fact retains repository ID, path, commit SHA, extractor/version, and confidence for LLM-derived facts.

Graph expansion is query-dependent. Simple semantic questions should not pay graph traversal cost by default.

### Tasks

- [ ] Finalize minimal graph schema from real evaluation questions.
- [ ] Implement AGE adapter.
- [ ] Implement deterministic extractors.
- [ ] Implement entity normalization/canonicalization.
- [ ] Implement evidence-backed upsert and source-change invalidation.
- [ ] Add optional LLM semantic extraction.
- [ ] Implement entity resolution and bounded traversal.
- [ ] Integrate graph expansion into Context Builder.
- [ ] Add multi-hop evaluation questions.

### Acceptance

Relationship-heavy questions about dependencies, databases, APIs, and deployments can use bounded multi-hop traversal, and every graph fact is traceable to repository evidence.

## 13. M4 — Runtime Context

### Objective

Connect durable repository knowledge to current Kubernetes state without turning ephemeral runtime objects into long-term knowledge.

Persist stable mapping only:

```text
repository
  -> cluster
  -> namespace
  -> Deployment / StatefulSet
  -> label selector
```

Current Pod names are resolved through Kubernetes API at query time.

### Runtime flow

```text
Repository or Service
  -> Stable Workload Mapping
  -> Kubernetes API
  -> Current Workload / Pods
  -> Status / Logs
  -> Runtime Evidence
  -> Context Builder
```

Potential bounded operations include `resolve_repo_workload`, `get_workload`, `get_pods`, and `get_pod_logs`.

The backend uses a dedicated ServiceAccount with least-privilege RBAC. Dex is not required for initial service identity. Runtime tools require authorization checks, audit logs, timeouts, log-size limits, and explicit cluster/namespace scoping.

### Tasks

- [ ] Define `RuntimeProvider` and stable workload mapping model.
- [ ] Implement Kubernetes client adapter.
- [ ] Implement ServiceAccount/RBAC deployment configuration.
- [ ] Implement workload and Pod lookup.
- [ ] Implement bounded Pod log retrieval.
- [ ] Add runtime authorization and audit logging.
- [ ] Add timeout/payload guardrails.
- [ ] Integrate Runtime evidence into Context Builder.
- [ ] Add runtime troubleshooting tests.

### Acceptance

Given an authorized repository/service, the system resolves its stable Kubernetes workload and retrieves current status, Pods, and logs without persisting ephemeral Pod identity as durable knowledge.

## 14. M5 — Memory and Agent Platform

### Objective

Combine Knowledge, Memory, and Runtime through one orchestrated context layer after each source is independently useful and testable.

### Memory v1

Use PostgreSQL behind `MemoryStore`, initially focusing on:

- **Decision memory** — architecture/implementation decisions;
- **Episodic memory** — prior troubleshooting/work episodes.

Memory is not automatically canonical Knowledge. Promotion from experience into verified engineering knowledge must be explicit or verified.

Define creation, scope, retrieval, validity/invalidation, consolidation, and promotion rules. Graphiti/Zep or Mem0 remain optional future implementations if PostgreSQL-backed memory becomes insufficient.

### LangGraph

LangGraph is introduced in M5 to decide whether a request needs Knowledge, Memory, Runtime, or a combination:

```text
Question
  -> LangGraph
       -> Knowledge Retriever
       -> Memory Retriever
       -> Runtime Retriever
  -> Context Builder
  -> General LLM
```

Potential bounded MCP/Agent tools include `kb_search`, `kb_fetch`, `graph_neighbors`, `graph_traverse`, `memory_search`, `get_repo_runtime`, `get_pods`, and `get_pod_logs`. Raw database and Kubernetes clients are never exposed directly to the model.

### Tasks

- [ ] Implement PostgreSQL MemoryStore adapter.
- [ ] Implement decision and episodic memory.
- [ ] Define memory scope/invalidation and promotion workflow.
- [ ] Implement cross-session memory retrieval.
- [ ] Add LangGraph orchestration.
- [ ] Expose bounded Knowledge/Graph/Memory/Runtime tools.
- [ ] Add MCP/FastMCP adapter when required.
- [ ] Add authorization/approval boundaries, tracing, and metrics.
- [ ] Add tool-selection evaluation.

### Acceptance

A new AI session can retrieve important prior decisions/episodes and combine them with repository knowledge and, when necessary, current Kubernetes evidence. Tool use is bounded, authorized, and traceable.

## 15. Testing and Evaluation Strategy

Unit tests cover configuration/secret separation, validation, chunking, content hashes, repository filters, ordering, provider/store errors, graph normalization, and memory lifecycle rules.

Integration tests cover PostgreSQL/schema bootstrap, pgvector insert/search, AGE availability/traversal, full/incremental indexing, deleted-file invalidation, GitHub source access, and Kubernetes runtime access when M4 begins.

Maintain a versioned retrieval evaluation dataset with question, target scope, expected evidence, optional expected entities/relations, and acceptable alternatives. Use results to tune chunk size, overlap, Top-K, reranking, vector indexing, and graph expansion rather than hard-coding those choices without measurement.

## 16. Operational Requirements

Production readiness is added continuously to the milestone introducing each capability rather than postponed into a separate phase.

Required capabilities over time include structured logging, Prometheus metrics, health/readiness endpoints, retry/failure visibility, bounded concurrency, GitHub webhook verification, database backup/restore, vector rebuild, graph rebuild, Kubernetes audit logs, and Docker/Kubernetes deployment configuration.

The application does not provision PostgreSQL itself. Database infrastructure and credentials are supplied externally.

## 17. Explicit Non-Goals Before M2 Completion

Do not make the following dependencies of the core MVP before M2 is complete:

- image/VLM ingestion;
- Java/Python AST-wide extraction;
- comprehensive Helm/Kubernetes semantic graph extraction;
- AGE traversal in every query;
- Graphiti/Zep/Mem0;
- LangGraph orchestration;
- Kubernetes runtime access;
- MCP as the only application interface;
- MinIO/object storage.

MinIO becomes useful later for PDFs, images, diagrams, screenshots, audio, large attachments, repository snapshots, build artifacts, or archived logs. Current textual engineering knowledge remains in PostgreSQL.

## 18. Milestone Summary

| Milestone | Outcome | Completion signal |
| --- | --- | --- |
| **M0 Foundation** | PostgreSQL + pgvector + AGE foundation is runnable | real DB readiness + vector/AGE integration tests |
| **M1 Knowledge Ingestion MVP** | GitHub -> Markdown/Text -> Chunk -> pgvector | full + incremental indexing works on initial repos |
| **M2 Search and RAG MVP** | Question -> Retrieval -> LLM -> Evidence | grounded answers + reproducible retrieval baseline |
| **M3 Engineering Knowledge Graph** | AGE-backed multi-hop engineering relationships | traceable multi-hop answers |
| **M4 Runtime Context** | Repo/service -> K8s workload -> live status/logs | live runtime troubleshooting evidence |
| **M5 Memory and Agent Platform** | Knowledge + Memory + Runtime orchestration | cross-session memory + bounded LangGraph tools |

## 19. Immediate Next Work

The project is currently in **M0 Foundation**. The next implementation sequence is:

1. add `EmbeddingProvider` and `LLMProvider` ports;
2. resolve embedding-dimension/schema and AGE graph-name configuration invariants;
3. establish the migration strategy;
4. implement PostgreSQL/pgvector/AGE readiness validation;
5. expose `/health/live` and `/health/ready`;
6. add PostgreSQL, pgvector, and AGE integration tests;
7. expand DocumentStore/write transaction boundaries required by M1;
8. complete M0 acceptance criteria before beginning the M1 GitHub ingestion pipeline.
