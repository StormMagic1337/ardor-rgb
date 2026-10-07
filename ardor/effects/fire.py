"""Fire 2.0: Doom-fire heat simulation on a fine grid sampled at the keys, rising sparks, glowing embers.
A key press throws a burst of heat and sparks from that key."""
import numpy as np
from .base import Effect, Param, Noise, X, Y, N
from .. import layout

ROWS, COLS = 30, 80
# heat (0..1) -> colour; black, deep red, orange, yellow, white-hot
STOPS = np.array([0.0, 0.18, 0.45, 0.75, 1.0])
PALETTE = np.array([[0, 0, 0], [0.35, 0.0, 0.0], [1.0, 0.18, 0.0], [1.0, 0.55, 0.05], [1.0, 0.9, 0.55]])


def palette(h, cool=0.0):
    h = np.clip(h, 0, 1)
    out = np.stack([np.interp(h, STOPS, PALETTE[:, c]) for c in range(3)], -1)
    if cool:                                   # "blue fire" option: rotate channels toward blue
        out = out * (1 - cool) + out[..., [2, 1, 0]] * cool
    return out


class Fire(Effect):
    name, title = "fire", "Огонь"
    params = [
        Param("height", "Высота пламени", 0.3, 2.0, 1.2),
        Param("intensity", "Жар", 0.3, 1.5, 1.0),
        Param("wind", "Ветер", -1.5, 1.5, 0.0),
        Param("sparks", "Искры", 0.0, 2.0, 1.0),
        Param("cool", "Синее пламя", 0.0, 1.0, 0.0),
    ]

    def reset(self):
        self.heat = np.zeros((ROWS, COLS))
        self.sparks = np.zeros((0, 4))         # x, y, vy, life
        self.noise = Noise(self.rng)
        self.acc = 0.0

    def _step(self, t):
        p = self.p
        h = self.heat
        base = self.noise(np.arange(COLS) * 0.15, np.full(COLS, t * 1.7))
        h[-1] = np.clip(0.55 + 0.5 * base + self.rng.uniform(-0.15, 0.15, COLS), 0, 1) * p["intensity"]
        shift = self.rng.integers(-1, 2, (ROWS - 1, COLS)) + int(round(p["wind"] * self.rng.random()))
        cols = np.clip(np.arange(COLS)[None, :] + shift, 0, COLS - 1)
        src = np.take_along_axis(h[1:], cols, axis=1)
        decay = self.rng.random((ROWS - 1, COLS)) * 0.11 / p["height"]
        h[:-1] = np.clip(src - decay, 0, 1)

    def render(self, t, dt, presses, calm):
        p = self.p
        for s in presses:
            c = int(X[s] / layout.W * (COLS - 1))
            r = int(Y[s] / (layout.H - 1) * (ROWS - 1))
            self.heat[max(0, r - 3):r + 2, max(0, c - 3):c + 4] = 1.0
            self._spawn_sparks(X[s], Y[s], 6)
        self.acc += dt * 45                    # fixed simulation rate, independent of fps
        while self.acc >= 1:
            self._step(t)
            self.acc -= 1

        if self.rng.random() < dt * 4 * p["sparks"]:
            self._spawn_sparks(self.rng.uniform(0, 19.5), 5.2, 1)
        sp = self.sparks
        sp[:, 1] += sp[:, 2] * dt
        sp[:, 0] += (np.sin(sp[:, 1] * 3 + sp[:, 3] * 10) * 0.8 + p["wind"]) * dt
        sp[:, 3] -= dt * 0.9
        self.sparks = sp = sp[(sp[:, 3] > 0) & (sp[:, 1] > -0.5)]

        heat = layout.sample(self.heat)
        ember = (Y >= 4.5) * (0.25 + 0.2 * self.noise(X * 0.8, np.full(N, t * 2.5)))
        out = palette(np.maximum(heat, ember), p["cool"])
        if len(sp):
            d = np.hypot(X[:, None] - sp[None, :, 0], (Y[:, None] - sp[None, :, 1]) * 1.2)
            glow = (np.clip(1 - d / 0.7, 0, 1) * sp[None, :, 3]).max(1)
            out = out + palette(np.full(N, 0.85), p["cool"]) * glow[:, None]
        return np.clip(out, 0, 1)

    def _spawn_sparks(self, x, y, n):
        new = np.column_stack([x + self.rng.uniform(-0.4, 0.4, n), np.full(n, y),
                               -self.rng.uniform(2.5, 5.0, n), self.rng.uniform(0.6, 1.0, n)])
        self.sparks = np.vstack([self.sparks, new])
