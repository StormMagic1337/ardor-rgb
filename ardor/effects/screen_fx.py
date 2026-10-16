"""Ambilight: the keyboard repeats the colours of the screen (see screen.py)."""
import numpy as np
from .base import Effect, Param, X, Y, N
from .. import layout
from ..screen import Screen, ROWS, COLS

NX, NY = X / layout.W, Y / layout.YMAX                     # key position, 0..1 across the board


def _edges():
    """Each key takes the colour of the nearest screen edge: top row - top edge, left keys - left edge..."""
    d = np.stack([NX, 1 - NX, NY, 1 - NY])
    side = d.argmin(0)
    ex, ey = NX.copy(), NY.copy()
    ex[side == 0], ex[side == 1] = 0.0, 1.0
    ey[side == 2], ey[side == 3] = 0.0, 1.0
    return ex, ey


EX, EY = _edges()


def sample(grid, nx, ny):
    """Bilinear sample of the (ROWS, COLS, 3) grid at normalised positions."""
    gx, gy = nx * (COLS - 1), ny * (ROWS - 1)
    x0, y0 = np.floor(gx).astype(int), np.floor(gy).astype(int)
    x1, y1 = np.minimum(x0 + 1, COLS - 1), np.minimum(y0 + 1, ROWS - 1)
    fx, fy = (gx - x0)[:, None], (gy - y0)[:, None]
    top = grid[y0, x0] * (1 - fx) + grid[y0, x1] * fx
    bot = grid[y1, x0] * (1 - fx) + grid[y1, x1] * fx
    return top * (1 - fy) + bot * fy


class ScreenLight(Effect):
    name, title = "screen", "Экран (Ambilight)"
    params = [
        Param("monitor", "Монитор", 0, 2, 0, "choice", ("Основной", "Второй", "Третий")),
        Param("edges", "Только края экрана", 0, 1, 0, "bool"),
        Param("saturation", "Насыщенность", 0.0, 2.5, 1.4),
        Param("gain", "Яркость", 0.3, 2.0, 1.0),
        Param("smooth", "Сглаживание", 0.0, 1.0, 0.3),
    ]

    def reset(self):
        self.screen = Screen.get()
        self.shown = np.zeros((N, 3))

    def info(self):
        return "Экран: " + self.screen.status

    def render(self, t, dt, presses, calm):
        p = self.p
        self.screen.want(p["monitor"])
        grid = self.screen.grid
        if grid is None:
            target = np.zeros((N, 3))
        else:
            c = sample(grid, EX, EY) if p["edges"] else sample(grid, NX, NY)
            gray = c.mean(1, keepdims=True)
            c = np.clip(gray + (c - gray) * p["saturation"], 0, 1)
            target = np.clip(c ** 2.0 * p["gain"], 0, 1)       # LEDs look brighter than the monitor: gamma
        tau = 0.02 + p["smooth"] * 0.5
        self.shown += (target - self.shown) * (1 - np.exp(-dt / tau))
        return np.clip(self.shown, 0, 1)
