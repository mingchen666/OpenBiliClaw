# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenBiliClaw is an AI Agent for personalized Bilibili content recommendation. It builds a deep psychological profile ("Soul") of users through behavioral analysis, then proactively discovers and recommends content with warm, friend-like explanations. The project is bilingual (Chinese primary, English supported) and in pre-alpha (v0.1-dev).

## Build & Development Commands

### Python Backend

```bash
pip install -e ".[dev]"          # Install with dev dependencies
pytest                           # Run all tests
pytest tests/test_foo.py         # Run single test file
pytest tests/test_foo.py::test_bar  # Run single test
pytest --cov=openbiliclaw        # Tests with coverage
ruff format src/ tests/          # Format code
ruff check src/ tests/           # Lint
mypy src/                        # Type check (strict mode)
```

### Browser Extension (extension/)

```bash
cd extension
npm run build                    # Full build (clean + types + bundle)
npm run typecheck                # Type check only
npm run test                     # Run tests (node --test)
```

### CLI

```bash
openbiliclaw start               # Start daemon
openbiliclaw init                # First-time setup (fetch history + generate profile)
openbiliclaw recommend           # Show recommendations
openbiliclaw profile             # View user portrait
openbiliclaw config-show         # Show current config
openbiliclaw serve-api           # Start FastAPI server (used by Docker)
```

### Docker

```bash
docker compose up -d --build     # Start backend (port 8420)
# Health check: http://127.0.0.1:8420/api/health
```

## Architecture

The system follows a pipeline: **Behavioral Data -> Soul Engine -> Discovery -> Recommendation**.

### Core Pipeline

1. **Soul Engine** (`soul/`) - Transforms raw behavioral events into deep user understanding through 5 layers: Event -> Preference -> Awareness -> Insight -> Soul. Each layer feeds bidirectionally into the next. The `SoulEngine` orchestrates analyzers (`preference_analyzer.py`, `insight_analyzer.py`, `awareness_analyzer.py`) and outputs a `SoulProfile`.

2. **Memory Manager** (`memory/manager.py`) - Coordinates 4 memory types (Core, Episodic, Semantic, Working) across a networked architecture with cross-layer updates and self-editing capabilities.

3. **Discovery Engine** (`discovery/engine.py`) - Finds content via 4 strategies defined in `discovery/strategies/strategies.py`:
   - `SearchStrategy` - generates keywords from soul profile, searches Bilibili
   - `TrendingStrategy` - scans trending channels
   - `ExploreStrategy` - cross-domain exploration outside user's comfort zone
   - `RelatedChainStrategy` - follows related video chains deeply

4. **Recommendation Engine** (`recommendation/engine.py`) - Ranks discovered content against soul profile and generates natural-language explanations for each recommendation.

### Supporting Layers

- **LLM Adapter** (`llm/`) - Multi-provider abstraction. All providers implement `LLMProvider` protocol from `base.py`. `registry.py` handles provider instantiation by name. Supported: OpenAI, Claude, Gemini, DeepSeek, Ollama (local), OpenRouter.

- **Bilibili Integration** (`bilibili/api.py`) - `BilibiliAPIClient` wraps the bilibili-api-python library. Authentication via cookie or QR code (`auth.py`). Browser automation via agent-browser (`browser.py`).

- **FastAPI Backend** (`api/app.py`) - REST API on port 8420 serving the browser extension. Factory function `create_app()` initializes all components. Receives behavior events, serves recommendations, and pushes real-time cognition updates.

- **Storage** (`storage/database.py`) - SQLite with vector index for semantic search. Single database at `data/openbiliclaw.db`.

- **CLI** (`cli.py`) - Typer-based. Entry point: `openbiliclaw.cli:app`.

### Extension <-> Backend Flow

The Chrome extension (`extension/`) captures user behavior on bilibili.com pages via content script (`content/collector.ts`), buffers events in the service worker (`background/service-worker.ts`), and sends them to the FastAPI backend at `http://127.0.0.1:8420`. The popup/side panel (`popup/`) displays recommendations fetched from the same backend.

## Configuration

- Template: `config.example.toml` -> copy to `config.toml` for local use
- `config.toml` is gitignored; never commit it
- Key sections: `[llm]` (provider + API keys), `[bilibili]` (auth), `[scheduler]` (discovery cron), `[storage]` (db path)
- Config logic: `src/openbiliclaw/config.py` with Pydantic validation and env var overrides

## Code Conventions

- Python 3.11+, 4-space indent, 100-char line length
- Type annotations required on all functions (MyPy strict)
- Ruff for formatting and linting (rules: E, W, F, I, N, UP, B, SIM, TCH)
- Test files: `test_<module>.py`, test functions: `test_<behavior>`
- Integration tests requiring real Bilibili credentials: mark with `@pytest.mark.integration`
- Async tests use `asyncio_mode = "auto"` (no manual `@pytest.mark.asyncio` needed)
- Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `perf:`, `ci:`

## Documentation Requirements

When completing a task from `docs/v0.1-todolist.md`, these doc updates are **mandatory**:

1. `docs/modules/<module>.md` - Update "implemented features" table and "public API" section
2. `docs/changelog.md` - Add entry under the relevant milestone
3. `docs/modules/cli.md` - If CLI commands changed
4. `docs/modules/config.md` - If config fields changed

## Development Order

Follow `docs/v0.1-todolist.md` roadmap: Connect -> Understand -> Discover -> Recommend -> Learn -> Extension -> Stable Delivery. Do not skip lower layers to build upper-layer features.
