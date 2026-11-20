"""
FastAPI LAN Web Server with Real-time WebSocket Control.
Controls:
- Headphone Volume (0-200%)
- Game Mic Output Volume (0-200%)
- Mute/Unmute AI voice to game
- Live Screen Stream FPS Slider (1-5 FPS)
- AI Voice Presets, Rate, Pitch
- Permission-Gated Chat Draft Approval / Rejection
- Integrated Virtual Audio Cable 1-Click Driver Installation
- QR Code generation for 1-touch mobile LAN connection
"""

import socket
import io
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import qrcode
from core.config import config, get_resource_path
from core.in_game_chat import chat_manager
from core.cable_installer import is_vbcable_installed, install_vbcable_integrated

app = FastAPI(title="Valorant Voice AI - LAN Control", docs_url=None, redoc_url=None)

# Resolve templates and static directories (supporting PyInstaller bundle)
STATIC_DIR = Path(get_resource_path("web_control/static"))
TEMPLATES_DIR = Path(get_resource_path("web_control/templates"))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_local_ip() -> str:
    """Detects local LAN IPv4 address reliably."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        with self._lock:
            self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        with self._lock:
            conns = list(self.active_connections)
        for conn in conns:
            try:
                await conn.send_json(message)
            except Exception:
                pass


ws_manager = ConnectionManager()

# References to shared engine components
engine_router = None
engine_screen = None
engine_bridge = None
engine_orchestrator = None


def bind_engine_components(router, screen, bridge, orchestrator=None):
    global engine_router, engine_screen, engine_bridge, engine_orchestrator
    engine_router = router
    engine_screen = screen
    engine_bridge = bridge
    engine_orchestrator = orchestrator


# Pydantic Request Models
class VolumeUpdateRequest(BaseModel):
    headphone: Optional[float] = Field(None, ge=0.0, le=2.0)
    game_mic: Optional[float] = Field(None, ge=0.0, le=2.0)
    mute_game_mic: Optional[bool] = None


class ScreenSettingsRequest(BaseModel):
    fps: int = Field(..., ge=1, le=10)


class VoiceSettingsRequest(BaseModel):
    voice_name: str
    speech_rate: float = Field(1.0, ge=0.5, le=2.0)
    pitch: float = Field(0.0, ge=-10.0, le=10.0)


class ChatActionRequest(BaseModel):
    draft_id: str
    action: str


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    local_ip = get_local_ip()
    port = config.data["web"]["port"]
    url = f"http://{local_ip}:{port}"
    context = {
        "request": request,
        "local_url": url,
        "local_ip": local_ip,
        "port": port,
        "has_cable": is_vbcable_installed(),
        "require_pin": config.data["web"]["require_pin"],
    }
    try:
        # Starlette >= 0.28 / 0.36+ signature: TemplateResponse(request=request, name="index.html", context=context)
        return templates.TemplateResponse(request=request, name="index.html", context=context)
    except TypeError:
        # Starlette < 0.28 legacy signature: TemplateResponse("index.html", context)
        return templates.TemplateResponse("index.html", context)


@app.get("/api/qr")
async def get_qr_code():
    local_ip = get_local_ip()
    port = config.data["web"]["port"]
    url = f"http://{local_ip}:{port}"

    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#FF4655", back_color="#12161C")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/api/status")
async def get_system_status():
    headphone_vol = engine_router.volume_headphone if engine_router else 1.0
    game_mic_vol = engine_router.volume_game_mic if engine_router else 1.0
    is_muted = engine_router.mute_game_mic if engine_router else False
    fps = engine_screen.fps_live if engine_screen else 2
    is_connected = engine_bridge.is_connected if engine_bridge else False

    active_draft = None
    if chat_manager.current_active_draft and chat_manager.current_active_draft.status == "PENDING":
        active_draft = {
            "draft_id": chat_manager.current_active_draft.draft_id,
            "content": chat_manager.current_active_draft.content,
            "channel": chat_manager.current_active_draft.target_channel
        }

    return {
        "headphone_volume": headphone_vol,
        "game_mic_volume": game_mic_vol,
        "mute_game_mic": is_muted,
        "screen_fps": fps,
        "gemini_connected": is_connected,
        "has_virtual_cable": is_vbcable_installed(),
        "teammate_voice_trigger": engine_orchestrator.teammate_voice_trigger_enabled if engine_orchestrator else True,
        "voice_name": config.data["gemini"]["voice_name"],
        "pending_chat": active_draft
    }


@app.post("/api/teammate-trigger")
async def toggle_teammate_trigger(req: dict):
    enabled = req.get("enabled", True)
    if engine_orchestrator:
        engine_orchestrator.set_teammate_voice_trigger(enabled)
    return {"status": "ok", "enabled": enabled}


@app.post("/api/cable/install")
async def trigger_cable_installation():
    """Triggers 1-click silent elevated installation of embedded virtual cable driver."""
    success, message = install_vbcable_integrated()
    return {"success": success, "message": message}


@app.post("/api/volume")
async def update_volume(req: VolumeUpdateRequest):
    if engine_router:
        if req.headphone is not None:
            engine_router.set_headphone_volume(req.headphone)
        if req.game_mic is not None:
            engine_router.set_game_mic_volume(req.game_mic)
        if req.mute_game_mic is not None:
            engine_router.mute_game_mic = req.mute_game_mic

        await ws_manager.broadcast({
            "type": "volume_update",
            "headphone": engine_router.volume_headphone,
            "game_mic": engine_router.volume_game_mic,
            "mute_game_mic": engine_router.mute_game_mic
        })
    return {"status": "ok"}


@app.post("/api/screen")
async def update_screen(req: ScreenSettingsRequest):
    if engine_screen:
        engine_screen.set_live_fps(req.fps)
        await ws_manager.broadcast({
            "type": "screen_update",
            "fps": engine_screen.fps_live
        })
    return {"status": "ok"}


@app.post("/api/voice")
async def update_voice(req: VoiceSettingsRequest):
    config.data["gemini"]["voice_name"] = req.voice_name
    config.data["gemini"]["speech_rate"] = req.speech_rate
    config.data["gemini"]["pitch"] = req.pitch
    config.save()
    if engine_bridge:
        engine_bridge.voice_name = req.voice_name
    return {"status": "ok"}


@app.post("/api/chat/action")
async def handle_chat_action(req: ChatActionRequest):
    if req.action == "approve":
        success = chat_manager.approve_and_send(req.draft_id)
        return {"status": "sent" if success else "failed"}
    elif req.action == "reject":
        chat_manager.reject(req.draft_id)
        return {"status": "rejected"}
    raise HTTPException(status_code=400, detail="Invalid action")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
