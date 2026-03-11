from typing import List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

class GameStatus(str, Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"

class GameStage(str, Enum):
    NIGHT_WOLF = "NIGHT_WOLF"
    NIGHT_SEER = "NIGHT_SEER"
    NIGHT_WITCH = "NIGHT_WITCH"
    DAY_ANNOUNCE = "DAY_ANNOUNCE"
    DAY_DISCUSSION = "DAY_DISCUSSION"
    DAY_VOTING = "DAY_VOTING"

class Role(str, Enum):
    WEREWOLF = "WEREWOLF"
    SEER = "SEER"
    WITCH = "WITCH"
    VILLAGER = "VILLAGER"
    UNKNOWN = "UNKNOWN"

class ActionType(str, Enum):
    SPEAK = "SPEAK"
    SKILL = "SKILL"

class SkillName(str, Enum):
    KILL = "KILL"
    VERIFY = "VERIFY"
    POISON = "POISON"
    GUARD = "GUARD"
    VOTE = "VOTE"

class Player(BaseModel):
    slot_id: int
    is_alive: bool
    name: str
    is_human: bool
    role: Role = Role.UNKNOWN
    is_captain: bool = False

class HistoryEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    round: int
    stage: GameStage
    event: str
    from_id: int = Field(alias="from")
    to_id: Optional[int] = Field(None, alias="to")
    content: Optional[str] = None

class GameState(BaseModel):
    game_id: str
    status: GameStatus
    current_round: int
    current_stage: GameStage
    players: List[Player]
    history: List[HistoryEvent]

class SpeakAction(BaseModel):
    content: str
    is_whisper: bool = False

class SkillAction(BaseModel):
    skill_name: SkillName
    target_id: Optional[int] = None
    reason: Optional[str] = None

class AgentAction(BaseModel):
    action_type: ActionType
    data: Union[SpeakAction, SkillAction]

class EventType(str, Enum):
    STAGE_START = "STAGE_START"
    NEW_SPEECH = "NEW_SPEECH"
    VOTE_RESULT = "VOTE_RESULT"
    GAME_OVER = "GAME_OVER"

class EventStream(BaseModel):
    event_type: EventType
    data: dict
