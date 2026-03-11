from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ui_entry_served():
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "AI Werewolf Console" in resp.text


def test_static_assets_served():
    css = client.get("/static/styles.css")
    js = client.get("/static/app.js")
    html = client.get("/ui")
    assert css.status_code == 200
    assert js.status_code == 200
    assert html.status_code == 200
    assert "--bg" in css.text
    assert "createGame" in js.text
    assert "minimax" in html.text
    assert "updateActionForm" in js.text
