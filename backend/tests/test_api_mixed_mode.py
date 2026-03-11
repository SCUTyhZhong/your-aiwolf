from fastapi.testclient import TestClient

from app.main import app, active_games


client = TestClient(app)


def setup_function():
    active_games.clear()


def test_solo_human_mode_allocates_five_humans_one_ai():
    resp = client.post(
        "/games/create",
        json={
            "solo_human_mode": True,
            "solo_human_slots": 5,
            "model_provider": "mock",
            "random_seed": 11,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["human_slots"] == [1, 2, 3, 4, 5]
    assert payload["ai_slots"] == [6]


def test_autoplay_stops_when_human_action_is_needed():
    resp = client.post(
        "/games/create",
        json={
            "solo_human_mode": True,
            "solo_human_slots": 5,
            "model_provider": "mock",
            "random_seed": 21,
        },
    )
    game_id = resp.json()["game_id"]

    auto = client.post(f"/games/{game_id}/autoplay", json={"max_actions": 200})
    assert auto.status_code == 200
    auto_payload = auto.json()
    assert auto_payload["status"] in {"RUNNING", "FINISHED"}

    pending = client.get(f"/games/{game_id}/pending")
    assert pending.status_code == 200
    pending_payload = pending.json()
    assert "pending_actions" in pending_payload

    if auto_payload["status"] == "RUNNING":
        # Should halt at a human-required decision point in mixed mode.
        assert any(item["is_human"] for item in pending_payload["pending_actions"])
