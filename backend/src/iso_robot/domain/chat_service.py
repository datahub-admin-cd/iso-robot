"""Chat service: grounded, streaming answers from retrieved org context.

Uses the async Azure OpenAI client with ``stream=True`` so the handler can relay
token deltas over SSE. The model is instructed to answer only from the supplied
context and to cite sources, keeping answers grounded in the org's real records.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from iso_robot.config import Settings
from iso_robot.integrations.azure_openai import get_async_azure_openai_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the ISO Robot assistant for enterprise risk management. "
    "Answer the user's question using ONLY the CONTEXT provided below. The context "
    "contains records belonging to the user's own organisation (org profile, controls, "
    "issues, risk classifications, published risks, tags, and owner assignments), each "
    "prefixed with a bracket number like [1]. "
    "Cite the sources you rely on using their bracket numbers, e.g. [1], [2]. "
    "If the answer is not present in the context, clearly say you do not have that "
    "information for this organisation. Be concise and specific, and never invent "
    "records, numbers, owners, or citations."
)


def _deployment(settings: Settings) -> str:
    name = (settings.azure_openai_deployment or "").strip()
    if not name:
        raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is not set (chat deployment name).")
    return name


def build_context(sources: Sequence[Dict[str, Any]], max_chars: int) -> str:
    """Render retrieved sources into a numbered context block, bounded by max_chars."""
    blocks: List[str] = []
    total = 0
    for i, source in enumerate(sources, start=1):
        header = f"[{i}] {source.get('entity_type') or 'record'} {source.get('entity_id') or ''}".strip()
        body = (source.get("text") or "").strip()
        block = f"{header}\n{body}"
        if blocks and total + len(block) > max_chars:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n".join(blocks)


def _history_messages(history: Optional[Sequence[Any]]) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    for item in history or []:
        if isinstance(item, dict):
            role, content = item.get("role"), item.get("content")
        else:
            role, content = getattr(item, "role", None), getattr(item, "content", None)
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)})
    return messages


def build_messages(
    settings: Settings,
    *,
    question: str,
    sources: Sequence[Dict[str, Any]],
    history: Optional[Sequence[Any]] = None,
) -> List[Dict[str, str]]:
    context = build_context(sources, settings.chatbot_max_context_chars)
    messages: List[Dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(_history_messages(history))
    user_block = (
        "CONTEXT:\n"
        f"{context if context else '(no organisation knowledge was retrieved)'}\n\n"
        f"QUESTION: {question}"
    )
    messages.append({"role": "user", "content": user_block})
    return messages


async def stream_answer(
    settings: Settings,
    *,
    question: str,
    sources: Sequence[Dict[str, Any]],
    history: Optional[Sequence[Any]] = None,
) -> AsyncIterator[str]:
    """Yield answer token deltas from Azure OpenAI streaming chat completions."""
    client = get_async_azure_openai_client(settings)
    if client is None:
        raise RuntimeError(
            "Azure OpenAI is not configured (AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_KEY)."
        )
    deployment = _deployment(settings)
    messages = build_messages(settings, question=question, sources=sources, history=history)

    kwargs: Dict[str, Any] = {"model": deployment, "messages": messages, "stream": True}
    if settings.azure_openai_temperature is not None:
        kwargs["temperature"] = settings.azure_openai_temperature

    stream = await client.chat.completions.create(**kwargs)
    async for chunk in stream:
        choices = getattr(chunk, "choices", None)
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        content = getattr(delta, "content", None) if delta is not None else None
        if content:
            yield content
