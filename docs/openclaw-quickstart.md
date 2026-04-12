# OpenClaw 接入指南

> 给 OpenClaw 和维护者的完整落地说明：怎么部署 OpenBiliClaw、怎么初始化、怎么让 OpenClaw 调用、以及日常怎么用。

## 适用场景

当你希望 OpenClaw 在当前仓库里直接调用 OpenBiliClaw 的学习与推荐能力时，使用这份指南。

当前接入方式不是 Python SDK 注册，而是：

1. 仓库根目录提供 workspace skill：`skills/openbiliclaw-adapter/SKILL.md`
2. skill 通过 JSON CLI bridge 调用：`src/openbiliclaw/integrations/openclaw/cli.py`
3. CLI bridge 再调用内部 adapter operation

## 部署策略

推荐按目标机器能力决定：

1. 目标机器有 Docker：优先 Docker 部署
2. 目标机器没有 Docker：退回本地 Python 部署

这个判断很直接，因为 OpenClaw 最终只需要两件事：

1. 能发现仓库里的 workspace skill
2. 能执行 skill 要求的命令

## 前置条件

- 已克隆当前仓库
- 目标机器可用 Python 3.11+
- 可以访问当前配置所需的 LLM provider
- 准备好 B 站 Cookie，或能在交互式终端里现场输入
- 如果走 Docker 路径，目标机器上还需要可用的 Docker / Docker Compose

## 方案 A：Docker 优先

这是推荐方案，适合长期运行 OpenBiliClaw 后端。

### 1. 启动后端容器

在仓库根目录执行：

```bash
docker compose up -d --build
```

当前 compose 定义见：

- `docker-compose.yml`
- `Dockerfile`

默认行为：

- 容器名：`openbiliclaw-backend`
- 对外端口：`8420`
- 运行时目录：`/app/runtime`
- 配置、数据、日志分别持久化在 Docker volumes 中

### 2. 完成首次初始化

容器启动后，必须先做一次初始化：

```bash
docker exec -it openbiliclaw-backend openbiliclaw init
```

初始化会顺序完成：

1. 检查 LLM 配置
2. 检查 B 站认证
3. 拉取历史
4. 写入事件并分析偏好
5. 生成初始画像
6. 自动补首轮内容池

如果当前终端是交互式，且还没配置 API Key 或 B 站 Cookie，`init` 会直接引导输入。

### 3. 给 OpenClaw 保留一个本地 workspace

即使后端跑在 Docker 里，OpenClaw 仍需要能看到当前仓库，因为它要发现：

- `skills/openbiliclaw-adapter/SKILL.md`

同时，宿主机最好保留一套轻量 Python 环境，方便 OpenClaw 或维护者执行 bridge / doctor 命令：

```bash
# 推荐：使用 uv（更快）
uv sync

# 或使用传统 venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 方案 B：本地部署

当目标机器没有 Docker 时，直接全本地部署。

在仓库根目录执行：

```bash
# 推荐：使用 uv（更快）
uv sync
cp config.example.toml config.toml

# 或使用传统 venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.toml config.toml
```

然后初始化：

```bash
openbiliclaw init
```

如果 `config.toml` 里还缺 API Key 或 B 站 Cookie，交互式终端会提示补齐。

## OpenClaw 如何发现并调用

OpenClaw 当前应直接发现仓库里的 workspace skill：

- `skills/openbiliclaw-adapter/SKILL.md`

这个 skill 不直接实现推荐逻辑，而是要求 OpenClaw 调下面的 CLI bridge：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli <command> [flags]
```

已支持的命令：

- `sync-account`
- `get-profile`
- `runtime-status`
- `recommend --limit 5`
- `recommend --limit 5 --refresh-if-needed`
- `submit-feedback --recommendation-id 7 --feedback-type like`
- `doctor`
- `emit-skill-descriptors`

## 首次初始化后要做什么

不管是 Docker 还是本地部署，初始化完成后都建议做一轮自检。

### Docker 路径最小自检

```bash
docker exec -it openbiliclaw-backend openbiliclaw profile
uv run python -m openbiliclaw.integrations.openclaw.cli doctor
uv run python -m openbiliclaw.integrations.openclaw.cli get-profile
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

### 本地路径最小自检

```bash
openbiliclaw profile
uv run python -m openbiliclaw.integrations.openclaw.cli doctor
uv run python -m openbiliclaw.integrations.openclaw.cli get-profile
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

期望结果：

1. `profile` 能读到画像或至少给出初始化后状态
2. `doctor` 返回 `skill_pack_exists: true`
3. `get-profile` 返回 `{"ok": true, "data": ...}`
4. `recommend --limit 3` 返回推荐列表

## OpenClaw 日常使用流程

推荐给 OpenClaw 的常规使用顺序如下。

### 1. 读当前画像

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli get-profile
```

### 2. 取推荐

优先走快路径：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

### 3. 写反馈

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli submit-feedback \
  --recommendation-id 12 \
  --feedback-type like
```

如果是评论型反馈：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli submit-feedback \
  --recommendation-id 12 \
  --feedback-type comment \
  --note "方向对，但我想看更深一点。"
```

### 4. 查看运行时状态

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli runtime-status
```

### 5. 低频做账户同步

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli sync-account
```

## OpenClaw 调用约定

给 OpenClaw 的规则建议保持为：

1. 优先用 `recommend --limit <n>`，这是快路径
2. 只有明确需要新鲜度检查时，才加 `--refresh-if-needed`
3. 解析 CLI 返回 JSON，不要依赖自然语言输出
4. 如果返回 `{ "ok": false, ... }`，直接上抛错误，不要继续串后续动作
5. 对 `comment` 反馈，必须带 `--note`
6. 把 `doctor` 当成接线排障入口，而不是日常业务命令

## 常见问题

### 1. 不确定该走 Docker 还是本地

按目标机能力判断：

- 有 Docker：优先 Docker
- 没 Docker：本地部署

### 2. `doctor` 失败

优先检查：

- 当前目录是不是仓库根目录
- 虚拟环境是否已激活
- 依赖是否已安装
- `src/openbiliclaw/integrations/openclaw/cli.py` 是否存在
- `skills/openbiliclaw-adapter/SKILL.md` 是否存在

### 3. `get-profile` 或 `recommend` 报未初始化

说明还没有完成初始化：

Docker：

```bash
docker exec -it openbiliclaw-backend openbiliclaw init
```

本地：

```bash
openbiliclaw init
```

### 4. 显式 refresh 太慢

这是预期风险之一。OpenClaw 交互默认应走快路径：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

只有在用户明确要求更强新鲜度时，才触发：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3 --refresh-if-needed
```
