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
