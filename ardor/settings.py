"""Persistent settings in %APPDATA%\\ardor-rgb\\settings.json."""
import json, os
from pathlib import Path

PATH = Path(os.environ["APPDATA"]) / "ardor-rgb" / "settings.json"
DEFAULTS = {
    "board": "auto",            # "auto" (whichever is plugged in), "guardian" or "aula_f75"
    "effect": "storm",
    "brightness": 1.0,
    "calm": False,
    "game_calm": True,          # auto calm while a fullscreen app/game is in front
    "lock_breathe": True,       # slow breathing while the PC is locked
    "overlays": {"CpuOverlay": False, "VolumeOverlay": True, "NotifyOverlay": True},
    "notify_apps": None,        # None -> notifications.DEFAULT_APPS
    "params": {},               # {effect: {param: value}}
    "exit_mode": "restore",     # firmware mode left on the keyboard when the app stops (engine.EXIT_MODES)
    "exit_hue": 0.6,
    "true_black": False,        # cut near-black areas to fully off
    "black_level": 0.08,
}


def load():
    s = json.loads(json.dumps(DEFAULTS))
    try:
        s.update(json.loads(PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return s


def save(s):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(PATH)
