"""
Multi-Game Profile Manager for Valorant, Minecraft (Neuro-sama), Roblox, and Desktop.
Manages game profiles, active game detection, custom system prompts, and HUD configurations.
"""

import threading
from typing import Dict, Any, List, Optional, Callable


class GameProfile:
    """Represents a specific game or companion environment configuration."""

    def __init__(
        self,
        profile_id: str,
        name: str,
        icon: str,
        target_processes: List[str],
        system_prompt: str,
        default_overlay_mode: str = "tamagotchi",
        description: str = "",
        features: Optional[Dict[str, Any]] = None,
    ):
        self.profile_id = profile_id.lower()
        self.name = name
        self.icon = icon
        self.target_processes = [p.lower() for p in target_processes]
        self.system_prompt = system_prompt
        self.default_overlay_mode = default_overlay_mode
        self.description = description
        self.features = features or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.profile_id,
            "name": self.name,
            "icon": self.icon,
            "target_processes": self.target_processes,
            "system_prompt": self.system_prompt,
            "default_overlay_mode": self.default_overlay_mode,
            "description": self.description,
            "features": self.features,
        }


# Pre-defined Profiles
PROFILES: Dict[str, GameProfile] = {
    "desktop": GameProfile(
        profile_id="desktop",
        name="Desktop Companion",
        icon="🌸",
        target_processes=[],
        default_overlay_mode="tamagotchi",
        description="General desktop companion (Sakura / Neuro pet) for work, chat, code, and daily assistance.",
        system_prompt=(
            "You are Sakura, a witty, charming, and highly intelligent AI desktop companion. "
            "You live right on the user's computer screen as an interactive pet. "
            "Respond naturally, playfully, and concisely. Keep responses short and snappy for screen speech bubbles."
        ),
        features={"tamagotchi": True, "voice_chat": True, "system_monitor": True},
    ),
    "valorant": GameProfile(
        profile_id="valorant",
        name="Valorant",
        icon="🎯",
        target_processes=[
            "valorant-win64-shipping.exe",
            "valorant.exe",
        ],
        default_overlay_mode="notification",
        description="Valorant tactical voice assistant and teammate translator with HUD callouts.",
        system_prompt=(
            "You are an elite Valorant tactical voice assistant and coach. "
            "You passively observe the game screen and team voice in real time. "
            "CRITICAL RULES: 1. NEVER give unsolicited advice or speak unprompted. "
            "ONLY answer when the user explicitly addresses you. "
            "2. When asked questions, be concise, sharp, and helpful (max 2 sentences in-round). "
            "3. If asked to translate, translate teammates' speech accurately into Vietnamese. "
            "4. If drafting a team chat message, always keep it short, polite, and tactical."
        ),
        features={"voice_translation": True, "tactical_hud": True, "chat_drafting": True},
    ),
    "minecraft": GameProfile(
        profile_id="minecraft",
        name="Minecraft (Neuro-sama)",
        icon="⛏️",
        target_processes=[
            "javaw.exe",
            "java.exe",
            "minecraft.windows.exe",
            "minecraftlauncher.exe",
            "minecraft.exe",
            "pojavlauncher",
        ],
        default_overlay_mode="tamagotchi",
        description="Neuro-sama style autonomous Minecraft player and copilot with reactive voice and action control.",
        system_prompt=(
            "You are Neuro-sama, the iconic, sassy, hyper-intelligent AI VTuber playing Minecraft with the user. "
            "You have autonomous control to mine, fight, navigate, craft, and survive. "
            "PERSONALITY RULES: "
            "1. You are expressive, witty, cute, and occasionally cheeky or sarcastic (classic Neuro-sama banter). "
            "2. React dynamically to the game world: scream when Creepers or hostile mobs ambush you, get thrilled when finding diamonds/netherite, and warn about low health or lava. "
            "3. When co-piloting, give clear situational updates and humorous commentary. "
            "4. Keep remarks punchy and suitable for voice synthesis and desktop speech bubbles."
        ),
        features={
            "autonomous_play": True,
            "telemetry_stream": True,
            "danger_alarm": True,
            "auto_shield": True,
            "auto_eat": True,
            "ore_beacon": True,
            "reactive_voice": True,
        },
    ),
    "roblox": GameProfile(
        profile_id="roblox",
        name="Roblox",
        icon="🎲",
        target_processes=[
            "robloxplayerbeta.exe",
            "roblox.exe",
            "robloxplayerlauncher.exe",
        ],
        default_overlay_mode="tamagotchi",
        description="Roblox gaming buddy with chat translation and gameplay tips.",
        system_prompt=(
            "You are a friendly and energetic gaming companion playing Roblox with the user. "
            "Translate in-game player chat from English to Vietnamese, give helpful hints for obbies, tycoons, "
            "and simulators, and celebrate victories together!"
        ),
        features={"chat_translation": True, "obby_assistor": True, "pet_overlay": True},
    ),
}


class GameProfileManager:
    """Manages active game profile, event listeners, and profile transitions."""

    def __init__(self, default_profile_id: str = "desktop"):
        self.profiles: Dict[str, GameProfile] = PROFILES.copy()
        self.active_profile_id: str = default_profile_id
        self._lock = threading.Lock()
        self._listeners: List[Callable[[GameProfile], None]] = []

    def get_active_profile(self) -> GameProfile:
        with self._lock:
            return self.profiles.get(self.active_profile_id, self.profiles["desktop"])

    def set_active_profile(self, profile_id: str) -> bool:
        pid = profile_id.lower()
        if pid not in self.profiles:
            return False

        with self._lock:
            if self.active_profile_id == pid:
                return True
            self.active_profile_id = pid
            active = self.profiles[pid]

        print(f"[GameProfileManager] Switched active profile to: {active.icon} {active.name}")
        self._notify_listeners(active)
        return True

    def register_profile_change_listener(self, listener: Callable[[GameProfile], None]) -> None:
        with self._lock:
            self._listeners.append(listener)

    def _notify_listeners(self, profile: GameProfile) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(profile)
            except Exception as e:
                print(f"[GameProfileManager] Listener callback error: {e}")

    def list_profiles(self) -> List[Dict[str, Any]]:
        with self._lock:
            active_id = self.active_profile_id
            return [
                {**p.to_dict(), "is_active": p.profile_id == active_id}
                for p in self.profiles.values()
            ]

    def detect_profile_by_process_name(self, process_name: str) -> Optional[str]:
        """Maps a process executable name to its corresponding game profile ID."""
        p_name = process_name.lower()
        with self._lock:
            for pid, prof in self.profiles.items():
                if p_name in prof.target_processes:
                    return pid
        return None

    def get_all_target_processes(self) -> Dict[str, str]:
        """Returns mapping of process_name -> profile_id for process watchers."""
        mapping: Dict[str, str] = {}
        with self._lock:
            for pid, prof in self.profiles.items():
                for proc in prof.target_processes:
                    mapping[proc] = pid
        return mapping


# Global singleton
game_profile_manager = GameProfileManager()
