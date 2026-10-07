"""Watches Windows toast notifications by polling the notification database (read-only) once a second.
The official UserNotificationListener API needs a packaged app; the database works for a plain script.
Every toast an app shows lands in %LOCALAPPDATA%\\Microsoft\\Windows\\Notifications\\wpndatabase.db."""
import os, re, sqlite3, threading, time

DB = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db")
DEFAULT_APPS = [
    {"name": "Telegram", "match": "telegram|unigram", "hue": 0.55},
    {"name": "Discord", "match": "discord", "hue": 0.72},
]

_QUERY = ("select n.\"Order\", h.PrimaryId from Notification n "
          "join NotificationHandler h on h.RecordId = n.HandlerId "
          "where n.\"Order\" > ? and n.Type = 'toast' order by n.\"Order\"")


class NotificationWatcher:
    def __init__(self, apps, callback):
        self.apps = apps                 # list of {"name", "match", "hue"}; may be replaced at runtime
        self.callback = callback         # callback(app_dict) on the watcher thread
        self.error = None
        self.last_app_id = None          # last seen app id (helps users write match patterns)
        threading.Thread(target=self._loop, name="ardor-notify", daemon=True).start()

    def match(self, app_id):
        for app in self.apps:
            try:
                if app["match"] and re.search(app["match"], app_id, re.I):
                    return app
            except re.error:
                continue
        return None

    def _loop(self):
        last = None
        while True:
            try:
                con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=2)
                try:
                    if last is None:         # start after whatever is already there
                        last = con.execute('select coalesce(max("Order"), 0) from Notification').fetchone()[0]
                    for order, app_id in con.execute(_QUERY, (last,)).fetchall():
                        last = max(last, order)
                        self.last_app_id = app_id
                        app = self.match(app_id)
                        if app:
                            self.callback(app)
                finally:
                    con.close()
                self.error = None
            except sqlite3.Error as e:
                self.error = str(e)
            time.sleep(1.0)
