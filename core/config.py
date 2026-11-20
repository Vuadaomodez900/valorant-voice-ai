"""
Configuration loader, validator, and runtime resource path management.
Supports frozen PyInstaller bundles and standard Python environments.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_CONFIG: Dict[str, Any] = {
    "audio": {
        "physical_mic": "",
        "virtual_mic_out": "CABLE Input",
        "headphone_out": "",
        "wasapi_loopback_device": "",
        "volume_headphone": 1.0,
        "volume_game_mic": 1.0,
        "mute_game_mic": False,
        "auto_mic_trigger": True,
        "ptt_key": "v",
        "sample_rate": 16000,
        "teammate_voice_trigger": True,
    },
    "screen": {
        "fps_live_stream": 2,
        "fps_buffer": 15,
        "buffer_seconds": 20,
        "monitor_index": 0,
        "capture_resolution": [1280, 720],
    },
    "wake_word": {
        "enabled": True,
        "model_name": "hey_gemini",
        "threshold": 0.5,
        "barge_in": True,
    },
    "gemini": {
        "api_key": "",
        "model": "gemini-2.0-flash-exp",
        "voice_name": "Puck",
        "speech_rate": 1.0,
        "pitch": 0.0,
        "system_prompt": (
            "You are an elite Valorant tactical voice assistant and coach. "
            "You passively observe the game screen and team voice in real time. "
            "CRITICAL RULES: 1. NEVER give unsolicited advice or speak unprompted. "
            "ONLY answer when the user explicitly addresses you. "
            "2. When asked questions, be concise, sharp, and helpful (max 2 sentences in-round). "
            "3. If asked to translate, translate teammates' speech accurately into Vietnamese. "
            "4. If drafting a team chat message, always keep it short, polite, and tactical."
        ),
    },
    "overlay": {
        "enabled": True,
        "opacity": 0.88,
        "click_through": True,
        "exclude_from_capture": True,
        "position": "top-right",
        "translation_enabled": True,
        "translation_target_lang": "vi",
    },
    "web": {
        "host": "0.0.0.0",
        "port": 8765,
        "require_pin": False,
        "pin": "1234",
    },
    "process_watcher": {
        "target_process": "VALORANT-Win64-Shipping.exe",
        "check_interval": 2.0,
        "auto_toggle_overlay": True,
    },
}


def get_base_dir() -> Path:
    """Returns the base directory where assets and configs reside."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_user_data_dir() -> Path:
    """Returns directory where user config and logs are persisted."""
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            path = Path(app_data) / "ValorantVoiceAI"
            path.mkdir(parents=True, exist_ok=True)
            return path
    # Fallback to local working directory
    return Path.cwd()


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    base_dir = get_base_dir()
    target_path = base_dir / relative_path
    if target_path.exists():
        return str(target_path)
    # Check current working directory
    cwd_path = Path.cwd() / relative_path
    if cwd_path.exists():
        return str(cwd_path)
    return str(target_path)


class AppConfig:
    """Singleton-style Application Configuration Manager."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Loads configuration from file and applies environment overrides."""
        self.data = DEFAULT_CONFIG.copy()

        # Check user data dir first, then local path
        user_cfg = get_user_data_dir() / "config.yaml"
        load_target = user_cfg if user_cfg.exists() else self.config_path

        if load_target.exists() and yaml is not None:
            try:
                with open(load_target, "r", encoding="utf-8") as f:
                    user_data = yaml.safe_load(f) or {}
                self._deep_update(self.data, user_data)
            except Exception as e:
                print(f"[Config] Error loading {load_target}: {e}. Using defaults.")

        # Environment variable overrides
        env_key = os.environ.get("GEMINI_API_KEY")
        if env_key:
            self.data["gemini"]["api_key"] = env_key

        env_port = os.environ.get("VALORANT_AI_PORT")
        if env_port:
            try:
                self.data["web"]["port"] = int(env_port)
            except ValueError:
                pass

    def save(self) -> None:
        """Saves current configuration to user data dir."""
        if yaml is None:
            return
        target = get_user_data_dir() / "config.yaml"
        try:
            with open(target, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        except Exception as e:
            print(f"[Config] Failed to save config: {e}")

    def _deep_update(self, base: dict, update: dict) -> None:
        for k, v in update.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._deep_update(base[k], v)
            else:
                base[k] = v

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, item: str) -> Any:
        return self.data[item]


# Global config instance
config = AppConfig()
