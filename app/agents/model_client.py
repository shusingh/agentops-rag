from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


class ModelClient(Protocol):
    async def complete_json(self, prompt: str, schema: type[TModel]) -> TModel:
        ...

    async def complete_text(self, prompt: str) -> str:
        ...


class FakeModelClient:
    async def complete_json(self, prompt: str, schema: type[TModel]) -> TModel:
        raise NotImplementedError("FakeModelClient does not infer arbitrary JSON schemas")

    async def complete_text(self, prompt: str) -> str:
        return prompt
