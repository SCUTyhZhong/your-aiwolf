# AI Werewolf

一个基于 FastAPI 的 AI 狼人杀 MVP，包含规则引擎、可插拔 LLM Agent、HTTP API、WebSocket，以及一个最小可玩的 Web UI。

## 当前能力

- 支持标准 6 人局：2 狼、1 预言家、1 女巫、2 平民。
- 支持纯 AI 对局和人机混局。
- 支持 `mock`、`openai`、`gemini`、`minimax` 模型提供方。
- 模型不可用、缺失密钥或返回非法 JSON 时，会自动回退到规则策略，保证对局继续。
- 提供历史记录、待行动槽位查询、单步推进和自动推进接口。
- 自带基础测试覆盖核心对局流程和接口行为。

## 项目结构

- `backend/app/core`: 游戏规则、角色、状态机和结算逻辑。
- `backend/app/agents`: LLM 客户端、Agent 抽象和规则回退实现。
- `backend/app/api`: 协议模型与动作结构。
- `backend/app/static`: 内置调试 UI。
- `backend/tests`: 后端自动化测试。
- `PROTOCOLS.md`: 通信协议。
- `RULES.md`: 游戏规则说明。
- `AGENTS_SPEC.md`: Agent 行为约束。
- `GAMEPLAY_AND_MODEL_SETUP.md`: 更详细的玩法和模型配置说明。

## 快速开始

### 1. 安装依赖

```powershell
cd backend
python -m pip install -r requirements.txt
```

### 2. 启动服务

```powershell
cd backend
python -m app.main
```

默认地址：

- API: `http://127.0.0.1:8000`
- UI: `http://127.0.0.1:8000/ui`

### 3. 运行测试

```powershell
cd backend
python -m pytest tests -q
```

## 常用接口

- `POST /games/create`: 创建对局。
- `GET /games/{game_id}/pending`: 查看当前待行动玩家和可用动作。
- `GET /games/{game_id}/state/{slot_id}`: 查看某个玩家视角下的脱敏状态。
- `POST /games/{game_id}/actions/{slot_id}`: 提交动作。
- `POST /games/{game_id}/step`: 推进一步。
- `POST /games/{game_id}/autoplay`: 自动推进，直到遇到人类动作或游戏结束。
- `GET /games/{game_id}/history`: 获取对局历史。
- `GET /ui`: 打开浏览器调试界面。

## 示例：创建一局单人控制 5 个角色的混合对局

```json
{
  "solo_human_mode": true,
  "solo_human_slots": 5,
  "model_provider": "mock",
  "model_name": "rule-fallback",
  "random_seed": 11
}
```

## 模型配置

支持的 provider：

- `mock`: 默认值，不需要 API Key。
- `openai`: 读取 `OPENAI_API_KEY`。
- `gemini`: 读取 `GOOGLE_API_KEY`。
- `minimax`: 读取 `MINIMAX_API_KEY` 和可选的 `MINIMAX_BASE_URL`。

安全建议：

- 不要把真实 API Key 写进仓库文件或测试数据。
- 优先使用环境变量，不要把密钥直接写进提交的 JSON 示例。
- 本仓库的 `.gitignore` 已忽略常见 `.env`、本地配置和缓存目录。

## 说明

- 当前会话状态保存在内存中，重启服务后会清空活动对局。
- 前端 `frontend` 目录尚未完善，当前可用的交互入口是 `backend/app/static` 下的内置页面。
- 协议发生变更时，应同步更新 `PROTOCOLS.md` 和相关测试。