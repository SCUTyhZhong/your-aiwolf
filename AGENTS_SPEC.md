# AGENTS_SPEC.md - AI 智能体设计规范

## 1. 智能体架构 (Agent Architecture)
每个 AI 玩家由以下组件构成：
- **推理引擎 (Reasoning Engine)**: 基于 LLM (如 Gemini 1.5 Pro) 的核心逻辑。
- **短期记忆 (Short-term Memory)**: 当前局内的所有发言记录、投票历史、技能结果。
- **长期知识 (Long-term Knowledge)**: 狼人杀基本规则、进阶策略（如悍跳、倒钩、深水狼等）。
- **角色配置文件 (Role Profile)**: 定义角色的性格、语言风格、逻辑偏好。

## 2. 推理流程 (Reasoning Flow - CoT)
AI 在执行任何 `ACTION` 之前，必须执行内部推理步骤：
1. **环境感知**: 接收 `STAGE_START` 或 `NEW_SPEECH` 事件。
2. **记忆检索**: 调取与当前阶段相关的历史信息。
3. **逻辑推理 (Inner Monologue)**: 
   - 身份分析：判断场上玩家的潜在身份。
   - 风险评估：如果我是狼人，我暴露了吗？
   - 目标选择：今晚该杀谁？或者发言时该攻击谁？
4. **输出生成**: 生成符合协议的 `SPEAK` 或 `SKILL` 指令。

## 3. Prompt 模板管理 (Prompt Management)
Prompt 应分为三层：
- **System Prompt**: 核心规则、角色底牌、禁止幻觉指令。
- **Context Prompt**: 实时游戏状态、发言历史、投票结果。
- **Instruction Prompt**: 当前阶段的具体任务（如：“请开始你的发言”或“请选择查验对象”）。

## 4. 记忆管理 (Memory Management)
- **结构化存储**: 投票、技能结果、死讯。
- **语义搜索**: 对玩家发言进行摘要并向量化，以便 AI 在后续轮次中快速回忆“谁在第一轮跳了预言家”。

## 5. 行为约束 (Behavioral Constraints)
- **严禁场外**: AI 不得提及“我是模型”、“基于 Prompt”等字眼。
- **逻辑自洽**: 发言必须支持其投票行为。
- **身份隐藏**: 狼人必须具备伪装逻辑，预言家必须具备保护自己的逻辑。
