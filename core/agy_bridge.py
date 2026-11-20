"""
Gemini Multimodal Live API Bridge & AGY CLI Integration.
Implements:
- Asynchronous Bidirectional WebSocket connection via google-genai SDK.
- Streaming PCM Audio (16kHz in, 24kHz out).
- Passive Continuous Video streaming (1-5 FPS JPEG frames).
- Voice Activity Detection, Barge-in, Interruption handling.
- Permission-gated in-game chat message draft detection.
"""

import asyncio
import threading
import time
import re
from typing import Optional, Callable, List, Dict
import numpy as np

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from core.in_game_chat import chat_manager


class GeminiLiveBridge:
    """Manages the real-time multimodal live session with Gemini."""

    def __init__(self,
                 api_key: str = "",
                 model_name: str = "gemini-2.0-flash-exp",
                 voice_name: str = "Puck",
                 system_prompt: str = ""):
        self.api_key = api_key
        self.model_name = model_name
        self.voice_name = voice_name
        self.system_prompt = system_prompt or (
            "You are an elite Valorant tactical voice assistant and coach. "
            "Passively observe the game screen and team voice in real time. "
            "NEVER speak unprompted. Only respond when addressed. Be concise and sharp. "
            "If drafting a game chat, prefix with [CHAT_DRAFT: <message>]."
        )

        self.is_connected = False
        self.is_session_active = False

        # Callbacks
        self.on_audio_out_cbs: List[Callable[[bytes], None]] = []
        self.on_text_out_cbs: List[Callable[[str], None]] = []
        self.on_status_change_cbs: List[Callable[[str], None]] = []

        # Internal asyncio loop running in a dedicated background daemon thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._live_session = None

        # Queue for outbound frames and audio to prevent blocking
        self._outbound_audio_queue: Optional[asyncio.Queue] = None
        self._outbound_video_queue: Optional[asyncio.Queue] = None

    def register_audio_output(self, cb: Callable[[bytes], None]) -> None:
        self.on_audio_out_cbs.append(cb)

    def register_text_output(self, cb: Callable[[str], None]) -> None:
        self.on_text_out_cbs.append(cb)

    def register_status_change(self, cb: Callable[[str], None]) -> None:
        self.on_status_change_cbs.append(cb)

    def send_user_audio_chunk(self, chunk_pcm_int16: np.ndarray) -> None:
        """Sends raw 16kHz PCM audio chunk to Gemini Live API."""
        if not self.is_connected or self._loop is None or self._outbound_audio_queue is None:
            return
        pcm_bytes = chunk_pcm_int16.tobytes()
        try:
            self._loop.call_soon_threadsafe(self._outbound_audio_queue.put_nowait, pcm_bytes)
        except Exception:
            pass

    def send_screen_frame_jpeg(self, jpeg_bytes: bytes) -> None:
        """Sends single downscaled JPEG screen frame to Gemini Live API."""
        if not self.is_connected or self._loop is None or self._outbound_video_queue is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._outbound_video_queue.put_nowait, jpeg_bytes)
        except Exception:
            pass

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True, name="GeminiLiveLoop")
        self._thread.start()
        print("[GeminiLive] Bridge thread started.")

    def _run_event_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_session_task())
        except Exception as e:
            print(f"[GeminiLive] Loop terminated: {e}")
        finally:
            self._loop.close()

    async def _main_session_task(self) -> None:
        self._outbound_audio_queue = asyncio.Queue(maxsize=100)
        self._outbound_video_queue = asyncio.Queue(maxsize=5)

        if not self.api_key or genai is None or types is None:
            status_msg = "Running in Mock/Offline Mode (Configure API Key in GUI/Web)"
            print(f"[GeminiLive] {status_msg}")
            self._notify_status(status_msg)
            while not self._stop_event.is_set():
                await asyncio.sleep(1.0)
            return

        try:
            client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1beta"})
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
                    )
                ),
                system_instruction=types.Content(
                    parts=[types.Part.from_text(text=self.system_prompt)]
                )
            )

            self._notify_status(f"Connecting to Gemini Live API ({self.model_name})...")
            async with client.aio.live.connect(model=self.model_name, config=config) as session:
                self._live_session = session
                self.is_connected = True
                self._notify_status("Connected & Passive Screen Observation Active")
                print("[GeminiLive] Connected to Gemini Multimodal Live API successfully.")

                # Concurrently run sender and receiver
                await asyncio.gather(
                    self._audio_sender_task(session),
                    self._video_sender_task(session),
                    self._receiver_task(session)
                )

        except Exception as e:
            print(f"[GeminiLive] Session error: {e}")
            self._notify_status(f"Error: {e}")
        finally:
            self.is_connected = False
            self._live_session = None

    async def _audio_sender_task(self, session) -> None:
        """Pushes user microphone PCM chunks to Gemini."""
        while not self._stop_event.is_set():
            try:
                pcm_bytes = await self._outbound_audio_queue.get()
                await session.send_realtime_input(
                    audio=types.Blob(
                        data=pcm_bytes,
                        mime_type="audio/pcm;rate=16000"
                    )
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(0.05)

    async def _video_sender_task(self, session) -> None:
        """Pushes periodic screen capture JPEG frames to Gemini."""
        while not self._stop_event.is_set():
            try:
                jpeg_bytes = await self._outbound_video_queue.get()
                await session.send_realtime_input(
                    media=types.Blob(
                        data=jpeg_bytes,
                        mime_type="image/jpeg"
                    )
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(0.1)

    async def _receiver_task(self, session) -> None:
        """Listens for responses from Gemini Live API."""
        try:
            accumulated_text = ""
            async for response in session.receive():
                # Handle barge-in interruptions
                if response.server_content and response.server_content.interrupted:
                    print("[GeminiLive] User barge-in detected. Audio output interrupted.")
                    accumulated_text = ""
                    continue

                server_content = response.server_content
                if server_content and server_content.model_turn:
                    for part in server_content.model_turn.parts:
                        # Audio chunk (24kHz PCM)
                        if part.inline_data and "audio/pcm" in part.inline_data.mime_type:
                            audio_bytes = part.inline_data.data
                            for cb in self.on_audio_out_cbs:
                                try:
                                    cb(audio_bytes)
                                except Exception:
                                    pass

                        # Text stream / transcription
                        if part.text:
                            accumulated_text += part.text
                            for cb in self.on_text_out_cbs:
                                try:
                                    cb(part.text)
                                except Exception:
                                    pass

                            # Check for in-game chat draft proposals
                            self._check_chat_draft_intent(accumulated_text)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[GeminiLive] Receiver error: {e}")

    def _check_chat_draft_intent(self, text: str) -> None:
        """If AI suggested a chat draft like [CHAT_DRAFT: Sova 40 HP A], register with gate."""
        match = re.search(r"\[CHAT_DRAFT:\s*([^\]]+)\]", text, re.IGNORECASE)
        if match:
            draft_text = match.group(1).strip()
            chat_manager.propose_chat(draft_text, target_channel="team")

    def _notify_status(self, status: str) -> None:
        for cb in self.on_status_change_cbs:
            try:
                cb(status)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.is_connected = False
        print("[GeminiLive] Bridge stopped.")
