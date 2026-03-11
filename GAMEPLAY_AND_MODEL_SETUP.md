# AI Werewolf: Gameplay and Model Setup Guide

## 1. Purpose
This guide explains:
- How to start and play a full game using backend APIs.
- How to run mixed mode (you control 5 roles, test AI controls 1 role).
- How to configure model providers (`mock`, `openai`, `gemini`, `minimax`).

Project root: `./`
Backend folder: `./backend`

## 2. Start Backend
From `backend`:

```powershell
cd backend
python -m app.main
```

Default server:
- Base URL: `http://127.0.0.1:8000`

Quick health check:

```http
GET /
```

Web UI entry:

```text
http://127.0.0.1:8000/ui
```

The UI supports:
- Model configuration (`mock/openai/gemini/minimax`, model name, temperature, seed)
- Mode selection (currently fixed to `single AI + single human with 5 roles`)
- Create game, refresh pending actions, submit human actions, autoplay AI
- Smart action form (input fields auto-switch based on legal action)

## 3. Create a Game

### 3.1 Recommended for your current test (1 client controls 5 roles)
Use `solo_human_mode=true` and `solo_human_slots=5`.

```http
POST /games/create
Content-Type: application/json

{
  "solo_human_mode": true,
  "solo_human_slots": 5,
  "model_provider": "mock",
  "model_name": "rule-fallback",
  "random_seed": 11
}
```

Response includes:
- `game_id`
- `human_slots` (expected `[1,2,3,4,5]`)
- `ai_slots` (expected `[6]`)
- `players`

### 3.2 Regular mixed mode (manual human slot selection)

```json
{
  "human_slots": [1, 3],
  "model_provider": "mock",
  "model_name": "rule-fallback"
}
```

## 4. Core Gameplay Loop

### Step A: Query who should act now

```http
GET /games/{game_id}/pending
```

Key fields:
- `stage`: current stage
- `pending_slots`: slots that need to act
- `pending_actions`: for each slot: `is_human`, `legal_actions`

### Step B: Submit action for your human-controlled slots

```http
POST /games/{game_id}/actions/{slot_id}
Content-Type: application/json

{
  "action": {
    "action_type": "SKILL",
    "data": {
      "skill_name": "KILL",
      "target_id": 3
    }
  }
}
```

### Step C: Let AI auto-progress when possible

```http
POST /games/{game_id}/autoplay
Content-Type: application/json

{
  "max_actions": 100
}
```

Behavior:
- Server executes AI actions only.
- If a human action is required, autoplay stops.
- If game reaches terminal state, status becomes `FINISHED`.

### Step D: Repeat A -> B -> C until finished

Useful endpoints during loop:
- `GET /games/{game_id}/state/{slot_id}`: masked state from one role's view.
- `GET /games/{game_id}/history`: event history for replay/debug.

## 5. Action Format Reference

## 5.1 Speak

```json
{
  "action": {
    "action_type": "SPEAK",
    "data": {
      "content": "I suspect slot 3.",
      "is_whisper": false
    }
  }
}
```

## 5.2 Skill

```json
{
  "action": {
    "action_type": "SKILL",
    "data": {
      "skill_name": "VOTE",
      "target_id": 4
    }
  }
}
```

Supported skills in current MVP:
- `KILL`
- `VERIFY`
- `GUARD` (used as witch antidote/save)
- `POISON`
- `VOTE`

Witch pass action in `NIGHT_WITCH`:

```json
{
  "action": {
    "action_type": "SKILL",
    "data": {
      "skill_name": "VOTE",
      "target_id": null
    }
  }
}
```

## 6. Model Configuration

`/games/create` accepts:
- `model_provider`: `mock` | `openai` | `gemini` | `minimax`
- `model_name`: model id string
- `temperature`: float, e.g. `0.3`
- `model_api_key` (optional): overrides env var for current game session
- `model_base_url` (optional): provider endpoint override

## 6.1 `mock` (default, safest for local full-loop test)
No API key required.
System uses rule fallback to keep game running.

Example:

```json
{
  "model_provider": "mock",
  "model_name": "rule-fallback"
}
```

## 6.2 `openai`
Requirements:
- Install package (already in requirements in this project): `openai`
- Set env var `OPENAI_API_KEY`

PowerShell example:

```powershell
$env:OPENAI_API_KEY = "<your-openai-api-key>"
```

Create game payload example:

```json
{
  "model_provider": "openai",
  "model_name": "gpt-4.1-mini",
  "temperature": 0.3
}
```

## 6.3 `gemini`
Requirements:
- Install package: `google-generativeai`
- Set env var `GOOGLE_API_KEY`

PowerShell example:

```powershell
$env:GOOGLE_API_KEY = "<your-google-api-key>"
```

Create game payload example:

```json
{
  "model_provider": "gemini",
  "model_name": "gemini-1.5-pro",
  "temperature": 0.3
}
```

## 6.4 Fallback behavior (important)
If model call fails (missing key, provider unavailable, invalid JSON output), server falls back to deterministic rule behavior so the game can continue.

## 6.5 `minimax`
Current integration path uses OpenAI-compatible API style.

You can configure key in either way:

1. Environment variables (recommended)

```powershell
$env:MINIMAX_API_KEY = "<your-minimax-api-key>"
$env:MINIMAX_BASE_URL = "<your-openai-compatible-base-url>"
```

2. UI / create API payload (session-scoped)
- In `/ui`, set provider to `minimax`, then fill `API Key` and `Base URL`.
- Or send in create payload. If you need to share examples publicly, replace the key with a placeholder and prefer env vars in real usage:

```json
{
  "solo_human_mode": true,
  "solo_human_slots": 5,
  "model_provider": "minimax",
  "model_name": "abab6.5-chat",
  "model_api_key": "<redacted-or-set-via-env>",
  "model_base_url": "<your-openai-compatible-base-url>",
  "temperature": 0.3
}
```

Note: Different MiniMax accounts/models may use different model IDs and endpoints. If unsure, use your account's official API docs as source of truth.

## 7. Suggested Practical Flow (Your Scenario)
For one-API-client play testing:
1. `POST /games/create` with `solo_human_mode=true`, `solo_human_slots=5`.
2. Loop:
   - `GET /games/{game_id}/pending`
   - For each `is_human=true` pending slot, call `POST /actions/{slot_id}`.
   - Call `POST /autoplay` to process AI turns.
3. End when `status=FINISHED`.
4. Inspect `GET /games/{game_id}/history`.

## 8. Common Errors
- `400 detail: SKILL is not valid during stage ...`
  - Action does not match current stage.
- `400 detail: Self-targeting is not allowed`
  - Current action forbids self-target.
- `404 Game not found`
  - Wrong `game_id` or server restarted.

## 9. Notes
- Current MVP keeps game sessions in memory.
- Restarting backend clears all active games.
- Protocol details are in `PROTOCOLS.md`.
