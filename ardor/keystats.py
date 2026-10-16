"""Key press counters for the heat map effect. Only "key name -> number of presses" is kept, locally, in
%APPDATA%\\ardor-rgb\\keystats.json: no order, no timing, nothing is sent anywhere.
Nothing is counted while the PC is locked (the password is typed there)."""
import datetime, json, threading
from . import settings

PATH = settings.PATH.with_name("keystats.json")
PERIODS = ("session", "today", "all")


class KeyStats:
    def __init__(self):
        self._lock = threading.Lock()
        self._loaded = False
        self.all, self.today, self.session = {}, {}, {}
        self.day = ""
        self._dirty = False

    def _load(self):
        if self._loaded:
            return
        self._loaded = True
        try:
            d = json.loads(PATH.read_text(encoding="utf-8"))
            self.all, self.today, self.day = dict(d.get("all", {})), dict(d.get("today", {})), d.get("day", "")
        except (OSError, ValueError):
            pass

    def _roll(self):
        day = datetime.date.today().isoformat()
        if day != self.day:
            self.day, self.today = day, {}

    def add(self, names):
        with self._lock:
            self._load()
            self._roll()
            for n in names:
                for d in (self.all, self.today, self.session):
                    d[n] = d.get(n, 0) + 1
            self._dirty = True

    def counts(self, period):
        with self._lock:
            self._load()
            self._roll()
            return dict({"session": self.session, "today": self.today, "all": self.all}[period])

    def reset(self, period):
        """Clears one period; clearing "all" clears everything."""
        with self._lock:
            self._load()
            if period == "all":
                self.all, self.today, self.session = {}, {}, {}
            elif period == "today":
                self.today = {}
            else:
                self.session = {}
            self._dirty = True
        self.save()

    def save(self):
        with self._lock:
            if not self._dirty:
                return
            data = {"all": self.all, "day": self.day, "today": self.today}
            self._dirty = False
        try:
            PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(PATH)
        except OSError:
            pass


STATS = KeyStats()
