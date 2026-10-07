"""Storm: dark drifting clouds, sheet lightning inside them and branching bolts. A key press calls a bolt into it."""
import numpy as np
from .base import Effect, Param, Noise, X, Y, N

CLOUD_DARK = np.array([0.010, 0.014, 0.030])
CLOUD_LIT = np.array([0.16, 0.18, 0.26])
BOLT = np.array([0.80, 0.82, 1.00])
GLOW = np.array([0.45, 0.50, 1.00])
RAIN = np.array([0.10, 0.22, 0.45])


class Storm(Effect):
    name, title = "storm", "Гроза"
    params = [
        Param("frequency", "Частота молний", 0.0, 3.0, 1.0),
        Param("wind", "Ветер", 0.0, 3.0, 1.0),
        Param("clouds", "Яркость облаков", 0.0, 2.0, 1.0),
        Param("rain", "Дождь", 0.0, 1.0, 0.3),
        Param("music", "Молнии в такт музыке (бас)", 0, 1, 0, "bool"),
        Param("cycles", "Шторм нарастает и стихает", 0, 1, 0, "bool"),
        Param("cycle_min", "Длина цикла, мин", 1.0, 10.0, 4.0),
    ]

    def reset(self):
        self.noise = Noise(self.rng)
        self.strikes = []
        self.drops = []
        self.audio = None
        self.last_beat_strike = -10.0

    # --- lightning geometry -------------------------------------------------
    def _path(self, x_start, y_end, x_end=None):
        """Jagged path from the top row down to y_end; converges on x_end if given."""
        pts, x = [], x_start
        steps = max(2, int(round(y_end * 2)))
        for s in range(steps + 1):
            y = y_end * s / steps
            if x_end is not None:
                x += (x_end - x) * (s / steps) ** 2
            pts.append((x, y))
            x += self.rng.choice([-1.0, -0.5, 0.0, 0.5, 1.0])
        return pts

    def _bolt(self, target=None):
        if target is None:
            x0 = self.rng.uniform(1, 18)
            pts = self._path(x0, self.rng.uniform(3.5, 5.0))
        else:
            tx, ty = X[target], Y[target]
            pts = self._path(tx + self.rng.uniform(-3, 3), ty, tx)
        for _ in range(self.rng.integers(1, 3)):                     # side branches
            bx, by = pts[self.rng.integers(1, max(2, len(pts) - 1))]
            dirx = self.rng.choice([-1, 1])
            pts += [(bx + dirx * k * 0.8 + self.rng.uniform(-0.3, 0.3), by + k * 0.5) for k in range(1, 4)]
        p = np.array(pts)
        d2 = (X[:, None] - p[None, :, 0]) ** 2 + ((Y[:, None] - p[None, :, 1]) * 1.3) ** 2
        dmin = d2.min(1)
        core = np.exp(-dmin / 0.35)
        cx = p[:, 0].mean()
        glow = np.exp(-((X - cx) ** 2) / 30) * 0.6
        return core, glow

    def _strike(self, t, target=None):
        if target is not None or self.rng.random() < 0.6:
            core, glow = self._bolt(target)
            kind = "bolt"
        else:
            cx = self.rng.uniform(0, 19)
            core = np.zeros(N)
            glow = np.exp(-((X - cx) ** 2) / self.rng.uniform(15, 60))
            kind = "sheet"
        n = self.rng.integers(1, 4)
        pulses = np.sort(np.concatenate([[0.0], self.rng.uniform(0.05, 0.35, n - 1)]))
        amps = np.concatenate([[1.0], self.rng.uniform(0.4, 1.0, n - 1)])
        self.strikes.append(dict(kind=kind, t0=t, core=core, glow=glow, pulses=pulses, amps=amps))

    # --- frame ----------------------------------------------------------------
    def intensity(self, t):
        """Storm strength 0.1..1: constant 1 unless cycles are on."""
        if not self.p["cycles"]:
            return 1.0
        period = self.p["cycle_min"] * 60
        wave = 0.5 - 0.5 * np.cos(2 * np.pi * t / period)
        return 0.1 + 0.9 * wave ** 1.5 * (0.85 + 0.3 * self.noise(t * 0.05, 7.7))

    def render(self, t, dt, presses, calm):
        p = self.p
        k = self.intensity(t)
        for slot in presses:
            self._strike(t, target=slot)
        if p["music"]:
            if self.audio is None:
                from ..audio import Audio
                self.audio = Audio.get()
            self.audio.update(dt)
            if self.audio.beat and t - self.last_beat_strike > 0.35 and self.rng.random() < 0.35 + 0.65 * k:
                self._strike(t)
                self.last_beat_strike = t
        elif t > 1.5 and self.rng.random() < dt * p["frequency"] * k / 6.0:     # ~every 6 s at full strength
            self._strike(t)

        wind = p["wind"] * (0.4 + 0.9 * k)
        c = self.noise.fbm(X * 0.22 - t * 0.35 * wind, Y * 0.4 + t * 0.04, octaves=3)
        c = np.clip((c - 0.35) * 1.8, 0, 1) * p["clouds"] * (0.5 + 0.5 * k)
        out = CLOUD_DARK + (CLOUD_LIT - CLOUD_DARK) * c[:, None]

        light = np.zeros(N)
        bolt = np.zeros(N)
        alive = []
        for s in self.strikes:
            age = t - s["t0"]
            if age > 1.6:
                continue
            alive.append(s)
            env = sum(a * np.exp(-(age - pt) / 0.06) for pt, a in zip(s["pulses"], s["amps"]) if age >= pt)
            after = 0.25 * np.exp(-age / 0.5)
            light = np.maximum(light, s["glow"] * (env + after) * (0.4 + 0.9 * c))
            if s["kind"] == "bolt":
                bolt = np.maximum(bolt, s["core"] * min(1.0, env * 1.2))
        self.strikes = alive
        out = out + GLOW * light[:, None] + BOLT * bolt[:, None]

        if p["rain"] > 0:
            out = out + RAIN * self._rain(dt, p["rain"] * (0.2 + 1.3 * k), wind)[:, None]
        return np.clip(out, 0, 1)

    def _rain(self, dt, density, wind):
        if self.rng.random() < density * 0.6:
            self.drops.append([self.rng.uniform(0, 19.5), -0.5, self.rng.uniform(7, 10)])
        v = np.zeros(N)
        keep = []
        for d in self.drops:
            d[1] += d[2] * dt
            d[0] += wind * 0.6 * dt
            if d[1] > 6:
                continue
            keep.append(d)
            dx = np.abs(X - d[0])
            dy = d[1] - Y
            v = np.maximum(v, np.where((dx < 0.55) & (dy > -0.5) & (dy < 1.4), np.clip(1 - dy / 1.4, 0, 1), 0))
        self.drops = keep
        return v
