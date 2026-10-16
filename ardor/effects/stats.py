"""Heat map of key presses: how often each key was pressed in this session, today or overall (keystats)."""
import numpy as np
from .base import Effect, Param, N
from .. import layout
from ..keystats import STATS, PERIODS

# cold -> hot: dark blue, blue, teal, yellow, orange, red
STOPS = np.array([0.0, 0.2, 0.45, 0.7, 0.85, 1.0])
COLORS = np.array([[0.00, 0.02, 0.10], [0.00, 0.12, 0.65], [0.00, 0.65, 0.55],
                   [0.95, 0.85, 0.00], [1.00, 0.40, 0.00], [1.00, 0.00, 0.00]])
NAMES = [layout.NAMES[led] for led in layout.LEDS]


def colormap(v):
    return np.stack([np.interp(v, STOPS, COLORS[:, c]) for c in range(3)], -1)


class Heatmap(Effect):
    name, title = "heatmap", "Тепловая карта нажатий"
    params = [
        Param("period", "Период", 0, 2, 1, "choice", ("Этот сеанс", "Сегодня", "Всё время")),
        Param("contrast", "Контраст редких клавиш", 0.0, 1.0, 0.5),
        Param("flash", "Вспышка при нажатии", 0, 1, 1, "bool"),
        Param("reset", "Сбросить счётчики", 0, 0, 0, "button", ("Обнулить нажатия за выбранный период?",)),
    ]

    def reset(self):
        self.target = np.zeros(N)
        self.shown = np.zeros(N)
        self.flashes = np.zeros(N)
        self.next_read = 0.0
        self.total, self.top = 0, []

    def action(self, name):
        if name == "reset":
            STATS.reset(PERIODS[int(self.p["period"])])
            self.next_read = 0.0

    def info(self):
        when = ("за сеанс", "за сегодня", "за всё время")[int(self.p["period"])]
        if not self.total:
            return f"Нажатий {when} пока нет"
        return f"Нажатий {when}: {self.total:,}".replace(",", " ") + " · чаще всего: " + ", ".join(self.top)

    def _read(self):
        counts = STATS.counts(PERIODS[int(self.p["period"])])
        c = np.array([counts.get(n, 0) for n in NAMES], float)
        self.total = int(sum(counts.values()))
        self.top = [n for n, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:3]]
        if c.max() <= 0:
            self.target = np.zeros(N)
            return
        # log scale so rarely used keys still show; contrast lifts them further
        v = np.log1p(c) / np.log1p(c.max())
        self.target = v ** (1.6 - 1.2 * self.p["contrast"])

    def render(self, t, dt, presses, calm):
        if t >= self.next_read:
            self._read()
            self.next_read = t + 0.5
        self.shown += (self.target - self.shown) * (1 - np.exp(-dt / 0.4))
        out = colormap(self.shown)
        if self.p["flash"]:
            self.flashes[presses] = 1.0
            self.flashes *= np.exp(-dt / 0.25)
            out = out + (1 - out) * self.flashes[:, None] * 0.8
        return np.clip(out, 0, 1)
