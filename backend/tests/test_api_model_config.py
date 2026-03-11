from fastapi.testclient import TestClient

from app.main import app, active_games


client = TestClient(app)


def setup_function():
    active_games.clear()


def test_create_game_accepts_minimax_session_config():
    resp = client.post(
        "/games/create",
        json={
            "solo_human_mode": True,
            "solo_human_slots": 5,
            "model_provider": "minimax",
            "model_name": "abab6.5-chat",
            "model_api_key": "test-key",
            "model_base_url": "https://example.local/v1",
            "random_seed": 3,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["model"]["provider"] == "minimax"
    assert payload["model"]["model_name"] == "abab6.5-chat"
    assert payload["model"]["base_url"] == "https://example.local/v1"
    assert payload["model"]["api_key_configured"] is True
