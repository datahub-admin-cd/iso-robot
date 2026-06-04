from __future__ import annotations

import asyncio
import io
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from iso_robot.config import Settings
from iso_robot.domain.heuristics import heuristic_controls_from_text
from iso_robot.domain.llm_service import chat_json_object
from iso_robot.helpers.pdf_text import extract_pdf_text, extract_pdf_text_with_page_markers
from iso_robot.helpers.text_chunk import chunk_by_chars
from iso_robot.integrations.document_intelligence import analyze_pdf_bytes_marked
from iso_robot.repositories.control_repository import ControlRepository
from iso_robot.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)

_PAGE_MARKER_RE = re.compile(r"\[PAGE\s+(\d+)\]", re.I)


def _control_system_prompt(*, has_page_markers: bool) -> str:
    base = (
        "You extract auditable requirements from regulatory and policy text (IMO circulars, ISO annexes, "
        "maritime guidance, internal policies). "
        "A control is one distinct obligation, requirement, recommendation to act, mandatory procedure, "
        "or measurable rule — not document titles, headers, or generic introductions.\n"
        "**Granularity:** Prefer **many** controls: **one JSON object per numbered clause, bullet, "
        "sub-clause, table row, or distinct sentence** that states a duty or recommendation. "
        "Do **not** merge unrelated bullets into one control_text. "
        "A page with 12 bullets should yield about 12 controls unless two are duplicate wording.\n"
        "Return exactly one JSON object with key \"controls\" whose value is an array of objects. "
        'Each object MUST include \"control_text\" (string): one requirement, verbatim or lightly edited for clarity. '
        "Optional: section_ref, framework. "
    )
    page_instr = (
        "Optional key \"source_page\" (integer): **required whenever possible**. "
        "The segment may contain lines `[PAGE N]` from the PDF layout — use the **N** from the **most recent** "
        "`[PAGE N]` line **above** that requirement's text in this segment. "
        "If a requirement spans pages, use the page where it begins.\n"
        if has_page_markers
        else 'Optional \"source_page\" (integer) only if this segment explicitly shows a page number near the clause.\n'
    )
    tail = (
        "Include **every** distinct requirement in the supplied text. Merge exact duplicates only. "
        "Respond with JSON only — no markdown fences, no commentary outside the JSON object."
    )
    return base + page_instr + tail


def _build_control_user_prompt(
    label: str,
    chunk: str,
    chunk_index: int,
    total_chunks: int,
    *,
    retry: bool,
    has_page_markers: bool,
) -> str:
    if total_chunks == 1:
        scope = (
            "SCOPE: FULL DOCUMENT — the text below is the entire PDF as extracted text "
            "(Azure Document Intelligence layout). Extract controls from all parts."
        )
    else:
        scope = (
            f"SCOPE: SEGMENT {chunk_index + 1} OF {total_chunks} — overlapping slices of the same PDF. "
            "Extract every requirement that appears in this segment only."
        )
    retry_note = ""
    if retry:
        retry_note = (
            "\n\nYour previous answer had too few or empty \"control_text\" entries. "
            "Re-read the text: emit **one control per bullet / numbered item / distinct obligation**. "
            "Every item MUST use the key \"control_text\". "
            "Do not return a single merged paragraph unless the source truly has only one requirement.\n"
        )
    markers_note = ""
    if has_page_markers:
        markers_note = (
            "\n\nPAGE NUMBERS: This text contains `[PAGE N]` lines inserted before each layout paragraph. "
            "For **every** control, set `\"source_page\"` to the integer N from the `[PAGE N]` line that applies "
            "(the last `[PAGE N]` still above that requirement).\n"
        )
    return (
        f"Document: {label}\n"
        f"{scope}\n"
        f"{retry_note}"
        f"{markers_note}\n"
        f"--- BEGIN TEXT ---\n{chunk}\n--- END TEXT ---\n\n"
        'Respond with JSON only: {"controls": [{"control_text": "...", "section_ref": null, "framework": null, "source_page": null}]}'
    )


def _chunk_has_page_markers(chunk: str) -> bool:
    return bool(_PAGE_MARKER_RE.search(chunk))


def _annotate_pages_from_chunk_markers(chunk: str, controls: List[Dict[str, Any]]) -> None:
    """Fill missing source_page using `[PAGE N]` positions vs control text location in chunk."""
    markers = [(m.start(), int(m.group(1))) for m in _PAGE_MARKER_RE.finditer(chunk)]
    if not markers:
        return
    for c in controls:
        if c.get("source_page") is not None:
            continue
        ct = (c.get("control_text") or "").strip()
        if not ct:
            continue
        needle = ct[:120]
        pos = chunk.find(needle)
        if pos < 0 and ct.split():
            pos = chunk.find(ct.split()[0][:50])
        if pos < 0:
            pos = 0
        page = markers[0][1]
        for start, pn in markers:
            if start <= pos:
                page = pn
            else:
                break
        c["source_page"] = page


def _control_text_from_llm_item(item: Dict[str, Any]) -> Optional[str]:
    for key in (
        "control_text",
        "text",
        "requirement",
        "statement",
        "description",
        "summary",
        "control",
        "obligation",
        "measure",
    ):
        v = item.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if len(s) >= 12:
            return s
    return None


async def _llm_controls_from_chunk(
    settings: Settings,
    document_label: str,
    chunk: str,
    chunk_index: int,
    total_chunks: int,
    *,
    retry: bool,
) -> List[Dict[str, Any]]:
    has_pm = _chunk_has_page_markers(chunk)
    user = _build_control_user_prompt(
        document_label,
        chunk,
        chunk_index,
        total_chunks,
        retry=retry,
        has_page_markers=has_pm,
    )
    data = await chat_json_object(settings, system=_control_system_prompt(has_page_markers=has_pm), user=user)
    raw = data.get("controls")
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            s = item.strip()
            if len(s) >= 12:
                out.append(
                    {
                        "control_text": s[:2000],
                        "section_ref": None,
                        "framework": None,
                        "source_page": None,
                    }
                )
            continue
        if not isinstance(item, dict):
            continue
        text = _control_text_from_llm_item(item)
        if not text:
            continue
        page = item.get("source_page")
        try:
            page_i = int(page) if page is not None else None
        except (TypeError, ValueError):
            page_i = None
        out.append(
            {
                "control_text": text[:2000],
                "section_ref": item.get("section_ref"),
                "framework": item.get("framework"),
                "source_page": page_i,
            }
        )
    _annotate_pages_from_chunk_markers(chunk, out)
    return out


async def _llm_try_chunk(
    settings: Settings,
    label: str,
    chunk: str,
    chunk_index: int,
    total_chunks: int,
) -> List[Dict[str, Any]]:
    first = await _llm_controls_from_chunk(
        settings, label, chunk, chunk_index, total_chunks, retry=False
    )
    if first:
        return first
    if len(chunk.strip()) < 400:
        return []
    logger.warning(
        "Chunk %s/%s: LLM returned no controls (%d chars); retrying.",
        chunk_index + 1,
        total_chunks,
        len(chunk.strip()),
    )
    return await _llm_controls_from_chunk(
        settings, label, chunk, chunk_index, total_chunks, retry=True
    )


_MIN_CHUNK_CHARS_FOR_EMPTY_HEURISTIC = 80


async def _controls_from_chunk_with_fallback(
    settings: Settings,
    label: str,
    chunk: str,
    chunk_index: int,
    total_chunks: int,
) -> List[Dict[str, Any]]:
    chunk_stripped = chunk.strip()

    async def _heuristic_salvage() -> List[Dict[str, Any]]:
        if not settings.control_extraction_heuristic_on_empty:
            return []
        if len(chunk_stripped) < _MIN_CHUNK_CHARS_FOR_EMPTY_HEURISTIC:
            return []
        logger.warning(
            "No LLM controls for chunk %s; heuristic salvage (CONTROL_EXTRACTION_HEURISTIC_ON_EMPTY=true).",
            chunk_index,
        )
        rows = heuristic_controls_from_text(chunk, chunk_index)
        _annotate_pages_from_chunk_markers(chunk, rows)
        return rows

    try:
        part = await _llm_try_chunk(settings, label, chunk, chunk_index, total_chunks)
        if part:
            return part
        if settings.control_extraction_heuristic_on_empty and settings.use_llm_fallback:
            return await _heuristic_salvage()
        return []
    except Exception as exc:
        logger.warning("LLM control extraction failed chunk=%s: %s", chunk_index, exc)
        if settings.use_llm_fallback:
            rows = heuristic_controls_from_text(chunk, chunk_index)
            _annotate_pages_from_chunk_markers(chunk, rows)
            return rows
        raise


def _dedupe_key(control_text: str) -> str:
    return " ".join(control_text.lower().split())[:260]


async def _layout_or_local_pdf_text(settings: Settings, path: Path, pdf_bytes: bytes) -> str:
    local = extract_pdf_text_with_page_markers(path)
    try:
        di = await analyze_pdf_bytes_marked(settings, pdf_bytes)
        di_len = len((di or "").strip())
        local_len = len((local or "").strip())
        # DI can occasionally return very little text for long PDFs; prefer local text if it
        # is materially richer so the control extractor sees the full document context.
        if local_len > max(di_len * 2, di_len + 2000):
            logger.warning(
                "DI text seems sparse for %s (di=%d chars, local=%d chars); using local extraction.",
                path.name,
                di_len,
                local_len,
            )
            return local
        return di
    except Exception as exc:
        msg = str(exc)
        # DI can reject very large image-heavy PDFs with InvalidContentLength.
        # In that case, retry DI in small page batches before giving up.
        if "InvalidContentLength" in msg or "input image is too large" in msg.lower():
            logger.warning(
                "Document Intelligence rejected full PDF (%s); retrying in small page batches: %s",
                path.name,
                msg,
            )
            by_parts = await _analyze_pdf_in_small_page_batches(settings, path)
            if by_parts.strip():
                return by_parts
        logger.warning("Document Intelligence failed (%s); using local PDF text with page markers.", exc)
        if local.strip():
            return local
        return extract_pdf_text(path)


def _shift_page_markers(text: str, page_offset: int) -> str:
    if page_offset <= 0:
        return text
    return _PAGE_MARKER_RE.sub(lambda m: f"[PAGE {int(m.group(1)) + page_offset}]", text)


async def _analyze_pdf_in_small_page_batches(
    settings: Settings,
    path: Path,
    pages_per_batch: int = 2,
) -> str:
    """Best-effort DI fallback for oversized image PDFs: run layout on tiny page batches."""
    try:
        from pypdf import PdfReader, PdfWriter
    except Exception:
        return ""
    try:
        reader = await asyncio.to_thread(PdfReader, str(path))
    except Exception:
        return ""
    total = len(reader.pages)
    if total <= 0:
        return ""
    parts: List[str] = []
    for start in range(0, total, max(1, pages_per_batch)):
        end = min(total, start + max(1, pages_per_batch))
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        buf = io.BytesIO()
        try:
            await asyncio.to_thread(writer.write, buf)
            seg_bytes = buf.getvalue()
            seg_text = await analyze_pdf_bytes_marked(settings, seg_bytes)
            seg_text = _shift_page_markers(seg_text or "", page_offset=start).strip()
            if seg_text:
                parts.append(seg_text)
        except Exception as seg_exc:
            logger.warning(
                "DI batch fallback failed for %s pages %s-%s: %s",
                path.name,
                start + 1,
                end,
                seg_exc,
            )
            continue
    return "\n\n".join(parts).strip()


async def extract_controls_for_document(
    settings: Settings,
    conn: aiosqlite.Connection,
    document_id: str,
    client_org_id: Optional[str] = None,
) -> int:
    doc_repo = DocumentRepository(conn)
    ctrl_repo = ControlRepository(conn)
    row = await doc_repo.get_by_id(document_id)
    if row is None:
        raise ValueError(f"Unknown document_id={document_id}")
    path = Path(str(row["path"]))
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Only PDF extraction is supported; got {path.suffix}")

    await ctrl_repo.delete_for_document(document_id)

    pdf_bytes = await asyncio.to_thread(path.read_bytes)
    layout_text = await _layout_or_local_pdf_text(settings, path, pdf_bytes)
    full = layout_text.strip()
    if not full:
        logger.info("No text extracted for document %s", document_id)
        return 0

    max_single = settings.control_extraction_max_chars_per_call
    chunk_sz = settings.control_extraction_chunk_chars
    overlap = settings.control_extraction_chunk_overlap

    if len(full) <= max_single:
        chunks_list = [full]
        logger.info(
            "Controls extraction: single LLM pass for whole PDF (%d chars) — %s",
            len(full),
            path.name,
        )
    else:
        chunks_list = chunk_by_chars(full, max_chars=chunk_sz, overlap=overlap)
        logger.info(
            "Controls extraction: %d chunks (max %d chars each), total %d chars — %s",
            len(chunks_list),
            chunk_sz,
            len(full),
            path.name,
        )

    total_chunks = len(chunks_list)
    label = f"{row.get('filename') or path.name} ({document_id})"
    seen_keys: set[str] = set()
    running_total = 0

    for i, ch in enumerate(chunks_list):
        part = await _controls_from_chunk_with_fallback(settings, label, ch, i, total_chunks)
        batch: List[Dict[str, Any]] = []
        for c in part:
            ct = (c.get("control_text") or "").strip()
            if not ct:
                continue
            key = _dedupe_key(ct)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            batch.append(
                {
                    "id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "client_org_id": client_org_id,
                    "control_text": ct,
                    "section_ref": str(c["section_ref"]) if c.get("section_ref") else None,
                    "framework": str(c["framework"]) if c.get("framework") else None,
                    "source_page": c.get("source_page"),
                }
            )
        if batch:
            await ctrl_repo.insert_many(batch)
            running_total += len(batch)
            logger.info(
                "Controls chunk %s/%s committed %s rows (running total %s) — %s",
                i + 1,
                total_chunks,
                len(batch),
                running_total,
                path.name,
            )

    logger.info(
        "Controls extraction finished document=%s rows=%s path=%s",
        document_id,
        running_total,
        path.name,
    )
    return running_total


async def run_extract_controls_job(
    settings: Settings,
    conn: aiosqlite.Connection,
    payload: dict[str, Any],
) -> None:
    raw_ids = payload.get("document_ids")
    doc_repo = DocumentRepository(conn)
    if isinstance(raw_ids, list) and raw_ids:
        doc_ids = [str(x) for x in raw_ids]
    else:
        rows = await doc_repo.list_all(limit=500, offset=0)
        doc_ids = [str(r["id"]) for r in rows if str(r.get("path", "")).lower().endswith(".pdf")]

    cid = payload.get("client_org_id")
    for doc_id in doc_ids:
        try:
            await extract_controls_for_document(settings, conn, doc_id, client_org_id=cid)
        except Exception:
            logger.exception("Extract failed for document %s", doc_id)
            if not settings.use_llm_fallback:
                raise
