"""Remakes of the keyboard firmware's lighting modes (as listed in the Guardian app), rendered at 60 fps
with smooth motion and more options than the firmware has: 8 directions, single colour or rainbow, width."""
import numpy as np
from .base import Effect, Param, Noise, hsv, X, Y, N
from .. import layout

CX, CY = layout.W / 2, 2.6
_R = np.hypot(X - CX, Y - CY)
_ANG = np.arctan2(Y - CY, X - CX) / (2 * np.pi) % 1.0

DIRECTIONS = ("Слева направо", "Справа налево", "Сверху вниз", "Снизу вверх",
              "От центра", "К центру", "По часовой", "Против часовой")


def along(direction):
    """Position of every key along a direction, 0..1."""
    d = int(direction)
    return [X / layout.W, 1 - X / layout.W, Y / 5.2, 1 - Y / 5.2,
            _R / _R.max(), 1 - _R / _R.max(), _ANG, 1 - _ANG][d]


def colour(p, phase, v=1.0):
    """Rainbow by phase, or the chosen hue with brightness following the phase."""
    if p["rainbow"]:
        return hsv(phase, 1, v)
    return hsv(np.full(N, p["hue"]), 1, v)


COMMON = [Param("speed", "Скорость", 0.0, 3.0, 1.0),
          Param("rainbow", "Радуга", 0, 1, 1, "bool"),
          Param("hue", "Цвет (если не радуга)", 0.0, 1.0, 0.0, "hue")]
DIR = Param("direction", "Направление", 0, 7, 0, "choice", DIRECTIONS)


class ColorWave(Effect):
    name, title = "fw_wave", "Цветная волна"                    # firmware: Пульсация / Волна
    params = COMMON + [DIR, Param("width", "Ширина", 0.2, 3.0, 1.0)]

    def render(self, t, dt, presses, calm):
        p = self.p
        ph = along(p["direction"]) / p["width"] - t * 0.3 * p["speed"]
        if p["rainbow"]:
            return hsv(ph, 1, 1)
        v = 0.5 + 0.5 * np.cos(ph * 2 * np.pi)
        return hsv(np.full(N, p["hue"]), 1, 0.05 + 0.95 * v ** 2)


class Clouds(Effect):
    name, title = "fw_clouds", "Импульс (облака цвета)"           # firmware: Импульс
    params = [Param("speed", "Скорость", 0.0, 3.0, 1.0), Param("scale", "Размер пятен", 0.3, 3.0, 1.0)]

    def reset(self):
        self.noise = Noise(self.rng)

    def render(self, t, dt, presses, calm):
        s = 0.25 / self.p["scale"]
        v = self.noise.fbm(X * s - t * 0.25 * self.p["speed"], Y * s * 1.5, 2)
        return hsv(v * 1.6 + t * 0.04 * self.p["speed"], 1, 1)


class Spectrum(Effect):
    name, title = "fw_spectrum", "Радуга (вся клавиатура)"       # firmware: Радуга
    params = [Param("speed", "Скорость", 0.0, 3.0, 1.0)]

    def render(self, t, dt, presses, calm):
        return hsv(np.full(N, t * 0.08 * self.p["speed"]), 1, 1)


class Vortex(Effect):
    name, title = "fw_vortex", "Водоворот"                       # firmware: Водопад
    params = [Param("speed", "Скорость", 0.0, 3.0, 1.0), Param("twist", "Закрутка", 0.0, 2.0, 0.6),
              Param("clockwise", "По часовой", 0, 1, 1, "bool")]

    def render(self, t, dt, presses, calm):
        p = self.p
        sign = 1 if p["clockwise"] else -1
        return hsv(sign * _ANG + _R * 0.06 * p["twist"] - t * 0.25 * p["speed"], 1, 1)


class RainbowRings(Effect):
    name, title = "fw_rings", "Радужные круги"                   # firmware: Радужные переливы
    params = [Param("speed", "Скорость", 0.0, 3.0, 1.0), Param("width", "Ширина", 0.2, 3.0, 1.0),
              Param("inward", "К центру", 0, 1, 0, "bool")]

    def render(self, t, dt, presses, calm):
        p = self.p
        sign = -1 if p["inward"] else 1
        return hsv(_R / (12 * p["width"]) - sign * t * 0.35 * p["speed"], 1, 1)


class Scanner(Effect):
    name, title = "fw_scanner", "Из стороны в сторону"             # firmware: Из стороны в сторону
    params = COMMON + [Param("width", "Ширина луча", 0.5, 5.0, 2.0), Param("trail", "Шлейф", 0.0, 1.0, 0.6),
                       Param("vertical", "Вертикально", 0, 1, 0, "bool")]

    def render(self, t, dt, presses, calm):
        p = self.p
        u = (Y / 5.2) if p["vertical"] else (X / layout.W)
        pos = 0.5 - 0.5 * np.cos(t * 1.2 * p["speed"])              # eases at both ends
        moving_right = np.sin(t * 1.2 * p["speed"]) > 0
        size = p["width"] / (5.2 if p["vertical"] else layout.W)
        d = (u - pos) * (1 if moving_right else -1)                  # >0 ahead of the beam, <0 behind
        head = np.exp(-(d / size) ** 2 * 3)
        tail = np.where(d < 0, np.exp(d / (size * (0.3 + 3 * p["trail"]))), 0) * p["trail"]
        v = np.clip(np.maximum(head, tail * 0.7), 0, 1)
        return colour(p, u + t * 0.05, v)


class Arrow(Effect):
    name, title = "fw_arrow", "Стрела"                           # firmware: Стрела (реакция)
    params = COMMON + [Param("length", "Длина хвоста", 0.5, 4.0, 1.5)]

    def reset(self):
        self.shots = []                                          # (x, y, t0, hue)

    def render(self, t, dt, presses, calm):
        p = self.p
        for k in presses:
            self.shots.append((X[k], Y[k], t, self.rng.random()))
        if calm and self.rng.random() < dt * 0.7:
            k = self.rng.integers(N)
            self.shots.append((X[k], Y[k], t, self.rng.random()))
        self.shots = [s for s in self.shots if t - s[2] < 2.0]
        out = np.zeros((N, 3))
        for x, y, t0, h in self.shots:
            front = (t - t0) * 14 * max(p["speed"], 0.2)
            same_row = np.abs(Y - y) < 0.4
            d = front - np.abs(X - x)                            # >0 behind the arrow head
            v = same_row * np.where(d >= 0, np.exp(-d / p["length"]), np.exp(d * 3))
            c = hsv(np.full(N, h if p["rainbow"] else p["hue"]), 1, np.clip(v, 0, 1))
            out = np.maximum(out, c)
        return out


class Mosaic(Effect):
    name, title = "fw_mosaic", "Разноцветная мозаика"            # firmware: Разноцветная мозаика
    params = [Param("speed", "Скорость", 0.1, 3.0, 1.0), Param("saturation", "Насыщенность", 0.0, 1.0, 1.0)]

    def reset(self):
        self.h = self.rng.random(N)
        self.target = self.rng.random(N)

    def render(self, t, dt, presses, calm):
        flip = self.rng.random(N) < dt * 0.6 * self.p["speed"]
        self.target[flip] = self.rng.random(flip.sum())
        diff = (self.target - self.h + 0.5) % 1.0 - 0.5          # shortest way around the hue circle
        self.h = (self.h + diff * (1 - np.exp(-dt * 3 * self.p["speed"]))) % 1.0
        for k in presses:
            self.target[k] = self.rng.random()
        return hsv(self.h, self.p["saturation"], 1)


class Geometry(Effect):
    name, title = "fw_geometry", "Геометрия"                     # firmware: Геометрический рисунок
    params = COMMON + [Param("shape", "Фигура", 0, 2, 1, "choice", ("Квадраты", "Ромбы", "Круги")),
                       Param("gap", "Шаг", 1.0, 6.0, 3.0)]

    def render(self, t, dt, presses, calm):
        p = self.p
        dx, dy = np.abs(X - CX), np.abs(Y - CY) * 1.6
        d = [np.maximum(dx, dy), dx + dy, np.hypot(dx, dy)][int(p["shape"])]
        ph = d / p["gap"] - t * 0.6 * p["speed"]
        band = (0.5 + 0.5 * np.cos(ph * 2 * np.pi)) ** 3
        return colour(p, np.floor(ph) * 0.13, band)


class RainbowFall(Effect):
    name, title = "fw_rainfall", "Радужный водопад"                # firmware: Радужный водопад
    params = [Param("speed", "Скорость", 0.0, 3.0, 1.0), Param("width", "Ширина", 0.2, 3.0, 1.0),
              Param("up", "Снизу вверх", 0, 1, 0, "bool")]

    def render(self, t, dt, presses, calm):
        p = self.p
        u = (1 - Y / 5.2) if p["up"] else Y / 5.2
        return hsv(u / (1.2 * p["width"]) - t * 0.35 * p["speed"] + X * 0.01, 1, 1)


class Static(Effect):
    name, title = "fw_static", "Статичный цвет"                  # firmware: Статичный / Приглушённая белая
    params = [Param("hue", "Цвет", 0.0, 1.0, 0.0, "hue"), Param("saturation", "Насыщенность", 0.0, 1.0, 1.0),
              Param("level", "Яркость", 0.05, 1.0, 1.0),
              Param("rainbow", "Радуга по клавишам (приглушённая разноцветная)", 0, 1, 0, "bool")]

    def render(self, t, dt, presses, calm):
        p = self.p
        h = X / layout.W if p["rainbow"] else np.full(N, p["hue"])
        return hsv(h, p["saturation"], p["level"])
