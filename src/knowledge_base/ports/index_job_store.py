from typing import Protocol

from knowledge_base.domain.models import IndexJob


class IndexJobStore(Protocol):
    async def create_index_job(self, job: IndexJob) -> None: ...

    async def save_index_job(self, job: IndexJob) -> None: ...

    async def get_index_job(self, job_id: str) -> IndexJob | None: ...
