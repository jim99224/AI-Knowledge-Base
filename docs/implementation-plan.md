# AI Knowledge Base Implementation Plan

## 1. Goal

Build a Python-first team engineering knowledge platform that:

- indexes Markdown, source code, comments, and infrastructure configuration from GitHub repositories;
- uses the existing text embedding model for semantic retrieval;
- uses the existing general LLM for grounded answer generation and semantic knowledge extraction;
- standardizes persistence on PostgreSQL;
- uses pgvector for vector search;
- uses Apache AGE for graph relationships and multi-hop traversal;
- keeps Knowledge, Memory, and Runtime context as separate logical layers;
- can later be exposed as Agent tools or an MCP server;
- keeps image understanding as a later extension rather than an MVP requirement.

## 2. Architecture Principles

1. PostgreSQL is the durable source of truth for repositories, documents, chunks, metadata, indexing state, and simple memory records.
2. pgvector is the semantic retrieval index. Embeddings must be rebuildable from canonical PostgreSQL content.
3. Apache AGE stores graph entities and relationships that benefit from traversal; graph data must retain evidence back to canonical repository content.
4. Knowledge, AI memory, and live runtime state are different context sources and must not be mixed into one lifecycle.
5. Application services depend on Python ports/protocols rather than database-specific APIs.
6. Deterministic parsers are preferred over LLM extraction for structured formats.
7. FastAPI, Agent tools, and MCP reuse the same application services.
8. Every grounded knowledge answer should retain repository, path, commit, and heading references.
9. Runtime Kubernetes data is fetched live where practical instead of being treated as durable knowledge.

## 3. Target Architecture

```mermaid
flowchart TB
    U[User / AI Client] --> O[LangGraph Orchestrator / Context Builder]
    O --> K[Knowledge Retriever]
    O --> M[Memory Retriever]
    O --> R[Runtime Retriever]

    subgraph Knowledge Layer
        GH[GitHub repositories] --> GS[Git sync / webhook]
        GS --> SC[Repository scanner]
        SC --> PC[Parser + chunker]
        PC --> PG[(PostgreSQL)]
        PC --> EM[Embedding provider]
        EM --> PV[pgvector]
        SC --> EX[Entity / relation extraction]
        EX --> AGE[Apache AGE]
        K --> PG
        K --> PV
        K --> AGE
    end

    subgraph Memory Layer
        M --> MS[(PostgreSQL memory tables)]
    end

    subgraph Runtime Layer
        R --> K8S[Kubernetes API]
        K8S --> RT[Deployments / Pods / Logs]
    end

    O --> LLM[General LLM]
```

The three retrieval layers have different responsibilities:

- **Knowledge Layer**: what the repositories and verified engineering sources say.
- **Memory Layer**: what the AI/team previously decided or experienced across sessions.
- **Runtime Layer**: what the deployed system is doing now.

## 4. Initial Technology Stack

| Area | Initial choice | Replaceable |
| --- | --- | --- |
| Language | Python 3.12+ | No |
| HTTP API | FastAPI | Yes |
| Validation | Pydantic | Yes |
| Canonical database | PostgreSQL | Yes, behind ports |
| Vector search | pgvector | Yes, behind `VectorStore` |
| Graph | Apache AGE | Yes, behind `GraphStore` |
| Embedding | Existing embedding model | Yes, behind `EmbeddingProvider` |
| Generation / extraction | Existing general LLM | Yes, behind `LLMProvider` |
| Agent orchestration | LangGraph | Yes |
| Runtime integration | Kubernetes Python client | Yes |
| Background work | Dramatiq or Celery | Yes |
| Deployment | Docker and Kubernetes | Yes |
| Metrics | Prometheus endpoint | Yes |
| MCP | Python MCP SDK / FastMCP | Yes |

The database deployment is intentionally consolidated: PostgreSQL provides relational/document metadata storage, pgvector provides vector search, and AGE provides graph capability.

## 5. Repository Layout

```text
ai-knowledge-base/
├── apps/
│   ├── api/
│   ├── worker/
│   ├── mcp_server/
│   └── agent/
├── src/knowledge_base/
│   ├── domain/
│   ├── application/
│   │   ├── indexing_service.py
│   │   ├── retrieval_service.py
│   │   ├── graph_service.py
│   │   ├── memory_service.py
│   │   ├── runtime_service.py
│   │   └── answer_service.py
│   ├── ports/
│   │   ├── document_store.py
│   │   ├── vector_store.py
│   │   ├── graph_store.py
│   │   ├── memory_store.py
│   │   ├── runtime_provider.py
│   │   ├── embedding_provider.py
│   │   ├── llm_provider.py
│   │   └── source_repository.py
│   └── adapters/
│       ├── postgres/
│       │   ├── document_store.py
│       │   ├── vector_store.py
│       │   ├── graph_store.py
│       │   └── memory_store.py
│       ├── kubernetes/
│       ├── models/
│       └── github/
├── tests/
├── deploy/
├── docs/
├── pyproject.toml
└── README.md
```

## 6. Core Ports

Keep the existing `EmbeddingProvider`, `LLMProvider`, `DocumentStore`, and `VectorStore` abstractions. Add two important boundaries:

### GraphStore

```python
from typing import Protocol, Sequence

class GraphStore(Protocol):
    async def upsert_entities(self, entities: Sequence[object]) -> None: ...
    async def upsert_relations(self, relations: Sequence[object]) -> None: ...
    async def neighbors(self, entity_id: str, relation_types: list[str] | None = None) -> list[object]: ...
    async def traverse(self, start_id: str, max_depth: int = 3) -> list[object]: ...
```

### MemoryStore

```python
from typing import Protocol, Sequence

class MemoryStore(Protocol):
    async def add(self, memory: object) -> None: ...
    async def search(self, query: str, limit: int = 10) -> Sequence[object]: ...
    async def invalidate(self, memory_id: str) -> None: ...
```

These ports allow AGE or the memory implementation to evolve without coupling the agent to a database SDK.

## 7. PostgreSQL Data Model

Initial relational tables:

### `repositories`

- `id`
- `owner`
- `name`
- `default_branch`
- `last_indexed_commit`
- `enabled`
- `created_at`
- `updated_at`

### `documents`

- `id`
- `repository_id`
- `path`
- `title`
- `document_type`
- `branch`
- `commit_sha`
- `content_hash`
- `raw_text`
- `metadata JSONB`
- `index_status`
- `created_at`
- `updated_at`
- `deleted_at`

### `chunks`

- `id`
- `document_id`
- `repository_id`
- `chunk_index`
- `heading_path`
- `content`
- `token_count`
- `content_hash`
- `commit_sha`
- `embedding vector(N)`
- `embedding_model`
- `embedding_index_version`
- `metadata JSONB`
- `created_at`
- `updated_at`

### `index_jobs`

- `id`
- `repository_id`
- `commit_sha`
- `status`
- `files_scanned`
- `documents_updated`
- `chunks_created`
- `error`
- `started_at`
- `finished_at`

### `memories` (later phase)

- `id`
- `scope`
- `memory_type` (`semantic`, `episodic`, `decision`)
- `content`
- `metadata JSONB`
- `valid_from`
- `valid_until`
- `created_at`
- `updated_at`

Use pgvector indexes on chunk embeddings. Index selection (HNSW/IVFFlat) should be benchmarked using the project evaluation set instead of hard-coded prematurely.

## 8. Apache AGE Graph Model

Initial entity types:

- Repository
- Service
- API
- Database
- Technology
- Deployment
- KubernetesWorkload
- Document

Initial relationships:

- `CONTAINS`
- `DEPENDS_ON`
- `CALLS`
- `USES`
- `EXPOSES`
- `DEPLOYED_BY`
- `DESCRIBES`

Each graph fact should retain evidence such as repository ID, path, commit SHA, parser/extractor version, and confidence when the relationship came from an LLM.

Do not persist ephemeral Pod names as durable graph facts. Store stable workload identity such as cluster, namespace, Deployment/StatefulSet, and label selectors; resolve current Pods through the Kubernetes API at query time.

## 9. Knowledge Extraction Flow

```mermaid
flowchart TD
    A[GitHub webhook / sync / manual trigger] --> B[Create index job]
    B --> C[Compare commit SHA]
    C --> D[Download changed files]
    D --> E[File router]
    E --> F[Deterministic parsers]
    E --> G[LLM semantic extractor when needed]
    F --> H[Documents + chunks + metadata]
    G --> H
    H --> PG[(PostgreSQL)]
    H --> I[Embedding provider]
    I --> PV[pgvector]
    F --> J[Entity / relation candidates]
    G --> J
    J --> N[Normalize + deduplicate + validate]
    N --> AGE[Apache AGE]
```

Prefer deterministic parsing for Kubernetes YAML, Helm, OpenAPI, package manifests, Dockerfiles, and other structured formats. Use the LLM for README semantics, code intent, ambiguous relationships, summaries, and normalization assistance.

## 10. Consistency Strategy

PostgreSQL consolidation simplifies the previous MongoDB/external-vector consistency problem, but indexing must remain idempotent.

Recommended state flow:

```text
pending -> parsed -> embedded -> graph_extracted -> indexed
                     |                |
                     +---- failed ----+
                              |
                            retry
```

Requirements:

- canonical document/chunk rows are written before derived indexes are considered complete;
- `content_hash` prevents unnecessary re-embedding;
- stable chunk IDs allow safe upserts;
- embedding/model versions are recorded;
- graph facts retain evidence and extractor version;
- incremental scans remove or invalidate facts whose source content was deleted;
- monthly or operator-triggered full rebuild remains supported;
- vector and graph projections can be reconstructed from canonical repository content.

## 11. Retrieval and Answer Flow

```mermaid
flowchart TD
    A[User query] --> B[Intent + permission validation]
    B --> C[Query embedding]
    C --> D[pgvector Top-K]
    D --> E[Rerank / metadata filter]
    E --> F{Relationship context needed?}
    F -->|No| H[Context builder]
    F -->|Yes| G[AGE graph expansion]
    G --> H
    H --> I[Fetch canonical PostgreSQL content]
    I --> J[General LLM]
    J --> K[Answer with source references]
```

Graph traversal is query-dependent. A simple question such as "How do I run service X locally?" may only need vector retrieval. Questions such as "Which services depend on X and where are they deployed?" can use AGE for multi-hop traversal.

## 12. Runtime Layer

Runtime retrieval is implemented as explicit tools, for example:

```text
resolve_repo_workload(repo)
get_deployments(cluster, namespace)
get_pods(cluster, namespace, selector)
get_pod_logs(cluster, namespace, pod, container?, since?)
```

Flow:

```text
repository
  -> PostgreSQL / AGE stable workload mapping
  -> cluster + namespace + workload + selector
  -> Kubernetes API
  -> current Pods / status / logs
  -> Context Builder
```

Use a dedicated Kubernetes ServiceAccount with least-privilege RBAC. Dex is not required for the initial service identity. User-aware OIDC/RBAC can be introduced later if runtime authorization must differ by user.

## 13. Memory Layer

The first memory implementation should remain intentionally simple and use PostgreSQL behind `MemoryStore`.

Memory categories:

- semantic memory: durable learned/confirmed facts;
- episodic memory: prior troubleshooting or work sessions;
- decision memory: architecture and implementation decisions;
- working/session state remains in the orchestrator rather than being promoted automatically to long-term memory.

A specialized framework such as Graphiti/Zep or Mem0 can be evaluated later when temporal fact invalidation, memory consolidation, or high-volume cross-session retrieval becomes necessary.

## 14. Configuration

```env
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/ai_knowledge_base

PGVECTOR_ENABLED=true
EMBEDDING_MODEL_ID=text-embedding-model
EMBEDDING_DIMENSION=1024
EMBEDDING_INDEX_VERSION=embedding-v1

AGE_ENABLED=true
AGE_GRAPH_NAME=ai_knowledge_graph

GENERAL_LLM_MODEL_ID=general-llm

KUBERNETES_RUNTIME_ENABLED=false
```

The embedding dimension is configuration. A model migration must be versioned and should build a new index before retiring the old one.

## 15. API / MCP / Agent Boundaries

FastAPI endpoints can retain the retrieval/answer split:

```text
POST /v1/search
POST /v1/answer
GET  /v1/documents/{document_id}
GET  /v1/repositories
POST /v1/repositories/{repository_id}/index
GET  /v1/index-jobs/{job_id}
POST /internal/github/webhook
GET  /health/live
GET  /health/ready
GET  /metrics
```

Later MCP/Agent tools:

```text
kb_search
kb_fetch
graph_neighbors
graph_traverse
memory_search
get_repo_runtime
get_pods
get_pod_logs
```

LangGraph is the planned orchestrator for choosing between Knowledge, Memory, and Runtime tools. Tool implementations call application services; the LLM/agent must not access PostgreSQL, AGE, or Kubernetes clients directly.

## 16. Delivery Phases

### Phase 0: PostgreSQL Foundation

- initialize Python project and ports;
- configure PostgreSQL lifecycle and migrations;
- enable pgvector and AGE in the target PostgreSQL environment;
- implement PostgreSQL `DocumentStore`;
- implement pgvector `VectorStore`;
- add fake model/store adapters and unit tests.

Acceptance: application services work through ports and one PostgreSQL platform can provide canonical storage plus vector capability.

### Phase 1: Indexing MVP

- GitHub repository synchronization;
- incremental commit comparison;
- Markdown/text/source/config parsing;
- chunking and metadata;
- PostgreSQL persistence;
- embedding batch calls;
- pgvector indexing;
- retryable index jobs.

Acceptance: repositories can be indexed end-to-end and unchanged chunks are not embedded again.

### Phase 2: Retrieval MVP

- query embedding;
- pgvector Top-K retrieval;
- metadata/repository/authorization filters;
- reranking hook;
- canonical PostgreSQL fetch;
- retrieval evaluation dataset.

Acceptance: known questions retrieve expected evidence in Top 5 and stale/unauthorized chunks are excluded.

### Phase 3: RAG Answer

- context builder;
- grounded prompt;
- LLM generation;
- answer citations;
- evidence-missing refusal behavior;
- latency/token metrics.

### Phase 4: Knowledge Graph

- finalize entity/relation schema;
- implement deterministic entity extraction from structured files;
- add LLM relation extraction for semantic sources;
- normalize/canonicalize entities;
- implement AGE adapter and evidence-backed upserts;
- add graph traversal to retrieval when intent requires it.

Acceptance: relationship-heavy test questions can traverse repository -> service -> dependency/deployment relationships with traceable evidence.

### Phase 5: Production Readiness

- background workers;
- webhook verification;
- PostgreSQL/pgvector/AGE health checks;
- retry/dead-letter handling;
- Prometheus metrics/alerts;
- Docker/Kubernetes manifests;
- backup, restore, vector rebuild, and graph rebuild procedures.

### Phase 6: Runtime Kubernetes Context

- implement stable repo-to-workload mapping;
- Kubernetes ServiceAccount + least-privilege RBAC;
- workload/Pod/status/log tools;
- runtime authorization and audit logging;
- separate live runtime evidence from durable KB content.

### Phase 7: Memory

- implement `MemoryStore` on PostgreSQL;
- decision and episodic memory;
- cross-session retrieval;
- explicit promotion/invalidation rules;
- evaluate Graphiti/Zep or Mem0 only when requirements justify them.

### Phase 8: MCP / Agent

- expose knowledge, graph, memory, and runtime services as bounded tools;
- use LangGraph for orchestration;
- add session state, guardrails, tracing, authorization, and approval boundaries.

## 17. Metrics and Evaluation

### Indexing

- job success rate;
- commit-to-searchable latency;
- files/chunks processed per minute;
- embedding latency/failure rate;
- unchanged chunks skipped;
- graph extraction success/error rate.

### Retrieval

- Recall@5 / Recall@10;
- mean reciprocal rank;
- irrelevant chunk rate;
- P50/P95 latency;
- graph traversal usefulness and latency.

### Answer Quality

- citation correctness;
- faithfulness;
- refusal accuracy;
- answer latency/token usage.

### Runtime

- Kubernetes API latency/error rate;
- authorization denials;
- Pod/log tool success rate;
- freshness of runtime evidence.

### Memory / Agent

- relevant memory recall rate;
- stale memory rate;
- tool selection accuracy;
- task completion rate;
- average tool calls;
- invalid loop/authorization violation rate.

## 18. Immediate Next Steps

1. Add PostgreSQL, pgvector, and AGE configuration/migration strategy.
2. Replace the MongoDB adapter with PostgreSQL `DocumentStore`.
3. Make pgvector the concrete `VectorStore` implementation.
4. Add `GraphStore` and AGE adapter interfaces without forcing graph traversal into every query.
5. Keep repository scanning/chunking independent from persistence SDKs.
6. Index a small repository set and build a retrieval evaluation dataset.
7. Add graph extraction only after vector retrieval is stable.
8. Add Kubernetes runtime tools after stable repo-to-workload identity is available.
9. Add PostgreSQL-backed memory after the core Knowledge Layer is stable.

The core dependency direction remains:

```text
FastAPI / MCP / LangGraph Agent
            |
            v
     Application Services
            |
   +--------+---------+----------------+
   |        |         |                |
Document  Vector    Graph           Runtime
 Store     Store     Store           Provider
   |        |         |                |
   +--------+---------+                v
            |                    Kubernetes API
            v
 PostgreSQL + pgvector + AGE
```
