"""Configuration management for OpenBiliClaw.

Loads configuration from TOML files with environment variable overrides.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Default config search paths
_CONFIG_FILENAMES = ["config.toml", "config.local.toml"]
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class LLMProviderConfig:
    """Configuration for a single LLM provider."""

    api_key: str = ""
    model: str = ""
    base_url: str = ""


@dataclass
class LLMConfig:
    """LLM configuration."""

    default_provider: str = "openai"
    openai: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    claude: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    deepseek: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    ollama: LLMProviderConfig = field(default_factory=LLMProviderConfig)


@dataclass
class BilibiliConfig:
    """Bilibili connection configuration."""

    auth_method: str = "cookie"
    cookie: str = ""
    browser_executable: str = ""
    browser_headed: bool = False


@dataclass
class SchedulerConfig:
    """Scheduler configuration."""

    enabled: bool = True
    discovery_cron: str = "0 */4 * * *"


@dataclass
class StorageConfig:
    """Storage configuration."""

    db_path: str = "data/openbiliclaw.db"


@dataclass
class Config:
    """Root configuration for OpenBiliClaw."""

    language: str = "zh"
    data_dir: str = "data"
    llm: LLMConfig = field(default_factory=LLMConfig)
    bilibili: BilibiliConfig = field(default_factory=BilibiliConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)

    @property
    def data_path(self) -> Path:
        """Resolved data directory path."""
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = _PROJECT_ROOT / p
        return p


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts, override values take precedence."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides.

    Environment variables follow the pattern: OPENBILICLAW_SECTION_KEY
    e.g. OPENBILICLAW_LLM_DEFAULT_PROVIDER=claude
    """
    prefix = "OPENBILICLAW_"
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        parts = env_key[len(prefix) :].lower().split("_")
        current = raw
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = env_value
    return raw


def _build_config(raw: dict[str, Any]) -> Config:
    """Build a Config dataclass from raw dict."""
    general = raw.get("general", {})
    llm_raw = raw.get("llm", {})
    bili_raw = raw.get("bilibili", {})
    sched_raw = raw.get("scheduler", {})
    store_raw = raw.get("storage", {})

    llm = LLMConfig(
        default_provider=llm_raw.get("default_provider", "openai"),
        openai=LLMProviderConfig(**llm_raw.get("openai", {})),
        claude=LLMProviderConfig(**llm_raw.get("claude", {})),
        deepseek=LLMProviderConfig(**llm_raw.get("deepseek", {})),
        ollama=LLMProviderConfig(**llm_raw.get("ollama", {})),
    )

    browser_raw = bili_raw.pop("browser", {})
    bilibili = BilibiliConfig(
        auth_method=bili_raw.get("auth_method", "cookie"),
        cookie=bili_raw.get("cookie", ""),
        browser_executable=browser_raw.get("executable", ""),
        browser_headed=browser_raw.get("headed", False),
    )

    return Config(
        language=general.get("language", "zh"),
        data_dir=general.get("data_dir", "data"),
        llm=llm,
        bilibili=bilibili,
        scheduler=SchedulerConfig(**sched_raw),
        storage=StorageConfig(**store_raw),
    )


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from TOML file(s).

    Resolution order:
    1. Explicit path (if provided)
    2. config.toml in project root
    3. config.local.toml overrides (if exists)
    4. Environment variable overrides

    Args:
        config_path: Optional explicit path to config file.

    Returns:
        Populated Config instance.
    """
    raw: dict[str, Any] = {}

    if config_path:
        path = Path(config_path)
        if path.exists():
            with open(path, "rb") as f:
                raw = tomllib.load(f)
    else:
        for filename in _CONFIG_FILENAMES:
            path = _PROJECT_ROOT / filename
            if path.exists():
                with open(path, "rb") as f:
                    file_data = tomllib.load(f)
                raw = _deep_merge(raw, file_data)

    raw = _apply_env_overrides(raw)
    return _build_config(raw)
