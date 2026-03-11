import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agents.llm_client import LLMConfig
from app.agents.model_agent import ModelAgent
from app.api.schemas import ActionType, AgentAction, GameStage, GameStatus, Role, SkillAction, SkillName
from app.core.game import GameEngine
from app.core.rules import MVP_ROLE_DISTRIBUTION

app = FastAPI(title="AI Werewolf API")
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@dataclass
class GameSession:
    game: GameEngine
    agents: Dict[int, ModelAgent] = field(default_factory=dict)


class CreateGameRequest(BaseModel):
    human_slots: List[int] = Field(default_factory=list)
    model_provider: str = "mock"
    model_name: str = "rule-fallback"
    temperature: float = 0.3
    model_api_key: Optional[str] = None
    model_base_url: Optional[str] = None
    random_seed: Optional[int] = None
    solo_human_mode: bool = False
    solo_human_slots: int = 5


class ActionRequest(BaseModel):
    action: AgentAction


class AutoPlayRequest(BaseModel):
    max_actions: int = 250


# In-memory store for active sessions
active_games: Dict[str, GameSession] = {}

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    return {"message": "AI Werewolf API is running"}


@app.get("/ui")
async def web_console():
    return FileResponse(str(STATIC_DIR / "index.html"))

def _ordered_mvp_roles() -> List[Role]:
    roles: List[Role] = []
    for role, count in MVP_ROLE_DISTRIBUTION.items():
        roles.extend([role] * count)
    return roles


def _get_session_or_404(game_id: str) -> GameSession:
    session = active_games.get(game_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return session


def _resolve_stage_players(game: GameEngine) -> List[int]:
    if game.state == GameStage.NIGHT_WOLF:
        return [slot for slot, p in game.players.items() if p.is_alive and p.role_type == Role.WEREWOLF and slot not in game.wolf_actions]
    if game.state == GameStage.NIGHT_SEER:
        return [slot for slot, p in game.players.items() if p.is_alive and p.role_type == Role.SEER]
    if game.state == GameStage.NIGHT_WITCH:
        return [slot for slot, p in game.players.items() if p.is_alive and p.role_type == Role.WITCH]
    if game.state == GameStage.DAY_DISCUSSION:
        return [slot for slot, p in game.players.items() if p.is_alive]
    if game.state == GameStage.DAY_VOTING:
        return [slot for slot, p in game.players.items() if p.is_alive and slot not in game.day_votes]
    return []


def _legal_actions_for_slot(game: GameEngine, slot_id: int) -> List[str]:
    player = game.players.get(slot_id)
    if player is None or not player.is_alive:
        return []

    if game.state == GameStage.NIGHT_WOLF and player.role_type == Role.WEREWOLF and slot_id not in game.wolf_actions:
        return ["SKILL.KILL"]
    if game.state == GameStage.NIGHT_SEER and player.role_type == Role.SEER:
        return ["SKILL.VERIFY"]
    if game.state == GameStage.NIGHT_WITCH and player.role_type == Role.WITCH:
        return ["SKILL.GUARD", "SKILL.POISON", "SKILL.PASS"]
    if game.state == GameStage.DAY_DISCUSSION and player.is_alive:
        return ["SPEAK", "SKILL.VOTE"]
    if game.state == GameStage.DAY_VOTING and player.is_alive and slot_id not in game.day_votes:
        return ["SKILL.VOTE"]
    return []


def _build_pending_payload(session: GameSession) -> Dict[str, object]:
    game = session.game
    pending_slots = _resolve_stage_players(game)
    return {
        "game_id": game.game_id,
        "status": game.status,
        "stage": game.state,
        "round": game.current_round,
        "pending_slots": pending_slots,
        "pending_actions": [
            {
                "slot_id": slot_id,
                "is_human": game.players[slot_id].is_human,
                "legal_actions": _legal_actions_for_slot(game, slot_id),
            }
            for slot_id in pending_slots
        ],
    }


async def _drive_one_action(session: GameSession) -> bool:
    game = session.game
    if game.status != GameStatus.RUNNING:
        return False

    acting_slots = _resolve_stage_players(game)
    if not acting_slots:
        return False

    # During discussion, MVP auto-run skips speech and goes directly to voting actions.
    if game.state == GameStage.DAY_DISCUSSION:
        ai_slots = [slot_id for slot_id in acting_slots if slot_id in session.agents]
        human_slots = [slot_id for slot_id in acting_slots if slot_id not in session.agents]

        # Mixed game: wait for human to control discussion and start voting.
        if human_slots:
            return False

        for slot_id in ai_slots:
            view = game.get_game_state(slot_id)
            agent = session.agents[slot_id]
            action = agent.make_vote_action(view)
            game.handle_action(slot_id, action)
            if game.status != GameStatus.RUNNING:
                break
            if game.state != GameStage.DAY_VOTING and game.state != GameStage.DAY_DISCUSSION:
                break
        return bool(ai_slots)

    ai_actors = [slot_id for slot_id in acting_slots if slot_id in session.agents]
    if not ai_actors:
        return False

    slot_id = ai_actors[0]
    agent = session.agents.get(slot_id)
    if agent is None:
        return False

    viewer_state = game.get_game_state(slot_id)
    action = await agent.think(viewer_state)
    try:
        game.handle_action(slot_id, action)
    except ValueError:
        # Model output may be off-protocol; retry with deterministic fallback.
        game.handle_action(slot_id, agent._fallback_action(viewer_state))
    return True


@app.post("/games/create")
async def create_game(payload: Optional[CreateGameRequest] = None):
    payload = payload or CreateGameRequest()
    if payload.random_seed is not None:
        random.seed(payload.random_seed)

    game = GameEngine()
    session = GameSession(game=game)

    roles = _ordered_mvp_roles()
    random.shuffle(roles)

    llm_config = LLMConfig(
        provider=payload.model_provider,
        model_name=payload.model_name,
        temperature=payload.temperature,
        api_key=payload.model_api_key,
        base_url=payload.model_base_url,
    )

    if payload.solo_human_mode:
        max_slots = len(roles)
        human_count = max(1, min(payload.solo_human_slots, max_slots - 1))
        human_slot_set = set(range(1, human_count + 1))
    else:
        human_slot_set = set(payload.human_slots)
    for i, role in enumerate(roles):
        slot = i + 1
        game.add_player(slot, f"Player_{slot}", role)
        if slot in game.players:
            game.players[slot].is_human = slot in human_slot_set
        if slot not in human_slot_set:
            session.agents[slot] = ModelAgent(slot_id=slot, role=role, llm_config=llm_config)

    game.start_game()
    active_games[game.game_id] = session
    return {
        "game_id": game.game_id,
        "human_slots": sorted(human_slot_set),
        "ai_slots": sorted([slot for slot in game.players if slot not in human_slot_set]),
        "players": [
            {
                "slot_id": slot,
                "name": p.name,
                "is_human": p.is_human,
            }
            for slot, p in sorted(game.players.items())
        ],
        "model": {
            "provider": payload.model_provider,
            "model_name": payload.model_name,
            "temperature": payload.temperature,
            "base_url": payload.model_base_url,
            "api_key_configured": bool(payload.model_api_key),
        },
    }


@app.get("/games/{game_id}/pending")
async def get_pending(game_id: str):
    session = _get_session_or_404(game_id)
    return _build_pending_payload(session)


@app.get("/games/{game_id}/state/{slot_id}")
async def get_state(game_id: str, slot_id: int):
    session = _get_session_or_404(game_id)
    if slot_id not in session.game.players:
        raise HTTPException(status_code=404, detail="Player slot not found")
    return session.game.get_game_state(slot_id)


@app.post("/games/{game_id}/actions/{slot_id}")
async def submit_action(game_id: str, slot_id: int, payload: ActionRequest):
    session = _get_session_or_404(game_id)
    try:
        session.game.handle_action(slot_id, payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "status": session.game.status,
        "stage": session.game.state,
        "round": session.game.current_round,
    }


@app.post("/games/{game_id}/step")
async def step_once(game_id: str):
    session = _get_session_or_404(game_id)
    progressed = await _drive_one_action(session)
    return {
        "progressed": progressed,
        "status": session.game.status,
        "stage": session.game.state,
        "round": session.game.current_round,
        "history_size": len(session.game.history),
    }


@app.post("/games/{game_id}/autoplay")
async def autoplay(game_id: str, payload: AutoPlayRequest):
    session = _get_session_or_404(game_id)
    executed = 0
    for _ in range(payload.max_actions):
        progressed = await _drive_one_action(session)
        if not progressed:
            break
        executed += 1
        if session.game.status != GameStatus.RUNNING:
            break

    return {
        "executed_actions": executed,
        "status": session.game.status,
        "stage": session.game.state,
        "round": session.game.current_round,
        "history_size": len(session.game.history),
    }


@app.get("/games/{game_id}/history")
async def get_history(game_id: str):
    session = _get_session_or_404(game_id)
    return {
        "game_id": game_id,
        "history": session.game.history,
    }

@app.websocket("/ws/{game_id}/{slot_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, slot_id: int):
    if game_id not in active_games:
        await websocket.close(code=1000, reason="Game not found")
        return

    session = active_games[game_id]
    game = session.game
    if slot_id not in game.players:
        await websocket.close(code=1000, reason="Player not found")
        return

    await websocket.accept()

    try:
        state = game.get_game_state(slot_id)
        await websocket.send_text(state.model_dump_json())

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            try:
                if message.get("type") == "step":
                    progressed = await _drive_one_action(session)
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "step_result",
                                "progressed": progressed,
                                "status": game.status,
                                "stage": str(game.state),
                            }
                        )
                    )
                    continue

                action = AgentAction(**message)
                game.handle_action(slot_id, action)
                updated_state = game.get_game_state(slot_id)
                await websocket.send_text(updated_state.model_dump_json())
            except ValueError as exc:
                await websocket.send_text(json.dumps({"error": str(exc)}))

    except WebSocketDisconnect:
        print(f"Player {slot_id} disconnected from game {game_id}")
    except Exception as e:
        print(f"Error in websocket: {e}")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
