PROTOCOLS.md - AI 狼人杀通信协议规范
本文件定义了系统各组件（Engine, Agent, Frontend）之间的数据交换格式，所有开发者与 AI 接入必须遵循此标准。

## 1. 游戏全局状态 (Global Game State)由后端规则引擎维护并广播。根据接收者身份（神、狼、民、死者），下发的字段需经过信息遮蔽处理。JSON{
  "game_id": "uuid-12345",
  "status": "RUNNING", // WAITING, RUNNING, FINISHED
  "current_round": 1,
  "current_stage": "NIGHT_WOLF_PHASE", 
  /* 阶段枚举: 
     NIGHT_WOLF, NIGHT_SEER, NIGHT_WITCH, 
     DAY_ANNOUNCE (死讯), DAY_DISCUSSION (发言), DAY_VOTING (投票) 
  */
  "players": [
    {
      "slot_id": 1,
      "is_alive": true,
      "name": "Player_1",
      "is_human": false,
      "role": "WEREWOLF", // 仅对本人或队友可见，否则为 "UNKNOWN"
      "is_captain": false
    }
    // ... 其他玩家
  ],
  "history": [
    {
      "round": 1,
      "stage": "DAY_VOTING",
      "event": "PLAYER_VOTE",
      "from": 1,
      "to": 3
    }
  ]
}

2. 智能体行动指令 (Agent Actions)AI Agent 或人类玩家向后端发送的操作。后端必须校验 action_type 是否符合当前 current_stage。
A. 语音/文本发言 (Chat/Speech)用于讨论阶段。
JSON{
  "action_type": "SPEAK",
  "data": {
    "content": "我觉得3号玩家刚才的发言逻辑有漏洞...",
    "is_whisper": false // 狼人夜间频道为 true
  }
}
B. 功能性技能 (Skill Execution)用于夜间或特殊环节。
JSON{
  "action_type": "SKILL",
  "data": {
    "skill_name": "KILL", // KILL, VERIFY, POISON, GUARD, VOTE
    "target_id": 5,
    "reason": "Internal reasoning for logs" // AI 的内部思考，不公开
  }
}
3. 核心事件流 (Event Stream)当状态发生变更时，由引擎推送给 Agent 的事件，用于触发 AI 的推理。事件类型触发时机包含信息STAGE_START进入新阶段（如天亮了）阶段名称、限时、死亡名单NEW_SPEECH任何玩家完成发言发言者 ID、发言内容VOTE_RESULT投票结束详细票型公示GAME_OVER游戏结束最终胜负、全员身份复盘
4. 信息遮蔽规则 (Data Masking Rules) - 核心开发规范为了防止 AI 违规，后端在序列化 GameState 时必须执行以下过滤逻辑：身份可见性：如果 receiver.role == WEREWOLF，可见所有 role == WEREWOLF 的玩家身份。如果 receiver.role == SEER，可见其已查验过的玩家身份。其余情况，所有其他存活玩家的 role 必须重写为 UNKNOWN。动作可见性：狼人杀人过程仅对狼人可见。预言家验人过程仅对预言家可见。女巫用药情况仅在天亮死讯中体现，不显示具体操作过程。
5. 扩展性说明TTS 接入：若开启语音模式，NEW_SPEECH 事件将额外包含 audio_url 字段。多模型对抗：Agent 的请求头中需携带 model_version 以便统计不同 AI 的胜率。

## 6. MVP 后端实现约定 (2026-03)

- 阶段动作校验:
  - `NIGHT_WOLF` 仅接受狼人 `KILL`。
  - `NIGHT_SEER` 仅接受预言家 `VERIFY`。
  - `NIGHT_WITCH` 仅接受女巫 `GUARD`(解药)、`POISON`(毒药)、或 `VOTE+target_id=null`(pass)。
  - `DAY_DISCUSSION` 接受 `SPEAK`；当收到第一条 `VOTE` 时自动进入 `DAY_VOTING`。
  - `DAY_VOTING` 仅接受 `VOTE`。

- 女巫技能映射:
  - 由于当前 `SkillName` 未定义 `SAVE`，MVP 使用 `GUARD` 表示解药救人。
  - 解药仅可对当晚狼刀目标使用，且女巫不可自救。

- 投票结算:
  - 所有存活玩家投票后结算。
  - 平票时本轮无人出局（MVP 简化，未实现 PK 发言）。

- WebSocket 错误回包:
  - 非法动作会返回 `{ "error": "..." }`，不会导致连接直接断开。

- 新增接口层 (Backend API):
  - `POST /games/create`
    - 入参: `human_slots`, `solo_human_mode`, `solo_human_slots`, `model_provider`, `model_name`, `temperature`, `random_seed`。
    - 默认 `model_provider=mock`，走规则回退策略，可在无 Key 时完整跑局。
    - `solo_human_mode=true` 时，默认按槽位 `1..5` 分配给人类，剩余 `1` 个槽位分配给测试 AI。
  - `GET /games/{game_id}/state/{slot_id}`: 获取指定视角遮蔽状态。
  - `GET /games/{game_id}/pending`: 获取当前阶段待行动槽位和可用动作。
  - `POST /games/{game_id}/actions/{slot_id}`: 提交玩家动作。
  - `POST /games/{game_id}/step`: 由服务端推进一个动作（适合调试/人机混合）。
  - `POST /games/{game_id}/autoplay`: 连续推进直到游戏结束、到达步数上限、或遇到人类必须行动的阶段。
  - `GET /games/{game_id}/history`: 获取对局事件历史。

- 模型接入策略:
  - `LLMClient` 支持 `mock/openai/gemini`。
  - 若 provider 不可用、API Key 缺失、或模型输出 JSON 不合法，自动回退到规则策略，保证对局不中断。