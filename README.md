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

Docker Compose starts MongoDB, waits for it to become healthy, builds the Python
development image, and runs the Phase 0 unit-test suite inside the
`knowledge-base` container.

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
docker compose up --build --abort-on-container-exit \
  --exit-code-from knowledge-base
```

The `knowledge-base` container exits after the tests finish because Phase 0 is a
library foundation and does not yet include a long-running API. To run MongoDB
alone while developing locally:

```bash
docker compose up -d mongodb
```

Stop containers while preserving MongoDB data:

```bash
docker compose down
```

To intentionally delete the local MongoDB volume as well:

```bash
docker compose down -v
```

Inside Compose, the application uses `mongodb://mongodb:27017`. Programs running
directly on the host use `mongodb://localhost:${MONGODB_PORT:-27017}`.

Phase 0 includes domain models, storage/model ports, OpenAI-compatible HTTP model
adapters, a MongoDB document-store adapter, an in-memory vector store, fake model
adapters, and unit tests. It intentionally contains no production Vector DB SDK.
The Docker artifacts are a reproducible development and test baseline; production
API images and Kubernetes deployment remain part of later delivery phases.
