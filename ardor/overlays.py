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

    def busy(self):
        """True while the overlay must be drawn even if disabled (e.g. a manually triggered popup)."""
        return False

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


class NotifyOverlay(Overlay):
    """A wave in the app's colour from the centre; in fullscreen games only Esc blinks until any key is pressed."""
    title = "Уведомления (Telegram, Discord…)"
    ESC = layout.slot_of("Esc")
    WAVE = 1.4

    def __init__(self, enabled=True):
        super().__init__(enabled)
        self.events = []                 # (t0, hue) waves in flight
        self.esc_hue = None              # pending Esc blink (game mode)
        self.esc_since = 0.0
        self.in_game = lambda: False     # set by the app
        self._incoming = []
        self._lock = threading.Lock()

    def notify(self, app):               # any thread
        with self._lock:
            self._incoming.append(app["hue"])

    MIN_BLINK = 4.0                      # in games keys are pressed all the time: blink at least this long

    def pressed(self):                   # engine: some key went down
        if self.esc_hue is not None and time.perf_counter() - self.esc_since > self.MIN_BLINK:
            self.esc_hue = None

    def busy(self):
        return False

    def apply(self, out, t, dt):
        with self._lock:
            incoming, self._incoming = self._incoming, []
        for hue in incoming:
            if self.in_game():
                self.esc_hue, self.esc_since = hue, time.perf_counter()
            else:
                self.events.append((t, hue))
        self.events = [e for e in self.events if t - e[0] < self.WAVE * 2]
        if not self.events and self.esc_hue is None:
            return out
        out = out.copy()
        d = np.hypot(layout.X - layout.W / 2, (layout.Y - 2.6) * 1.6)
        for t0, hue in self.events:
            for k in range(2):                                   # two rings, 0.5 s apart
                age = t - t0 - k * 0.5
                if 0 <= age < self.WAVE:
                    ring = np.clip(1 - np.abs(d - age * 11) / 1.8, 0, 1) * (1 - age / self.WAVE)
                    out = out * (1 - ring)[:, None] + hsv(np.full(layout.N, hue), 0.9, ring)
        if self.esc_hue is not None:
            v = 0.5 + 0.5 * np.sin(t * 6)
            out[self.ESC] = hsv(np.array([self.esc_hue]), 1, v)[0]
        return np.clip(out, 0, 1)


ALL = [CpuOverlay, VolumeOverlay, NotifyOverlay]
