"""Persistent settings in %APPDATA%\\ardor-rgb\\settings.json."""
import json, os
from pathlib import Path

PATH = Path(os.environ["APPDATA"]) / "ardor-rgb" / "settings.json"
DEFAULTS = {
    "effect": "storm",
    "brightness": 1.0,
    "calm": False,
    "game_calm": True,          # auto calm while a fullscreen app/game is in front
    "lock_breathe": True,       # slow breathing while the PC is locked
    "overlays": {"CpuOverlay": False, "VolumeOverlay": True},
    "params": {},               # {effect: {param: value}}
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
