"""
Unified Low-Latency Fast AI Router.
Supports:
1. Antigravity CLI / Codex / Claude Code via OmniRoute Gateway (http://127.0.0.1:20128/v1).
2. Direct API Key (Google Gemini 2.0 Flash / Live, OpenAI, Claude, Groq).
3. Zero-Latency Fast Tactical Heuristics (<15ms response for critical in-game questions).
4. Audio & Lip-Sync Viseme pipeline integration.
"""

import os
import re
import json
import time
import shutil
import sqlite3
import subprocess
import urllib.request
import urllib.error
import urllib.parse
import threading
import random
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from core.config import config
from core.lipsync import lipsync_analyzer


def read_omniroute_key_from_db() -> str:
    """Reads the most recent active API key from ~/.omniroute/storage.sqlite."""
    db_path = Path(os.environ.get("OMNIROUTE_DB_PATH") or Path.home() / ".omniroute" / "storage.sqlite")
    if not db_path.exists():
        return ""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1.0)
        try:
            row = conn.execute(
                "SELECT key FROM api_keys WHERE is_active = 1 AND revoked_at IS NULL "
                "AND key IS NOT NULL ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            return str(row[0]).strip() if row and row[0] else ""
        finally:
            conn.close()
    except Exception:
        return ""


def is_agy_active(gateway_url: str = "http://127.0.0.1:20128") -> bool:
    """Checks whether AGY CLI or the local OmniRoute/AGY gateway is active."""
    if shutil.which("agy"):
        return True
    origin = gateway_url.replace("/v1", "").rstrip("/")
    try:
        req = urllib.request.Request(f"{origin}/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            return resp.status == 200
    except Exception:
        return False


def synthesize_gura_tts_wav(text: str, lang: str = "vi") -> Optional[bytes]:
    """Synthesizes fast Gura-style (high-pitched cute anime) WAV audio via Google TTS + ffmpeg."""
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean or not shutil.which("ffmpeg"):
        return None
    try:
        url = (
            "https://translate.google.com/translate_tts"
            f"?ie=UTF-8&q={urllib.parse.quote(clean[:180])}&tl={urllib.parse.quote(lang)}&client=tw-ob"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            mp3_bytes = resp.read()
        if not mp3_bytes:
            return None
        proc = subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-f", "mp3", "-i", "pipe:0",
                "-af", "asetrate=48000*1.25,aresample=48000,atempo=0.84",
                "-ar", "24000", "-ac", "1", "-f", "wav", "pipe:1",
            ],
            input=mp3_bytes,
            capture_output=True,
            timeout=8.0,
        )
        return proc.stdout if proc.returncode == 0 and proc.stdout else None
    except Exception:
        return None


class FastTacticalCache:
    """Pre-compiled fast heuristic matcher for tactical game queries (<15ms)."""

    def __init__(self):
        self.rules = [
            (
                r"\b(spike|bom|bomb|dat bom|đặt spike)\b",
                "Spike đã được phát hiện! Ưu tiên kiểm tra âm thanh gỡ hoặc đặt, giữ cự ly bọc lót đồng đội."
            ),
            (
                r"\b(eco|save|mua|buy|tiet kiem|tiền)\b",
                "Xem xét lượng tiền: Nếu dưới 3900 tiền vòng sau, hãy Eco round giữ súng ngắn để dành tiền cho vòng súng lớn."
            ),
            (
                r"\b(retake|chiem lai|chiếm lại)\b",
                "Retake cần tập hợp đủ người, dùng kỹ năng smoke che tầm nhìn súng bắn tỉa và flash đẩy đồng thời."
            ),
            (
                r"\b(creeper|no|nổ|no banh)\b",
                "Cảnh báo Creeper! Lùi lại ngay lập tức hoặc giơ khiên đỡ sát thương nổ!"
            ),
            (
                r"\b(kim cuong|diamond|kim cương|netherite)\b",
                "Đã phát hiện quặng quý! Cắm đuốc quanh khu vực và kiểm tra xem có hồ nham thạch bên dưới không trước khi đào."
            ),
            (
                r"\b(neuro|neuro-sama|choi minecraft|chơi minecraft)\b",
                "Heart heart heart! Neuro-sama đây! Mình đang co-pilot Minecraft cùng bạn, sẵn sàng đào quặng và diệt quái!"
            ),
            (
                r"\b(roblox|obby|parkour)\b",
                "Khi nhảy Obby Roblox, hãy chuyển góc nhìn thứ nhất (First Person) hoặc khóa Shift-Lock để căn góc chuẩn nhất!"
            ),
            (
                r"\b(drop|cho sung|cho súng|vandal|phantom)\b",
                "Đang phát tín hiệu yêu cầu đồng đội hỗ trợ drop súng cho bạn."
            ),
            (
                r"\b(rush|day nhanh|đẩy nhanh|ap vao|ập vào)\b",
                "Địch có dấu hiệu đẩy nhanh! Hãy dùng kỹ năng làm chậm (slow/molly/smoke) ngay cửa chính để câu giờ."
            ),
            (
                r"\b(clutch|mot minh|1 minh|1vs|1v1|1v2)\b",
                "Bình tĩnh! Hãy cô lập từng góc đấu súng 1-đối-1, tận dụng thời gian và lắng nghe tiếng bước chân."
            ),
            (
                r"\b(chao|hello|hi gemini|hey gemini|alo|sakura)\b",
                "Chào bạn! Sakura AI đồng hành cùng bạn. Bàn cờ đang được theo dõi, chúc bạn một trận đấu thắng lợi!"
            )
        ]

    def match(self, prompt: str) -> Optional[str]:
        p = prompt.strip().lower()
        for pattern, response in self.rules:
            if re.search(pattern, p, re.IGNORECASE):
                return response
        return None


class UnifiedAIRouter:
    """Orchestrates fast communication between local Antigravity CLI and cloud API keys."""

    def __init__(self):
        self.cache = FastTacticalCache()
        self._provider = "antigravity_cli" # "antigravity_cli", "gemini_live", "claude_code", "codex", "direct_api"
        self._gateway_url = "http://127.0.0.1:20128/v1"
        self._model = "gemini-2.0-flash"
        self._api_key = ""
        self._load_config()

        self.on_response_cbs: List[Callable[[str], None]] = []
        self._lock = threading.Lock()

    def _load_config(self) -> None:
        cfg = config.data.get("ai", {})
        self._provider = cfg.get("provider", "antigravity_cli")
        self._gateway_url = cfg.get("antigravity_gateway_url", "http://127.0.0.1:20128/v1").rstrip("/")
        self._model = cfg.get("model", "ddgw/claude-haiku-4-5")
        self._fallback_models = cfg.get("fallback_models", [
            "ddgw/gpt-5.4-mini",
            "ddgw/gpt-5.6-luna",
            "auto/best-chat",
        ])
        self._api_key = (
            cfg.get("api_key")
            or os.environ.get("OMNIROUTE_API_KEY")
            or read_omniroute_key_from_db()
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )

    def register_response_callback(self, cb: Callable[[str], None]) -> None:
        self.on_response_cbs.append(cb)

    @property
    def current_provider(self) -> str:
        return self._provider

    def set_provider(self, provider: str, api_key: str = "", model: str = "") -> None:
        with self._lock:
            self._provider = provider
            if api_key:
                self._api_key = api_key
            if model:
                self._model = model
            # Save to config data
            if "ai" not in config.data:
                config.data["ai"] = {}
            config.data["ai"]["provider"] = self._provider
            config.data["ai"]["api_key"] = self._api_key
            config.data["ai"]["model"] = self._model
            config.save()
        print(f"[AIRouter] Provider updated to: {self._provider} (model: {self._model})")

    def query_fast(self, prompt: str, system_context: str = "") -> str:
        """
        Processes prompt with ultra-low latency:
        1. Checks FastTacticalCache (<15ms).
        2. Routes to configured provider (Antigravity CLI or Direct API Key).
        3. Updates Lip-Sync viseme state and triggers callbacks.
        """
        # 1. Zero-latency heuristic check
        cached = self.cache.match(prompt)
        if cached:
            self._broadcast_response(cached)
            self._simulate_lipsync_for_text(cached)
            return cached

        # 2. Dispatch to provider
        response_text = ""
        try:
            if self._provider in ["antigravity_cli", "claude_code", "codex"]:
                response_text = self._call_antigravity_gateway(prompt, system_context)
            elif self._provider in ["gemini_live", "direct_api"]:
                response_text = self._call_direct_api(prompt, system_context)
            else:
                response_text = self._call_antigravity_gateway(prompt, system_context)
        except Exception as e:
            print(f"[AIRouter] Primary provider ({self._provider}) error: {e}. Trying fallback...")
            response_text = self._fallback_answer(prompt, str(e))

        self._broadcast_response(response_text)
        self._simulate_lipsync_for_text(response_text)
        return response_text

    def _get_active_system_prompt(self, fallback: str = "") -> str:
        try:
            from core.game_profiles import game_profile_manager
            return game_profile_manager.get_active_profile().system_prompt
        except Exception:
            return fallback or (
                "You are Sakura AI, an elite gaming companion and tactical assistant. "
                "Be ultra-concise, sharp, and helpful (max 1-2 sentences in Vietnamese)."
            )

    def generate_tactical_advice(
        self,
        screen_analysis: str = "",
        game_state: Optional[Dict[str, Any]] = None,
        user_question: str = ""
    ) -> str:
        """Unified method for generating tactical advice / commentary across all game modes."""
        prompt_parts = []
        if screen_analysis:
            prompt_parts.append(f"State info: {screen_analysis}")
        if user_question:
            prompt_parts.append(f"Question: {user_question}")
        full_prompt = "\n".join(prompt_parts) if prompt_parts else "Hãy đưa ra chỉ dẫn hữu ích lúc này."
        return self.query_fast(full_prompt)

    def _call_antigravity_gateway(self, prompt: str, system_context: str = "") -> str:
        """Calls OmniRoute / Antigravity Gateway at 127.0.0.1:20128 with model fallback."""
        endpoint = f"{self._gateway_url}/chat/completions"
        system_prompt = system_context or self._get_active_system_prompt()
        api_key = self._api_key or read_omniroute_key_from_db() or "antigravity-local"

        candidates = [self._model] + [m for m in getattr(self, "_fallback_models", []) if m != self._model]
        last_err: Optional[Exception] = None

        for model_name in candidates:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 150,
                "temperature": 0.4
            }

            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"].strip()
                    if content:
                        return content
            except Exception as err:
                last_err = err
                continue

        raise last_err or RuntimeError("All OmniRoute models failed")

    def _call_direct_api(self, prompt: str, system_context: str = "") -> str:
        """Calls Google Gemini REST API or OpenAI endpoint with API key."""
        if not self._api_key:
            # Fallback to Antigravity CLI if no direct key
            return self._call_antigravity_gateway(prompt, system_context)

        # Google Gemini v1beta endpoint
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        system_instruction = system_context or "You are Sakura AI tactical assistant. Respond in Vietnamese concisely."

        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "maxOutputTokens": 150,
                "temperature": 0.3
            }
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
            return "Đã tiếp nhận thông tin chiến thuật."

    def _fallback_answer(self, prompt: str, err_msg: str) -> str:
        """Graceful offline fallback so the player is never left hanging."""
        return (
            f"Sakura AI: Đã ghi nhận chỉ thị. "
            f"(Đang chạy chế độ đệm cục bộ, bạn có thể kiểm tra cổng Antigravity CLI 20128 hoặc API Key)."
        )

    def _simulate_lipsync_for_text(self, text: str) -> None:
        """Simulates mouth shapes (visemes) for avatar corresponding to text duration."""
        def worker():
            words = text.split()
            duration_per_word = 0.22 # seconds
            vowels = ["A", "I", "U", "E", "O"]

            lipsync_analyzer.set_emotion("speaking")
            for w in words:
                vowel = random.choice(vowels)
                # Open mouth
                lipsync_analyzer.mouth_open = random.uniform(0.45, 0.95)
                lipsync_analyzer.current_viseme = vowel
                lipsync_analyzer._notify(lipsync_analyzer.get_current_state())
                time.sleep(duration_per_word * 0.6)

                # Relax mouth
                lipsync_analyzer.mouth_open = random.uniform(0.1, 0.3)
                lipsync_analyzer._notify(lipsync_analyzer.get_current_state())
                time.sleep(duration_per_word * 0.4)

            # Close mouth
            lipsync_analyzer.mouth_open = 0.0
            lipsync_analyzer.current_viseme = "closed"
            lipsync_analyzer.set_emotion("neutral")
            lipsync_analyzer._notify(lipsync_analyzer.get_current_state())

        threading.Thread(target=worker, daemon=True).start()

    def _broadcast_response(self, text: str) -> None:
        for cb in self.on_response_cbs:
            try:
                cb(text)
            except Exception:
                pass


# Global Singleton
ai_router = UnifiedAIRouter()
