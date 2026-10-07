"""Calm ambient effects: Matrix rain, aurora, ocean / lava."""
import numpy as np
from .base import Effect, Param, Noise, hsv, X, Y, N

COLUMNS = np.unique(np.round(X * 2) / 2)              # distinct key columns for falling streams


class Matrix(Effect):
    name, title = "matrix", "Матрица"
    params = [
        Param("density", "Плотность", 0.2, 3.0, 1.0),
        Param("speed", "Скорость", 0.3, 3.0, 1.0),
        Param("hue", "Цвет", 0.0, 1.0, 0.33, "hue"),
    ]

    def reset(self):
        self.streams = np.zeros((0, 4))                # x, head y, speed, trail length
        self.glyph = self.rng.random(N)

    def _spawn(self, x, y=-0.5):
        s = np.array([[x, y, self.rng.uniform(3, 7), self.rng.uniform(2, 5)]])
        self.streams = np.vstack([self.streams, s])

    def render(self, t, dt, presses, calm):
        p = self.p
        for k in presses:
            self._spawn(X[k], Y[k])
        for _ in range(self.rng.poisson(dt * 3.5 * p["density"])):
            self._spawn(self.rng.choice(COLUMNS))
        s = self.streams
        s[:, 1] += s[:, 2] * p["speed"] * dt
        self.streams = s = s[s[:, 1] - s[:, 3] < 6]
        flick = self.rng.random(N) < dt * 6                 # "glyphs" changing
        self.glyph[flick] = self.rng.random(flick.sum())
        head = np.zeros(N)
        trail = np.zeros(N)
        if len(s):
            same_col = np.abs(X[:, None] - s[None, :, 0]) < 0.5
            dy = s[None, :, 1] - Y[:, None]
            head = (same_col * np.clip(1 - np.abs(dy) / 0.5, 0, 1)).max(1)
            trail = (same_col * (dy > 0) * np.clip(1 - dy / s[None, :, 3], 0, 1)).max(1)
        trail = trail * (0.55 + 0.45 * self.glyph)
        out = hsv(np.full(N, p["hue"]), 1, trail * 0.9) + hsv(np.full(N, p["hue"]), 0.35, head)
        return np.clip(out + hsv(np.full(N, p["hue"]), 1, 0.015), 0, 1)


class Aurora(Effect):
    name, title = "aurora", "Северное сияние"
    params = [
        Param("speed", "Скорость", 0.2, 3.0, 1.0),
        Param("hue1", "Цвет низа", 0.0, 1.0, 0.38, "hue"),
        Param("hue2", "Цвет верха", 0.0, 1.0, 0.80, "hue"),
        Param("stars", "Звёзды", 0, 1, 1, "bool"),
    ]

    def reset(self):
        self.noise = Noise(self.rng)
        self.star = self.rng.random(N) < 0.12
        self.star_phase = self.rng.uniform(0, 6.28, N)
        self.flare = np.zeros(N)

    def render(self, t, dt, presses, calm):
        p = self.p
        t = t * p["speed"]
        for k in presses:
            self.flare = np.maximum(self.flare, np.exp(-((X - X[k]) ** 2) / 3))
        self.flare *= np.exp(-dt / 0.6)
        n = self.noise
        centre = 2.4 + 1.3 * np.sin(X * 0.28 + t * 0.25) + 1.2 * (n(X * 0.25 + t * 0.15, t * 0.1) - 0.5)
        width = 0.9 + 0.6 * n(X * 0.4 - t * 0.2, 5 + t * 0.07)
        curtain = np.exp(-((Y - centre) / width) ** 2)
        rays = 0.55 + 0.45 * n(X * 1.3 + t * 0.6, t * 0.4)        # vertical ray structure
        v = np.clip(curtain * rays * (0.8 + self.flare), 0, 1)
        mix = np.clip((centre - Y) / 2.5 + 0.5, 0, 1)            # above the curtain centre -> hue2
        hue = p["hue1"] + (p["hue2"] - p["hue1"]) * mix * 0.7
        out = hsv(hue, 0.85, v * 0.95) + np.array([0.0, 0.004, 0.02])
        if p["stars"]:
            tw = 0.5 + 0.5 * np.sin(t * 2.0 + self.star_phase)
            out = out + (self.star * tw * (1 - v) * 0.25)[:, None]
        return np.clip(out, 0, 1)


PALETTES = {
    0: (np.array([0.0, 0.25, 0.55, 0.85, 1.0]),                     # ocean
        np.array([[0.0, 0.01, 0.05], [0.0, 0.06, 0.25], [0.0, 0.3, 0.55], [0.1, 0.7, 0.8], [0.8, 1.0, 1.0]])),
    1: (np.array([0.0, 0.3, 0.6, 0.85, 1.0]),                       # lava
        np.array([[0.02, 0.0, 0.0], [0.3, 0.0, 0.0], [0.9, 0.12, 0.0], [1.0, 0.45, 0.0], [1.0, 0.85, 0.3]])),
}


class Liquid(Effect):
    name, title = "liquid", "Океан / лава"
    params = [
        Param("lava", "0 океан, 1 лава", 0, 1, 0, "bool"),
        Param("speed", "Скорость", 0.2, 3.0, 1.0),
        Param("scale", "Масштаб волн", 0.5, 2.0, 1.0),
    ]

    def reset(self):
        self.noise = Noise(self.rng)
        self.drops = []

    def render(self, t, dt, presses, calm):
        p = self.p
        for k in presses:
            self.drops.append((X[k], Y[k], t))
        self.drops = [d for d in self.drops if t - d[2] < 1.5]
        t = t * p["speed"]
        sc = 0.22 / p["scale"]
        n = self.noise
        # domain warping gives slow "liquid" motion
        wx = n.fbm(X * sc + t * 0.10, Y * sc * 1.6, 2)
        wy = n.fbm(X * sc - 3.1, Y * sc * 1.6 + t * 0.08, 2)
        v = n.fbm(X * sc + 2.5 * wx + t * 0.05, Y * sc * 1.6 + 2.5 * wy, 3)
        v = np.clip((v - 0.3) * 1.9, 0, 1)
        for x, y, t0 in self.drops:
            age = (t / p["speed"]) - t0
            r = np.hypot(X - x, (Y - y) * 1.3)
            v = v + 0.6 * np.clip(1 - np.abs(r - age * 7) / 0.8, 0, 1) * (1 - age / 1.5)
        stops, cols = PALETTES[int(p["lava"])]
        v = np.clip(v, 0, 1)
        return np.stack([np.interp(v, stops, cols[:, c]) for c in range(3)], -1)
