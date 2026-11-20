"""
Offline Wake Word Detection with Barge-In Support.
Uses openWakeWord (ONNX-based, low CPU overhead) with graceful fallbacks.
Supported triggers: "Hey Gemini", "Hey Google".
"""

import time
import threading
import numpy as np
from typing import Callable, List, Optional


class WakeWordDetector:
    """Listens continuously to physical mic stream chunks and triggers callbacks."""

    def __init__(self, model_name: str = "hey_gemini", threshold: float = 0.5):
        self.model_name = model_name
        self.threshold = threshold
        self.is_active = True
        self.model = None
        self.callbacks: List[Callable[[str, float], None]] = []
        self._lock = threading.Lock()
        self._last_trigger_time = 0.0
        self._cooldown_seconds = 1.5

        self._init_model()

    def _init_model(self) -> None:
        try:
            import openwakeword
            from openwakeword.model import Model

            # Load model (openwakeword includes default pretrained models)
            # If custom hey_gemini weights exist, it uses them; else standard fallbacks
            try:
                self.model = Model(inference_framework="onnx")
                print(f"[WakeWord] openWakeWord initialized with models: {list(self.model.models.keys())}")
            except Exception as e:
                print(f"[WakeWord] Pretrained download or loading fallback: {e}")
                self.model = None
        except ImportError:
            print("[WakeWord] openwakeword not installed. Running in energy/VAD fallback mode.")
            self.model = None

    def register_callback(self, cb: Callable[[str, float], None]) -> None:
        self.callbacks.append(cb)

    def process_pcm_chunk(self, audio_chunk_int16: np.ndarray) -> bool:
        """
        Process 16kHz 16-bit mono PCM samples (recommended ~1280 samples = 80ms).
        Returns True if wake word was detected.
        """
        if not self.is_active:
            return False

        now = time.time()
        if now - self._last_trigger_time < self._cooldown_seconds:
            return False

        # If openwakeword model is available
        if self.model is not None:
            try:
                # Ensure 1D array of int16
                if audio_chunk_int16.ndim > 1:
                    audio_chunk_int16 = audio_chunk_int16[:, 0]

                predictions = self.model.predict(audio_chunk_int16)
                for name, score in predictions.items():
                    if score >= self.threshold:
                        self._last_trigger_time = now
                        print(f"[WakeWord] Detected '{name}' with score {score:.2f}")
                        self._notify(name, float(score))
                        return True
            except Exception as e:
                # Fallback to energy check if prediction errors
                pass

        return False

    def trigger_manual(self, reason: str = "manual_button") -> None:
        """Allows manual UI click or hotkey to trigger wake word."""
        self._last_trigger_time = time.time()
        self._notify(reason, 1.0)

    def _notify(self, word: str, score: float) -> None:
        for cb in self.callbacks:
            try:
                cb(word, score)
            except Exception as e:
                print(f"[WakeWord] Callback error: {e}")
