"""
Dual Audio Router for Valorant Voice AI.
Architecture:
- Input 1: Physical Mic (Voice queries + Wake Word + Pass-through to team)
- Input 2: WASAPI Loopback (In-game team voice chat capture -> translation)
- Output 1: User Headphones (Low-latency Gemini AI speech playback)
- Output 2: VB-Audio Virtual Cable (Mix of User voice + Gemini AI speech -> Valorant mic input)
- Volume Controls: Headphone volume (0-200%), Game Mic volume (0-200%), Mute toggle.
- Auto PTT simulation or Open Mic trigger when AI speaks.
"""

import sys
import time
import threading
import queue
from typing import List, Dict, Optional, Tuple, Callable
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    pyaudio = None


class AudioRouter:
    """Manages audio streams, mixing, and routing between hardware and virtual devices."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.volume_headphone: float = 1.0  # 0.0 - 2.0
        self.volume_game_mic: float = 1.0   # 0.0 - 2.0
        self.mute_game_mic: bool = False
        self.auto_mic_trigger: bool = True
        self.ptt_key: str = "v"
        self.is_running: bool = False

        # Devices indices/names
        self.physical_mic_id: Optional[int] = None
        self.virtual_cable_out_id: Optional[int] = None
        self.headphone_out_id: Optional[int] = None
        self.wasapi_loopback_id: Optional[int] = None

        # Queues and buffers
        self.ai_audio_queue: queue.Queue = queue.Queue(maxsize=100)
        self.mic_subscribers: List[Callable[[np.ndarray], None]] = []
        self.loopback_subscribers: List[Callable[[np.ndarray], None]] = []

        # Stream references
        self._mic_stream = None
        self._headphone_stream = None
        self._virtual_mic_stream = None
        self._loopback_thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # State tracking for PTT
        self._is_ai_speaking = False
        self._ai_speech_counter = 0

    @staticmethod
    def get_audio_devices() -> Dict[str, List[Dict]]:
        """Scans and categorizes audio devices."""
        inputs, outputs = [], []
        if sd is None:
            return {"inputs": inputs, "outputs": outputs}

        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                name = dev.get("name", f"Device {idx}")
                host_api = sd.query_hostapis(dev.get("hostapi", 0)).get("name", "")
                if dev.get("max_input_channels", 0) > 0:
                    inputs.append({
                        "index": idx,
                        "name": f"{name} ({host_api})",
                        "raw_name": name,
                        "channels": dev["max_input_channels"],
                        "default_samplerate": dev.get("default_samplerate", 44100)
                    })
                if dev.get("max_output_channels", 0) > 0:
                    outputs.append({
                        "index": idx,
                        "name": f"{name} ({host_api})",
                        "raw_name": name,
                        "channels": dev["max_output_channels"],
                        "default_samplerate": dev.get("default_samplerate", 44100)
                    })
        except Exception as e:
            print(f"[AudioRouter] Error querying devices: {e}")
        return {"inputs": inputs, "outputs": outputs}

    def find_device_by_keyword(self, keyword: str, is_input: bool = False) -> Optional[int]:
        """Finds device index matching keyword (e.g. 'CABLE Input')."""
        devs = self.get_audio_devices()
        target_list = devs["inputs"] if is_input else devs["outputs"]
        kw_lower = keyword.lower()
        for d in target_list:
            if kw_lower in d["name"].lower():
                return d["index"]
        return None

    def subscribe_mic(self, callback: Callable[[np.ndarray], None]) -> None:
        """Register subscriber for raw user mic chunks (16kHz 16-bit PCM)."""
        self.mic_subscribers.append(callback)

    def subscribe_loopback(self, callback: Callable[[np.ndarray], None]) -> None:
        """Register subscriber for in-game loopback audio chunks."""
        self.loopback_subscribers.append(callback)

    def feed_ai_audio_pcm(self, pcm_bytes: bytes, original_sample_rate: int = 24000) -> None:
        """
        Feeds PCM bytes received from Gemini Live API (24kHz standard).
        Resamples or converts to internal sample rate (16kHz or device rate).
        """
        if not pcm_bytes:
            return

        # Convert bytes to int16 numpy array
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)

        # Simple linear or scipy resampling if rates differ
        if original_sample_rate != self.sample_rate and len(samples) > 0:
            target_len = int(len(samples) * (self.sample_rate / original_sample_rate))
            if target_len > 0:
                indices = np.linspace(0, len(samples) - 1, target_len)
                samples = np.interp(indices, np.arange(len(samples)), samples).astype(np.int16)

        try:
            self.ai_audio_queue.put_nowait(samples)
            self._handle_ai_speaking_state(True)
        except queue.Full:
            pass

    def _handle_ai_speaking_state(self, speaking: bool) -> None:
        """Controls in-game PTT keypress simulation when AI talks."""
        if not self.auto_mic_trigger or sys.platform != "win32":
            return

        with self._lock:
            if speaking and not self._is_ai_speaking:
                self._is_ai_speaking = True
                self._press_ptt_key(True)
            elif not speaking and self._is_ai_speaking:
                self._is_ai_speaking = False
                self._press_ptt_key(False)

    def _press_ptt_key(self, pressed: bool) -> None:
        """Simulates in-game voice chat PTT key on Windows."""
        try:
            import pyautogui
            if pressed:
                pyautogui.keyDown(self.ptt_key)
            else:
                pyautogui.keyUp(self.ptt_key)
        except Exception:
            pass

    def start(self,
              physical_mic_name: str = "",
              virtual_cable_name: str = "CABLE Input",
              headphone_name: str = "") -> bool:
        """Starts physical mic recording, dual output streams, and WASAPI loopback."""
        if self.is_running:
            return True

        if sd is None:
            print("[AudioRouter] sounddevice not available. Running mock audio loop.")
            self.is_running = True
            return True

        self._stop_event.clear()

        # Resolve device indices
        if physical_mic_name:
            self.physical_mic_id = self.find_device_by_keyword(physical_mic_name, is_input=True)
        if virtual_cable_name:
            self.virtual_cable_out_id = self.find_device_by_keyword(virtual_cable_name, is_input=False)
        if headphone_name:
            self.headphone_out_id = self.find_device_by_keyword(headphone_name, is_input=False)

        print(f"[AudioRouter] Configuration: Mic={self.physical_mic_id}, "
              f"VirtualCable={self.virtual_cable_out_id}, Headphone={self.headphone_out_id}")

        try:
            # 1. Start User Physical Mic Input Stream
            def mic_callback(indata, frames, time_info, status):
                if status:
                    pass
                chunk = indata[:, 0].copy()
                for cb in self.mic_subscribers:
                    try:
                        cb(chunk)
                    except Exception:
                        pass

            self._mic_stream = sd.InputStream(
                device=self.physical_mic_id,
                channels=1,
                samplerate=self.sample_rate,
                dtype="int16",
                blocksize=1280,
                callback=mic_callback
            )
            self._mic_stream.start()

            # 2. Start Dual Output Playback Thread (Headphone + Virtual Mic)
            self._start_output_player()

            # 3. Start WASAPI Loopback capture for game audio translation
            self._start_wasapi_loopback()

            self.is_running = True
            print("[AudioRouter] All audio routes active and synchronized.")
            return True

        except Exception as e:
            print(f"[AudioRouter] Failed to start audio streams: {e}")
            self.stop()
            return False

    def _start_output_player(self) -> None:
        """Plays AI audio concurrently to Headphone and Virtual Mic."""
        def output_worker():
            hp_stream = None
            vm_stream = None
            try:
                # Open headphone stream
                hp_stream = sd.OutputStream(
                    device=self.headphone_out_id,
                    channels=1,
                    samplerate=self.sample_rate,
                    dtype="int16",
                    blocksize=1280
                )
                hp_stream.start()

                # Open virtual cable output stream (if device found)
                if self.virtual_cable_out_id is not None:
                    vm_stream = sd.OutputStream(
                        device=self.virtual_cable_out_id,
                        channels=1,
                        samplerate=self.sample_rate,
                        dtype="int16",
                        blocksize=1280
                    )
                    vm_stream.start()

                empty_chunk = np.zeros(1280, dtype=np.int16)
                idle_count = 0

                while not self._stop_event.is_set():
                    try:
                        chunk = self.ai_audio_queue.get(timeout=0.08)
                        idle_count = 0

                        # Volume scaling for Headphones (0% - 200%)
                        hp_chunk = np.clip(chunk.astype(np.float32) * self.volume_headphone, -32768, 32767).astype(np.int16)
                        if hp_stream:
                            hp_stream.write(hp_chunk)

                        # Volume scaling for Game Virtual Mic (0% - 200%) or Muted
                        if vm_stream:
                            if self.mute_game_mic:
                                vm_chunk = empty_chunk
                            else:
                                vm_chunk = np.clip(chunk.astype(np.float32) * self.volume_game_mic, -32768, 32767).astype(np.int16)
                            vm_stream.write(vm_chunk)

                    except queue.Empty:
                        idle_count += 1
                        if idle_count > 3:
                            self._handle_ai_speaking_state(False)

            except Exception as e:
                print(f"[AudioRouter] Output stream error: {e}")
            finally:
                if hp_stream:
                    hp_stream.stop()
                    hp_stream.close()
                if vm_stream:
                    vm_stream.stop()
                    vm_stream.close()
                self._handle_ai_speaking_state(False)

        self._output_thread = threading.Thread(target=output_worker, daemon=True, name="AudioOutputPlayer")
        self._output_thread.start()

    def _start_wasapi_loopback(self) -> None:
        """Captures system/game audio using pyaudiowpatch WASAPI loopback."""
        if pyaudio is None or sys.platform != "win32":
            print("[AudioRouter] pyaudiowpatch not available on this platform. WASAPI Loopback skipped.")
            return

        def loopback_worker():
            p = None
            stream = None
            try:
                p = pyaudio.PyAudio()
                wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
                default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

                # Find loopback device corresponding to default speakers
                loopback_device = None
                if not default_speakers.get("isLoopbackDevice"):
                    for dev in p.get_loopback_device_info_generator():
                        if default_speakers["name"] in dev["name"]:
                            loopback_device = dev
                            break
                else:
                    loopback_device = default_speakers

                if not loopback_device:
                    print("[AudioRouter] No matching WASAPI loopback device found.")
                    return

                def loopback_cb(in_data, frame_count, time_info, status):
                    raw_samples = np.frombuffer(in_data, dtype=np.int16)
                    # Convert to mono if multichannel
                    channels = loopback_device.get("maxInputChannels", 2)
                    if channels > 1:
                        mono_samples = raw_samples[::channels]
                    else:
                        mono_samples = raw_samples

                    for cb in self.loopback_subscribers:
                        try:
                            cb(mono_samples)
                        except Exception:
                            pass
                    return (in_data, pyaudio.paContinue)

                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=loopback_device["maxInputChannels"],
                    rate=int(loopback_device["defaultSampleRate"]),
                    input=True,
                    input_device_index=loopback_device["index"],
                    stream_callback=loopback_cb
                )
                stream.start_stream()

                while not self._stop_event.is_set():
                    time.sleep(0.2)

            except Exception as e:
                print(f"[AudioRouter] WASAPI Loopback error: {e}")
            finally:
                if stream:
                    stream.stop_stream()
                    stream.close()
                if p:
                    p.terminate()

        self._loopback_thread = threading.Thread(target=loopback_worker, daemon=True, name="WASAPILoopbackThread")
        self._loopback_thread.start()

    def set_headphone_volume(self, volume: float) -> None:
        self.volume_headphone = max(0.0, min(2.0, volume))

    def set_game_mic_volume(self, volume: float) -> None:
        self.volume_game_mic = max(0.0, min(2.0, volume))

    def toggle_game_mic_mute(self) -> bool:
        self.mute_game_mic = not self.mute_game_mic
        print(f"[AudioRouter] Game Mic Mute is now: {self.mute_game_mic}")
        return self.mute_game_mic

    def stop(self) -> None:
        """Stops all streams and releases audio hardware cleanly."""
        self._stop_event.set()
        if self._mic_stream:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

        self._handle_ai_speaking_state(False)
        self.is_running = False
        print("[AudioRouter] All audio resources released cleanly.")
