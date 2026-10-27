import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()
PAGE_FILE = Path(__file__).parent / "index.html"

WIN_LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
GRACE_SECONDS = 20   # kopan oyuncunun geri dönmesi için bekleme süresi
MAX_MSG = 200        # bundan uzun mesajlar yok sayılır


def other(mark):
    return "O" if mark == "X" else "X"


class Player:
    def __init__(self, mark, name, token, ws):
        self.mark = mark
        self.name = name
        self.token = token
        self.ws = ws            # bağlantı koptuysa None
        self.drop_task = None   # koltuğu boşaltacak zamanlayıcı


class Game:
    def __init__(self):
        self.players: dict[str, Player] = {}
        self.full_reset()

    def full_reset(self):
        self.scores = {"X": 0, "O": 0, "draw": 0}
        self.first = "X"
        self.new_round()

    def new_round(self):
        self.board = [""] * 9
        self.turn = self.first
        self.winner = None  # "X", "O", "draw" ya da None

    def ready(self):
        return len(self.players) == 2 and all(
            p.ws is not None for p in self.players.values()
        )

    def check_winner(self):
        for a, b, c in WIN_LINES:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        if all(self.board):
            return "draw"
        return None

    def state(self):
        return {
            "type": "state",
            "board": self.board,
            "turn": self.turn,
            "winner": self.winner,
            "scores": self.scores,
            "players": {
                m: {"name": p.name, "online": p.ws is not None}
                for m, p in self.players.items()
            },
        }

    async def broadcast(self):
        msg = json.dumps(self.state())
        for p in list(self.players.values()):
            if p.ws is not None:
                try:
                    await p.ws.send_text(msg)
                except Exception:
                    pass


rooms: dict[str, Game] = {}


async def drop_later(code, game, player):
    """Oyuncu kopunca süre tanır; dönmezse koltuğu boşaltır."""
    try:
        await asyncio.sleep(GRACE_SECONDS)
    except asyncio.CancelledError:
        return
    if game.players.get(player.mark) is player and player.ws is None:
        del game.players[player.mark]
        game.full_reset()
        if game.players:
            await game.broadcast()
        elif rooms.get(code) is game:
            del rooms[code]


@app.get("/")
async def index():
    return HTMLResponse(PAGE_FILE.read_text(encoding="utf-8"))


@app.websocket("/ws/{code}")
async def ws_endpoint(ws: WebSocket, code: str, name: str = "", token: str = ""):
    await ws.accept()
    code = code.upper()
    token = token[:64]
    name = " ".join(name.split())[:16]

    if not (4 <= len(code) <= 8 and code.isascii() and code.isalnum()) or not token:
        await ws.send_text(json.dumps({"type": "error", "msg": "Geçersiz oda kodu."}))
        await ws.close()
        return

    game = rooms.setdefault(code, Game())

    # Aynı token ile gelen oyuncu: kendi koltuğuna geri dönüyor
    player = next((p for p in game.players.values() if p.token == token), None)
    if player:
        if player.drop_task:
            player.drop_task.cancel()
            player.drop_task = None
        old = player.ws
        player.ws = ws
        if name:
            player.name = name
        if old is not None:
            try:
                await old.close()
            except Exception:
                pass
    else:
        mark = next((m for m in ("X", "O") if m not in game.players), None)
        if mark is None:
            await ws.send_text(json.dumps({"type": "full"}))
            await ws.close()
            return
        player = Player(mark, name or f"Oyuncu {mark}", token, ws)
        game.players[mark] = player

    mark = player.mark
    await ws.send_text(json.dumps({"type": "you", "mark": mark}))
    await game.broadcast()

    try:
        while True:
            text = await ws.receive_text()
            if len(text) > MAX_MSG:
                continue
            try:
                data = json.loads(text)
            except ValueError:
                continue
            if not isinstance(data, dict):
                continue

            kind = data.get("type")
            if kind == "move":
                i = data.get("cell")
                if (
                    game.winner is None
                    and game.ready()
                    and game.turn == mark
                    and type(i) is int
                    and 0 <= i < 9
                    and game.board[i] == ""
                ):
                    game.board[i] = mark
                    game.winner = game.check_winner()
                    if game.winner:
                        game.scores[game.winner] += 1
                    else:
                        game.turn = other(mark)
                    await game.broadcast()
            elif kind == "reset":
                if game.winner is not None and game.ready():
                    game.first = other(game.first)
                    game.new_round()
                    await game.broadcast()
            # "ping" mesajları sadece bağlantıyı canlı tutar, işlem yok
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # Eski bağlantı yenisiyle değiştirildiyse dokunma
        if player.ws is ws:
            player.ws = None
            player.drop_task = asyncio.create_task(drop_later(code, game, player))
            await game.broadcast()