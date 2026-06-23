"""Retrieval service: turn a question into org-scoped knowledge chunks.

Always filters on ``client_org_id`` (hard tenant isolation) and applies a light
stage "boost" based on question intent (risk / issue / control / ...), as
described in chatbot.pdf. Boosting is done by merging an intent-filtered search
into an unfiltered one so general context is never lost.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence

from iso_robot.config import Settings
from iso_robot.domain.embedding_service import embed_text, is_embedding_configured
from iso_robot.repositories.vector_repository import VectorRepository

logger = logging.getLogger(__name__)

# Valid stage labels (must match IndexingService.STAGE_*).
_VALID_STAGES = {"org", "control", "issue", "classification", "risk", "tag", "assignment"}

# Intent keyword -> stages to boost.
_INTENT_RULES: List[tuple[re.Pattern[str], Sequence[str]]] = [
    (re.compile(r"\b(risk|risks|residual|inherent|likelihood|mitigat)", re.I), ("risk", "tag", "assignment")),
    (re.compile(r"\b(issue|issues|incident|event|news)", re.I), ("issue", "classification")),
    (re.compile(r"\b(control|controls|policy|requirement|clause|compliance|iso)", re.I), ("control",)),
    (re.compile(r"\b(owner|owners|assigned|assignment|responsible|accountable)", re.I), ("assignment", "risk")),
    (re.compile(r"\b(tag|tags|process|function|kpi|department|region)", re.I), ("tag", "risk")),
    (re.compile(r"\b(pestel|swot|tvra|classification|threat|vulnerab)", re.I), ("classification",)),
    (re.compile(r"\b(company|organisation|organization|profile|industry|demograph|headquarter|employee)", re.I), ("org",)),
]

# Score increment applied to chunks that match the question's intent stages.
_BOOST = 0.05


class RetrievalService:
    def __init__(self, settings: Settings, vector_repo: VectorRepository) -> None:
        self._settings = settings
        self._vectors = vector_repo

    @property
    def available(self) -> bool:
        return self._vectors.enabled and is_embedding_configured(self._settings)

    def stages_for(self, question: str, stage_hint: Optional[str]) -> List[str]:
        if stage_hint and stage_hint.strip().lower() in _VALID_STAGES:
            return [stage_hint.strip().lower()]
        stages: List[str] = []
        for pattern, mapped in _INTENT_RULES:
            if pattern.search(question or ""):
                for s in mapped:
                    if s not in stages:
                        stages.append(s)
        return stages

    async def retrieve(
        self,
        *,
        client_org_id: str,
        question: str,
        top_k: Optional[int] = None,
        stage_hint: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.available or not client_org_id or not (question or "").strip():
            return []

        k = int(top_k or self._settings.chatbot_top_k)
        try:
            query_vector = await embed_text(self._settings, question)
        except Exception:  # noqa: BLE001 — embedding failure => no context, not an error
            logger.exception("Failed to embed chat question for org=%s", client_org_id)
            return []
        if not query_vector:
            return []

        # Always retrieve broadly (all stages) so general context is available.
        base = await self._vectors.search(
            client_org_id=client_org_id, query_vector=query_vector, top_k=k
        )
        ranked: Dict[str, Dict[str, Any]] = {}
        for hit in base:
            hit_id = str(hit.get("id"))
            ranked[hit_id] = {**hit, "rank_score": float(hit.get("score") or 0.0)}

        # Boost: re-rank intent-matching stages slightly higher.
        stages = self.stages_for(question, stage_hint)
        if stages:
            focused = await self._vectors.search(
                client_org_id=client_org_id,
                query_vector=query_vector,
                top_k=k,
                stages=stages,
            )
            for hit in focused:
                hit_id = str(hit.get("id"))
                entry = ranked.get(hit_id) or {**hit, "rank_score": float(hit.get("score") or 0.0)}
                entry["rank_score"] = float(entry.get("rank_score") or 0.0) + _BOOST
                ranked[hit_id] = entry

        ordered = sorted(ranked.values(), key=lambda x: x["rank_score"], reverse=True)
        return [self._to_source(h) for h in ordered[:k]]

    @staticmethod
    def _to_source(hit: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": hit.get("id"),
            "entity_type": hit.get("entity_type"),
            "entity_id": hit.get("entity_id"),
            "stage": hit.get("stage"),
            "source_table": hit.get("source_table"),
            "score": hit.get("score"),
            "text": hit.get("text") or "",
        }
