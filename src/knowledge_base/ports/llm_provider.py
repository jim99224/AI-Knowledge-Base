from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


class LLMProvider(Protocol):
    @property
    def model_id(self) -> str: ...

    async def generate(
        self,
        messages: Sequence[ChatMessage],
        temperature: float = 0.0,
    ) -> str: ...
