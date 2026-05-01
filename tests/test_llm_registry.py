"""Tests for the LLM registry and fallback behavior."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from openbiliclaw.config import Config, LLMConfig, LLMProviderConfig
from openbiliclaw.llm.base import (
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
)
from openbiliclaw.llm.gemini_provider import gemini_sdk_available
from openbiliclaw.llm.registry import (
    RegistryBuildError,
    build_embedding_service,
    build_llm_registry,
)


@dataclass
class FakeProvider(LLMProvider):
    """Simple fake provider for registry tests."""

    provider_name: str
    responses: list[LLMResponse] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)
    health: bool = True
    call_count: int = 0

    @property
    def name(self) -> str:
        return self.provider_name

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        self.call_count += 1
        if self.errors:
            raise self.errors.pop(0)
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="ok", provider=self.provider_name, model="fake")

    async def health_check(self) -> bool:
        return self.health


def test_build_llm_registry_registers_available_providers() -> None:
    config = Config(
        llm=LLMConfig(
            default_provider="openai",
            openai=LLMProviderConfig(api_key="openai-key"),
            deepseek=LLMProviderConfig(api_key="deepseek-key"),
            ollama=LLMProviderConfig(model="llama3"),
        )
    )

    registry = build_llm_registry(config)

    assert registry.default_provider == "openai"
    assert registry.available_providers == ["openai", "deepseek", "ollama"]


def test_build_llm_registry_registers_openrouter() -> None:
    config = Config(
        llm=LLMConfig(
            default_provider="openrouter",
            openrouter=LLMProviderConfig(
                api_key="openrouter-key",
                model="openai/gpt-4o-mini",
                base_url="https://openrouter.ai/api/v1",
            ),
        )
    )

    registry = build_llm_registry(config)

    assert registry.default_provider == "openrouter"
    assert "openrouter" in registry.available_providers


@pytest.mark.skipif(not gemini_sdk_available(), reason="google-genai is not installed")
def test_build_llm_registry_registers_gemini() -> None:
    config = Config(
        llm=LLMConfig(
            default_provider="gemini",
            gemini=LLMProviderConfig(
                api_key="gemini-key",
                model="gemini-2.5-flash",
            ),
        )
    )

    registry = build_llm_registry(config)

    assert registry.default_provider == "gemini"
    assert "gemini" in registry.available_providers


@pytest.mark.skipif(not gemini_sdk_available(), reason="google-genai is not installed")
def test_build_llm_registry_registers_gemini_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "env-gemini-key")
    config = Config(
        llm=LLMConfig(
            default_provider="gemini",
            gemini=LLMProviderConfig(api_key="", model="gemini-2.5-flash"),
        )
    )

    registry = build_llm_registry(config)

    assert registry.default_provider == "gemini"
    assert "gemini" in registry.available_providers


def test_build_llm_registry_downgrades_default_provider() -> None:
    config = Config(
        llm=LLMConfig(
            default_provider="claude",
            openai=LLMProviderConfig(api_key="openai-key"),
            ollama=LLMProviderConfig(model="llama3"),
        )
    )

    registry = build_llm_registry(config)

    assert registry.default_provider == "openai"


def test_build_llm_registry_requires_explicit_ollama_config() -> None:
    config = Config(
        llm=LLMConfig(
            default_provider="openai",
            ollama=LLMProviderConfig(model="", base_url=""),
        )
    )

    with pytest.raises(RegistryBuildError):
        build_llm_registry(config)


def test_build_llm_registry_registers_ollama_when_base_url_is_explicit() -> None:
    config = Config(
        llm=LLMConfig(
            default_provider="openai",
            ollama=LLMProviderConfig(model="", base_url="http://localhost:11434/v1"),
        )
    )

    registry = build_llm_registry(config)

    assert registry.default_provider == "ollama"
    assert registry.available_providers == ["ollama"]


def test_build_llm_registry_auto_registers_ollama_when_embedding_wants_it() -> None:
    """If [llm.embedding] provider="ollama" but [llm.ollama] is empty, the
    registry must still register Ollama — otherwise build_embedding_service
    can't resolve the provider and silently falls back to the default LLM,
    so the user's "I want local embedding" preference is ignored.

    Real-world manifestation: setup-embedding wizard wrote only
    [llm.embedding] but left [llm.ollama] empty; the backend kept calling
    Gemini's embedding API for every reshuffle even though config said
    ollama.
    """
    from openbiliclaw.config import EmbeddingConfig

    config = Config(
        llm=LLMConfig(
            default_provider="gemini",
            gemini=LLMProviderConfig(api_key="test-key", model="gemini-2.0-flash"),
            ollama=LLMProviderConfig(model="", base_url=""),
            embedding=EmbeddingConfig(provider="ollama", model="bge-m3"),
        )
    )
    registry = build_llm_registry(config)
    assert "ollama" in registry.available_providers
    # Default provider is still gemini (we don't pollute chat selection)
    assert registry.default_provider == "gemini"


def test_build_embedding_service_picks_bge_m3_default_for_ollama(
    tmp_path,
) -> None:
    """When [llm.embedding] provider=ollama and model is empty, the service
    must use bge-m3 — not the gemini-embedding-001 default — so the
    install-time wizard's choice actually takes effect."""
    from openbiliclaw.config import EmbeddingConfig

    config = Config(
        llm=LLMConfig(
            default_provider="ollama",
            ollama=LLMProviderConfig(model="llama3", base_url="http://localhost:11434/v1"),
            embedding=EmbeddingConfig(provider="ollama", model=""),
        ),
        data_dir=str(tmp_path),
    )
    registry = build_llm_registry(config)
    service = build_embedding_service(config, registry)
    assert service is not None
    assert service._model == "bge-m3"


def test_build_embedding_service_respects_explicit_model_override(
    tmp_path,
) -> None:
    """An explicit [llm.embedding] model wins over the per-provider default."""
    from openbiliclaw.config import EmbeddingConfig

    config = Config(
        llm=LLMConfig(
            default_provider="ollama",
            ollama=LLMProviderConfig(model="llama3", base_url="http://localhost:11434/v1"),
            embedding=EmbeddingConfig(provider="ollama", model="custom-embed-v2"),
        ),
        data_dir=str(tmp_path),
    )
    registry = build_llm_registry(config)
    service = build_embedding_service(config, registry)
    assert service is not None
    assert service._model == "custom-embed-v2"


# ---------------------------------------------------------------------------
# Regression: providers without an embeddings endpoint must NOT silently
# return None. v0.3.18 and earlier handed the request to Claude / DeepSeek /
# OpenRouter via ``hasattr(provider, "embed")`` — DeepSeek and OpenRouter
# inherit ``embed`` from OpenAIProvider so the check passed even though
# the backend has no embeddings route, and the call would 404 at runtime.
# v0.3.19+ uses the ``supports_embedding`` flag and falls back to a
# provider that actually works.


def test_build_embedding_service_falls_back_when_claude_is_default(
    tmp_path,
) -> None:
    """Claude has no embeddings API. When it's the default LLM and the
    [llm.embedding] section is empty, embedding must transparently fall
    back to a registered provider that can actually embed (Ollama in this
    fixture). Previously this returned None and the recommendation
    pipeline silently lost diversity / dedup."""
    config = Config(
        llm=LLMConfig(
            default_provider="claude",
            claude=LLMProviderConfig(api_key="claude-key"),
            ollama=LLMProviderConfig(model="llama3", base_url="http://localhost:11434/v1"),
        ),
        data_dir=str(tmp_path),
    )
    registry = build_llm_registry(config)
    service = build_embedding_service(config, registry)
    assert service is not None, "embedding must fall back, not silently disable"
    # Ollama wins the fallback chain (ordered: requested → ollama → gemini → openai).
    assert service._provider.name == "ollama"
    assert service._model == "bge-m3"


def test_build_embedding_service_falls_back_when_deepseek_is_default(
    tmp_path,
) -> None:
    """DeepSeek inherits ``embed`` from OpenAIProvider but its backend has
    no embeddings route. ``supports_embedding=False`` makes the fallback
    chain skip it instead of letting the call 404 at runtime."""
    config = Config(
        llm=LLMConfig(
            default_provider="deepseek",
            deepseek=LLMProviderConfig(api_key="deepseek-key"),
            ollama=LLMProviderConfig(model="llama3", base_url="http://localhost:11434/v1"),
        ),
        data_dir=str(tmp_path),
    )
    registry = build_llm_registry(config)
    service = build_embedding_service(config, registry)
    assert service is not None
    assert service._provider.name == "ollama"


def test_build_embedding_service_returns_none_with_no_capable_provider(
    tmp_path,
) -> None:
    """When no registered provider can actually embed (e.g. Claude only),
    the service returns None — but logs a warning so the failure mode is
    observable, not silent."""
    config = Config(
        llm=LLMConfig(
            default_provider="claude",
            claude=LLMProviderConfig(api_key="claude-key"),
        ),
        data_dir=str(tmp_path),
    )
    registry = build_llm_registry(config)
    service = build_embedding_service(config, registry)
    assert service is None


def test_ollama_base_url_normalised_to_v1_suffix() -> None:
    """Older config.example.toml shipped ``base_url = "http://localhost:11434"``
    (no /v1). The OpenAI SDK then calls ``/chat/completions`` directly,
    which Ollama 404s — its OpenAI-compat shim lives at /v1. The
    registry must auto-append /v1 so users with stale configs still work
    after upgrade. Regression for v0.3.20.1."""
    config = Config(
        llm=LLMConfig(
            default_provider="ollama",
            ollama=LLMProviderConfig(model="llama3", base_url="http://localhost:11434"),
        ),
    )
    registry = build_llm_registry(config)
    ollama_provider = registry.get("ollama")
    assert ollama_provider.base_url.endswith("/v1"), (
        f"expected /v1 suffix, got {ollama_provider.base_url!r}"
    )


def test_openai_primary_with_default_embedding_model_uses_correct_default(
    tmp_path,
) -> None:
    """Pre-v0.3.20.1, config.example.toml hardcoded
    ``[llm.embedding] model = "gemini-embedding-001"`` as the default.
    For OpenAI / Ollama / DeepSeek primaries that string was wrong —
    OpenAI's embeddings endpoint 404s on it. After the fix
    config.example.toml ships ``model = ""`` so the registry's
    per-provider defaults kick in (text-embedding-3-small for OpenAI)."""
    from openbiliclaw.config import EmbeddingConfig

    config = Config(
        llm=LLMConfig(
            default_provider="openai",
            openai=LLMProviderConfig(api_key="openai-key"),
            embedding=EmbeddingConfig(provider="", model=""),
        ),
        data_dir=str(tmp_path),
    )
    registry = build_llm_registry(config)
    service = build_embedding_service(config, registry)
    assert service is not None
    assert service._provider.name == "openai"
    assert service._model == "text-embedding-3-small", (
        f"expected text-embedding-3-small for OpenAI primary, got {service._model!r}"
    )


def test_openai_provider_supports_embedding_flag_is_set() -> None:
    """``supports_embedding`` must be True for providers with a working
    embeddings endpoint and False for those that don't. This is the
    canonical signal used by ``build_embedding_service`` — replacing the
    fragile ``hasattr(provider, "embed")`` check."""
    from openbiliclaw.llm.claude_provider import ClaudeProvider
    from openbiliclaw.llm.gemini_provider import gemini_sdk_available
    from openbiliclaw.llm.ollama_provider import OllamaProvider
    from openbiliclaw.llm.openai_provider import DeepSeekProvider, OpenAIProvider
    from openbiliclaw.llm.openrouter_provider import OpenRouterProvider

    # Have a working /v1/embeddings backend
    assert OpenAIProvider.supports_embedding is True
    assert OllamaProvider.supports_embedding is True

    # Inherit from OpenAIProvider but their backend has no embeddings route
    assert DeepSeekProvider.supports_embedding is False
    assert OpenRouterProvider.supports_embedding is False

    # No embeddings API at all
    assert ClaudeProvider.supports_embedding is False

    if gemini_sdk_available():
        from openbiliclaw.llm.gemini_provider import GeminiProvider

        assert GeminiProvider.supports_embedding is True


@pytest.mark.asyncio
async def test_registry_falls_back_on_retryable_errors() -> None:
    registry = build_llm_registry(
        Config(
            llm=LLMConfig(
                default_provider="openai",
                openai=LLMProviderConfig(api_key="openai-key"),
            )
        ),
        provider_overrides={
            "openai": FakeProvider("openai", errors=[LLMProviderError("down")]),
            "claude": FakeProvider(
                "claude",
                responses=[LLMResponse(content="ok", provider="claude")],
            ),
        },
        fallback_order=["openai", "claude"],
    )

    response = await registry.complete([{"role": "user", "content": "hi"}])

    assert response.provider == "claude"
    assert response.content == "ok"


@pytest.mark.asyncio
async def test_registry_does_not_fallback_on_response_error() -> None:
    registry = build_llm_registry(
        Config(
            llm=LLMConfig(
                default_provider="openai",
                openai=LLMProviderConfig(api_key="openai-key"),
            )
        ),
        provider_overrides={
            "openai": FakeProvider("openai", errors=[LLMResponseError("bad response")]),
            "claude": FakeProvider(
                "claude",
                responses=[LLMResponse(content="ok", provider="claude")],
            ),
        },
        fallback_order=["openai", "claude"],
    )

    with pytest.raises(LLMResponseError):
        await registry.complete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_registry_health_check_all() -> None:
    registry = build_llm_registry(
        Config(
            llm=LLMConfig(
                default_provider="openai",
                openai=LLMProviderConfig(api_key="openai-key"),
            )
        ),
        provider_overrides={
            "openai": FakeProvider("openai", health=True),
            "ollama": FakeProvider("ollama", health=False),
        },
        fallback_order=["openai", "ollama"],
    )

    results = await registry.health_check_all()

    assert results["openai"].available is True
    assert results["openai"].is_default is True
    assert results["ollama"].available is False


@pytest.mark.asyncio
async def test_registry_temporarily_cools_down_rate_limited_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"now": 100.0}
    monkeypatch.setattr("openbiliclaw.llm.base.time.monotonic", lambda: clock["now"])

    openai = FakeProvider("openai", errors=[LLMRateLimitError("limited")])
    claude = FakeProvider("claude")
    registry = build_llm_registry(
        Config(
            llm=LLMConfig(
                default_provider="openai",
                openai=LLMProviderConfig(api_key="openai-key"),
            )
        ),
        provider_overrides={
            "openai": openai,
            "claude": claude,
        },
        fallback_order=["openai", "claude"],
    )

    first = await registry.complete([{"role": "user", "content": "hi"}])
    second = await registry.complete([{"role": "user", "content": "hi again"}])
    clock["now"] += 61
    third = await registry.complete([{"role": "user", "content": "welcome back"}])

    assert first.provider == "claude"
    assert second.provider == "claude"
    assert third.provider == "openai"
    assert openai.call_count == 2


@pytest.mark.asyncio
async def test_embedding_only_ollama_is_excluded_from_chat_fallback() -> None:
    """Regression: when [llm.embedding] provider="ollama" but the user
    never configured a chat model, the registry registers Ollama so the
    embedding service can reach it — but the chat fallback chain MUST
    skip it. Otherwise a primary cloud LLM failure cascades to Ollama,
    which only has bge-m3 on disk, returning 404 from /api/chat and the
    user sees 'All providers failed (openai, ollama)'.
    """
    from openbiliclaw.config import EmbeddingConfig

    cfg = Config(
        llm=LLMConfig(
            default_provider="openai",
            openai=LLMProviderConfig(api_key="openai-key"),
            # Ollama: NO chat model configured. Empty model + non-default.
            ollama=LLMProviderConfig(
                api_key="ollama",
                model="",  # ← critical: no chat model
                base_url="http://localhost:11434/v1",
            ),
            # Embedding wants Ollama → forces registration even though
            # the user never set up chat.
            embedding=EmbeddingConfig(provider="ollama", model="bge-m3"),
        )
    )

    openai_fake = FakeProvider("openai", errors=[LLMProviderError("primary failed")])
    ollama_fake = FakeProvider(
        "ollama",
        # If the bug is back, the chain will reach this — and we'd want
        # to assert that it WASN'T called. We don't queue any responses;
        # if reached it'd raise IndexError.
    )

    registry = build_llm_registry(
        cfg,
        provider_overrides={"openai": openai_fake, "ollama": ollama_fake},
    )

    # Sanity: both providers ARE registered (embedding service still
    # needs to find ollama).
    assert "openai" in registry.available_providers
    assert "ollama" in registry.available_providers

    # ...but the chat fallback should NOT include ollama.
    chat_chain = registry._fallback_order()
    assert "ollama" not in chat_chain, (
        f"embedding-only ollama leaked into chat fallback: {chat_chain}"
    )

    # End-to-end: chat call with a failing primary should raise the
    # primary error (not silently fall through to ollama and 404).
    with pytest.raises(LLMProviderError):
        await registry.complete([{"role": "user", "content": "hi"}])
    # Verify ollama was never called.
    assert ollama_fake.call_count == 0


@pytest.mark.asyncio
async def test_ollama_with_explicit_chat_model_is_chat_capable() -> None:
    """Counterpart to the embedding-only test: when the user configures
    [llm.ollama] model = "llama3", Ollama IS chat-capable and SHOULD
    appear in the chat fallback. (We had to make sure the previous fix
    didn't accidentally exclude every Ollama from chat.)
    """
    cfg = Config(
        llm=LLMConfig(
            default_provider="openai",
            openai=LLMProviderConfig(api_key="openai-key"),
            ollama=LLMProviderConfig(
                api_key="ollama",
                model="llama3",  # ← explicit chat model
                base_url="http://localhost:11434/v1",
            ),
        )
    )

    registry = build_llm_registry(
        cfg,
        provider_overrides={
            "openai": FakeProvider("openai", errors=[LLMProviderError("primary failed")]),
            "ollama": FakeProvider(
                "ollama", responses=[LLMResponse(content="ok", provider="ollama")]
            ),
        },
    )
    chat_chain = registry._fallback_order()
    assert chat_chain == ["openai", "ollama"]

    response = await registry.complete([{"role": "user", "content": "hi"}])
    assert response.provider == "ollama"
