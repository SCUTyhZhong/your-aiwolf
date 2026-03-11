from abc import ABC, abstractmethod
from app.api.schemas import ActionType, AgentAction, GameStage, GameState, Role, SpeakAction

class BaseAgent(ABC):
    def __init__(self, slot_id: int, role: Role):
        self.slot_id = slot_id
        self.role = role
        self.memory = []
        self.inner_monologue = []

    @abstractmethod
    async def think(self, game_state: GameState) -> AgentAction:
        """
        AI Reasoning process (CoT).
        1. Observe game_state.
        2. Update memory.
        3. Internal reasoning (Inner Monologue).
        4. Return Action.
        """
        pass

    def add_to_memory(self, event: str):
        self.memory.append(event)

    def log_thinking(self, thought: str):
        self.inner_monologue.append(thought)
        # Optional: Log to file or debug console
        print(f"[Agent {self.slot_id} Thought]: {thought}")

class SimpleAgent(BaseAgent):
    """
    A simple rule-based agent for testing.
    """
    async def think(self, game_state: GameState) -> AgentAction:
        self.log_thinking("Observing game state...")

        if game_state.current_stage == GameStage.DAY_DISCUSSION:
            return AgentAction(
                action_type=ActionType.SPEAK,
                data=SpeakAction(content=f"Hello, I am player {self.slot_id}. I am a {self.role.value}.")
            )
        
        # Default empty action or skill
        return AgentAction(
            action_type=ActionType.SPEAK,
            data=SpeakAction(content="...")
        )
