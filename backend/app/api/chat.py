"""
/api/chat — offline RAG chat endpoint.

Streams the answer token-by-token via Server-Sent Events so the UI feels
responsive even though CPU generation takes several seconds.

Protocol:
  event: sources    data: {"sources": [{n, article_id, archive_id, title, archive_title, path, summary}, …]}
  event: token      data: "<single token text>"
  event: token      data: "<more text>"
  …
  event: done       data: {}

(Sources are sent BEFORE the first token so the UI can show citation chips
 the moment text starts appearing.)
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.services.rag_service import RagService
from app.services.llm_service import LlmService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []  # [{role: "user"|"assistant", content: str}, …]


# Reused across requests — model load is the slow step
_load_lock = threading.Lock()
_load_state = {"loading": False, "error": None}


def _sse(event: str, data) -> bytes:
    """Format one SSE event."""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@router.post("/ask")
def chat_ask(req: ChatRequest):
    """SSE-stream a RAG answer to the user's question."""
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required.")

    question = req.question.strip()

    def generate() -> Iterator[bytes]:
        # ── Retrieval (always synchronous, < 100 ms) ─────────────────
        db: Optional[Session] = None
        try:
            db = SessionLocal()
            sources = RagService.retrieve(db, question, top_k=8)
        finally:
            if db:
                db.close()

        # Emit sources first so the UI can render citation chips immediately
        yield _sse("sources", {
            "sources": [
                {
                    "n": s.n,
                    "article_id": s.article_id,
                    "archive_id": s.archive_id,
                    "title": s.title,
                    "archive_title": s.archive_title,
                    "path": s.path,
                }
                for s in sources
            ]
        })

        # ── Generation ───────────────────────────────────────────────
        if not LlmService.is_loaded():
            yield _sse("error", {
                "message": "Ollama is not running. Start it with `ollama serve` and ensure gemma3:1b is pulled."
            })
            yield _sse("done", {})
            return

        prompt = RagService.build_prompt(question, sources, history=req.history)
        try:
            # JSON-encode every token so leading spaces and embedded newlines
            # (e.g. "\n\n" between paragraphs) survive SSE transit intact.
            # max_tokens=768 (~2.5k chars) — enough for a thorough answer with
            # examples + bullet list. The model still uses its natural stop
            # tokens to end early on short answers; this cap only kicks in
            # for genuinely long responses, preventing the mid-sentence cut.
            for token in LlmService.stream_chat(prompt, max_tokens=768, temperature=0.4):
                yield _sse("token", json.dumps(token, ensure_ascii=False))
        except Exception as e:
            logger.exception("LLM generation failed")
            yield _sse("error", {"message": f"Generation error: {e}"})

        yield _sse("done", {})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/status")
def chat_status():
    """Quick health check the UI can use to know if Ollama is reachable."""
    from app.services.llm_service import OLLAMA_URL, DEFAULT_MODEL
    return {
        "backend": "ollama",
        "ollama_url": OLLAMA_URL,
        "model": DEFAULT_MODEL,
        "reachable": LlmService.is_loaded(),
    }
