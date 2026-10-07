"""'Weather outside': shows the current weather of a city using the matching effect."""
import numpy as np
from .base import Effect, Param, Noise, hsv, X, Y, N
from .storm import Storm
from .rain import Rain
from .atmos import Snow, Meteors
from ..weather import Weather, condition

CONDITIONS = ("Авто (как на улице)", "Ясно", "Переменная облачность", "Пасмурно", "Туман", "Дождь", "Снег", "Гроза")
_KEYS = (None, "clear", "cloudy", "overcast", "fog", "rain", "snow", "storm")
FADE = 3.0


class WeatherOutside(Effect):
    name, title = "weather", "Погода за окном"
    params = [
        Param("city", "Город", 0, 0, "Новосибирск", "text"),
        Param("force", "Показать", 0, 7, 0, "choice", CONDITIONS),
        Param("night", "Ночь (если показ не авто)", 0, 1, 0, "bool"),
    ]

    def reset(self):
        self.src = Weather.get()
        self.noise = Noise(self.rng)
        self.sub = {}
        self.cur, self.prev, self.t_change = None, None, 0.0

    def info(self):
        return self.src.summary()

    def _state(self):
        """(condition, is_day, wind km/h, precipitation mm, cloud %)"""
        forced = _KEYS[int(self.p["force"])]
        n = self.src.now
        if forced:
            return forced, not self.p["night"], 12.0, 2.0, 80.0
        if not n:
            return "overcast", True, 5.0, 0.0, 80.0
        return condition(n["weather_code"]), bool(n["is_day"]), n["wind_speed_10m"], n["precipitation"], n["cloud_cover"]

    def _layer(self, cond, day, wind, precip, clouds, t, dt, presses, calm):
        w = np.clip(wind / 15, 0, 3)                         # km/h -> our wind units
        if cond == "storm":
            fx = self._sub("storm", Storm)
            fx.p.update(rain=0.8, wind=w, frequency=1.5)
            return fx.render(t, dt, presses, calm)
        if cond == "rain":
            fx = self._sub("rain", Rain)
            fx.p.update(density=float(np.clip(0.4 + precip, 0.3, 3)), wind=min(w, 2.0))
            return fx.render(t, dt, presses, calm)
        if cond == "snow":
            fx = self._sub("snow", Snow)
            fx.p.update(density=float(np.clip(0.5 + precip, 0.3, 3)), wind=min(w, 2.0),
                        blizzard=float(np.clip((wind - 20) / 25, 0, 1)))
            return fx.render(t, dt, presses, calm)
        if cond == "clear" and not day:
            fx = self._sub("night", Meteors)
            fx.p.update(frequency=0.3, stars=0.8)
            return fx.render(t, dt, presses, calm)
        return self._sky(cond, day, w, clouds, t)

    def _sub(self, key, cls):
        if key not in self.sub:
            self.sub[key] = cls()
        return self.sub[key]

    def _sky(self, cond, day, w, clouds, t):
        """Clear day, clouds, overcast, fog."""
        n = self.noise
        if cond == "fog":
            v = 0.10 + 0.08 * n.fbm(X * 0.15 + t * 0.05, Y * 0.3 + t * 0.03, 2)
            return np.stack([v, v, v * 1.1], -1)
        if day:
            sky = hsv(0.58 - Y * 0.01, 0.75, 0.30 + 0.05 * Y)                  # blue, lighter at the bottom
            sun = np.exp(-((X - 15) ** 2 + (Y * 1.5) ** 2) / 10) * (0.85 + 0.15 * np.sin(t * 0.7))
            sky = sky + np.array([1.0, 0.75, 0.3]) * sun[:, None]
        else:
            sky = hsv(np.full(N, 0.65), 0.8, np.full(N, 0.03))
        if cond == "clear":
            return np.clip(sky, 0, 1)
        cover = 0.5 if cond == "cloudy" else 0.95
        c = n.fbm(X * 0.2 - t * 0.12 * (0.3 + w), Y * 0.4 + t * 0.02, 3)
        c = np.clip((c - (1 - cover) * 0.8) * 2.2, 0, 1) * (0.5 + 0.5 * clouds / 100)
        grey = np.array([0.35, 0.37, 0.42]) if day else np.array([0.06, 0.065, 0.09])
        return np.clip(sky * (1 - c)[:, None] + grey * c[:, None], 0, 1)

    def render(self, t, dt, presses, calm):
        self.src.want(str(self.p["city"]).strip() or "Новосибирск")
        cond, day, wind, precip, clouds = self._state()
        key = (cond, day)
        if key != self.cur:
            self.prev, self.cur, self.t_change = self.cur, key, t
        out = self._layer(cond, day, wind, precip, clouds, t, dt, presses, calm)
        a = (t - self.t_change) / FADE
        if self.prev and a < 1:
            old = self._layer(self.prev[0], self.prev[1], wind, precip, clouds, t, dt, [], calm)
            out = old * (1 - a) + out * a
        return out
