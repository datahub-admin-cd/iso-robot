from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'.")
    content: str = Field(..., description="Message text.")


class ChatRequest(BaseModel):
    """Body for the SSE chat endpoint. The org is taken from the auth token, never here."""

    question: str = Field(..., min_length=1, description="The user's question.")
    history: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Prior conversation turns for multi-turn context (optional).",
    )
    top_k: Optional[int] = Field(
        default=None, ge=1, le=50, description="Override the number of chunks retrieved."
    )
    stage_hint: Optional[str] = Field(
        default=None,
        description="Optional retrieval bias: risk | issue | control | org | classification | tag | assignment.",
    )


class ChatReindexRequest(BaseModel):
    """Body for the admin reindex endpoint."""

    client_org_id: Optional[str] = Field(
        default=None,
        description="Org to reindex. Admins may target any org; non-admins are forced to their own.",
    )
