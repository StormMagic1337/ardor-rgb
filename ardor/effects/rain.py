"""Rain: falling drops with trails, wind, splashes on the bottom row; a key press splashes where you hit."""
import numpy as np
from .base import Effect, Param, Noise, hsv, X, Y, N
from .. import layout


class Rain(Effect):
    name, title = "rain", "Дождь"
    params = [
        Param("density", "Сила дождя", 0.1, 3.0, 1.0),
        Param("speed", "Скорость капель", 0.3, 2.5, 1.0),
        Param("wind", "Ветер", -2.0, 2.0, 0.3),
        Param("hue", "Цвет", 0.0, 1.0, 0.56, "hue"),
        Param("splash", "Брызги", 0, 1, 1, "bool"),
    ]

    def reset(self):
        self.drops = np.zeros((0, 4))        # x, y, speed, brightness
        self.splashes = []                   # (x, y, t0, strength)
        self.noise = Noise(self.rng)

    def _splash(self, x, y, t, strength):
        if self.p["splash"]:
            self.splashes.append((x, y, t, strength))

    def render(self, t, dt, presses, calm):
        p = self.p
        for s in presses:
            self._splash(X[s], Y[s], t, 1.0)

        spawn = self.rng.poisson(dt * 9 * p["density"])
        if spawn:
            new = np.column_stack([self.rng.uniform(-2, layout.W + 3.1, spawn), self.rng.uniform(-1.5, -0.3, spawn),
                                   self.rng.uniform(7, 12, spawn), self.rng.uniform(0.5, 1.0, spawn)])
            self.drops = np.vstack([self.drops, new])
        d = self.drops
        d[:, 1] += d[:, 2] * p["speed"] * dt
        d[:, 0] += p["wind"] * d[:, 2] * p["speed"] * dt * 0.25
        landed = d[:, 1] >= layout.YMAX
        for x, _, _, b in d[landed]:
            self._splash(x, 5.0, t, b * 0.7)
        self.drops = d = d[~landed]

        v = np.zeros(N)
        if len(d):
            dx = np.abs(X[:, None] - d[None, :, 0])
            dy = d[None, :, 1] - Y[:, None]                 # >0 when the drop is below the key
            trail = np.clip(1 - dy / (1.0 + 0.4 * p["speed"]), 0, 1) * (dy > -0.45)
            v = (np.clip(1 - dx / 0.6, 0, 1) * trail * d[None, :, 3]).max(1)

        sp = np.zeros(N)
        alive = []
        for x, y, t0, s in self.splashes:
            age = t - t0
            if age > 0.45:
                continue
            alive.append((x, y, t0, s))
            r = np.hypot(X - x, (Y - y) * 1.4)
            sp = np.maximum(sp, s * np.clip(1 - np.abs(r - age * 5) / 0.7, 0, 1) * (1 - age / 0.45))
        self.splashes = alive

        puddle = (Y >= 4.5) * 0.06 * (0.6 + 0.4 * self.noise(X * 0.6 + t * 0.4, t * 0.3))
        bg = 0.025 + puddle
        h = p["hue"]
        out = hsv(np.full(N, h + 0.02), 0.8, bg)
        out = out + hsv(np.full(N, h), 0.55, v) + hsv(np.full(N, h - 0.03), 0.25, sp * 0.9)
        return np.clip(out, 0, 1)
