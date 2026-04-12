# 架构设计

## 系统概览

OpenBiliClaw 采用分层架构设计，从上到下依次为：

1. **用户交互层** — Chrome 浏览器插件（行为采集 + 推荐展示 + 对话交互）
2. **外部集成层** — OpenClaw adapter / skill wrappers / 本地 API 等对外接入边界
3. **Agent 核心层** — 自研编排器 + Soul Engine + Discovery Engine + Recommendation Engine + Skill System
4. **Bilibili 接入层** — API 优先 + agent-browser 浏览器操作
5. **多层网状记忆存储** — Core / Episodic / Semantic / Working Memory

详见 [项目 Spec](spec.md) 中的架构图。

## 模块职责

### Agent Orchestrator (`agent/`)
- 任务调度和策略决策
- 多步推理和自省优化
- Skill 注册、发现和调度

### Integrations (`integrations/`)
- 对外系统接入边界
- adapter bootstrap、DTO 裁剪和异常翻译
- 将现有 runtime / engine 能力暴露为 OpenClaw 可调用 skill
- 提供 JSON CLI bridge，供仓库内真实 OpenClaw skill pack 调用

### User Soul Engine (`soul/`)
- 行为数据分析和画像构建
- 五层灵魂模型（事件→偏好→觉察→洞察→灵魂）
- `InterestSpeculator` — 兴趣推测与投机性发现
- 苏格拉底式用户对话

### Memory System (`memory/`)
- 五层网状记忆管理
- 跨层关联和双向修正
- 自我编辑和遗忘机制

### Content Discovery (`discovery/`)
- 多策略内容发现
- 内容评估（基于用户 Soul）
- 两阶段候选供给（primary + backfill）
- 候选分层、去重和缓存写入

### Recommendation Engine (`recommendation/`)
- 推荐排序
- 朋友式推荐表达生成
- 缓存候选与实时候选统一排序
- 个性化专题生成
- `PoolCurator` — 推荐侧候选池评分与筛选

### Runtime (`runtime/`)
- 系统生命周期管理和服务编排
- `ContinuousRefreshController` — 后台定时刷新候选池
- `AccountSyncService` — 历史记录、收藏夹、关注列表同步

### Bilibili Client (`bilibili/`)
- B 站 API 封装
- agent-browser 集成
- 登录态 / Cookie 管理

### LLM Providers (`llm/`)
- 统一的多模型接口
- Provider 注册和切换
- 成本和性能监控

### Storage (`storage/`)
- SQLite 数据库管理
- 冷备份、完整性检查与显式修复
- 候选质量信号持久化与数据迁移

## 运行时数据库约束

本地 API 与 CLI 的高频运行路径现在遵循两条约束：

1. **同进程共享单个 SQLite 实例**
   `MemoryManager`、`RecommendationEngine`、`ContentDiscoveryEngine` 会优先复用同一个 `Database`，避免一轮运行里多次 `Database(...).initialize()` 争锁。
2. **启动前先检查、运行中按周期冷备**
   `openbiliclaw start` 会在启动前检查数据库完整性；若健康且超过默认 24 小时未备份，会先生成一份冷备到 `data/backups/`。

数据库修复不在启动路径里自动执行，高风险恢复统一通过 `openbiliclaw db-repair` 触发。

## 对外集成约束

当前 OpenClaw 接入遵循两条边界：

1. **外部集成只通过 adapter 调用内核**
   OpenClaw 不直接访问 SQLite、memory JSON 或内部 engine 组合细节。
2. **skill 只是协议包装，不是业务主链**
   学习、推荐、反馈回流仍由 `runtime/`、`soul/`、`recommendation/` 等模块负责，`integrations/openclaw/skill.py` 只负责对外暴露稳定 handler。
3. **真实 OpenClaw 技能发现走仓库根目录 `skills/`**
   当前仓库通过 `skills/openbiliclaw-adapter/SKILL.md` 提供真实 workspace skill，再由 skill 内部调用 adapter CLI bridge。
