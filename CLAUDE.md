# CLAUDE.md - AI 狼人杀项目开发指南

## 项目愿景
开发一个 AI 驱动的狼人杀应用程序，初期作为人类玩家的“陪玩/练习工具”，后期扩展为 AI 竞技场及观察者平台。

## 核心架构原则 (Technical Principles)
1. **混合驱动逻辑 (Hybrid Drive)**
   - 规则引擎（Python）：负责状态流转、技能结算、投票与胜负判定。
   - LLM 引擎（如 Gemini/GPT）：负责发言策略、身份博弈与行为选择。
2. **模块化设计 (Extensibility)**
   - 角色系统、阶段流程、Agent 接入必须可替换。
   - 前端 UI 与对局逻辑解耦，后端通过协议输出标准状态与事件。
3. **故障可降级 (Graceful Degradation)**
   - 模型不可用、输出异常时，系统必须自动回退规则策略，保证对局可继续。

## 当前阶段 (Current Phase: MVP 可完整跑局)
截至 2026-03，MVP 后端已支持从建局到结束的完整链路。

- **已实现模块**
  - `backend/app/api/schemas.py`: 协议模型与动作结构定义。
  - `backend/app/core/roles.py`: 基础角色能力定义。
  - `backend/app/core/rules.py`: MVP 阵容与胜负规则。
  - `backend/app/core/game.py`: 基于 `transitions` 的状态机和动作结算。
  - `backend/app/agents/base_agent.py`: Agent 抽象基类。
  - `backend/app/agents/model_agent.py`: 模型优先、规则回退的 Agent 实现。
  - `backend/app/agents/llm_client.py`: `mock/openai/gemini` 可插拔模型客户端。
  - `backend/app/main.py`: FastAPI 接口层 + WebSocket。

- **可用接口**
  - `POST /games/create`
  - `GET /games/{game_id}/state/{slot_id}`
  - `POST /games/{game_id}/actions/{slot_id}`
  - `POST /games/{game_id}/step`
  - `POST /games/{game_id}/autoplay`
  - `GET /games/{game_id}/history`

- **模式**
  - 标准 6 人局（2 狼、1 预、1 女、2 民）。

## MVP 定义 (Definition of Done)
满足以下条件视为 MVP 完成：
1. 可创建一局并进入运行态。
2. 可按阶段接收并校验动作。
3. 可自动推进到游戏结束（含模型失败回退）。
4. 可按玩家视角返回遮蔽后的状态。
5. 核心引擎和接口层有自动化测试覆盖。

## 关键业务逻辑 (Business Logic)
- **信息遮蔽**: `game.get_game_state(viewer_slot_id)` 按身份返回可见字段。
- **状态机驱动**: 夜晚和白天流程通过 `transitions` 统一调度。
- **动作校验**: 每个阶段仅接受合法动作（详见 `PROTOCOLS.md`）。
- **回退机制**: LLM 不可用或输出非法 JSON 时，自动降级规则策略。

## 核心戒律 (Core Tenets)
1. **绝对信息隔离 (God's Perspective Isolation)**
   - 严禁将角色视野外信息注入对应 Agent 的上下文。
2. **协议先行 (Protocol First)**
   - 任何接口或动作变更，必须先更新 `PROTOCOLS.md`。
3. **可回放与可测试 (Replayable and Testable)**
   - 对局关键事件必须写入 `history`，便于复盘和测试。

## 下阶段优先级 (Next Priorities)
1. **人机混局调度**
   - 自动驱动 AI，遇到人类回合暂停并等待提交动作。
2. **Agent Prompt 分层落地**
   - 按 `AGENTS_SPEC.md` 拆分 system/context/instruction 模板。
3. **前端 MVP 联调**
   - 建局、状态刷新、动作提交、历史事件展示。
4. **可观测性**
   - 增加对局日志级别、错误码、关键耗时指标。

## 常用命令 (Common Commands)
- **安装依赖**: `pip install -r backend/requirements.txt`
- **启动后端**: 在 `backend` 目录执行 `python -m app.main`
- **运行测试**: 在 `backend` 目录执行 `python -m pytest tests -q`
