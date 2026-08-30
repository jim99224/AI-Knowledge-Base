from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from knowledge_base.domain.models import Chunk


class PostgresDocumentStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_chunks(self, chunk_ids: Sequence[str]) -> list[Chunk]:
        if not chunk_ids:
            return []

        ids = [uuid.UUID(value) for value in chunk_ids]
        async with self._session_factory() as session:
            result = await session.execute(select(Chunk).where(Chunk.id.in_(ids)))
            chunks = list(result.scalars())

        by_id = {str(chunk.id): chunk for chunk in chunks}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]
