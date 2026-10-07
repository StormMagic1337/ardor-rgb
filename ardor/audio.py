"""System audio analyser: captures what plays on the default output device (WASAPI loopback)
and turns it into normalised band levels, a bass level and beat events for music effects.

The capture starts on first use and follows default-device changes. WASAPI loopback delivers
no data while nothing is playing, so silence is detected by the age of the last buffer."""
import threading, time
from collections import deque
import numpy as np

N_BANDS = 19                    # one per key column (the board is ~18.4 keys wide)
FFT = 2048
LO_HZ, HI_HZ = 35.0, 14000.0


class Audio:
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = Audio()
        return cls._inst

    def __init__(self):
        self.rate = 48000
        self.buf = deque(maxlen=FFT * 2)
        self.last_data = 0.0
        self.levels = np.zeros(N_BANDS)
        self.peak = np.full(N_BANDS, 1e-3)      # per-band auto gain
        self.bass = 0.0
        self.beat = False
        self._bass_avg = 1e-3
        self._last_beat = 0.0
        self.device = None
        self._lock = threading.Lock()
        self._pa = self._stream = None
        threading.Thread(target=self._keep_open, name="ardor-audio", daemon=True).start()

    # --- capture --------------------------------------------------------------
    def _keep_open(self):
        import pyaudiowpatch as pa
        self._pa = pa.PyAudio()
        while True:
            try:
                lb = self._pa.get_default_wasapi_loopback()
                if lb["name"] != self.device:
                    self._open(pa, lb)
            except Exception as e:                   # device unplugged etc.: retry later
                self.device = f"нет звука ({e})"
            time.sleep(3)

    def _open(self, pa, lb):
        if self._stream:
            self._stream.close()
        ch, self.rate = lb["maxInputChannels"], int(lb["defaultSampleRate"])

        def cb(data, frames, info, status):
            x = np.frombuffer(data, np.float32).reshape(-1, ch).mean(1)
            with self._lock:
                self.buf.extend(x)
                self.last_data = time.perf_counter()
            return None, pa.paContinue

        self._stream = self._pa.open(format=pa.paFloat32, channels=ch, rate=self.rate, input=True,
                                     input_device_index=lb["index"], frames_per_buffer=512, stream_callback=cb)
        self.device = lb["name"]
        freqs = np.fft.rfftfreq(FFT, 1 / self.rate)
        edges = np.geomspace(LO_HZ, HI_HZ, N_BANDS + 1)
        self._bins = [np.flatnonzero((freqs >= a) & (freqs < b)) for a, b in zip(edges[:-1], edges[1:])]
        self._bins = [b if len(b) else np.array([np.argmin(np.abs(freqs - a))]) for b, a in zip(self._bins, edges)]
        self._win = np.hanning(FFT)

    # --- analysis (call once per frame) -----------------------------------------
    def update(self, dt, sensitivity=1.0):
        silent = time.perf_counter() - self.last_data > 0.25 or not hasattr(self, "_bins")
        if silent:
            raw = np.zeros(N_BANDS)
        else:
            with self._lock:
                x = np.array(self.buf)[-FFT:]
            if len(x) < FFT:
                x = np.pad(x, (FFT - len(x), 0))
            mag = np.abs(np.fft.rfft(x * self._win))
            raw = np.array([mag[b].mean() for b in self._bins])
            raw *= np.linspace(1.0, 4.0, N_BANDS)          # tilt: highs carry less energy
        # auto gain: peak follows loud parts fast, relaxes slowly; floor keeps silence dark
        self.peak = np.maximum(raw, self.peak * np.exp(-dt / 4.0))
        self.peak = np.maximum(self.peak, 0.5)
        target = np.clip(raw / self.peak * sensitivity, 0, 1) ** 1.3
        attack = target > self.levels
        k_up, k_down = 1 - np.exp(-dt / 0.03), 1 - np.exp(-dt / 0.18)
        self.levels += (target - self.levels) * np.where(attack, k_up, k_down)

        bass = float(raw[:4].mean())
        now = time.perf_counter()
        loud_enough = bass > 0.25 * float(self.peak[:4].mean()) and not silent
        self.beat = loud_enough and bass > self._bass_avg * 1.4 and now - self._last_beat > 0.18
        if self.beat:
            self._last_beat = now
        self._bass_avg += (bass - self._bass_avg) * (1 - np.exp(-dt / 0.6))
        self.bass = float(self.levels[:4].mean())
        return self.levels
