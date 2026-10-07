"""The first six effects, ported to the Effect API."""
import numpy as np
from .base import Effect, Param, hsv, X, Y, N
from .. import layout


class Wave(Effect):
    name, title = "wave", "Радужная волна"
    params = [Param("speed", "Скорость", 0.0, 3.0, 1.0), Param("width", "Ширина радуги", 0.3, 3.0, 1.0)]

    def render(self, t, dt, presses, calm):
        return hsv((X + Y * 0.6) / (20 * self.p["width"]) - t * 0.35 * self.p["speed"], 1, 1)


class Plasma(Effect):
    name, title = "plasma", "Плазма"
    params = [Param("speed", "Скорость", 0.0, 3.0, 1.0)]

    def render(self, t, dt, presses, calm):
        t = t * self.p["speed"]
        v = np.sin(X * 0.45 + t) + np.sin(Y * 0.8 - t * 1.3) + np.sin((X + Y) * 0.3 + t * 0.7)
        return hsv(v / 6 + t * 0.05, 1, 0.75 + 0.25 * np.sin(v))


class Ripple(Effect):
    name, title = "ripple", "Круги от нажатий"
    params = [Param("speed", "Скорость кругов", 0.3, 3.0, 1.0), Param("bg", "Фон", 0.0, 1.0, 0.3)]

    def reset(self):
        self.rings = []

    def render(self, t, dt, presses, calm):
        for s in presses:
            self.rings.append((X[s], Y[s], t, self.rng.random()))
        if calm and self.rng.random() < dt * 0.8:                 # without input: random drops
            s = self.rng.integers(N)
            self.rings.append((X[s], Y[s], t, self.rng.random()))
        self.rings = [r for r in self.rings if t - r[2] < 1.6]
        best, hue = np.zeros(N), np.zeros(N)
        for cx, cy, t0, h in self.rings:
            age = t - t0
            d = np.hypot(X - cx, (Y - cy) * 1.1)
            v = np.clip(1 - np.abs(d - age * 11 * self.p["speed"]) / 1.3, 0, 1) * max(0.0, 1 - age / 1.6)
            m = v > best
            best[m], hue[m] = v[m], h
        bg = hsv(0.6 + 0.03 * np.sin(t + X * 0.3), 1, 0.25 * self.p["bg"])
        return np.where((best > 0.02)[:, None], hsv(hue, 1, best), bg)


class Typing(Effect):
    name, title = "typing", "Вспышки при печати"
    params = [Param("fade", "Затухание", 0.3, 3.0, 1.0), Param("hue", "Цвет", 0.0, 1.0, 0.0, "hue"),
              Param("rainbow", "Радужный", 0, 1, 1, "bool")]

    def reset(self):
        self.glow = np.zeros(N)
        self.h = np.zeros(N)

    def render(self, t, dt, presses, calm):
        for s in presses:
            self.glow[s] = 1.0
            self.h[s] = (t * 0.1) if self.p["rainbow"] else self.p["hue"]
        self.glow *= np.exp(-dt * 4 / self.p["fade"])
        out = hsv(self.h, 1 - self.glow * 0.6, self.glow)
        return np.maximum(out, np.array([0, 0, 0.05]))


class Stars(Effect):
    name, title = "stars", "Звёзды"
    params = [Param("density", "Плотность", 0.1, 3.0, 1.0), Param("hue", "Оттенок", 0.0, 1.0, 0.6, "hue")]

    def reset(self):
        self.phase = np.full(N, -1.0)
        self.h = np.zeros(N)

    def render(self, t, dt, presses, calm):
        born = (self.phase < 0) & (self.rng.random(N) < dt * 0.25 * self.p["density"])
        self.phase[born] = 0
        self.h[born] = self.p["hue"] + self.rng.uniform(-0.08, 0.08, born.sum())
        live = self.phase >= 0
        self.phase[live] += dt * 0.9
        self.phase[self.phase > 1] = -1
        v = np.where(self.phase >= 0, np.sin(np.clip(self.phase, 0, 1) * np.pi), 0)
        return np.maximum(hsv(self.h, 0.4, v), np.array([0, 0, 0.025]))


class FireClassic(Effect):
    name, title = "fire_classic", "Огонь (простой)"
    params = [Param("height", "Высота", 0.3, 2.0, 1.0)]

    def reset(self):
        self.heat = np.zeros(N)

    def render(self, t, dt, presses, calm):
        target = np.clip(Y / 5, 0, 1) ** (1.6 / self.p["height"]) * self.rng.uniform(0.6, 1.25, N)
        self.heat += (target - self.heat) * 0.25
        return hsv(0.09 * self.heat, 1, self.heat)


class Breathe(Effect):
    """Slow breathing, also used while the PC is locked."""
    name, title = "breathe", "Дыхание"
    params = [Param("hue", "Цвет", 0.0, 1.0, 0.62, "hue"), Param("period", "Период, с", 2.0, 12.0, 6.0),
              Param("rainbow", "Новый цвет на каждом вдохе", 0, 1, 0, "bool")]

    def render(self, t, dt, presses, calm):
        per = self.p["period"]
        v = 0.08 + 0.5 * (0.5 - 0.5 * np.cos(2 * np.pi * t / per)) ** 2
        hue = self.p["hue"] + (np.floor(t / per) * 0.17 if self.p["rainbow"] else 0)
        return hsv(np.full(N, hue), 0.9, v)


class Off(Effect):
    name, title = "off", "Выключено"

    def render(self, t, dt, presses, calm):
        return np.zeros((N, 3))
