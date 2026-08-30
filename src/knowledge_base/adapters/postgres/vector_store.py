from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from knowledge_base.domain.models import Chunk
from knowledge_base.ports.stores import VectorMatch


class PgVectorStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def search(
        self,
        query_vector: Sequence[float],
        top_k: int,
        repository_ids: Sequence[str] | None = None,
    ) -> list[VectorMatch]:
        if top_k <= 0:
            return []

        distance = Chunk.embedding.cosine_distance(list(query_vector))
        statement = (
            select(Chunk, distance.label("distance"))
            .where(Chunk.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )

        if repository_ids:
            repo_ids = [uuid.UUID(value) for value in repository_ids]
            statement = statement.where(Chunk.repository_id.in_(repo_ids))

        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()

        return [
            VectorMatch(
                chunk_id=str(chunk.id),
                score=max(0.0, 1.0 - float(distance_value)),
                metadata={
                    "repository_id": str(chunk.repository_id),
                    "document_id": str(chunk.document_id),
                    "commit_sha": chunk.commit_sha,
                    **chunk.metadata_,
                },
            )
            for chunk, distance_value in rows
        ]
