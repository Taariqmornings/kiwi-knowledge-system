"""
LlmService — streams responses from the local Ollama server.

We use Ollama instead of in-process llama-cpp-python because Ollama ships
prebuilt llama.cpp binaries that work on CPUs without AVX-512 (Kaby Lake etc.).
The user starts `ollama serve` once; we talk to it over loopback HTTP.
"""
from __future__ import annotations

import json
import logging
from typing import Iterator, Optional

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:1b"


class LlmService:
    @classmethod
    def is_loaded(cls) -> bool:
        """Cheap reachability check — does an Ollama daemon answer on the loopback?"""
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=1.5) as r:
                return r.status == 200
        except Exception:
            return False

    @classmethod
    def stream_chat(
        cls,
        prompt: str,
        max_tokens: int = 320,
        temperature: float = 0.4,
        stop: Optional[list[str]] = None,
        model: str = DEFAULT_MODEL,
    ) -> Iterator[str]:
        """
        Yield response chunks from Ollama's /api/generate streaming endpoint.
        Each chunk is one JSON-line; we extract its "response" text field.
        """
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": max_tokens,
                "stop": stop or ["<end_of_turn>", "</s>"],
            },
            "raw": True,  # prompt is already Gemma-formatted by RagService
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw_line in resp:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk = obj.get("response", "")
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        return
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Cannot reach Ollama at {OLLAMA_URL}. Is `ollama serve` running? ({e})"
            )
