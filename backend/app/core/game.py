import uuid
from typing import Dict, List, Optional, Set

from transitions import Machine

from app.api.schemas import (
    ActionType,
    AgentAction,
    GameStage,
    GameState,
    GameStatus,
    HistoryEvent,
    Role,
    SkillAction,
    SkillName,
    SpeakAction,
    Player,
)
from app.core.roles import BaseRole, Seer, Villager, Werewolf, Witch
from app.core.rules import evaluate_winner

class GameEngine:
    states = [
        GameStage.NIGHT_WOLF,
        GameStage.NIGHT_SEER,
        GameStage.NIGHT_WITCH,
        GameStage.DAY_ANNOUNCE,
        GameStage.DAY_DISCUSSION,
        GameStage.DAY_VOTING
    ]

    def __init__(self, game_id: Optional[str] = None):
        self.game_id = game_id or str(uuid.uuid4())
        self.status = GameStatus.WAITING
        self.current_round = 0
        self.players: Dict[int, BaseRole] = {}
        self.history: List[HistoryEvent] = []
        
        # State Machine setup
        self.machine = Machine(
            model=self, 
            states=GameEngine.states, 
            initial=GameStage.NIGHT_WOLF,
            send_event=True
        )
        
        # Define transitions
        self.machine.add_transition('next_stage', GameStage.NIGHT_WOLF, GameStage.NIGHT_SEER)
        self.machine.add_transition('next_stage', GameStage.NIGHT_SEER, GameStage.NIGHT_WITCH)
        self.machine.add_transition('next_stage', GameStage.NIGHT_WITCH, GameStage.DAY_ANNOUNCE)
        self.machine.add_transition('next_stage', GameStage.DAY_ANNOUNCE, GameStage.DAY_DISCUSSION)
        self.machine.add_transition('next_stage', GameStage.DAY_DISCUSSION, GameStage.DAY_VOTING)
        self.machine.add_transition('next_stage', GameStage.DAY_VOTING, GameStage.NIGHT_WOLF, before='increment_round')

        # Runtime stage data
        self.night_kill_target: Optional[int] = None
        self.wolf_actions: Dict[int, int] = {}
        self.wolf_action_order: List[int] = []
        self.seer_acted: bool = False
        self.seer_results: Dict[int, Dict[int, Role]] = {}
        self.witch_acted: bool = False
        self.witch_saved: bool = False
        self.witch_poison_target: Optional[int] = None
        self.pending_night_deaths: Set[int] = set()
        self.day_votes: Dict[int, int] = {}

    def increment_round(self, event):
        self.current_round += 1

    def add_player(self, slot_id: int, name: str, role_type: Role):
        role_map = {
            Role.WEREWOLF: Werewolf,
            Role.SEER: Seer,
            Role.WITCH: Witch,
            Role.VILLAGER: Villager
        }
        if role_type in role_map:
            self.players[slot_id] = role_map[role_type](slot_id, name)

    def start_game(self):
        self.status = GameStatus.RUNNING
        self.current_round = 1
        self._reset_night_state()
        self._reset_day_votes()
        self._advance_if_stage_has_no_actor()

    def get_game_state(self, viewer_slot_id: Optional[int] = None) -> GameState:
        visible_players = []
        viewer_role = Role.UNKNOWN
        verified_by_viewer: Set[int] = set()
        if viewer_slot_id and viewer_slot_id in self.players:
            viewer_role = self.players[viewer_slot_id].role_type
            if viewer_role == Role.SEER:
                verified_by_viewer = set(self.seer_results.get(viewer_slot_id, {}).keys())

        for slot_id, p in self.players.items():
            role_to_show = Role.UNKNOWN
            # Information Masking Rules
            if viewer_slot_id == slot_id:
                role_to_show = p.role_type
            elif viewer_role == Role.WEREWOLF and p.role_type == Role.WEREWOLF:
                role_to_show = Role.WEREWOLF
            elif viewer_role == Role.SEER and slot_id in verified_by_viewer:
                role_to_show = p.role_type
            
            visible_players.append(Player(
                slot_id=p.slot_id,
                is_alive=p.is_alive,
                name=p.name,
                is_human=p.is_human,
                role=role_to_show
            ))

        return GameState(
            game_id=self.game_id,
            status=self.status,
            current_round=self.current_round,
            current_stage=self.state, # transitions model's state
            players=visible_players,
            history=self.history
        )

    def handle_action(self, slot_id: int, action: dict):
        if self.status != GameStatus.RUNNING:
            raise ValueError("Game is not running")
        if slot_id not in self.players:
            raise ValueError("Invalid player slot")
        actor = self.players[slot_id]
        if not actor.is_alive:
            raise ValueError("Dead players cannot act")

        parsed_action = action if isinstance(action, AgentAction) else AgentAction(**action)

        if parsed_action.action_type == ActionType.SPEAK:
            self._handle_speak_action(slot_id, parsed_action.data)
        elif parsed_action.action_type == ActionType.SKILL:
            self._handle_skill_action(slot_id, parsed_action.data)
        else:
            raise ValueError("Unsupported action type")

        if self.status == GameStatus.FINISHED:
            return

        winner = self.check_winner()
        if winner is not None:
            self.status = GameStatus.FINISHED
            self._append_history("GAME_OVER", 0, None, winner)

    def _handle_speak_action(self, slot_id: int, payload: SpeakAction):
        if self.state != GameStage.DAY_DISCUSSION:
            raise ValueError("SPEAK is only valid during DAY_DISCUSSION")
        self._append_history("NEW_SPEECH", slot_id, None, payload.content)

    def _handle_skill_action(self, slot_id: int, payload: SkillAction):
        if self.state == GameStage.NIGHT_WOLF:
            self._handle_wolf_skill(slot_id, payload)
        elif self.state == GameStage.NIGHT_SEER:
            self._handle_seer_skill(slot_id, payload)
        elif self.state == GameStage.NIGHT_WITCH:
            self._handle_witch_skill(slot_id, payload)
        elif self.state == GameStage.DAY_DISCUSSION and payload.skill_name == SkillName.VOTE:
            self.next_stage()
            self._handle_vote_skill(slot_id, payload)
        elif self.state == GameStage.DAY_VOTING:
            self._handle_vote_skill(slot_id, payload)
        else:
            raise ValueError(f"SKILL is not valid during stage {self.state}")

    def _handle_wolf_skill(self, slot_id: int, payload: SkillAction):
        actor = self.players[slot_id]
        if actor.role_type != Role.WEREWOLF:
            raise ValueError("Only werewolves can act in NIGHT_WOLF")
        if payload.skill_name != SkillName.KILL:
            raise ValueError("NIGHT_WOLF only accepts KILL")
        target_id = self._validate_alive_target(slot_id, payload.target_id, allow_self=False)
        self.wolf_actions[slot_id] = target_id
        self.wolf_action_order.append(slot_id)
        self._append_history("WOLF_ACTION", slot_id, target_id)

        if len(self.wolf_actions) >= len(self._alive_players_by_role(Role.WEREWOLF)):
            last_actor = self.wolf_action_order[-1]
            self.night_kill_target = self.wolf_actions[last_actor]
            self.next_stage()
            self._advance_if_stage_has_no_actor()

    def _handle_seer_skill(self, slot_id: int, payload: SkillAction):
        actor = self.players[slot_id]
        if actor.role_type != Role.SEER:
            raise ValueError("Only seer can act in NIGHT_SEER")
        if self.seer_acted:
            raise ValueError("Seer already acted this night")
        if payload.skill_name != SkillName.VERIFY:
            raise ValueError("NIGHT_SEER only accepts VERIFY")

        target_id = self._validate_alive_target(slot_id, payload.target_id, allow_self=False)
        target_role = self.players[target_id].role_type
        self.seer_results.setdefault(slot_id, {})[target_id] = target_role
        self.seer_acted = True
        visible_result = Role.WEREWOLF if target_role == Role.WEREWOLF else Role.VILLAGER
        self._append_history("SEER_VERIFY", slot_id, target_id, visible_result.value)
        self.next_stage()
        self._advance_if_stage_has_no_actor()

    def _handle_witch_skill(self, slot_id: int, payload: SkillAction):
        actor = self.players[slot_id]
        if actor.role_type != Role.WITCH:
            raise ValueError("Only witch can act in NIGHT_WITCH")
        if self.witch_acted:
            raise ValueError("Witch already acted this night")

        if payload.skill_name == SkillName.GUARD:
            if not actor.has_antidote:
                raise ValueError("Antidote already used")
            if payload.target_id != self.night_kill_target:
                raise ValueError("Witch can only save the nightly victim")
            if payload.target_id == slot_id:
                raise ValueError("Witch cannot self-save in MVP rules")
            actor.has_antidote = False
            self.witch_saved = True
            self._append_history("WITCH_SAVE", slot_id, payload.target_id)
        elif payload.skill_name == SkillName.POISON:
            if not actor.has_poison:
                raise ValueError("Poison already used")
            target_id = self._validate_alive_target(slot_id, payload.target_id, allow_self=False)
            actor.has_poison = False
            self.witch_poison_target = target_id
            self._append_history("WITCH_POISON", slot_id, target_id)
        elif payload.skill_name == SkillName.VOTE and payload.target_id is None:
            # MVP no-op, allows witch to pass explicitly.
            self._append_history("WITCH_PASS", slot_id, None)
        else:
            raise ValueError("NIGHT_WITCH only accepts GUARD/POISON/PASS")

        self.witch_acted = True
        self._resolve_night()
        self.next_stage()  # DAY_ANNOUNCE
        self._append_history(
            "DAY_ANNOUNCE",
            0,
            None,
            ",".join(str(x) for x in sorted(self.pending_night_deaths)) if self.pending_night_deaths else "NONE",
        )
        self.next_stage()  # DAY_DISCUSSION
        self._advance_if_stage_has_no_actor()

    def _handle_vote_skill(self, slot_id: int, payload: SkillAction):
        if payload.skill_name != SkillName.VOTE:
            raise ValueError("DAY_VOTING only accepts VOTE")
        target_id = self._validate_alive_target(slot_id, payload.target_id, allow_self=False)
        self.day_votes[slot_id] = target_id
        self._append_history("PLAYER_VOTE", slot_id, target_id)

        alive_players = self._alive_players()
        if len(self.day_votes) >= len(alive_players):
            eliminated = self._resolve_day_vote()
            self._append_history("VOTE_RESULT", 0, eliminated)
            self.next_stage()  # NIGHT_WOLF + round increment
            self._reset_night_state()
            self._reset_day_votes()
            self._advance_if_stage_has_no_actor()

    def _resolve_night(self):
        deaths: Set[int] = set()
        if self.night_kill_target is not None and not self.witch_saved:
            deaths.add(self.night_kill_target)
        if self.witch_poison_target is not None:
            deaths.add(self.witch_poison_target)
        for slot_id in deaths:
            self.players[slot_id].is_alive = False
        self.pending_night_deaths = deaths

    def _resolve_day_vote(self) -> Optional[int]:
        if not self.day_votes:
            return None
        counter: Dict[int, int] = {}
        for target in self.day_votes.values():
            counter[target] = counter.get(target, 0) + 1
        max_votes = max(counter.values())
        finalists = [slot for slot, votes in counter.items() if votes == max_votes]
        if len(finalists) != 1:
            # MVP tie handling: no elimination.
            return None
        eliminated = finalists[0]
        self.players[eliminated].is_alive = False
        return eliminated

    def _append_history(self, event: str, from_id: int, to_id: Optional[int], content: Optional[str] = None):
        self.history.append(
            HistoryEvent(
                round=self.current_round,
                stage=self.state,
                event=event,
                from_id=from_id,
                to_id=to_id,
                content=content,
            )
        )

    def _validate_alive_target(self, actor_id: int, target_id: Optional[int], allow_self: bool) -> int:
        if target_id is None:
            raise ValueError("Target is required")
        if target_id not in self.players:
            raise ValueError("Target does not exist")
        if not self.players[target_id].is_alive:
            raise ValueError("Target is dead")
        if not allow_self and target_id == actor_id:
            raise ValueError("Self-targeting is not allowed")
        return target_id

    def _advance_if_stage_has_no_actor(self):
        moved = True
        while self.status == GameStatus.RUNNING and moved:
            moved = False
            if self.state == GameStage.NIGHT_WOLF and not self._alive_players_by_role(Role.WEREWOLF):
                self.next_stage()
                moved = True
            elif self.state == GameStage.NIGHT_SEER and not self._alive_players_by_role(Role.SEER):
                self.next_stage()
                moved = True
            elif self.state == GameStage.NIGHT_WITCH and not self._alive_players_by_role(Role.WITCH):
                self._resolve_night()
                self.next_stage()  # DAY_ANNOUNCE
                self._append_history(
                    "DAY_ANNOUNCE",
                    0,
                    None,
                    ",".join(str(x) for x in sorted(self.pending_night_deaths)) if self.pending_night_deaths else "NONE",
                )
                self.next_stage()  # DAY_DISCUSSION
                moved = True
            elif self.state == GameStage.DAY_DISCUSSION and len(self._alive_players()) <= 1:
                self.next_stage()
                moved = True

            winner = self.check_winner()
            if winner is not None:
                self.status = GameStatus.FINISHED
                self._append_history("GAME_OVER", 0, None, winner)
                break

    def _alive_players(self) -> List[int]:
        return [slot_id for slot_id, p in self.players.items() if p.is_alive]

    def _alive_players_by_role(self, role: Role) -> List[int]:
        return [slot_id for slot_id, p in self.players.items() if p.is_alive and p.role_type == role]

    def _reset_night_state(self):
        self.night_kill_target = None
        self.wolf_actions = {}
        self.wolf_action_order = []
        self.seer_acted = False
        self.witch_acted = False
        self.witch_saved = False
        self.witch_poison_target = None
        self.pending_night_deaths = set()

    def _reset_day_votes(self):
        self.day_votes = {}

    def check_winner(self) -> Optional[str]:
        alive_roles = [p.role_type for p in self.players.values() if p.is_alive]
        return evaluate_winner(alive_roles)
