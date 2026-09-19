from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import get_settings

StructuredCall = Callable[[type[BaseModel], str, str], Awaitable[BaseModel]]


class GraphError(RuntimeError):
    pass


def chat_model() -> ChatOpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise GraphError("OPENAI_API_KEY is not set")
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        reasoning_effort=settings.openai_reasoning_effort,
    )


async def complete_structured(schema: type[BaseModel], system: str, user: str) -> Any:
    model = chat_model().with_structured_output(schema)
    return await model.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
