"""Music effects driven by system audio (see audio.py)."""
import numpy as np
from .base import Effect, Param, hsv, X, Y, N
from ..audio import Audio, N_BANDS
from .. import layout

COL = np.clip((X / layout.W * N_BANDS).astype(int), 0, N_BANDS - 1)   # key -> band
HEIGHT = (5.2 - Y) / 5.2                                                # 0 at bottom row, 1 at F-row


class Equalizer(Effect):
    name, title = "music_eq", "Эквалайзер"
    params = [
        Param("sensitivity", "Чувствительность", 0.3, 3.0, 1.0),
        Param("style", "Цвет: 0 зелёный→красный, 1 радуга", 0, 1, 0, "bool"),
        Param("hue", "Сдвиг цвета", 0.0, 1.0, 0.0, "hue"),
        Param("caps", "Падающие пики", 0, 1, 1, "bool"),
    ]

    def reset(self):
        self.audio = Audio.get()
        self.caps = np.zeros(N_BANDS)

    def render(self, t, dt, presses, calm):
        lv = self.audio.update(dt, self.p["sensitivity"])
        level = lv[COL] * 1.08
        lit = np.clip((level - HEIGHT) * 6 + 1, 0, 1)         # soft edge on the top lit key
        if self.p["style"]:
            hue = COL / N_BANDS * 0.85 + self.p["hue"]
        else:
            hue = 0.33 - HEIGHT * 0.33 + self.p["hue"]           # green at the bottom, red on top
        out = hsv(hue, 1, lit)
        if self.p["caps"]:
            self.caps = np.maximum(lv * 1.08, self.caps - dt * 0.6)
            cap = np.exp(-((HEIGHT - self.caps[COL]) * 6) ** 2) * (self.caps[COL] > 0.08)
            out = np.maximum(out, np.array([1.0, 1.0, 1.0]) * cap[:, None] * 0.8)
        return np.clip(out + np.array([0, 0, 0.02]), 0, 1)


class Pulse(Effect):
    name, title = "music_pulse", "Пульс на басах"
    params = [
        Param("sensitivity", "Чувствительность", 0.3, 3.0, 1.0),
        Param("hue_step", "Смена цвета на долю", 0.0, 0.5, 0.13),
        Param("sparkle", "Искры от высоких", 0.0, 2.0, 1.0),
    ]

    def reset(self):
        self.audio = Audio.get()
        self.hue = 0.0
        self.rings = []                     # (t0, hue)
        self.spark = np.zeros(N)

    def render(self, t, dt, presses, calm):
        a = self.audio
        lv = a.update(dt, self.p["sensitivity"])
        if a.beat:
            self.hue += self.p["hue_step"]
            self.rings.append((t, self.hue))
        self.rings = [r for r in self.rings if t - r[0] < 0.8]
        cx, cy = 9.0, 2.6
        d = np.hypot(X - cx, (Y - cy) * 1.6)
        ring = np.zeros(N)
        for t0, h in self.rings:
            age = t - t0
            ring = np.maximum(ring, np.clip(1 - np.abs(d - age * 16) / 2.0, 0, 1) * (1 - age / 0.8))
        base = hsv(np.full(N, self.hue), 1, 0.05 + 0.55 * a.bass ** 1.5 * np.exp(-d / 9))
        treble = float(lv[12:].mean())
        born = self.rng.random(N) < dt * 12 * treble ** 2 * self.p["sparkle"]
        self.spark = np.maximum(self.spark * np.exp(-dt / 0.12), born.astype(float))
        out = base + hsv(np.full(N, self.hue + 0.08), 0.7, ring) + self.spark[:, None] * 0.8
        return np.clip(out, 0, 1)
