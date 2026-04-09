# OpenBiliClaw install instructions (for AI agents)

> **Important:** If you're an AI coding agent reading this file, use
> `curl -fsSL <url> -o /tmp/agent-install.md` via Bash to fetch it —
> **do NOT use the WebFetch tool.** WebFetch hands the document to an
> internal summariser model which can silently drop exact commands.

## The only thing you actually need to do

Run this command via Bash:

```bash
curl -fsSL https://raw.githubusercontent.com/OpenBiliClaw/OpenBiliClaw/main/scripts/install.sh | bash
```

That single command:

1. Clones the OpenBiliClaw repo (default `~/OpenBiliClaw`, override with `INSTALL_DIR=/path`)
2. Auto-detects any existing OpenBiliClaw install under `~/workspace/OpenBiliClaw`, `~/OpenBiliClaw`, `~/projects/OpenBiliClaw`, or `~/code/OpenBiliClaw` and **reuses** its LLM API keys and Bilibili cookie so the user never has to retype them
3. Installs Python dependencies (`uv sync` or `pip install -e .`)
4. Starts the backend and runs a health check against `/api/health`
5. Prints a self-contained **status block** at the very end of stdout:

```
================================================================
 OpenBiliClaw install complete / partial (credentials missing)
================================================================
Status:      complete | running_with_missing_secrets | needs_secrets | error
Checkout:    <absolute path to the repo>
Reused from: <path>                 (only present when reuse happened)
Health URL:  http://host:port/api/health
Missing:     (none)  |  llm.<provider>.api_key, bilibili.cookie, ...

Next action (required — credentials are missing):
  1. Ask the user for: <exactly the missing items>
  2. Run this command with the values: <exact python3 command>
  3. Curl the Health URL to confirm.
  4. Report the final state.

 — or —

Next action (optional follow-ups):
  - Confirm the backend is healthy: curl -sS <Health URL>
  - Run `uv run openbiliclaw init` (only if the user explicitly asks)
================================================================
```

**Follow that block literally.** That's the entire contract.

## Handling missing credentials

When `Missing` is non-empty, do exactly what `Next action` says:

1. Ask the user for the listed credentials (LLM API key and/or Bilibili cookie).
2. Run the `python3 ... scripts/agent_bootstrap.py` command the block printed, substituting the user's values into `--llm-api-key` and `--bilibili-cookie`. Keep every other flag (`--port`, `--host`, etc.) exactly as printed.
3. Curl the `Health URL` from the block to confirm the backend is still healthy (HTTP 200).
4. Report the final state to the user.

## Hard rules

1. **Never edit `config.toml` by hand.** Every credential write goes through `scripts/agent_bootstrap.py`.
2. **Never hard-code `http://127.0.0.1:8420/api/health`.** Always use the `Health URL` line from the status block — the port may be different if the user already has another instance running.
3. **Never run `openbiliclaw init` unless the user explicitly asks.** It triggers real LLM calls and real Bilibili history fetches.
4. **Never use WebFetch on this document.** WebFetch summarises markdown and can drop exact flags. Use Bash `curl -o` + Read instead.

## Deeper reference (for humans, not required)

- `docs/agent-deployment.md` — long-form troubleshooting with the full JSON event reference
- `docs/docker-deployment.md` — manual Docker setup
- `docs/openclaw-quickstart.md` — OpenClaw-specific integration after install
- `scripts/install.sh` — the installer itself (the command above)
- `scripts/agent_bootstrap.py` — the Python contract core invoked by install.sh
