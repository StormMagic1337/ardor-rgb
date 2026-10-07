"""Effect API. An effect renders an (N, 3) float array in 0..1, one row per key in layout.LEDS order.
Params are declared once; the GUI builds sliders from them and the CLI accepts name=value."""
from dataclasses import dataclass
import numpy as np
from .. import layout


@dataclass
class Param:
    name: str
    title: str
    lo: float
    hi: float
    default: float
    kind: str = "float"          # "float" | "int" | "hue" | "bool"


class Effect:
    name = ""
    title = ""
    params: list = []

    def __init__(self, **values):
        self.p = {pr.name: pr.default for pr in self.params}
        self.p.update({k: v for k, v in values.items() if k in self.p})
        self.rng = np.random.default_rng()
        self.reset()

    def set(self, name, value):
        self.p[name] = value

    def reset(self):
        pass

    def render(self, t, dt, presses, calm):
        """t: seconds since start, dt: frame time, presses: slots pressed this frame (empty when calm)."""
        raise NotImplementedError


def hsv(h, s, v):
    """Vectorised HSV -> RGB. h, s, v broadcast to (N,), result (N, 3)."""
    h, s, v = np.broadcast_arrays(np.asarray(h, float) % 1.0, np.asarray(s, float), np.asarray(v, float))
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.clip(np.stack([r, g, b], -1), 0, 1)


def rgb(hexstr):
    return np.array([int(hexstr[i:i + 2], 16) / 255 for i in (0, 2, 4)])


class Noise:
    """Tileable 2D value noise with fBm, evaluated at arbitrary coordinates."""

    def __init__(self, rng, size=64):
        self.g = rng.random((size, size))
        self.n = size

    def __call__(self, x, y):
        n = self.n
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = x - x0, y - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        x0, y0 = x0 % n, y0 % n
        x1, y1 = (x0 + 1) % n, (y0 + 1) % n
        g = self.g
        top = g[y0, x0] * (1 - fx) + g[y0, x1] * fx
        bot = g[y1, x0] * (1 - fx) + g[y1, x1] * fx
        return top * (1 - fy) + bot * fy

    def fbm(self, x, y, octaves=3):
        total, amp, norm = 0.0, 1.0, 0.0
        for o in range(octaves):
            total = total + amp * self(x * 2 ** o + o * 17.3, y * 2 ** o + o * 9.1)
            norm += amp
            amp *= 0.5
        return total / norm


X, Y, N = layout.X, layout.Y, layout.N
