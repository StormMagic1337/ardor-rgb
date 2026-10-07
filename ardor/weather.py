"""Current weather from Open-Meteo (free, no API key). Fetched in a background thread every 10 minutes."""
import json, threading, time, urllib.parse, urllib.request

GEO = "https://geocoding-api.open-meteo.com/v1/search?count=1&language=ru&name="
NOW = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&timezone=auto"
       "&current=temperature_2m,weather_code,is_day,wind_speed_10m,precipitation,cloud_cover")
REFRESH = 600

# WMO weather code -> our condition
def condition(code):
    if code in (95, 96, 99):
        return "storm"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if code in (45, 48):
        return "fog"
    if code == 3:
        return "overcast"
    if code in (1, 2):
        return "cloudy"
    return "clear"


NAMES = {"clear": "ясно", "cloudy": "переменная облачность", "overcast": "пасмурно", "fog": "туман",
         "rain": "дождь", "snow": "снег", "storm": "гроза"}


class Weather:
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = Weather()
        return cls._inst

    def __init__(self):
        self.city = None
        self.place = None            # (name, lat, lon)
        self.now = None              # dict from Open-Meteo "current"
        self.error = None
        self._wake = threading.Event()
        threading.Thread(target=self._loop, name="ardor-weather", daemon=True).start()

    def want(self, city):
        if city != self.city:
            self.city, self.place, self.now = city, None, None
            self._wake.set()

    def _fetch(self, url):
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.load(r)

    def _loop(self):
        while True:
            self._wake.clear()
            city = self.city
            if city:
                try:
                    if self.place is None:
                        res = self._fetch(GEO + urllib.parse.quote(city)).get("results")
                        if not res:
                            raise ValueError(f"город «{city}» не найден")
                        self.place = (res[0]["name"], res[0]["latitude"], res[0]["longitude"])
                    _, lat, lon = self.place
                    self.now = self._fetch(NOW.format(lat=lat, lon=lon))["current"]
                    self.error = None
                except Exception as e:
                    self.error = str(e)
            self._wake.wait(REFRESH if self.now else 30)

    def summary(self):
        if self.error:
            return f"погода: ошибка ({self.error})"
        if not self.now:
            return "погода: загрузка…"
        n = self.now
        return (f"{self.place[0]}: {NAMES[condition(n['weather_code'])]}, {n['temperature_2m']:+.0f} °C, "
                f"ветер {n['wind_speed_10m']:.0f} км/ч, {'день' if n['is_day'] else 'ночь'}")
