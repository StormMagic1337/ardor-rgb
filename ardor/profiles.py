"""Per-app profiles: while a given program's window is in front, the keyboard shows that profile's effect,
brightness and calm setting, with the keys the game uses lit in fixed colours on top.

A profile is a plain dict kept in settings.json ("profiles"); Active is its parsed form for the engine.
A profile's effect has its own parameters, stored in the engine under the key "<effect>#<profile id>"."""
import re, uuid
import numpy as np
from . import layout
from .effects.base import hsv

# Ready-made key sets: (keys, hue) per colour group
PRESETS = {
    "Шутер": [("W A S D LShift LCtrl Space", 0.0),         # movement - red
              ("R E F G Q V C Tab", 0.53),                  # actions - cyan
              ("1 2 3 4 5", 0.13)],                         # weapons - amber
    "MOBA / RTS": [("Q W E R", 0.0), ("D F", 0.53), ("1 2 3 4 5 6", 0.13)],
}
GROUPS = 3
CALM_CHOICES = ("Не менять", "Включить", "Выключить")      # value = index

ALIASES = {"shift": "LShift", "ctrl": "LCtrl", "alt": "LAlt", "win": "LWin", "пробел": "Space",
           "backspace": "Bksp", "\\": "BSL", "caps lock": "Caps", "capslock": "Caps"}
_BY_LOWER = {layout.NAMES[led].lower(): k for k, led in enumerate(layout.LEDS)}


def new_profile(name="Новая игра", exe=""):
    groups = [{"keys": keys, "hue": hue} for keys, hue in PRESETS["Шутер"]]
    return {"id": uuid.uuid4().hex[:8], "name": name, "exe": exe, "enabled": True, "effect": "",
            "brightness": None, "calm": 0, "highlight": True, "dim": 0.2, "groups": groups}


def effect_key(profile):
    """Engine key of the profile's own effect instance, or None to keep the main window's effect."""
    return f"{profile['effect']}#{profile['id']}" if profile.get("effect") else None


def parse_keys(text):
    """'W A S D Shift' -> (slots, unknown names). Separators: spaces or commas."""
    slots, unknown = [], []
    for tok in re.split(r"[\s,;]+", text.strip()):
        if not tok:
            continue
        name = ALIASES.get(tok.lower(), tok).lower()
        if name in _BY_LOWER:
            slots.append(_BY_LOWER[name])
        else:
            unknown.append(tok)
    return slots, unknown


def match(profiles, exe):
    """The first enabled profile whose exe equals the foreground program's (case-insensitive)."""
    if not exe:
        return None
    for p in profiles or []:
        names = [n.strip().lower() for n in re.split(r"[,;]", p.get("exe", "")) if n.strip()]
        if p.get("enabled", True) and exe.lower() in names:
            return p
    return None


class Active:
    """What the engine needs from a matched profile."""

    def __init__(self, profile):
        self.id, self.name = profile["id"], profile["name"]
        self.effect = effect_key(profile)
        b = profile.get("brightness")
        self.brightness = None if b is None else float(b)
        self.calm = {1: True, 2: False}.get(int(profile.get("calm", 0)))
        self.mask = np.zeros(layout.N, bool)
        self.colors = np.zeros((layout.N, 3))
        self.dim = float(profile.get("dim", 0.2))
        if profile.get("highlight"):
            for g in profile.get("groups", []):
                slots, _ = parse_keys(g.get("keys", ""))
                self.mask[slots] = True
                self.colors[slots] = hsv(g.get("hue", 0.0), 1, 1)

    def apply(self, out):
        if not self.mask.any():
            return out
        out = out * self.dim
        out[self.mask] = self.colors[self.mask]
        return out
