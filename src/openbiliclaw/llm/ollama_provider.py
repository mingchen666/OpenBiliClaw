"""Ollama LLM provider via OpenAI-compatible API."""

from __future__ import annotations

import logging

import httpx

from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(OpenAIProvider):
    """Ollama provider using the local OpenAI-compatible endpoint.

    Inherits chat-completions support from OpenAIProvider via Ollama's
    ``/v1/chat/completions`` shim. Adds an ``embed()`` method that hits
    Ollama's *native* ``/api/embeddings`` endpoint — that route is more
    direct than the OpenAI-compat embedding shim and is the canonical
    integration point recommended by the Ollama docs.
    """

    def __init__(
        self,
        api_key: str = "ollama",
        model: str = "llama3",
        base_url: str = "http://localhost:11434/v1",
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            provider_name="ollama",
        )

    def _native_root(self) -> str:
        """Strip the OpenAI-compat ``/v1`` suffix to reach Ollama's native API root."""
        return self.base_url.rstrip("/").rsplit("/v1", 1)[0]

    async def embed(self, text: str, *, model: str = "bge-m3") -> list[float]:
        """Get text embedding via Ollama's native ``/api/embeddings`` endpoint.

        Recommended local fallback model is ``bge-m3`` (multilingual,
        1024-dim). Other Ollama embedding models also work — just pass
        ``model=...``.

        Returns an empty list on failure so callers can degrade gracefully
        (the embedding service treats empty vectors as "no embedding").
        """
        url = f"{self._native_root()}/api/embeddings"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    json={"model": model, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
        except Exception:
            logger.warning(
                "Ollama embedding failed (model=%s, url=%s)",
                model,
                url,
                exc_info=True,
            )
            return []

        vec = data.get("embedding")
        if not isinstance(vec, list):
            return []
        return [float(v) for v in vec if isinstance(v, int | float)]
