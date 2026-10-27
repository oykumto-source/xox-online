# XOX Online

A real-time, two-player multiplayer tic-tac-toe game built with Python, FastAPI and WebSockets.

**Live demo:** _(link will be added after deployment)_

## Features

- Create a room and invite a friend with a room code or a shareable link
- Real-time synchronization over WebSockets
- Server-authoritative game logic: the server holds the game state and validates every move, so clients cannot cheat
- Reconnection support: a player who disconnects (page refresh, brief network drop) has 20 seconds to return to the same seat with the same score
- Scoreboard across rounds, with the starting player alternating each round
- Responsive UI that works on desktop and mobile
- Input validation: oversized or malformed messages are ignored

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn, WebSockets
- **Frontend:** plain HTML, CSS and JavaScript (no build step)

## How it works

The browser only sends intents such as "I want to play cell 4". The server checks whose turn it is, whether the cell is free and whether the game is still running, then updates the state and broadcasts it to both players. Each room has its own game object, stored in an in-memory dictionary keyed by room code. Players are identified by a per-tab token, which is how a returning player is matched to their old seat.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn game:app --reload
```

On macOS or Linux, activate the virtual environment with `source .venv/bin/activate` instead.

Then open http://127.0.0.1:8000 in your browser. To test with two players on one machine, open the second player in a private window.

## Project structure

```
game.py            Server: rooms, game rules, WebSocket handling
index.html         Client: UI, styling and WebSocket logic
requirements.txt   Python dependencies
```

## Known limitations

- Rooms live in server memory, so they are lost when the server restarts.
- Designed for a single server process (no horizontal scaling).
- The user interface is currently in Turkish.
- No accounts or persistence: player names exist only for the duration of a session.

## License

MIT, see [LICENSE](LICENSE).