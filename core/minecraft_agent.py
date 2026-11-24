"""
Neuro-sama Style Minecraft Autonomous Agent and Copilot.
Connects with Antigravity Forge 1.20.1 Client Mod at http://127.0.0.1:28888.
Features:
- Live bidirectional telemetry (Player, Inventory, Radar, Danger, Target).
- Autonomous interventions: AutoShield, AutoEat, AutoEscape, AutoPilot, and Mob Combat.
- Neuro-sama reactive persona: spontaneous voiced commentary, screaming at creepers,
  celebrating diamonds, and snappy banter with Live2D lip-sync visemes.
- Direct player and world control actions.
"""

import os
import sys
import time
import json
import random
import threading
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Callable

from core.lipsync import lipsync_analyzer
from core.fast_ai_router import ai_router

DEFAULT_MC_HOST = os.environ.get("MC_BRIDGE_HOST", "127.0.0.1")
DEFAULT_MC_PORT = int(os.environ.get("MC_BRIDGE_PORT", "28888"))

# Pre-scripted instant reactive voice lines for 0-latency reactions (<10ms)
NEURO_REACTIONS = {
    "creeper_alert": [
        "Kyaaaa! Creeper right behind us! Run or shield up!",
        "CREEPER! Don't let it blow up our stuff!",
        "Watch out! That green hiss of doom is right here!",
    ],
    "low_health": [
        "Warning warning! We have almost no hearts left! Eat something right now!",
        "I don't wanna die here! Retreat and heal up!",
        "Low HP alert! Stop fighting and take cover!",
    ],
    "lava_danger": [
        "Aaaaah hot hot hot! We are in lava! Jump out quickly!",
        "Lava bath is NOT recommended! Get to water!",
    ],
    "diamond_found": [
        "Oooooh diamonds! We're rich! Mine it carefully, don't drop it in lava!",
        "Shiny diamonds spotted! That's what I'm talking about!",
        "Diamond time! My VTuber fortune is growing!",
    ],
    "night_alert": [
        "Night has fallen... The spooky monsters are coming out to play!",
        "It's dark outside. Should we build a fortress or go mob hunting?",
    ],
    "mob_defeated": [
        "Target eliminated! Neuro-sama reigns supreme!",
        "Easy win! Is that the best this Minecraft world can do?",
        "Another mob down. Good job team!",
    ],
    "idle_banter": [
        "Do you think Endermen get lonely standing in the rain?",
        "I could totally beat the Ender Dragon with just my bare hands.",
        "Remember, mining straight down is either brave or crazy. I vote brave!",
        "Heart heart heart! Neuro-sama is watching your back in Minecraft!",
    ],
}


class MinecraftAgent:
    """Autonomous agent and copilot playing Minecraft like Neuro-sama."""

    def __init__(self, host: str = DEFAULT_MC_HOST, port: int = DEFAULT_MC_PORT):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"

        # State tracking
        self.is_connected = False
        self.in_game = False
        self.last_state: Dict[str, Any] = {}
        self.last_state_time = 0.0

        # Copilot autonomous settings
        self.autonomous_enabled = True
        self.auto_shield_enabled = True
        self.auto_eat_enabled = True
        self.auto_escape_enabled = True
        self.reactive_voice_enabled = True

        # Internal cooldowns
        self._last_reaction_time: Dict[str, float] = {}
        self._last_idle_chatter_time = time.time()
        self._known_ores: set = set()

        # Callbacks
        self._commentary_listeners: List[Callable[[str, str], None]] = []  # (text, emotion)

        # Background loop
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def set_endpoint(self, host: str, port: int) -> None:
        with self._lock:
            self.host = host
            self.port = port
            self.base_url = f"http://{host}:{port}"

    def register_commentary_listener(self, listener: Callable[[str, str], None]) -> None:
        self._commentary_listeners.append(listener)

    # -------------------------------------------------------------------------
    # HTTP Bridge API Calls
    # -------------------------------------------------------------------------
    def _api_call(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None, timeout: float = 2.5) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        req = urllib.request.Request(url, method=method)
        req.add_header("Content-Type", "application/json")
        body = json.dumps(data).encode("utf-8") if data is not None else None

        try:
            with urllib.request.urlopen(req, data=body, timeout=timeout) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else {"status": "ok"}
        except urllib.error.URLError:
            return {"error": "connection_failed"}
        except Exception as e:
            return {"error": str(e)}

    def ping(self) -> bool:
        res = self._api_call("/api/v1/ping", timeout=1.5)
        self.is_connected = "error" not in res
        if self.is_connected:
            self.in_game = res.get("in_game", False)
        else:
            self.in_game = False
        return self.is_connected

    def fetch_state(self) -> Dict[str, Any]:
        res = self._api_call("/api/v1/state")
        if "error" not in res:
            with self._lock:
                self.last_state = res
                self.last_state_time = time.time()
                self.is_connected = True
                self.in_game = res.get("in_game", False)
            return res
        with self._lock:
            self.is_connected = False
        return self.last_state

    # -------------------------------------------------------------------------
    # Actions & Game Control
    # -------------------------------------------------------------------------
    def send_action(self, action_type: str, **kwargs) -> bool:
        """Sends physical client action to Minecraft (move, jump, attack, etc.)."""
        payload = {"action": action_type}
        payload.update(kwargs)
        res = self._api_call("/api/v1/action", method="POST", data=payload)
        return res.get("success", False) or res.get("status") == "ok"

    def send_in_game_chat(self, message: str, action_bar: bool = False) -> bool:
        """Sends chat message or action-bar toast inside Minecraft screen."""
        payload = {"message": message, "action_bar": action_bar}
        res = self._api_call("/api/v1/chat", method="POST", data=payload)
        return res.get("success", False) or res.get("status") == "ok"

    def move(self, direction: str = "forward", duration: float = 1.0, sprint: bool = False) -> bool:
        return self.send_action("move", direction=direction, duration=duration, sprint=sprint)

    def jump(self) -> bool:
        return self.send_action("jump")

    def attack(self, duration: float = 1.0) -> bool:
        return self.send_action("attack", duration=duration)

    def swing_arm(self) -> bool:
        return self.send_action("swing_arm")

    def eat(self) -> bool:
        return self.send_action("eat")

    def use_shield(self, duration: float = 1.5) -> bool:
        return self.send_action("use_shield", duration=duration)

    def select_slot(self, slot: int) -> bool:
        return self.send_action("select_slot", slot=max(0, min(8, slot)))

    def look_at(self, yaw: float, pitch: float) -> bool:
        return self.send_action("look_at", yaw=yaw, pitch=pitch)

    def goto_coords(self, x: float, z: float) -> bool:
        return self.send_action("goto", x=x, z=z)

    def set_autopilot(self, enable: bool) -> bool:
        return self.send_action("autopilot", enable=enable)

    def set_particle_fx(self, aura: Optional[str] = None, trail: Optional[bool] = None, beacon: Optional[bool] = None, density: float = 1.0) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"density": density}
        if aura:
            payload["aura"] = aura
        if trail is not None:
            payload["trail"] = trail
        if beacon is not None:
            payload["beacon"] = beacon
        return self._api_call("/api/v1/particle", method="POST", data=payload)

    def scan_xray(self, radius: int = 16) -> Dict[str, Any]:
        return self._api_call(f"/api/v1/xray?radius={radius}")

    # -------------------------------------------------------------------------
    # Neuro-sama Reactive Voice & Commentary
    # -------------------------------------------------------------------------
    def trigger_neuro_voice(self, category: str, text: Optional[str] = None, emotion: str = "happy") -> str:
        """Triggers a Neuro-sama voice reaction with Live2D lip-sync and desktop popups."""
        if not text:
            pool = NEURO_REACTIONS.get(category, NEURO_REACTIONS["idle_banter"])
            text = random.choice(pool)

        # Animate desktop Live2D pet avatar immediately
        lipsync_analyzer.synthesize_mock_viseme_stream(text)

        # Notify UI and sound listeners
        for listener in self._commentary_listeners:
            try:
                listener(text, emotion)
            except Exception:
                pass

        # Also push to Minecraft action bar or chat if in-game
        if self.in_game:
            self.send_in_game_chat(f"§d[Neuro]§f {text}", action_bar=True)

        return text

    def chat_with_neuro(self, user_prompt: str) -> str:
        """Chats with Neuro-sama, injecting live Minecraft telemetry into context."""
        state = self.last_state
        player = state.get("player", {})
        env = state.get("environment", {})
        danger = state.get("danger", {})
        radar = state.get("radar", {})

        mc_context = (
            f"[Current Minecraft Context: HP={player.get('health', 20)}/20, "
            f"Food={player.get('food_level', 20)}/20, "
            f"Coords=({player.get('x', 0):.1f}, {player.get('y', 0):.1f}, {player.get('z', 0):.1f}), "
            f"Biome={env.get('biome', 'Unknown')}, "
            f"Danger={danger.get('level', 'SAFE')}, "
            f"HostilesNearby={radar.get('hostile_count', 0)}]"
        )

        full_prompt = f"{mc_context}\nUser says: {user_prompt}\nNeuro-sama reply:"
        response = ai_router.generate_tactical_advice(
            screen_analysis=mc_context,
            game_state={"minecraft": state},
            user_question=user_prompt
        )

        # Trigger reactive speech and visemes
        self.trigger_neuro_voice("chat", text=response, emotion="happy")
        return response

    # -------------------------------------------------------------------------
    # Telemetry Monitor & Autonomous Decisions
    # -------------------------------------------------------------------------
    def _evaluate_autonomous_triggers(self, state: Dict[str, Any]) -> None:
        """Analyzes state changes and triggers instant Neuro reactions and copilot actions."""
        if not self.in_game:
            return

        now = time.time()
        player = state.get("player", {})
        danger = state.get("danger", {})
        radar = state.get("radar", {})
        env = state.get("environment", {})
        target = state.get("target", {})

        hp = float(player.get("health", 20.0))
        food = int(player.get("food_level", 20))
        danger_lvl = danger.get("level", "SAFE")
        reasons = " ".join(danger.get("reasons", [])).lower()

        # 1. Creeper Danger Check
        has_creeper = "creeper" in reasons or any(
            h.get("name", "").lower() == "creeper" and float(h.get("distance", 99)) <= 7.0
            for h in radar.get("hostiles", [])
        )
        if has_creeper and (now - self._last_reaction_time.get("creeper", 0)) > 15.0:
            self._last_reaction_time["creeper"] = now
            self.trigger_neuro_voice("creeper_alert", emotion="panic")
            if self.autonomous_enabled and self.auto_shield_enabled:
                self.use_shield(duration=2.0)

        # 2. Critical Low Health Check
        if hp <= 6.0 and (now - self._last_reaction_time.get("low_hp", 0)) > 20.0:
            self._last_reaction_time["low_hp"] = now
            self.trigger_neuro_voice("low_health", emotion="worried")
            if self.autonomous_enabled and self.auto_escape_enabled:
                self.set_autopilot(True)
                self.eat()

        # 3. Lava / Fire Check
        if "lava" in reasons or "fire" in reasons:
            if (now - self._last_reaction_time.get("lava", 0)) > 10.0:
                self._last_reaction_time["lava"] = now
                self.trigger_neuro_voice("lava_danger", emotion="panic")
                if self.autonomous_enabled:
                    self.jump()

        # 4. Auto-Eat Check
        if self.autonomous_enabled and self.auto_eat_enabled:
            if (food <= 14 or (hp <= 16.0 and food < 20)) and (now - self._last_reaction_time.get("eat", 0)) > 10.0:
                self._last_reaction_time["eat"] = now
                self.eat()

        # 5. Ore discovery check
        if target.get("type") == "BLOCK":
            block = target.get("block", {})
            block_id = block.get("id", "").lower()
            if "diamond" in block_id or "debris" in block_id or "emerald" in block_id:
                coord_key = f"{block.get('x')}_{block.get('y')}_{block.get('z')}"
                if coord_key not in self._known_ores:
                    self._known_ores.add(coord_key)
                    if (now - self._last_reaction_time.get("diamond", 0)) > 25.0:
                        self._last_reaction_time["diamond"] = now
                        self.trigger_neuro_voice("diamond_found", emotion="excited")

        # 6. Idle Neuro banter
        if (now - self._last_idle_chatter_time) > 60.0 and danger_lvl == "SAFE":
            self._last_idle_chatter_time = now
            if self.reactive_voice_enabled and random.random() < 0.6:
                self.trigger_neuro_voice("idle_banter", emotion="happy")

    def _loop(self) -> None:
        while self._running:
            try:
                state = self.fetch_state()
                if self.is_connected and self.in_game:
                    self._evaluate_autonomous_triggers(state)
            except Exception as e:
                pass
            time.sleep(1.0)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="MinecraftNeuroAgent")
        self._thread.start()
        print(f"[MinecraftAgent] Started Neuro-sama agent thread targeting http://{self.host}:{self.port}")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        print("[MinecraftAgent] Stopped")


# Global singleton instance
minecraft_agent = MinecraftAgent()
