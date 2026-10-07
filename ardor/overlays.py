"""Indicator layers drawn on top of any effect: CPU load on the F-row, volume popup on the number row.
Each samples its source in its own thread so the render loop never blocks on it."""
import threading, time
import numpy as np
from . import layout
from .effects.base import hsv


class Overlay:
    title = ""

    def __init__(self, enabled=True):
        self.enabled = enabled

    def apply(self, out, t, dt):
        raise NotImplementedError


class CpuOverlay(Overlay):
    title = "CPU на F-ряду"
    KEYS = [layout.slot_of(f"F{i}") for i in range(1, 13)]

    def __init__(self, enabled=True):
        super().__init__(enabled)
        self.load = 0.0                 # 0..1, sampled
        self.shown = 0.0                # smoothed for display
        threading.Thread(target=self._poll, name="ardor-cpu", daemon=True).start()

    def _poll(self):
        import psutil
        psutil.cpu_percent(None)
        while True:
            time.sleep(0.5)
            self.load = psutil.cpu_percent(None) / 100

    def apply(self, out, t, dt):
        self.shown += (self.load - self.shown) * (1 - np.exp(-dt / 0.3))
        fill = self.shown * len(self.KEYS)
        out = out.copy()
        for i, slot in enumerate(self.KEYS):
            v = np.clip(fill - i, 0, 1)
            hue = 0.33 * (1 - i / (len(self.KEYS) - 1))          # green -> red along the row
            out[slot] = hsv(hue, 1, 0.06 + 0.94 * v) if v > 0 else np.array([0.03, 0.03, 0.03])
        return out


class VolumeOverlay(Overlay):
    title = "Громкость при изменении"
    KEYS = [layout.slot_of(n) for n in "` 1 2 3 4 5 6 7 8 9 0 - = Bksp".split()]
    SHOW = 1.5

    def __init__(self, enabled=True):
        super().__init__(enabled)
        self.volume, self.muted = None, False
        self.changed_at = -10.0
        threading.Thread(target=self._poll, name="ardor-volume", daemon=True).start()

    def _poll(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities
        comtypes.CoInitialize()
        ep, last_dev = None, 0.0
        while True:
            try:
                if ep is None or time.time() - last_dev > 5:          # follow default-device changes
                    ep, last_dev = AudioUtilities.GetSpeakers().EndpointVolume, time.time()
                vol, muted = ep.GetMasterVolumeLevelScalar(), bool(ep.GetMute())
                if self.volume is not None and (abs(vol - self.volume) > 0.004 or muted != self.muted):
                    self.changed_at = time.perf_counter()
                self.volume, self.muted = vol, muted
            except Exception:
                ep = None
            time.sleep(0.08)

    def apply(self, out, t, dt):
        age = time.perf_counter() - self.changed_at
        if age > self.SHOW or self.volume is None:
            return out
        a = min(1.0, (self.SHOW - age) / 0.4)                       # fade out at the end
        fill = self.volume * len(self.KEYS)
        out = out.copy()
        for i, slot in enumerate(self.KEYS):
            v = np.clip(fill - i, 0, 1)
            col = np.array([1.0, 0.05, 0.05]) if self.muted else np.array([0.7, 0.9, 1.0]) * (0.05 + 0.95 * v)
            out[slot] = out[slot] * (1 - a) + col * a
        return out


ALL = [CpuOverlay, VolumeOverlay]
