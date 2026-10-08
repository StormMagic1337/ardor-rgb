"""Atmospheric effects: snowfall / blizzard, meteor shower, fireflies, surf, campfire, glitch, lava lamp."""
import numpy as np
from .base import Effect, Param, Noise, hsv, X, Y, N
from .. import layout
from .fire import ROWS, COLS, palette

FIRE_X = layout.W * 8.5 / 18.4             # campfire centre, a bit left of the middle


def particles_glow(px, py, strength, radius=0.6, yscale=1.2):
    """Brightness at every key from point particles (arrays px, py, strength)."""
    if len(px) == 0:
        return np.zeros(N)
    d = np.hypot(X[:, None] - px[None, :], (Y[:, None] - py[None, :]) * yscale)
    return (np.clip(1 - d / radius, 0, 1) * strength[None, :]).max(1)


class Snow(Effect):
    name, title = "snow", "Снегопад / метель"
    params = [
        Param("density", "Снегопад", 0.1, 3.0, 1.0),
        Param("wind", "Ветер", -2.0, 2.0, 0.4),
        Param("blizzard", "Порывы метели", 0.0, 1.0, 0.3),
        Param("drifts", "Сугробы внизу", 0, 1, 1, "bool"),
    ]

    def reset(self):
        self.f = np.zeros((0, 4))           # x, y, fall speed, phase
        self.noise = Noise(self.rng)
        self.cover = np.zeros(N)

    def _add(self, x, y, n, speed=(0.8, 2.0)):
        new = np.column_stack([x, y, self.rng.uniform(*speed, n), self.rng.uniform(0, 6.3, n)])
        self.f = np.vstack([self.f, new])

    def render(self, t, dt, presses, calm):
        p = self.p
        gust = p["blizzard"] * max(0.0, self.noise(t * 0.15, 3.3) * 2 - 0.8) * 4      # 0 most of the time
        wind = p["wind"] + np.sign(p["wind"] or 1) * gust * 2.5
        rate = 6 * p["density"] * (1 + gust * 2)
        n = self.rng.poisson(dt * rate)
        if n:
            self._add(self.rng.uniform(-3, 21.5, n), np.full(n, -0.6), n)
        for k in presses:
            self._add(X[k] + self.rng.uniform(-0.5, 0.5, 6), Y[k] + self.rng.uniform(-0.3, 0.3, 6), 6, (-1.5, 0.5))
        f = self.f
        f[:, 1] += f[:, 2] * dt * (1 + gust)
        f[:, 0] += (wind + 0.35 * np.sin(t * 1.3 + f[:, 3])) * dt
        landed = f[:, 1] > 5.4
        if p["drifts"] and landed.any():
            for x in f[landed, 0]:
                k = np.argmin(np.abs(X - x) + np.abs(Y - 5) * 3)
                self.cover[k] = min(1.0, self.cover[k] + 0.05)
        self.f = f = f[~landed & (f[:, 0] > -4) & (f[:, 0] < 23)]
        self.cover *= np.exp(-dt / 40)                                    # slow melt
        flakes = particles_glow(f[:, 0], f[:, 1], np.full(len(f), 1.0), 0.55)
        sky = 0.03 + 0.05 * gust
        out = hsv(np.full(N, 0.61), 0.7, np.full(N, sky)) + (np.array([0.75, 0.85, 1.0]) * flakes[:, None])
        out += np.array([0.5, 0.55, 0.65]) * (self.cover * (Y >= 4))[:, None]
        return np.clip(out, 0, 1)


class Meteors(Effect):
    name, title = "meteors", "Звездопад"
    params = [
        Param("frequency", "Частота метеоров", 0.1, 3.0, 1.0),
        Param("stars", "Звёзды", 0.0, 1.0, 0.6),
        Param("hue", "Цвет хвоста", 0.0, 1.0, 0.55, "hue"),
    ]

    def reset(self):
        self.star = self.rng.random(N) < 0.25
        self.phase = self.rng.uniform(0, 6.3, N)
        self.m = []                         # x0, y0, vx, vy, t0, life

    def _spawn(self, t, target=None):
        if target is None:
            vx = self.rng.choice([-1, 1]) * self.rng.uniform(9, 14)
            x0 = self.rng.uniform(2, layout.W - 1.4) - vx * 0.15
            self.m.append((x0, -0.5, vx, self.rng.uniform(3, 6), t, self.rng.uniform(0.6, 1.0), None))
        else:
            tx, ty = X[target], Y[target]
            vx, vy = self.rng.choice([-1, 1]) * 11.0, 7.0
            dur = (ty + 0.5) / vy
            self.m.append((tx - vx * dur, -0.5, vx, vy, t, dur, (tx, ty)))

    def render(self, t, dt, presses, calm):
        p = self.p
        if self.rng.random() < dt * 0.5 * p["frequency"]:
            self._spawn(t)
        for k in presses:
            self._spawn(t, k)
        tw = 0.5 + 0.5 * np.sin(t * 1.7 + self.phase)
        out = np.zeros((N, 3)) + np.array([0.0, 0.0, 0.02])
        out += (self.star * tw * 0.3 * p["stars"])[:, None] * np.array([0.8, 0.85, 1.0])
        alive = []
        for m in self.m:
            x0, y0, vx, vy, t0, life, hit = m
            age = t - t0
            if age > life + 0.6:
                continue
            alive.append(m)
            if age <= life:
                hx, hy = x0 + vx * age, y0 + vy * age
                ux, uy = vx / np.hypot(vx, vy), vy / np.hypot(vx, vy)
                rx, ry = X - hx, (Y - hy) * 1.3
                along = -(rx * ux + ry * uy)                       # distance behind the head
                across = np.abs(rx * uy - ry * ux)
                tail = np.clip(1 - along / 4.5, 0, 1) * (along > -0.4) * np.clip(1 - across / 0.6, 0, 1)
                head = np.clip(1 - np.hypot(rx, ry) / 0.7, 0, 1)
                out += hsv(np.full(N, p["hue"]), 0.6, tail * 0.8) + np.array([1, 1, 1]) * head[:, None]
            if hit and age > life:                                    # impact flash
                v = np.clip(1 - np.hypot(X - hit[0], (Y - hit[1]) * 1.3) / ((age - life) * 8 + 0.5), 0, 1)
                out += hsv(np.full(N, p["hue"]), 0.4, v * (1 - (age - life) / 0.6))
        self.m = alive
        return np.clip(out, 0, 1)


class Fireflies(Effect):
    name, title = "fireflies", "Светлячки"
    params = [
        Param("count", "Количество", 3, 25, 12, "int"),
        Param("hue", "Цвет", 0.0, 1.0, 0.18, "hue"),
        Param("speed", "Скорость", 0.2, 3.0, 1.0),
    ]

    def reset(self):
        self.pos = np.column_stack([self.rng.uniform(0, layout.W, 25), self.rng.uniform(0, layout.YMAX, 25)])
        self.vel = np.zeros((25, 2))
        self.phase = self.rng.uniform(0, 6.3, 25)
        self.rate = self.rng.uniform(0.4, 1.0, 25)
        self.lure = None

    def render(self, t, dt, presses, calm):
        p = self.p
        n = int(p["count"])
        if presses:
            self.lure = (X[presses[-1]], Y[presses[-1]], t)
        if self.lure and t - self.lure[2] > 3:
            self.lure = None
        acc = self.rng.normal(0, 1.5, (25, 2))
        if self.lure:
            acc += (np.array(self.lure[:2]) - self.pos) * 0.8
        self.vel = (self.vel + acc * dt) * np.exp(-dt * 1.2)
        self.pos += self.vel * dt * p["speed"]
        self.pos[:, 0] = np.clip(self.pos[:, 0], 0, layout.W)
        self.pos[:, 1] = np.clip(self.pos[:, 1], 0, layout.YMAX)
        self.vel[(self.pos[:, 0] <= 0) | (self.pos[:, 0] >= layout.W), 0] *= -1
        self.vel[(self.pos[:, 1] <= 0) | (self.pos[:, 1] >= layout.YMAX), 1] *= -1
        blink = np.clip(np.sin(t * self.rate * 1.5 + self.phase) * 1.6 - 0.3, 0, 1) ** 1.5
        g = particles_glow(self.pos[:n, 0], self.pos[:n, 1], blink[:n], radius=1.1)
        out = hsv(np.full(N, 0.4), 0.8, np.full(N, 0.015 + 0.01 * (Y > 3)))
        return np.clip(out + hsv(np.full(N, p["hue"]), 0.85, g), 0, 1)


class Surf(Effect):
    name, title = "surf", "Прибой"
    params = [
        Param("speed", "Скорость волн", 0.3, 2.5, 1.0),
        Param("height", "Высота волн", 0.3, 1.5, 1.0),
    ]

    def reset(self):
        self.noise = Noise(self.rng)
        self.splash = []

    def render(self, t, dt, presses, calm):
        p = self.p
        for k in presses:
            self.splash.append((X[k], Y[k], t))
        self.splash = [s for s in self.splash if t - s[2] < 0.8]
        ts = t * p["speed"]
        cycle = (0.5 - 0.5 * np.cos(ts * 0.9)) ** 1.5                    # 0 = low tide, 1 = wave at peak
        reach = 5.6 - (1.0 + 3.6 * cycle) * p["height"]                     # y of the wave edge
        edge = reach + 0.7 * (self.noise(X * 0.35 + ts * 0.3, ts * 0.2) - 0.5)
        depth = np.clip(Y - edge, 0, None)                                   # >0 under water
        water = np.where(Y >= edge, 1.0, 0.0)
        foam = np.exp(-((Y - edge) / 0.35) ** 2) * (0.6 + 0.4 * np.sin(X * 2 + ts * 3)) * (0.4 + cycle)
        wet = np.clip(1 - (edge - Y) / 1.2, 0, 1) * (Y < edge) * (1 - cycle) * 0.5   # wet sand after retreat
        sand = np.array([0.18, 0.12, 0.05]) * (1 - water)[:, None] * (1 - wet * 0.6)[:, None]
        sea = (np.array([0.0, 0.25, 0.45]) * np.exp(-depth * 0.35)[:, None] + np.array([0, 0.03, 0.12])) * water[:, None]
        out = sand + sea + np.array([0.8, 0.95, 1.0]) * foam[:, None]
        for x, y, t0 in self.splash:
            age = t - t0
            r = np.hypot(X - x, (Y - y) * 1.3)
            out += np.array([0.6, 0.9, 1.0]) * (np.clip(1 - np.abs(r - age * 6) / 0.7, 0, 1) * (1 - age / 0.8))[:, None]
        return np.clip(out, 0, 1)


class Campfire(Effect):
    name, title = "campfire", "Костёр"
    params = [
        Param("size", "Размер костра", 0.3, 1.5, 0.8),
        Param("glow", "Отсвет вокруг", 0.0, 1.0, 0.5),
        Param("sparks", "Искры", 0.0, 2.0, 1.0),
    ]

    def reset(self):
        self.heat = np.zeros((ROWS, COLS))
        self.noise = Noise(self.rng)
        self.sparks = np.zeros((0, 4))
        self.acc = 0.0
        self.boost = 0.0

    def render(self, t, dt, presses, calm):
        p = self.p
        if presses:
            self.boost = 1.0
        self.boost *= np.exp(-dt / 0.8)
        width = 3.2 * p["size"] * (1 + 0.4 * self.boost)
        cols = np.arange(COLS) / (COLS - 1) * layout.W
        source = np.exp(-((cols - FIRE_X) / width) ** 2)
        self.acc += dt * 45
        while self.acc >= 1:
            h = self.heat
            h[-1] = np.clip(source * (0.7 + 0.5 * self.noise(cols * 0.6, np.full(COLS, t * 2))), 0, 1)
            shift = self.rng.integers(-1, 2, (ROWS - 1, COLS))
            src = np.take_along_axis(h[1:], np.clip(np.arange(COLS)[None, :] + shift, 0, COLS - 1), axis=1)
            h[:-1] = np.clip(src - self.rng.random((ROWS - 1, COLS)) * 0.2 / (p["size"] * (1 + self.boost)), 0, 1)
            self.acc -= 1
        heat = layout.sample(self.heat)
        flicker = 0.75 + 0.25 * self.noise(t * 3, 1.7)
        ambient = p["glow"] * 0.22 * flicker * np.exp(-((X - FIRE_X) / 7) ** 2) * (0.4 + 0.6 * Y / layout.YMAX)
        out = palette(heat) + np.array([1.0, 0.35, 0.05]) * ambient[:, None]
        if self.rng.random() < dt * 2.5 * p["sparks"] * (1 + 3 * self.boost):
            s = np.array([[FIRE_X + self.rng.normal(0, width * 0.4), 4.5, -self.rng.uniform(1.5, 3.5), 1.0]])
            self.sparks = np.vstack([self.sparks, s])
        sp = self.sparks
        sp[:, 1] += sp[:, 2] * dt
        sp[:, 0] += np.sin(sp[:, 1] * 2.5 + sp[:, 3] * 7) * dt * 0.8
        sp[:, 3] -= dt * 0.5
        self.sparks = sp = sp[sp[:, 3] > 0]
        out += np.array([1.0, 0.6, 0.15]) * particles_glow(sp[:, 0], sp[:, 1], sp[:, 3], 0.5)[:, None]
        return np.clip(out, 0, 1)


class Glitch(Effect):
    name, title = "glitch", "Глитч / киберпанк"
    params = [
        Param("chaos", "Частота сбоев", 0.0, 3.0, 1.0),
        Param("hue1", "Неон 1", 0.0, 1.0, 0.88, "hue"),
        Param("hue2", "Неон 2", 0.0, 1.0, 0.5, "hue"),
    ]

    def reset(self):
        self.events = []                    # (kind, row, t0, dur, value)

    def render(self, t, dt, presses, calm):
        p = self.p
        rows = np.round(Y).astype(int)
        for k in presses:
            self.events.append(("shift", rows[k], t, 0.25, self.rng.uniform(-4, 4)))
        if self.rng.random() < dt * 2.5 * p["chaos"]:
            kind = self.rng.choice(["shift", "block", "split", "black"], p=[0.45, 0.3, 0.15, 0.1])
            self.events.append((kind, self.rng.integers(0, 6), t, self.rng.uniform(0.06, 0.3), self.rng.uniform(-5, 5)))
        self.events = [e for e in self.events if t - e[2] < e[3]]
        xs = X.copy()
        for kind, row, t0, dur, val in self.events:
            if kind == "shift":
                xs = np.where(rows == row, xs + val, xs)
        u = (xs / layout.W + t * 0.07) % 1.0
        mix = 0.5 + 0.5 * np.sin(u * 2 * np.pi * 1.5)
        base = hsv(np.full(N, p["hue1"]), 1, 0.9) * mix[:, None] + hsv(np.full(N, p["hue2"]), 1, 0.9) * (1 - mix)[:, None]
        scan = 0.55 + 0.45 * (np.sin(Y * 3.1 - t * 9) > 0.6)
        out = base * scan[:, None]
        for kind, row, t0, dur, val in self.events:
            if kind == "block":
                m = (np.abs(X - (val + 9)) < 2.5) & (np.abs(rows - row) <= 1)
                out[m] = hsv(self.rng.random(m.sum()), 0.3, 1)
            elif kind == "split":
                out[rows == row] = out[rows == row][:, [2, 0, 1]]
            elif kind == "black":
                out *= 0.08
        return np.clip(out, 0, 1)


class LavaLamp(Effect):
    name, title = "lavalamp", "Лавовая лампа"
    params = [
        Param("speed", "Скорость", 0.2, 3.0, 1.0),
        Param("blobs", "Капли", 3, 10, 6, "int"),
        Param("hue_blob", "Цвет капель", 0.0, 1.0, 0.04, "hue"),
        Param("hue_liquid", "Цвет жидкости", 0.0, 1.0, 0.78, "hue"),
    ]

    def reset(self):
        self.bx = self.rng.uniform(1, layout.W - 1.0, 10)
        self.ph = self.rng.uniform(0, 6.3, 10)
        self.per = self.rng.uniform(9, 18, 10)
        self.r = self.rng.uniform(1.0, 1.7, 10)
        self.pops = []

    def render(self, t, dt, presses, calm):
        p = self.p
        for k in presses:
            self.pops.append((X[k], Y[k], t))
        self.pops = [q for q in self.pops if t - q[2] < 2.5]
        n = int(p["blobs"])
        ts = t * p["speed"]
        by = layout.CY - 3.3 * np.sin(2 * np.pi * ts / self.per[:n] + self.ph[:n])         # rise and sink
        bx = self.bx[:n] + 0.8 * np.sin(ts * 0.21 + self.ph[:n] * 2)
        r = self.r[:n] * (1 + 0.15 * np.sin(ts * 0.5 + self.ph[:n]))
        cx, cy, cr = list(bx), list(by), list(r)
        for x, y, t0 in self.pops:                                                       # pressed key: a new blob rises
            age = t - t0
            cx.append(x); cy.append(y - age * 1.5); cr.append(1.2 * min(1, age * 3) * (1 - age / 2.5))
        cx, cy, cr = map(np.array, (cx, cy, cr))
        d2 = (X[:, None] - cx[None, :]) ** 2 + ((Y[:, None] - cy[None, :]) * 1.4) ** 2
        field = (cr[None, :] ** 2 / (d2 + 0.05)).sum(1)
        blob = np.clip((field - 0.9) * 2.5, 0, 1)
        liquid = hsv(np.full(N, p["hue_liquid"]), 0.9, 0.12 + 0.05 * Y / layout.YMAX)
        lava = hsv(np.full(N, p["hue_blob"]) + 0.05 * np.clip(field - 1.5, 0, 1), 1, 0.6 + 0.4 * np.clip(field - 1, 0, 1))
        return np.clip(liquid * (1 - blob)[:, None] + lava * blob[:, None], 0, 1)
