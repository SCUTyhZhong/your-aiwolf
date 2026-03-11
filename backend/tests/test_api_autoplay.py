from fastapi.testclient import TestClient

from app.main import app, active_games


client = TestClient(app)


def setup_function():
    active_games.clear()


def test_create_and_autoplay_finishes_game():
    resp = client.post(
        "/games/create",
        json={
            "model_provider": "mock",
            "model_name": "rule-fallback",
            "random_seed": 42,
        },
    )
    assert resp.status_code == 200
    game_id = resp.json()["game_id"]

    auto = client.post(f"/games/{game_id}/autoplay", json={"max_actions": 400})
    assert auto.status_code == 200
    payload = auto.json()
    assert payload["executed_actions"] > 0
    assert payload["status"] == "FINISHED"


def test_step_endpoint_progresses_or_blocks_cleanly():
    resp = client.post(
        "/games/create",
        json={
            "model_provider": "mock",
            "model_name": "rule-fallback",
            "random_seed": 7,
        },
    )
    game_id = resp.json()["game_id"]

    step = client.post(f"/games/{game_id}/step")
    assert step.status_code == 200
    payload = step.json()
    assert "progressed" in payload
    assert payload["status"] in {"RUNNING", "FINISHED"}
