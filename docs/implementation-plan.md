# AI Knowledge Base Implementation Plan

## 1. Goal

Build a Python-first, text-only knowledge base that:

- indexes Markdown, source code, comments, and infrastructure configuration from GitHub;
- uses an existing text embedding model for semantic retrieval;
- uses an existing general LLM for grounded answer generation;
- stores canonical text and metadata in MongoDB;
- keeps the Vector DB replaceable;
- can later be exposed as Agent tools or an MCP server for other AI clients;
- excludes image parsing, OCR, image embeddings, and image storage.

## 2. Architecture Principles

1. MongoDB is the source of truth for documents, chunks, metadata, and indexing state.
2. The Vector DB is a derived search index and must be rebuildable from MongoDB.
3. Application services depend on Python protocols, not database SDKs.
4. Model providers are replaceable through embedding and LLM ports.
5. FastAPI, Agent tools, and MCP tools reuse the same application services.
6. The first MCP release is read-only.
7. Every answer includes repository, path, commit, and heading references.

## 3. Target Architecture

```mermaid
flowchart TB
    A[GitHub repositories] --> B[Git sync or webhook]
    B --> C[Repository scanner]
    C --> D[Text parser and chunker]
    D --> E[MongoDB document store]
    D --> F[Embedding provider]
    F --> G[Vector store port]

    H[FastAPI] --> I[Retrieval service]
    J[Agent runtime] --> I
    K[MCP server] --> I

    I --> G
    I --> E
    I --> L[General LLM provider]
```

## 4. Initial Technology Stack

| Area | Initial choice | Replaceable |
| --- | --- | --- |
| Language | Python 3.12+ | No |
| HTTP API | FastAPI | Yes, but not required |
| Validation | Pydantic | Yes |
| Text database | MongoDB | Yes, through `DocumentStore` |
| Vector database | Undecided | Yes, through `VectorStore` |
| Embedding | Existing embedding model | Yes, through `EmbeddingProvider` |
| Generation | Existing general LLM | Yes, through `LLMProvider` |
| Background work | Dramatiq or Celery | Yes |
| Deployment | Docker and Kubernetes | Yes |
| Metrics | Prometheus endpoint | Yes |
| MCP | Python MCP SDK / FastMCP | Yes |

The MVP can use an in-memory vector adapter for development until the production Vector DB is selected.

## 5. Repository Layout

```text
ai-knowledge-base/
├── apps/
│   ├── api/
│   │   └── main.py
│   ├── worker/
│   │   └── main.py
│   ├── mcp_server/
│   │   └── server.py
│   └── agent/
│       └── agent.py
├── src/
│   └── knowledge_base/
│       ├── domain/
│       │   ├── models.py
│       │   └── exceptions.py
│       ├── application/
│       │   ├── indexing_service.py
│       │   ├── retrieval_service.py
│       │   ├── answer_service.py
│       │   └── reindex_service.py
│       ├── ports/
│       │   ├── document_store.py
│       │   ├── vector_store.py
│       │   ├── embedding_provider.py
│       │   ├── llm_provider.py
│       │   └── source_repository.py
│       └── adapters/
│           ├── document_stores/
│           │   └── mongodb.py
│           ├── vector_stores/
│           │   ├── memory.py
│           │   ├── qdrant.py
│           │   ├── milvus.py
│           │   └── pgvector.py
│           ├── models/
│           │   ├── embedding_client.py
│           │   └── llm_client.py
│           └── github/
│               ├── client.py
│               └── webhook.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
├── deploy/
│   ├── docker/
│   ├── helm/
│   └── kubernetes/
├── docs/
├── pyproject.toml
└── README.md
```

## 6. Core Python Ports

### 6.1 Embedding Provider

```python
from typing import Protocol, Sequence


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    async def embed_documents(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]: ...

    async def embed_query(
        self,
        text: str,
    ) -> list[float]: ...
```

### 6.2 General LLM Provider

```python
from typing import Protocol, Sequence
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str
    content: str


class LLMProvider(Protocol):
    async def generate(
        self,
        messages: Sequence[ChatMessage],
        temperature: float = 0.0,
    ) -> str: ...
```

### 6.3 Document Store

```python
from typing import Protocol, Sequence


class DocumentStore(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def upsert_documents(self, documents: Sequence[object]) -> None: ...
    async def upsert_chunks(self, chunks: Sequence[object]) -> None: ...
    async def get_chunk(self, chunk_id: str) -> object | None: ...
    async def get_chunks(self, chunk_ids: Sequence[str]) -> list[object]: ...
    async def delete_document_chunks(self, document_id: str) -> None: ...
    async def mark_chunks_indexed(
        self,
        chunk_ids: Sequence[str],
        index_version: str,
    ) -> None: ...
```

### 6.4 Vector Store

```python
from typing import Protocol, Sequence
from dataclasses import dataclass


@dataclass
class VectorRecord:
    id: str
    vector: list[float]
    metadata: dict


@dataclass
class VectorMatch:
    id: str
    score: float
    metadata: dict


class VectorStore(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...

    async def ensure_collection(
        self,
        collection_name: str,
        dimension: int,
    ) -> None: ...

    async def upsert(
        self,
        collection_name: str,
        records: Sequence[VectorRecord],
    ) -> None: ...

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[VectorMatch]: ...

    async def delete(
        self,
        collection_name: str,
        ids: Sequence[str],
    ) -> None: ...
```

## 7. MongoDB Data Model

### `repositories`

- `_id`
- `owner`
- `name`
- `default_branch`
- `last_indexed_commit`
- `enabled`
- `created_at`
- `updated_at`

### `documents`

- `_id`
- `repository_id`
- `path`
- `title`
- `document_type`
- `branch`
- `commit_sha`
- `content_hash`
- `raw_text`
- `metadata`
- `index_status`
- `created_at`
- `updated_at`
- `deleted_at`

### `chunks`

- `_id`
- `document_id`
- `repository_id`
- `chunk_index`
- `heading_path`
- `content`
- `token_count`
- `content_hash`
- `commit_sha`
- `vector_status`
- `vector_index_version`
- `embedding_model`
- `embedding_dimension`
- `retry_count`
- `metadata`
- `created_at`
- `updated_at`

### `index_jobs`

- `_id`
- `repository_id`
- `commit_sha`
- `status`
- `files_scanned`
- `documents_updated`
- `chunks_created`
- `error`
- `started_at`
- `finished_at`

## 8. Vector Record Contract

The Vector DB stores embeddings and references, not the canonical full text.

```json
{
  "id": "chunk-id",
  "vector": [0.012, -0.038, 0.104],
  "metadata": {
    "document_id": "document-id",
    "repository_id": "repo-id",
    "branch": "main",
    "commit_sha": "abc123",
    "document_type": "markdown",
    "index_version": "embedding-v1"
  }
}
```

Search returns chunk IDs and scores. Full chunk text is batch-loaded from MongoDB.

## 9. Indexing Flow

```mermaid
flowchart TD
    A[GitHub webhook or manual trigger] --> B[Create index job]
    B --> C[Compare commit SHA]
    C --> D[Download changed files]
    D --> E[Filter supported text files]
    E --> F[Parse and chunk]
    F --> G[Upsert MongoDB with vector status pending]
    G --> H[Generate embeddings]
    H --> I[Upsert Vector DB]
    I --> J[Mark MongoDB chunks indexed]
    H -->|Failure| K[Mark failed and retry]
    I -->|Failure| K
```

Initial supported inputs:

- Markdown and README files;
- Python source and comments;
- YAML and YML;
- Dockerfiles;
- Helm charts;
- Kubernetes manifests;
- GitHub Actions workflows.

Initial chunking targets:

- 400 to 800 tokens per chunk;
- 50 to 100 token overlap;
- Markdown split by heading hierarchy;
- source code split by class or function when possible;
- YAML split by top-level key or Kubernetes resource;
- stable metadata for repository, branch, path, commit, and heading.

## 10. Cross-Database Consistency

MongoDB and the Vector DB do not share a transaction. Indexing therefore uses an idempotent state machine:

```text
pending -> embedding -> vector_upsert -> indexed
                    \-> failed -> retry
```

Requirements:

- MongoDB is written before the Vector DB.
- `content_hash` prevents unnecessary re-embedding.
- every Vector DB upsert uses a stable chunk ID;
- retries must be idempotent;
- stale vectors are deleted after a successful replacement;
- a reconciliation job compares MongoDB state with Vector DB state;
- a complete Vector DB rebuild can be started from MongoDB.

## 11. Retrieval and Answer Flow

```mermaid
flowchart TD
    A[User query] --> B[Input and permission validation]
    B --> C[Query embedding]
    C --> D[Vector DB top-K search]
    D --> E[Chunk IDs and scores]
    E --> F[MongoDB batch fetch]
    F --> G[Deduplicate and build context]
    G --> H[General LLM]
    H --> I[Answer with source references]
```

MVP retrieval behavior:

1. Generate a query embedding.
2. Apply repository and authorization filters before or during vector search.
3. Request approximately 20 candidates.
4. Batch-fetch canonical chunks from MongoDB.
5. Remove duplicate or stale results.
6. Select approximately 5 to 10 chunks within the context budget.
7. Ask the LLM to answer only from retrieved context.
8. Return repository, path, heading, commit SHA, and score.

## 12. FastAPI Endpoints

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

`/v1/search` performs retrieval only. `/v1/answer` performs retrieval and LLM generation. This separation lets Agents and MCP clients retrieve knowledge without causing a second LLM call.

## 13. Configuration

```env
DOCUMENT_STORE_BACKEND=mongodb
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DATABASE=ai_knowledge_base

VECTOR_STORE_BACKEND=memory
VECTOR_STORE_URL=
VECTOR_STORE_API_KEY=
VECTOR_COLLECTION=knowledge_chunks_v1

EMBEDDING_MODEL_ID=text-embedding-model
EMBEDDING_DIMENSION=1024
EMBEDDING_INDEX_VERSION=embedding-v1

GENERAL_LLM_MODEL_ID=general-llm
```

The embedding dimension must be configuration, not a Python constant. A model change with a different dimension creates a new vector collection and index version.

## 14. MCP Expansion

The MCP server wraps application services and never accesses MongoDB or the Vector DB directly.

Initial read-only tools:

```text
search(query, repository_ids?, top_k?)
fetch(id)
list_repositories()
get_index_status(repository_id)
```

`search` returns result IDs, titles, and canonical URLs. `fetch` returns full text and metadata. The MCP layer uses explicit schemas and read-only safety annotations.

Development transport:

- STDIO for local testing;
- Streamable HTTP for Kubernetes and remote AI clients;
- OAuth or service authentication for private knowledge.

## 15. Agent Expansion

The first Agent uses the Knowledge Base as tools:

```text
kb_search
kb_fetch
list_repositories
get_index_status
```

Possible later workflows:

- compare deployment settings across repositories;
- find inconsistent README and Helm configuration;
- generate troubleshooting checklists from runbooks;
- combine monitoring alerts with knowledge retrieval;
- route questions to repository-specific specialists;
- request human approval before any future write action.

The Agent must not query database clients directly. It calls the same retrieval service used by FastAPI and MCP.

## 16. Delivery Phases

### Phase 0: Foundation — 3 to 5 days

- initialize the Python project;
- define domain models and ports;
- implement model adapters;
- implement MongoDB connection lifecycle;
- implement the in-memory Vector Store;
- add unit-test infrastructure.

Acceptance criteria:

- both models are callable through stable interfaces;
- application services run with fake stores in tests;
- no application code imports a specific vector database SDK.

### Phase 1: Indexing MVP — 1 to 2 weeks

- GitHub repository synchronization;
- incremental commit comparison;
- Markdown and text parsing;
- chunking and metadata;
- MongoDB persistence;
- embedding batch calls;
- Vector Store upsert;
- retryable indexing jobs.

Acceptance criteria:

- one repository can be indexed end-to-end;
- unchanged content is not embedded again;
- failed vector writes can be retried safely.

### Phase 2: Retrieval MVP — 1 week

- query embedding;
- top-K vector retrieval;
- MongoDB batch fetch;
- metadata filtering;
- source references;
- retrieval evaluation dataset.

Acceptance criteria:

- known test questions retrieve the expected source in Top 5;
- stale or unauthorized chunks are excluded;
- search latency metrics are exposed.

### Phase 3: RAG Answer — 1 week

- context builder;
- grounded prompt;
- LLM generation;
- answer citations;
- refusal behavior when evidence is missing.

Acceptance criteria:

- answers include valid repository and path references;
- unsupported questions do not produce fabricated answers;
- token usage and latency are measured.

### Phase 4: Production Readiness — 1 to 2 weeks

- background workers;
- webhook verification;
- MongoDB and Vector DB connection health;
- retry and dead-letter handling;
- Prometheus metrics and alerts;
- Docker and Kubernetes manifests;
- backup and Vector DB rebuild procedure.

### Phase 5: MCP Server — approximately 1 week

- implement `search` and `fetch`;
- add schemas and safety annotations;
- add Streamable HTTP transport;
- add authentication;
- test from an external MCP client.

### Phase 6: Agent — 1 to 2 weeks

- expose retrieval as Agent tools;
- implement bounded tool loops;
- add session state, guardrails, and tracing;
- evaluate tool selection and task completion.

Estimated MVP: 4 to 6 weeks. Estimated production system with MCP and Agent support: 7 to 10 weeks.

## 17. Metrics and Evaluation

### Indexing

- index job success rate;
- commit-to-searchable latency;
- files and chunks processed per minute;
- embedding request latency and failure rate;
- percentage of unchanged chunks skipped;
- retry and dead-letter counts.

### Retrieval

- Recall@5 and Recall@10;
- mean reciprocal rank;
- irrelevant chunk rate;
- P50 and P95 latency;
- hit rate by document type.

### Answer Quality

- citation correctness;
- faithfulness to retrieved context;
- refusal accuracy when evidence is missing;
- answer latency and token usage.

### Agent

- tool selection accuracy;
- task completion rate;
- average tool calls per task;
- invalid loop rate;
- authorization and approval enforcement.

## 18. Immediate Next Steps

1. Create the Python package and dependency configuration.
2. Define domain models and four core ports.
3. Implement MongoDB and in-memory Vector Store adapters.
4. Add fake embedding and fake LLM adapters for tests.
5. Implement Markdown parsing and chunking.
6. Index one sample GitHub repository.
7. Build retrieval evaluation questions before selecting the production Vector DB.
8. Benchmark candidate Vector DB adapters using the same evaluation set.

The most important boundary is:

```text
FastAPI / MCP / Agent
        -> Application Services
        -> Storage and Model Ports
        -> MongoDB / Vector DB / Model Adapters
```

This keeps the initial implementation simple while preserving the ability to replace either database and expose the same knowledge capability to future Agents and MCP clients.

## 19. Repository-Scoped Indexing Modes

All indexing operations use a repository as the smallest isolation unit. A job for one repository must not block or mutate any other repository.

Supported modes:

| Mode | Trigger | Behavior |
| --- | --- | --- |
| `incremental` | GitHub webhook or frequent Git sync | Process only added, modified, deleted, and renamed files between two commits |
| `full_reconcile` | Monthly schedule or detected drift | Scan the complete current repository, reuse unchanged content, and repair MongoDB/Vector DB drift |
| `full_rebuild` | Parser, chunking, graph schema, embedding model, or dimension change | Build new content, vector, or graph generations and activate them after validation |

### 19.1 Incremental Indexing

Git sync produces a working tree at a target commit. The indexer determines changes with:

```bash
git diff --name-status --find-renames <last_indexed_commit>..<target_commit>
```

Operations:

- `A`: parse, chunk, embed, and insert;
- `M`: compare content hashes and update only changed entities/chunks;
- `D`: deactivate MongoDB documents and delete their vectors and graph evidence;
- `R`: update paths and avoid re-embedding when content is unchanged.

`last_indexed_commit` is updated only after the complete job succeeds.

### 19.2 Monthly Full Reconcile

Full reconcile scans every supported path at a fixed target commit and builds a manifest:

```text
path -> content hash + commit SHA + parser version + extractor version
```

Reconciliation rules:

- Git file exists and MongoDB document is missing: create it;
- content hash changed: reparse and reindex it;
- content hash unchanged and parser/extractor versions match: reuse extraction results;
- MongoDB document exists but Git file is missing: deactivate it and remove vectors/graph evidence;
- vector state is missing or failed: repair it;
- graph relationships are unresolved or dangling: rerun the affected linker.

Monthly full reconcile does not re-embed unchanged content.

### 19.3 Full Rebuild

Full rebuild creates shadow generations instead of deleting active data first:

```text
build new generation
-> validate counts, retrieval, and graph integrity
-> atomically update repository active generation
-> retain old generation for rollback
-> clean up asynchronously
```

Automatic fallback to reconcile or rebuild occurs when:

- no previous indexed commit exists;
- the previous commit is missing or is no longer an ancestor because of force-push/rebase;
- the default branch changes;
- parser, extractor, chunking, graph schema, embedding model, or dimension changes;
- MongoDB and Vector DB drift exceeds an accepted threshold.

### 19.4 Monthly Kubernetes Schedule

Create one job per enabled repository rather than one large job for all repositories. This provides independent retries, progress, and failure isolation.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: knowledge-base-full-reconcile
spec:
  schedule: "0 2 1 * *"
  timeZone: "Asia/Taipei"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: scheduler
              image: ai-knowledge-base:latest
              args:
                - python
                - -m
                - apps.worker.schedule_reconcile
                - --all-enabled-repositories
```

Each repository uses a separate distributed lock:

```text
knowledge-base:index:{repository_id}
knowledge-base:graph:{repository_id}
```

Different repositories may run concurrently. Jobs for the same repository must be serialized.

## 20. Repository Registry and Lifecycle

The `repositories` collection is the control plane for onboarding, search, indexing, rebuild, deactivation, and purge.

Additional repository fields:

```json
{
  "status": "onboarding | active | inactive | purge_pending | purged | failed",
  "indexing_enabled": true,
  "search_enabled": true,
  "last_indexed_commit": "abc123",
  "last_full_scan_commit": "abc123",
  "last_full_scan_at": "datetime",
  "active_content_generation": "content-v3",
  "active_embedding_generation": "embedding-v2",
  "active_graph_generation": "graph-v7",
  "collection_strategy": "shared | dedicated | partitioned"
}
```

### 20.1 Add Repository

```text
register repository
-> verify access and default branch
-> status = onboarding
-> run initial full reconcile
-> validate text/vector/graph outputs
-> status = active
-> enable webhook/incremental indexing
```

The repository is excluded from production search until onboarding validation succeeds.

### 20.2 Remove Repository

Removal from the knowledge base never deletes the upstream GitHub repository.

Two-phase removal:

1. Deactivate immediately: stop indexing and exclude the repository from all searches.
2. Purge asynchronously after an optional grace period: remove vectors, chunks, documents, entities, and edges while retaining a minimal audit record.

```text
POST   /v1/repositories/{repository_id}/deactivate
POST   /v1/repositories/{repository_id}/activate
DELETE /v1/repositories/{repository_id}?purge=true
```

## 21. Hybrid Vector Collection Strategy

Do not require every repository to use the same physical layout.

### 21.1 Shared Collections

Use for normal repositories with compatible permissions and the same embedding model/version:

```text
knowledge_shared_embedding_v1
  repository_id = repo-a
  repository_id = repo-b
  repository_id = repo-c
```

Every vector record includes `repository_id`, generation, document ID, commit, and authorization metadata.

### 21.2 Dedicated Collections

Use for large legacy repositories, strict isolation, custom index parameters, or different embedding models:

```text
knowledge_legacy_erp_embedding_v1
```

### 21.3 Partitioned Collections

Very large repositories may be partitioned by meaningful module boundaries:

```text
knowledge_legacy_erp_backend_v1
knowledge_legacy_erp_database_v1
knowledge_legacy_erp_batch_v1
knowledge_legacy_erp_docs_v1
```

Partition by service, module, top-level path, language, or document type. Do not split only by an arbitrary file count.

### 21.4 Collection Registry

MongoDB resolves a logical repository to physical collections:

```json
{
  "repository_id": "legacy-erp",
  "strategy": "partitioned",
  "embedding_model": "text-embedding-model",
  "active_generation": "embedding-v3",
  "collections": [
    {
      "name": "knowledge_legacy_erp_backend_v3",
      "partition_key": "backend",
      "path_patterns": ["backend/**"]
    },
    {
      "name": "knowledge_legacy_erp_database_v3",
      "partition_key": "database",
      "path_patterns": ["database/**", "sql/**"]
    }
  ]
}
```

## 22. Cross-Repository Search

Searching every collection for every query does not scale. Use two-stage retrieval.

```mermaid
flowchart TD
    A[Query] --> B[Authorization filter]
    B --> C[Repository catalog search]
    C --> D[Candidate repositories and modules]
    D --> E[Resolve shared/dedicated/partitioned targets]
    E --> F[Bounded parallel searches]
    F --> G[Rank fusion and deduplication]
    G --> H[MongoDB batch fetch]
    H --> I[General LLM]
```

### 22.1 Repository Catalog

Maintain a small catalog index containing repository/module summaries, README topics, languages, frameworks, owners, services, paths, aliases, and authorization metadata. Global queries search this catalog first and select a bounded number of repository targets.

When the user explicitly specifies repositories, skip catalog routing and search only those targets.

### 22.2 Parallel Search

Use bounded concurrency to protect the Vector DB. Each target returns local Top-K results. Do not compare raw scores blindly across collections with different models or index configurations.

Prefer compatible models and metrics within one search group. Merge results using rank-based fusion such as Reciprocal Rank Fusion, then apply repository-routing confidence, deduplication, and an optional reranker.

### 22.3 Large File Policy

Large legacy files are not embedded as one document. Apply structured or streaming parsing:

| File | Strategy |
| --- | --- |
| Large SQL | procedure, statement, DDL object, or table block |
| Large YAML/XML | resource, top-level key, or element subtree |
| Source code | class/function/method |
| Large plain text | bounded streaming chunks |
| Generated/vendor/minified/binary | exclude by policy |

Use hierarchical indexing for large repositories:

```text
repository summary
-> module summary
-> file summary
-> code/text chunks
```

## 23. Code Intelligence and AST Pipeline

Document RAG alone cannot reliably answer code-lineage questions. Add a deterministic code-intelligence pipeline.

AST means Abstract Syntax Tree: a parser converts source text into structured nodes such as classes, functions, decorators, calls, arguments, and literals. AST extraction is deterministic and is not an AI model.

```mermaid
flowchart LR
    A[File] --> B[Classifier]
    B --> C[Parser]
    C --> D[Shared AST or IR]
    D --> E[Extractor planner]
    E --> F[Relevant extractors]
    F --> G[Entities and unresolved relations]
    G --> H[Local/cross-file/cross-repo linkers]
```

### 23.1 Extractor Selection

Twenty registered extractors do not mean twenty file reads or parses.

```text
read once
-> classify once
-> parse once
-> traverse shared AST/IR once when practical
-> dispatch relevant nodes to applicable extractors
```

Examples:

| File | Applicable extractors |
| --- | --- |
| React TSX | function, component, UI element, event handler, HTTP client |
| FastAPI Python | route, class, function, call, ORM/SQL |
| SQL | query, procedure, table reference |
| Kubernetes YAML | ingress, service, deployment, config, data source |
| Markdown | document metadata and links |

The planner considers repository profile, file type, framework imports, AST features, and configuration markers.

### 23.2 Parse and Extraction Cache

Cache key:

```text
repository_id
+ path
+ content_hash
+ parser_version
+ extractor_version
```

Monthly full scans reuse cached results when content and versions are unchanged.

### 23.3 Extractors and Linkers

Initial extractor families:

```text
RouteExtractor
ClassExtractor
FunctionExtractor
UIComponentExtractor
UIElementExtractor
EventHandlerExtractor
HttpClientCallExtractor
ImportExtractor
FunctionCallExtractor
RawSQLExtractor
ORMExtractor
StoredProcedureExtractor
DataSourceExtractor
ConfigurationExtractor
IngressExtractor
DeploymentExtractor
```

Extractors create facts and unresolved references. Linkers resolve symbols and create graph edges. This separation avoids embedding framework-specific assumptions in the graph store.

## 24. Entity Graph and Lineage Store

Add a replaceable `LineageStore` port. The MVP may use MongoDB; a graph database can be introduced later without changing FastAPI, MCP, Agent, or application-service contracts.

```python
class LineageStore(Protocol):
    async def upsert_entities(self, entities: list[object]) -> None: ...
    async def upsert_edges(self, edges: list[object]) -> None: ...
    async def delete_file_graph(
        self,
        repository_id: str,
        path: str,
    ) -> None: ...
    async def traverse(
        self,
        start_entity_ids: list[str],
        direction: str,
        target_types: set[str],
        allowed_edge_types: set[str],
        max_depth: int,
    ) -> list[object]: ...
```

### 24.1 Stable Entity Keys and Versioned Entities

Separate logical identity from a commit-specific location:

```text
API endpoint:
api_endpoint:{service}:{method}:{normalized_path}

Function:
function:{repository}:{module}:{qualified_name}

UI element:
ui_element:{repository}:{route}:{component}:{selector_or_text}

SQL:
sql:{repository}:{normalized_sql_hash}

Data source:
data_source:{environment}:{service}:{database_name}
```

Entity versions contain repository, graph generation, commit, path, line range, extractor, and evidence.

### 24.2 Edge Types

```text
RENDERS
CONTAINS
TRIGGERS
CALLS_API
ROUTES_TO
HANDLED_BY
CALLS
INVOKES
EXECUTES
CALLS_PROCEDURE
READS_FROM
WRITES_TO
ACCESSES
CONFIGURED_BY
RESOLVED_FROM
DEPLOYED_AS
```

Every edge records resolution type, confidence, commit, repository, generation, and source evidence.

Confidence classes:

```text
verified_runtime
verified_static
config_resolved
naming_heuristic
embedding_match
llm_inferred
unknown
```

LLM-inferred edges are never equivalent to AST/config/runtime-verified edges.

## 25. UI/API-to-Database Lineage

The target lineage is:

```text
URL
-> frontend route
-> page/component
-> button/UI element
-> event handler
-> HTTP request
-> gateway/ingress rewrite
-> backend API endpoint
-> controller
-> service
-> repository/DAO
-> raw SQL/ORM/stored procedure
-> database/table
-> connection configuration
-> ConfigMap/Secret reference
```

Vector search discovers candidates. The Entity Graph establishes verifiable relationships. The LLM explains retrieved evidence but does not invent missing hops.

### 25.1 Start from Any Entity

Users do not need to start from the UI. A known endpoint may be used directly:

```text
POST /api/orders/search
-> handler
-> service
-> repository
-> SQL
-> data source
-> connection configuration
```

Generic trace request:

```json
{
  "start": {
    "entity_type": "api_endpoint",
    "http_method": "POST",
    "path": "/api/orders/search",
    "service": "order-service",
    "environment": "production"
  },
  "direction": "downstream",
  "target_types": [
    "sql_query",
    "stored_procedure",
    "data_source",
    "connection_config"
  ],
  "max_depth": 10
}
```

Traversal supports:

- downstream: API to SQL/database;
- upstream: table/database to APIs/pages;
- both: full impact analysis.

Traversal requires cycle detection, maximum depth, maximum result count, timeout, edge allowlists, active-generation filtering, and repository/environment authorization.

### 25.2 Ambiguous and Branching Results

Endpoint identity should include method, path, service/host, environment, and deployed version when available. If multiple endpoints match, return candidates rather than guessing.

One endpoint may use multiple databases or queries based on runtime conditions. Preserve all paths and annotate conditions, confidence, evidence, and unknowns.

### 25.3 SQL Semantics

- Raw SQL: return the normalized SQL template and evidence.
- ORM: return the ORM expression and confirmed tables; do not fabricate compiled SQL.
- Stored procedure: return the procedure name and definition when indexed.
- Dynamic SQL: return confirmed fragments and mark the result partial.

### 25.4 Connection Security

Never index or return database passwords. Return a masked connection description and the configuration reference:

```text
Database type: PostgreSQL
Host: orders-db.prod.svc
Port: 5432
Database: orders
Variable: ORDERS_DATABASE_URL
Secret reference: order-system/order-db-secret#DATABASE_URL
Masked URI: postgresql://***:***@orders-db.prod.svc:5432/orders
```

Authorization applies before traversal, retrieval, and evidence fetch. Log access without logging credentials or unnecessary sensitive data.

### 25.5 Static-First, Runtime-Assisted

Static analysis may be insufficient for dynamic URLs, feature flags, dependency injection, gateway rewrites, dynamic SQL, ORM compilation, and deployment drift. Optional runtime evidence may include browser/network traces, API gateway logs, OpenTelemetry spans, application spans, and database audit records.

Runtime evidence validates the production path; static analysis remains the baseline graph.

## 26. Entity Graph Full Scan and Incremental Update

### 26.1 Full Graph Scan

Use shadow graph generations:

```mermaid
flowchart TD
    A[Pin repository HEAD commit] --> B[Create shadow graph generation]
    B --> C[Parse all supported files]
    C --> D[Extract entities]
    D --> E[Resolve local and cross-repo edges]
    E --> F[Validate graph]
    F -->|Pass| G[Activate generation]
    F -->|Fail| H[Keep previous generation]
    G --> I[Clean old generation asynchronously]
```

Graph validation includes:

- duplicate stable keys;
- dangling source/target references;
- incompatible entity/edge types;
- unexpected entity-count drops;
- unresolved-symbol and inferred-edge ratios;
- route-to-handler and query-to-data-source coverage;
- sampled API-to-database paths;
- repository/commit/path evidence validity.

### 26.2 Incremental Graph Update

For changed files:

1. identify entities previously produced from the file;
2. remove or deactivate edges whose evidence came from the old file version;
3. parse the new file once;
4. extract new entities and unresolved references;
5. relink impacted neighboring symbols;
6. enqueue cross-repo link resolution when exported routes or symbols change.

Stable entity keys prevent unaffected cross-repo references from depending on physical version IDs.

## 27. Model Requirements

No additional model is required for the first Entity Graph implementation.

| Capability | Primary mechanism |
| --- | --- |
| Function/class/route extraction | AST and framework extractors |
| YAML/JSON/deployment extraction | deterministic parsers |
| SQL/table/procedure extraction | SQL parser and ORM extractors |
| Symbol/call resolution | symbol tables, import resolution, and rule-based linkers |
| Candidate document/entity discovery | existing text embedding model |
| Natural-language query planning and explanation | existing general LLM |

Optional later additions must be justified by evaluation:

- code embedding model when the current embedding model has poor code/API/SQL Recall@K;
- reranker when cross-repository candidate ranking is weak;
- specialized code model for unfamiliar frameworks or complex dynamic code.

Any model-generated relationship is a candidate edge marked `llm_inferred` until static or runtime evidence verifies it.

## 28. Additional APIs and MCP/Agent Tools

### FastAPI

```text
POST   /v1/repositories
POST   /v1/repositories/{repository_id}/scan
POST   /v1/repositories/{repository_id}/deactivate
POST   /v1/repositories/{repository_id}/activate
DELETE /v1/repositories/{repository_id}?purge=true

POST   /v1/lineage/resolve
POST   /v1/lineage/trace
POST   /v1/lineage/ui-to-database
GET    /v1/entities/{entity_id}
GET    /v1/evidence/{evidence_id}
```

### MCP/Agent Read-Only Tools

```text
search
fetch
list_repositories
get_index_status
resolve_url
find_ui_element
trace_ui_action
trace_api_route
trace_to_database
get_sql_lineage
get_data_source
fetch_evidence
```

These adapters call application services and never access MongoDB, the Vector DB, or the Lineage Store directly.

## 29. Revised Delivery Sequence

1. Implement repository registry, model/storage ports, MongoDB, and in-memory vector adapter.
2. Implement repository-scoped incremental and monthly full-reconcile workflows.
3. Implement Markdown/text retrieval and grounded answers.
4. Inventory actual languages, frameworks, deployment formats, and legacy file patterns.
5. Build a single-stack lineage proof of concept, for example React -> HTTP -> FastAPI -> service -> SQLAlchemy/raw SQL -> PostgreSQL.
6. Add AST/IR parsing, extractor planning, caching, and deterministic entity/edge extraction.
7. Add shadow graph generations, validation, and incremental graph updates.
8. Add repository catalog routing and hybrid shared/dedicated/partitioned collections.
9. Add arbitrary-node upstream/downstream lineage APIs.
10. Add runtime evidence only where static analysis cannot provide sufficient confidence.
11. Expose stable read-only capabilities through MCP and Agent tools.

The system should progress from reliable document retrieval to evidence-backed code lineage. Agent behavior is added only after the underlying retrieval and graph contracts are stable and measurable.
