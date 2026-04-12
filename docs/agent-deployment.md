# Agent 一键部署指南

[← 返回 README](../README.md)

这份文档写给**AI 编码智能体**（Claude Code / Codex CLI / OpenClaw / Cursor Agent 等），同时也适合人类维护者作为部署参考。

当用户在 README 里看到那段复制粘贴的 "Agent deployment prompt"，把它整段粘贴给任意一个编码智能体时，智能体要能够仅凭这段文字独立完成 OpenBiliClaw 后端的完整部署、配置补齐和健康自检。本文是那段 prompt 的完整操作契约。

---

## 你的任务（给 AI 智能体）

你收到了一个包含以下意图的指令：

> 在当前环境把 OpenBiliClaw 后端跑起来，如果用户机器上已经有另一份 OpenBiliClaw 目录，就把它里面的 API Key / Cookie / 登录态复用过来，不要反复问用户。如果确实缺关键凭据，就明确告诉用户需要补什么。

你应当按以下顺序工作，并**不要擅自跳过步骤**。

### 1. 核对前置条件

必须存在：

- `python3`（3.11+）或 `uv`
- `git`

可选（存在就优先用）：

- `docker` + `docker compose`（部署后端首选）
- 另一份已经配好的 OpenBiliClaw 目录（用来复用 API Key 和 Cookie）

用户通常会在**项目目录外**直接发起这个部署，例如：

```bash
mkdir -p ~/workspace/openbiliclaw-new
cd ~/workspace/openbiliclaw-new
```

### 2. 获取代码

- 如果当前目录已经是 OpenBiliClaw 仓库（存在 `pyproject.toml` 和 `config.example.toml`），直接用当前目录。
- 否则确认当前目录为空，然后 `git clone https://github.com/OpenBiliClaw/OpenBiliClaw.git .`。
- 永远不要 `rm -rf` 一个非空目录。

### 3. 定位已有的 OpenBiliClaw 安装（关键）

这是最重要的一步。用户明确表示**希望复用旧项目里的凭据**，你的默认行为就是找到那份旧安装。

按以下顺序查找（找到第一份有效的就停止）：

1. 用户明确告诉你的路径。
2. 常见工作区路径：
   - `~/workspace/OpenBiliClaw`
   - `~/OpenBiliClaw`
   - `~/projects/OpenBiliClaw`
   - `~/code/OpenBiliClaw`
3. 在家目录下做一次 `find`：

```bash
find ~ -maxdepth 4 -type f -name "config.toml" -path "*OpenBiliClaw*" 2>/dev/null
```

一份"有效"的安装必须满足：

- 存在 `config.toml`（不是 `config.example.toml`）
- `config.toml` 里至少有一个非空的 `api_key`（`llm.openai.api_key` / `llm.gemini.api_key` / `llm.deepseek.api_key` / `llm.claude.api_key` / `llm.openrouter.api_key`）或者
- 存在 `data/bilibili_cookie.json`

如果找不到任何一份符合条件的安装，**向用户问一次**："我没找到已有的 OpenBiliClaw 安装，请告诉我路径，或者确认我现场帮你从 0 填配置。" 只问一次。

### 4. 跑部署脚本

用户的仓库里有 `scripts/agent_bootstrap.py`。这是你唯一需要直接调用的自动化入口。

```bash
python3 scripts/agent_bootstrap.py \
  --project-dir . \
  --mode auto \
  --reuse-from /ABSOLUTE/PATH/TO/EXISTING/OpenBiliClaw
```

如果没有找到已有安装，就去掉 `--reuse-from`。

关键参数：

| 参数 | 含义 |
|------|------|
| `--project-dir` | 目标仓库目录。默认当前目录。 |
| `--mode` | `auto`（默认，有 Docker 走 Docker，否则 local）、`docker`、`local`。 |
| `--reuse-from PATH` | 从另一份 OpenBiliClaw 目录复用 API Key / Bilibili Cookie。 |
| `--provider NAME` | 强制切换默认 LLM provider（openai/claude/gemini/deepseek/ollama/openrouter）。 |
| `--llm-api-key KEY` | 给当前（或 `--provider` 指定的）provider 写入 API Key。 |
| `--bilibili-cookie VALUE` | 直接写入 Bilibili Cookie，同时落盘到 `data/bilibili_cookie.json`。 |
| `--skip-start` | 只准备配置和依赖，不启动服务。 |
| `--skip-health-check` | 启动服务但不等 `/api/health`。 |
| `--host`, `--port` | local 模式下 API 监听地址，默认 `127.0.0.1:8420`。 |

脚本不会交互地向 stdin 要凭据——所有补齐都通过命令行参数传入。脚本向 stdout 输出两类行：

1. 以 `[bootstrap]` 开头的人类可读日志。
2. 以 `BOOTSTRAP_STATUS:` 开头的机器 JSON 行，你**必须**解析这些行来判断状态。

典型 JSON 事件：

```json
{"status": "ok", "message": "repo_ready", "details": {...}}
{"status": "ok", "message": "secrets_reused", "details": {"reused": [...], "source": "..."}}
{"status": "ok", "message": "config_summary", "details": {"provider": "gemini", "missing": [], "has_cookie_file": true}}
{"status": "ok", "message": "mode_selected", "details": {"mode": "local"}}
{"status": "ok", "message": "dependencies_installed", "details": {}}
{"status": "ok", "message": "local_started", "details": {"host": "127.0.0.1", "port": 8420}}
{"status": "complete", "message": "backend_healthy", "details": {"health_url": "...", "missing": []}}
```

最后一行的 `status` 字段是整体结论：

- `complete` — 一切就绪，API 已起来，没有缺失凭据。
- `running_with_missing_secrets` — 服务起来了但还缺 API Key 或 Cookie，某些功能会降级。
- `needs_secrets` — 没启动（或 `--skip-start`）且还缺凭据。
- `error` — 失败，`message` 和 `details.step` 会告诉你哪一步炸了。

### 5. 处理 `missing`

`config_summary` 事件里的 `details.missing` 是一个字符串数组，最多包含两类：

- `llm.<provider>.api_key` — 默认 provider 没有 API Key。
- `bilibili.cookie` — Bilibili 还没登录。

**不要从 `http://127.0.0.1:8420/api/health` 硬编码 URL**。永远从最后一条 `BOOTSTRAP_STATUS` 的 `details.health_url` 字段读，这样当用户自定义了 `--host`/`--port` 时也能命中正确的地址。

如果 `missing` 不为空：

1. 向用户清晰地一次性说明还需要什么，例如：

   > 我已经把 OpenBiliClaw 后端跑起来了（`<details.health_url>` 正常），但还缺 Bilibili Cookie。请你打开 https://www.bilibili.com 登录后，在开发者工具里复制完整的 Cookie 字符串，贴回来给我。

2. 拿到凭据后，**不要**手动改 `config.toml`。重新调用同一个脚本，把第 4 步用过的所有 flag（`--port`、`--host`、`--reuse-from` 等）原封不动地带上，再追加新的凭据参数：

   ```bash
   python3 scripts/agent_bootstrap.py --project-dir . --bilibili-cookie "$USER_PROVIDED_COOKIE" --skip-start [原有 --port / --host / --reuse-from ...]
   ```

   这样会把凭据写进 `config.toml` 和 `data/bilibili_cookie.json`，但不会重启服务，也不会意外回落到默认 8420 端口和另一个实例抢占地址。

3. 再次解析输出里的 `config_summary.missing`，确认为 `[]`。

### 6. 健康自检

脚本会自己轮询 `details.health_url`（默认 `/api/health`）。如果 `--skip-health-check` 被加上，或你想手动确认：

```bash
curl -sS "$HEALTH_URL"   # $HEALTH_URL 来自最后一条 BOOTSTRAP_STATUS 的 details.health_url
# → {"status":"ok","service":"openbiliclaw-api"}
```

如果使用 Docker 模式，健康检查之后建议再跑一次：

```bash
docker exec -it openbiliclaw-backend openbiliclaw config-show
```

### 7. （可选）首次初始化

当凭据都齐了，可以在本地模式下手动跑一次：

```bash
uv run openbiliclaw init         # 如果使用 uv
# 或
.venv/bin/openbiliclaw init       # 如果走 pip + venv
```

Docker 模式：

```bash
docker exec -it openbiliclaw-backend openbiliclaw init
```

`init` 会拉取 B 站历史、生成初始画像并补齐第一轮内容池。这一步**不是**部署必需的——服务跑起来就算部署完成——但用户通常希望你顺手做完。

### 8. 报告给用户

最终用简短的一段话告诉用户：

1. 用的是 `docker` 还是 `local` 模式。
2. 从哪儿复用了哪些凭据（如果有）。
3. 服务监听地址 + 健康检查 URL。
4. 如果还缺凭据：清晰的下一步指令。
5. 下一条推荐命令（如 `openbiliclaw recommend`）。

---

## 失败排查（供智能体自查）

| 故障 | 典型 `details.step` / 症状 | 处理 |
|------|--------------------------|------|
| `git` 不存在 | `clone` 步骤报错 | 提示用户先装 git，不要继续 |
| `config.example.toml` 缺失 | `config` 步骤报错 | 说明当前目录不是 OpenBiliClaw 仓库，要求确认路径 |
| `--reuse-from` 指向的目录无效 | `reuse` 步骤报错 | 回到第 3 步，重新搜索或问用户 |
| 依赖安装失败 | `install` 步骤报错 | 检查 Python 版本（需要 3.11+），尝试 `--install-cmd` 指定另一种命令 |
| Docker up 失败 | `docker_up` 步骤报错 | 降级到 `--mode local` 重新跑 |
| 健康检查超时 | `backend_healthy` 没出现，`health_check_failed` 出现 | 查看 `logs/agent-bootstrap.log`（local 模式）或 `docker compose logs` |

---

## 给人类维护者的备注

- 脚本故意不要求 stdin 输入。这是为了让各种 AI 编码智能体（很多都不支持交互式 TTY）都能照样跑完整个流程。
- 脚本写 config 的逻辑是**原位重写单行字符串**，不会改动你自己的注释或非标准字段。
- `data/bilibili_cookie.json` 是 OpenBiliClaw 运行时真正用的 cookie 源，`config.toml` 里的 `bilibili.cookie` 只是一个同步镜像。复用时两份都会被同步。
- 如果你想把这套流程接到 CI 或无人值守的部署里，可以把 `--skip-health-check` 加上，然后自行用任务队列处理健康轮询。

---

## 与其它部署指南的关系

- `docs/docker-deployment.md` — 手动 Docker 步骤（给人看的）。
- `docs/openclaw-quickstart.md` — OpenClaw 调用 OpenBiliClaw 的 CLI bridge 契约。
- 本文 `docs/agent-deployment.md` — AI 智能体**一键**部署契约。

三份文档互补：docker-deployment 说明 Docker 怎么跑；openclaw-quickstart 说明部署完成后 OpenClaw 怎么调；本文说明**从零到完成部署**这一跳该怎么走。
