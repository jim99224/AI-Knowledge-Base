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

Phase 0 includes domain models, storage/model ports, OpenAI-compatible HTTP model
adapters, a MongoDB document-store adapter, an in-memory vector store, fake model
adapters, and unit tests. It intentionally contains no production Vector DB SDK.

