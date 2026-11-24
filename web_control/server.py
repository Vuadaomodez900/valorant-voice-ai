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
import asyncio
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
from core.self_healer import self_healer
from core.lipsync import lipsync_analyzer
from core.fast_ai_router import ai_router

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


class CalloutRequest(BaseModel):
    text: str
    channel: str = "team"
    speak_in_game: bool = True
    speak_to_user: bool = True


class ConfigUpdateRequest(BaseModel):
    updates: Dict[str, Any]


class AIProviderRequest(BaseModel):
    provider: str  # "antigravity_cli", "gemini_live", "claude_code", "codex", "direct_api"
    api_key: Optional[str] = ""
    model: Optional[str] = ""


class AIChatRequest(BaseModel):
    prompt: str


class TamagotchiModeRequest(BaseModel):
    mode: str  # "tamagotchi", "notification", "card"


main_event_loop = None


@app.on_event("startup")
async def startup_event():
    global main_event_loop
    try:
        main_event_loop = asyncio.get_running_loop()
    except Exception:
        main_event_loop = None

    def on_viseme(state: dict):
        if main_event_loop and main_event_loop.is_running() and ws_manager.active_connections:
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast({"type": "lipsync", "data": state}),
                main_event_loop
            )

    lipsync_analyzer.register_subscriber(on_viseme)


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


@app.post("/api/callout")
async def handle_callout(req: CalloutRequest):
    """Allows phone / AGY CLI to send a tactical callout to the game."""
    draft = chat_manager.propose_chat(req.text, target_channel=req.channel)
    await ws_manager.broadcast({
        "type": "chat_draft",
        "draft_id": draft.draft_id,
        "content": draft.content,
        "channel": draft.target_channel
    })
    return {"status": "ok", "draft_id": draft.draft_id, "content": draft.content}


@app.get("/api/diagnostics")
async def get_diagnostics():
    """Returns complete system diagnostics, component health, and issues."""
    return self_healer.diagnose_system()


@app.post("/api/auto-fix")
async def run_auto_fix():
    """Autonomous Self-Healing: fixes drivers, audio streams, tunnels, and configuration."""
    result = self_healer.auto_fix_system()
    await ws_manager.broadcast({
        "type": "system_healed",
        "health_score": result.get("health_after_fix", 100),
        "actions": result.get("actions_taken", [])
    })
    return result


@app.get("/api/config")
async def get_current_config():
    """Returns live application configuration."""
    return config.data


@app.post("/api/config")
async def update_runtime_config(req: ConfigUpdateRequest):
    """Enables AI agents to dynamically change any configuration setting on the fly."""
    result = self_healer.update_runtime_config(req.updates)
    await ws_manager.broadcast({
        "type": "config_updated",
        "applied_keys": result.get("applied_keys", [])
    })
    return result


@app.get("/api/ai/provider")
async def get_ai_provider():
    """Returns currently active AI backend provider and model."""
    cfg = config.data.get("ai", {})
    return {
        "provider": ai_router.current_provider,
        "model": cfg.get("model", "gemini-2.0-flash"),
        "gateway_url": cfg.get("antigravity_gateway_url", "http://127.0.0.1:20128/v1"),
        "has_api_key": bool(cfg.get("api_key"))
    }


@app.post("/api/ai/provider")
async def set_ai_provider(req: AIProviderRequest):
    """Dynamically switches AI provider (Antigravity CLI / Codex / Claude Code / Gemini Live / API Key)."""
    ai_router.set_provider(req.provider, req.api_key or "", req.model or "")
    await ws_manager.broadcast({
        "type": "provider_changed",
        "provider": req.provider,
        "model": req.model
    })
    return {"status": "ok", "provider": req.provider}


@app.post("/api/ai/chat")
async def send_fast_chat(req: AIChatRequest):
    """Low-latency streaming chat query with instant tactical cache and lip-sync."""
    reply = ai_router.query_fast(req.prompt)
    await ws_manager.broadcast({
        "type": "ai_reply",
        "prompt": req.prompt,
        "response": reply
    })
    return {"status": "ok", "response": reply}


@app.post("/api/tamagotchi/mode")
async def set_tamagotchi_mode(req: TamagotchiModeRequest):
    """Switches overlay between tamagotchi (desktop pet), notification (toast), and card modes."""
    config.data["overlay"]["mode"] = req.mode
    config.save()
    await ws_manager.broadcast({
        "type": "overlay_mode_changed",
        "mode": req.mode
    })
    return {"status": "ok", "mode": req.mode}


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
