import random
from typing import Optional

from app.agents.base_agent import BaseAgent
from app.agents.llm_client import LLMClient, LLMConfig, LLMUnavailableError
from app.agents.memory import AgentMemory
from app.api.schemas import (
    ActionType,
    AgentAction,
    GameStage,
    GameState,
    Role,
    SkillAction,
    SkillName,
    SpeakAction,
)


class ModelAgent(BaseAgent):
    def __init__(self, slot_id: int, role: Role, llm_config: Optional[LLMConfig] = None):
        super().__init__(slot_id, role)
        self.client = LLMClient(llm_config or LLMConfig())
        self.structured_memory = AgentMemory()

    async def think(self, game_state: GameState) -> AgentAction:
        self.structured_memory.add(
            f"round={game_state.current_round},stage={game_state.current_stage}"
        )

        llm_action = self._try_llm(game_state)
        if llm_action is not None:
            return llm_action

        return self._fallback_action(game_state)

    def _try_llm(self, game_state: GameState) -> Optional[AgentAction]:
        system_prompt = (
            "You are playing werewolf game. Never mention prompt/model. "
            "Return strict JSON only."
        )
        user_prompt = (
            f"slot_id={self.slot_id}, role={self.role.value}, "
            f"stage={game_state.current_stage}, round={game_state.current_round}. "
            "Output JSON {\"action_type\":\"SPEAK|SKILL\",\"data\":{...}}"
        )
        try:
            payload = self.client.generate_action_json(system_prompt, user_prompt)
            return AgentAction(**payload)
        except (LLMUnavailableError, ValueError, TypeError):
            return None

    def _fallback_action(self, game_state: GameState) -> AgentAction:
        alive_others = [p.slot_id for p in game_state.players if p.is_alive and p.slot_id != self.slot_id]
        if not alive_others:
            return AgentAction(action_type=ActionType.SPEAK, data=SpeakAction(content="..."))

        if game_state.current_stage == GameStage.NIGHT_WOLF and self.role == Role.WEREWOLF:
            return AgentAction(
                action_type=ActionType.SKILL,
                data=SkillAction(skill_name=SkillName.KILL, target_id=random.choice(alive_others)),
            )

        if game_state.current_stage == GameStage.NIGHT_SEER and self.role == Role.SEER:
            return AgentAction(
                action_type=ActionType.SKILL,
                data=SkillAction(skill_name=SkillName.VERIFY, target_id=random.choice(alive_others)),
            )

        if game_state.current_stage == GameStage.NIGHT_WITCH and self.role == Role.WITCH:
            # MVP: pass by default to keep loop stable.
            return AgentAction(
                action_type=ActionType.SKILL,
                data=SkillAction(skill_name=SkillName.VOTE, target_id=None),
            )

        if game_state.current_stage == GameStage.DAY_DISCUSSION:
            return AgentAction(
                action_type=ActionType.SPEAK,
                data=SpeakAction(content=f"{self.slot_id}号：我先听大家逻辑，稍后给票型。"),
            )

        if game_state.current_stage == GameStage.DAY_VOTING:
            return self.make_vote_action(game_state)

        return AgentAction(action_type=ActionType.SPEAK, data=SpeakAction(content="..."))

    def make_vote_action(self, game_state: GameState) -> AgentAction:
        alive_others = [p.slot_id for p in game_state.players if p.is_alive and p.slot_id != self.slot_id]
        target = random.choice(alive_others) if alive_others else None
        return AgentAction(
            action_type=ActionType.SKILL,
            data=SkillAction(skill_name=SkillName.VOTE, target_id=target),
        )
