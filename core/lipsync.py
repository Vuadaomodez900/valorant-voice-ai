"""
Real-time Lip-Sync and Emotion Viseme Analyzer.
Extracts mouth shape (viseme), open magnitude, blinking, and emotional states
from PCM audio streams in real time for Live2D, SVG, and 3D avatars.
Zero external heavy dependencies (uses pure numpy).
"""

import time
import math
import random
import threading
from typing import Callable, List, Dict, Optional
import numpy as np


class LipSyncAnalyzer:
    """Analyzes raw audio PCM chunks and generates real-time visemes for avatar animations."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.mouth_open = 0.0          # 0.0 (closed) to 1.0 (fully open)
        self.current_viseme = "closed" # "closed", "A", "I", "U", "E", "O"
        self.is_blinking = False
        self.current_emotion = "neutral" # "neutral", "listening", "speaking", "alert", "happy"

        self.subscribers: List[Callable[[Dict], None]] = []
        self._last_speech_time = 0.0
        self._last_blink_time = time.time()
        self._blink_duration = 0.15 # seconds
        self._next_blink_interval = 3.5

        # Smoothing coefficient to prevent mouth jitter
        self._smooth_alpha = 0.45
        self._lock = threading.Lock()

        # Start background timer for natural idle eye blinking & emotion decays
        self._stop_event = threading.Event()
        self._idle_thread = threading.Thread(target=self._idle_animation_loop, daemon=True, name="LipSyncIdleLoop")
        self._idle_thread.start()

    def register_subscriber(self, callback: Callable[[Dict], None]) -> None:
        """Register a callback that receives viseme frames {mouth_open, viseme, blink, emotion}."""
        self.subscribers.append(callback)

    def feed_audio_chunk(self, chunk: np.ndarray, is_ai_speaking: bool = True) -> Dict:
        """
        Feeds a chunk of PCM int16 or float32 audio.
        Calculates energy and frequency balance to output mouth viseme parameters.
        """
        if len(chunk) == 0:
            return self.get_current_state()

        # Convert to float32 between -1.0 and 1.0
        if chunk.dtype == np.int16:
            audio_f = chunk.astype(np.float32) / 32768.0
        else:
            audio_f = chunk.astype(np.float32)

        # Compute RMS energy (volume)
        rms = float(np.sqrt(np.mean(audio_f ** 2)))

        # Target mouth open value with non-linear curve for organic speech
        raw_open = min(1.0, max(0.0, (rms - 0.02) * 5.0))
        if raw_open > 0.05:
            target_open = math.pow(raw_open, 0.75)
        else:
            target_open = 0.0

        with self._lock:
            # Exponential moving average filter
            self.mouth_open = (self._smooth_alpha * target_open) + ((1.0 - self._smooth_alpha) * self.mouth_open)
            self.mouth_open = round(float(self.mouth_open), 3)

            now = time.time()
            if self.mouth_open > 0.08:
                self._last_speech_time = now
                if is_ai_speaking:
                    self.current_emotion = "speaking"
                else:
                    self.current_emotion = "listening"

                # Estimate vowel viseme using zero-crossing rate and spectral centroid approximation
                zc = np.sum(np.abs(np.diff(np.signbit(audio_f)))) / len(audio_f)
                if zc < 0.08:
                    self.current_viseme = "O"
                elif zc < 0.16:
                    self.current_viseme = "U"
                elif zc < 0.28:
                    self.current_viseme = "A"
                elif zc < 0.42:
                    self.current_viseme = "E"
                else:
                    self.current_viseme = "I"
            else:
                self.current_viseme = "closed"
                if now - self._last_speech_time > 1.5:
                    self.current_emotion = "neutral"

        state = self.get_current_state()
        self._notify(state)
        return state

    def set_emotion(self, emotion: str) -> None:
        """Explicitly set avatar emotion (e.g., 'alert', 'happy', 'focused')."""
        with self._lock:
            self.current_emotion = emotion
        self._notify(self.get_current_state())

    def synthesize_mock_viseme_stream(self, text: str) -> None:
        """Simulates speech mouth-shapes (visemes) corresponding to text syllables."""
        def worker():
            words = text.split()
            duration_per_word = 0.20
            vowels = ["A", "I", "U", "E", "O"]

            self.set_emotion("speaking")
            for w in words:
                vowel = random.choice(vowels)
                with self._lock:
                    self.mouth_open = random.uniform(0.45, 0.95)
                    self.current_viseme = vowel
                self._notify(self.get_current_state())
                time.sleep(duration_per_word * 0.6)

                with self._lock:
                    self.mouth_open = random.uniform(0.1, 0.25)
                self._notify(self.get_current_state())
                time.sleep(duration_per_word * 0.4)

            with self._lock:
                self.mouth_open = 0.0
                self.current_viseme = "closed"
            self.set_emotion("neutral")
            self._notify(self.get_current_state())

        threading.Thread(target=worker, daemon=True, name="LipSyncSynthesizer").start()

    def get_current_state(self) -> Dict:
        """Returns snapshot of current viseme parameters."""
        with self._lock:
            return {
                "mouth_open": self.mouth_open,
                "viseme": self.current_viseme,
                "blink": self.is_blinking,
                "emotion": self.current_emotion,
                "timestamp": round(time.time(), 3)
            }

    def _idle_animation_loop(self) -> None:
        """Generates realistic human-like blinking and idle state pulses."""
        while not self._stop_event.is_set():
            time.sleep(0.04) # ~25Hz refresh
            now = time.time()

            # Blink trigger check
            if not self.is_blinking:
                if now - self._last_blink_time > self._next_blink_interval:
                    self.is_blinking = True
                    self._last_blink_time = now
                    # Natural variation in blink interval (2.5s to 5.5s)
                    self._next_blink_interval = random.uniform(2.5, 5.5)
                    self._notify(self.get_current_state())
            else:
                if now - self._last_blink_time > self._blink_duration:
                    self.is_blinking = False
                    self._notify(self.get_current_state())

    def _notify(self, state: Dict) -> None:
        for cb in self.subscribers:
            try:
                cb(state)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()


# Global Singleton
lipsync_analyzer = LipSyncAnalyzer()
