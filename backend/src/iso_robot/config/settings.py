from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _backend_root() -> Path:
    """Parent of `src/` — the `backend/` package root in the repo."""
    return Path(__file__).resolve().parents[3]


def _repo_root() -> Path:
    """Monorepo root (parent of `backend/`)."""
    return _backend_root().parent


def _existing_env_files() -> tuple[str, ...]:
    paths = []
    for p in (_backend_root() / ".env", _repo_root() / ".env"):
        if p.is_file():
            paths.append(str(p))
    return tuple(paths)


class Settings(BaseSettings):
    """Application settings from environment and `.env` (backend first, repo root second)."""

    model_config = SettingsConfigDict(
        env_file=_existing_env_files() or None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    # If unset, chat requests omit "temperature" and the deployment default applies.
    # Reasoning models (e.g. o4-mini) reject non-default temperature — leave unset.
    azure_openai_temperature: Optional[float] = Field(default=None)
    log_level: str = "INFO"
    
    # ── JWT auth (sliding window) ─────────────────────────────────────────────
    jwt_secret_key: str = Field(
        default="dev-only-change-me",
        description="HMAC secret for signing JWTs. Override in .env.",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_idle_minutes: int = Field(
        default=30,
        description="Sliding window: token lifetime per request. Each authenticated "
                    "request issues a fresh token, resetting this idle timeout.",
    )

    database_path: str = Field(
        default_factory=lambda: str(_backend_root() / "data" / "db.sqlite"),
    )
    documents_dir: str = Field(
        default_factory=lambda: str(_repo_root() / "all-docs"),
    )
    use_llm_fallback: bool = Field(
        default=True,
        description="Use local PDF text + heuristics when Azure OpenAI or Document Intelligence fail.",
    )
    control_extraction_max_chars_per_call: int = Field(
        default=100_000,
        description="If Document Intelligence text is under this size, send it in ONE LLM call (whole PDF flow).",
    )
    control_extraction_chunk_chars: int = Field(
        default=48_000,
        description="When text exceeds max_chars_per_call, split into chunks of this size.",
    )
    control_extraction_chunk_overlap: int = Field(
        default=1200,
        description="Overlap between chunks to avoid cutting requirements in half.",
    )
    control_extraction_heuristic_on_empty: bool = Field(
        default=False,
        description="If True, run keyword heuristics when the LLM returns no controls. Default False — use LLM + retry only.",
    )
    control_extraction_di_pages_per_batch: int = Field(
        default=2,
        description="When DI rejects a full PDF, analyze this many pages per DI call (streaming mode saves controls after each batch).",
    )
    control_extraction_min_local_chars: int = Field(
        default=5000,
        description="Prefer local PDF text over slow DI page-batching when at least this many characters are extractable locally.",
    )

    def resolved_database_path(self) -> Path:
        return Path(self.database_path).expanduser().resolve()

    def resolved_documents_dir(self) -> Path:
        return Path(self.documents_dir).expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
