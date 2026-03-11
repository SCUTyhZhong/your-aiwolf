from app.api.schemas import ActionType, AgentAction, GameStage, Role, SkillAction, SkillName
from app.core.game import GameEngine


def _build_game() -> GameEngine:
    game = GameEngine(game_id="test-game")
    game.add_player(1, "P1", Role.WEREWOLF)
    game.add_player(2, "P2", Role.WEREWOLF)
    game.add_player(3, "P3", Role.SEER)
    game.add_player(4, "P4", Role.WITCH)
    game.add_player(5, "P5", Role.VILLAGER)
    game.add_player(6, "P6", Role.VILLAGER)
    game.start_game()
    return game


def _skill(skill_name: SkillName, target_id: int | None = None) -> AgentAction:
    return AgentAction(
        action_type=ActionType.SKILL,
        data=SkillAction(skill_name=skill_name, target_id=target_id),
    )


def _run_first_night_to_discussion(game: GameEngine):
    game.handle_action(1, _skill(SkillName.KILL, 5))
    game.handle_action(2, _skill(SkillName.KILL, 5))
    assert game.state == GameStage.NIGHT_SEER

    game.handle_action(3, _skill(SkillName.VERIFY, 1))
    assert game.state == GameStage.NIGHT_WITCH

    # MVP pass for witch: VOTE with no target acts as no-op.
    game.handle_action(4, _skill(SkillName.VOTE, None))
    assert game.state == GameStage.DAY_DISCUSSION


def test_information_masking_for_werewolf_and_seer():
    game = _build_game()

    wolf_view = game.get_game_state(1)
    role_map = {p.slot_id: p.role for p in wolf_view.players}
    assert role_map[1] == Role.WEREWOLF
    assert role_map[2] == Role.WEREWOLF
    assert role_map[3] == Role.UNKNOWN

    _run_first_night_to_discussion(game)

    seer_view = game.get_game_state(3)
    seer_map = {p.slot_id: p.role for p in seer_view.players}
    assert seer_map[1] == Role.WEREWOLF
    assert seer_map[2] == Role.UNKNOWN


def test_night_resolution_and_day_vote_progression():
    game = _build_game()
    _run_first_night_to_discussion(game)

    assert game.players[5].is_alive is False

    # First vote also advances DAY_DISCUSSION -> DAY_VOTING.
    game.handle_action(1, _skill(SkillName.VOTE, 3))
    assert game.state == GameStage.DAY_VOTING

    game.handle_action(2, _skill(SkillName.VOTE, 3))
    game.handle_action(3, _skill(SkillName.VOTE, 1))
    game.handle_action(4, _skill(SkillName.VOTE, 1))
    game.handle_action(6, _skill(SkillName.VOTE, 1))

    assert game.players[1].is_alive is False
    assert game.current_round == 2
    assert game.state == GameStage.NIGHT_WOLF


def test_check_winner_matches_mvp_rule():
    game = _build_game()
    game.players[1].is_alive = False
    game.players[2].is_alive = False
    assert game.check_winner() == "GOOD_GUYS_WIN"

    game = _build_game()
    game.players[5].is_alive = False
    game.players[6].is_alive = False
    assert game.check_winner() == "WEREWOLVES_WIN"
