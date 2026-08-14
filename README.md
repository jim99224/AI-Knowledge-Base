# AI Knowledge Base

Python foundation for a repository knowledge base. MongoDB is the canonical text
store, while vector and model providers are replaceable through async protocols.

## Development

Requires Python 3.12 or newer.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check .
mypy src
```

## Docker development environment

Docker Compose builds the Python development image, loads user-provided connection
and model settings from `.env`, and runs the Phase 0 unit-test suite inside the
`knowledge-base` container. It does not create MongoDB or any other external
service.

Create a local environment file:

```bash
cp .env.example .env
```

On Windows PowerShell, use:

```powershell
Copy-Item .env.example .env
```

Validate the Compose configuration and run the stack:

```bash
docker compose config
docker compose run --rm knowledge-base python -c \
  "import os; assert os.environ.get('MONGODB_URI')"
docker compose up --build --abort-on-container-exit \
  --exit-code-from knowledge-base
```

The `env_file: .env` setting explicitly passes every variable in `.env` to the
container. Compose also reads the project `.env` for `${VAR}` interpolation, but
interpolation alone does not inject every variable into a container. The validation
command above checks that `MONGODB_URI` is present without printing the credential.

The `knowledge-base` container exits after the tests finish because Phase 0 is a
library foundation and does not yet include a long-running API. Stop and remove the
test container with:

```bash
docker compose down
```

Set `MONGODB_URI` and `MONGODB_DATABASE` to the connection information supplied by
the user or deployment environment. Do not commit `.env`; it is excluded from Git
and from the Docker build context.

Phase 0 includes domain models, storage/model ports, OpenAI-compatible HTTP model
adapters, a MongoDB document-store adapter, an in-memory vector store, fake model
adapters, and unit tests. It intentionally contains no production Vector DB SDK.
The Docker artifacts are a reproducible development and test baseline; production
API images and Kubernetes deployment remain part of later delivery phases.

## Phase 1 indexing worker

Phase 1 adds repository-scoped GitHub synchronization, Markdown and plain-text
parsing, deterministic structural chunking, MongoDB persistence, batched embedding,
idempotent vector upserts, stale-content deletion, retry state, and index jobs.

Configure `.env` with the user-provided MongoDB connection, GitHub repository, and
embedding endpoint. Leave `GITHUB_BASE_COMMIT` empty for an initial full scan. Set
it to the last successfully indexed commit for an incremental scan.

Run from the host:

```bash
python -m apps.worker.index_repository
```

Or run through Compose:

```bash
docker compose run --rm knowledge-base \
  python -m apps.worker.index_repository
```

Until a production Vector DB is selected, the worker uses the replaceable in-memory
adapter. MongoDB remains the canonical source for documents, chunks, and index-job
state; a later Vector Store adapter can rebuild its index from those records.
