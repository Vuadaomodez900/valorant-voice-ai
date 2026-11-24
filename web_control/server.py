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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
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
from core.game_profiles import game_profile_manager
from core.minecraft_agent import minecraft_agent
from core.security import security_guard, sanitize_data_payload
from core.auth import auth_manager, UserSession

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


class GameProfileRequest(BaseModel):
    profile_id: str


class MinecraftActionRequest(BaseModel):
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)


class MinecraftNeuroChatRequest(BaseModel):
    prompt: str


class MinecraftParticleRequest(BaseModel):
    aura: Optional[str] = None
    trail: Optional[bool] = None
    beacon: Optional[bool] = None
    density: float = 1.0


class MinecraftCopilotRequest(BaseModel):
    autonomous: Optional[bool] = None
    auto_shield: Optional[bool] = None
    auto_eat: Optional[bool] = None
    auto_escape: Optional[bool] = None
    reactive_voice: Optional[bool] = None


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

    def on_neuro_speech(text: str, emotion: str):
        if main_event_loop and main_event_loop.is_running() and ws_manager.active_connections:
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast({"type": "neuro_commentary", "text": text, "emotion": emotion}),
                main_event_loop
            )

    minecraft_agent.register_commentary_listener(on_neuro_speech)

    def on_profile_switch(profile):
        if main_event_loop and main_event_loop.is_running() and ws_manager.active_connections:
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast({
                    "type": "profile_changed",
                    "id": profile.profile_id,
                    "name": profile.name,
                    "icon": profile.icon
                }),
                main_event_loop
            )

    game_profile_manager.register_profile_change_listener(on_profile_switch)


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
    """Returns complete system diagnostics, component health, and issues (sanitized against secret leaks)."""
    diag = self_healer.diagnose_system()
    return sanitize_data_payload(diag)


@app.post("/api/auto-fix")
async def run_auto_fix():
    """Autonomous Self-Healing: fixes drivers, audio streams, tunnels, and configuration."""
    result = self_healer.auto_fix_system()
    await ws_manager.broadcast({
        "type": "system_healed",
        "health_score": result.get("health_after_fix", 100),
        "actions": result.get("actions_taken", [])
    })
    return sanitize_data_payload(result)


@app.get("/api/config")
async def get_current_config():
    """Returns live application configuration (sanitized against secret leaks)."""
    return sanitize_data_payload(config.data)


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


# =============================================================================
# Multi-Game Profile APIs
# =============================================================================

@app.get("/api/game/profiles")
async def get_game_profiles():
    """Lists all game profiles and returns the currently active one."""
    return {
        "active_profile": game_profile_manager.get_active_profile().to_dict(),
        "profiles": game_profile_manager.list_profiles()
    }


@app.post("/api/game/profile")
async def set_game_profile(req: GameProfileRequest):
    """Switches active game profile (valorant, minecraft, roblox, desktop)."""
    success = game_profile_manager.set_active_profile(req.profile_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Unknown game profile: {req.profile_id}")
    active = game_profile_manager.get_active_profile()
    return {"status": "ok", "active_profile": active.to_dict()}


# =============================================================================
# Minecraft (Neuro-sama) Autonomous APIs
# =============================================================================

@app.get("/api/minecraft/state")
async def get_minecraft_state():
    """Fetches live Minecraft world and player telemetry."""
    state = minecraft_agent.fetch_state()
    return {
        "connected": minecraft_agent.is_connected,
        "in_game": minecraft_agent.in_game,
        "state": state
    }


@app.post("/api/minecraft/action")
async def send_minecraft_action(req: MinecraftActionRequest):
    """Sends action to Minecraft client (move, jump, attack, eat, autopilot, etc.)."""
    success = minecraft_agent.send_action(req.action, **req.params)
    return {"status": "ok" if success else "failed", "action": req.action}


@app.post("/api/minecraft/neuro_chat")
async def chat_with_neuro_sama(req: MinecraftNeuroChatRequest):
    """Chats with Neuro-sama persona with live Minecraft world awareness."""
    reply = minecraft_agent.chat_with_neuro(req.prompt)
    await ws_manager.broadcast({
        "type": "neuro_chat_reply",
        "prompt": req.prompt,
        "reply": reply
    })
    return {"status": "ok", "reply": reply}


@app.post("/api/minecraft/copilot")
async def configure_minecraft_copilot(req: MinecraftCopilotRequest):
    """Configures autonomous behaviors for Neuro-sama in Minecraft."""
    if req.autonomous is not None:
        minecraft_agent.autonomous_enabled = req.autonomous
    if req.auto_shield is not None:
        minecraft_agent.auto_shield_enabled = req.auto_shield
    if req.auto_eat is not None:
        minecraft_agent.auto_eat_enabled = req.auto_eat
    if req.auto_escape is not None:
        minecraft_agent.auto_escape_enabled = req.auto_escape
    if req.reactive_voice is not None:
        minecraft_agent.reactive_voice_enabled = req.reactive_voice

    return {
        "status": "ok",
        "autonomous_enabled": minecraft_agent.autonomous_enabled,
        "auto_shield_enabled": minecraft_agent.auto_shield_enabled,
        "auto_eat_enabled": minecraft_agent.auto_eat_enabled,
        "auto_escape_enabled": minecraft_agent.auto_escape_enabled,
        "reactive_voice_enabled": minecraft_agent.reactive_voice_enabled,
    }


@app.post("/api/minecraft/particle")
async def configure_minecraft_particle(req: MinecraftParticleRequest):
    """Configures Particle FX (aura, trail, ore beacon)."""
    res = minecraft_agent.set_particle_fx(
        aura=req.aura,
        trail=req.trail,
        beacon=req.beacon,
        density=req.density
    )
    return res


# =============================================================================
# Security & Anti-Tamper Status
# =============================================================================

@app.get("/api/security/status")
async def get_security_status():
    """Returns runtime anti-debugging, anti-tamper, and integrity evaluation."""
    return security_guard.self_check()


# =============================================================================
# OAuth2 Social Login & Session Management (Discord, GitHub, Google)
# =============================================================================

@app.get("/api/auth/providers")
async def get_auth_providers():
    """Lists available social OAuth2 providers and their configuration status."""
    providers = {}
    for p in ["discord", "github", "google"]:
        creds = auth_manager.get_provider_credentials(p)
        providers[p] = {
            "name": p.capitalize(),
            "has_credentials": bool(creds["client_id"] and creds["client_secret"]),
            "client_id_preview": creds["client_id"][:6] + "..." if creds["client_id"] else "None (Dev Mode Available)"
        }
    return {
        "providers": providers,
        "allow_guest": config.data.get("auth", {}).get("allow_guest", True)
    }


@app.get("/api/auth/login/{provider}")
async def oauth_login_redirect(provider: str, request: Request):
    """Initiates OAuth2 login by redirecting to provider's authorization portal."""
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/auth/callback/{provider}"
    try:
        auth_url = auth_manager.generate_authorization_url(provider, redirect_uri)
        # If client requested JSON (e.g. from AJAX), return URL; otherwise redirect directly
        accept = request.headers.get("accept", "")
        if "application/json" in accept:
            return {"status": "ok", "auth_url": auth_url}
        return RedirectResponse(url=auth_url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/auth/callback/{provider}")
async def oauth_callback(provider: str, code: str = "", state: str = ""):
    """Handles OAuth2 redirect callback, verifies state, and issues session token."""
    user = auth_manager.exchange_code_for_session(provider, code, state)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication failed or state expired")

    token = auth_manager.issue_session_token(user)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 14,
        path="/"
    )
    return response


@app.get("/api/auth/mock-login")
async def oauth_mock_login(provider: str = "discord", state: str = ""):
    """Instant simulated social login for testing when cloud secrets are not yet registered."""
    user = auth_manager.exchange_code_for_session(provider, f"mock_{provider}", state)
    if not user:
        user = auth_manager._generate_mock_user(provider)

    token = auth_manager.issue_session_token(user)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 14,
        path="/"
    )
    return response


@app.get("/api/auth/me")
async def get_current_user_profile(
    request: Request,
    session_token: Optional[str] = Cookie(None)
):
    """Returns currently authenticated user profile from cookie or Bearer token."""
    token = session_token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    user = auth_manager.verify_session_token(token) if token else None

    if not user and config.data.get("auth", {}).get("allow_guest", True):
        user = auth_manager.create_guest_session()

    if user:
        return {
            "authenticated": True,
            "user": user.to_dict()
        }
    return {
        "authenticated": False,
        "user": None
    }


@app.post("/api/auth/logout")
async def logout_user():
    """Logs out current user and clears session token cookie."""
    response = JSONResponse(content={"status": "ok", "authenticated": False})
    response.delete_cookie(key="session_token", path="/")
    return response


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
