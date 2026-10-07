"""Physical layout of the 98% board: LED index -> key name and (x, y) position in key units,
measured from a photo of the keyboard. x runs 0 (Esc) .. 18.4 (numpad right column),
y runs 0 (F-row) .. 5.2 (bottom arrows)."""
import numpy as np

# Order matches the keyboard's key matrix (read with command 0x07). "_" = no key / no LED.
NAMES = ("Esc F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 Del Ins "
         "` 1 2 3 4 5 6 7 8 9 0 - = Bksp PgUp "
         "Tab Q W E R T Y U I O P [ ] BSL PgDn "
         "Caps A S D F G H J K L ; ' _ Enter _ "
         "LShift Z X C V B N M , . / RShift Up KP1 KPEnter "
         "LCtrl LWin LAlt _ _ Space _ _ _ Fn RCtrl _ Left Down Right "
         "NumLk KP/ KP* KP- KP7 KP8 KP9 KP4 KP5 KP6 KP+ KP2 KP3 KP0 KP.").split()

_ROWS = [
    (0.0, "Esc F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 Del Ins PgUp PgDn",
          [0, 2, 3, 4, 5, 6.5, 7.5, 8.5, 9.5, 11, 12, 13, 14, 15.4, 16.4, 17.4, 18.4]),
    (1.0, "` 1 2 3 4 5 6 7 8 9 0 - = Bksp NumLk KP/ KP* KP-",
          [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13.4, 15.4, 16.4, 17.4, 18.4]),
    (2.0, "Tab Q W E R T Y U I O P [ ] BSL KP7 KP8 KP9",
          [0.25, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.6, 15.4, 16.4, 17.4]),
    (3.0, "Caps A S D F G H J K L ; ' Enter KP4 KP5 KP6",
          [0.35, 1.8, 2.8, 3.8, 4.8, 5.8, 6.8, 7.8, 8.8, 9.8, 10.8, 11.8, 13.3, 15.4, 16.4, 17.4]),
    (4.0, "LShift Z X C V B N M , . / RShift KP1 KP2 KP3",
          [0.7, 2.2, 3.2, 4.2, 5.2, 6.2, 7.2, 8.2, 9.2, 10.2, 11.2, 12.5, 15.4, 16.4, 17.4]),
    (5.0, "LCtrl LWin LAlt Space Fn RCtrl KP0 KP.",
          [0.15, 1.4, 2.6, 6.3, 10.0, 11.3, 16.4, 17.4]),
]
_EXTRA = {"Up": (14.2, 4.2), "Left": (13.2, 5.2), "Down": (14.2, 5.2), "Right": (15.2, 5.2),
          "KP+": (18.4, 2.5), "KPEnter": (18.4, 4.5)}


def _positions():
    by_name = dict(_EXTRA)
    for y, names, xs in _ROWS:
        for n, x in zip(names.split(), xs):
            by_name[n] = (float(x), float(y))
    return {i: by_name[n] for i, n in enumerate(NAMES) if n in by_name}


POS = _positions()
LEDS = np.array(list(POS), dtype=int)                 # LED indices that exist, in render order
X = np.array([POS[i][0] for i in LEDS])
Y = np.array([POS[i][1] for i in LEDS])
N = len(LEDS)
W, H = 18.4, 6.2                                      # canvas size in key units
SLOT = {int(led): k for k, led in enumerate(LEDS)}    # LED index -> position in arrays above

# 98% board: Del/PrtSc, Ins/Pause, PgUp/Home share a key but have two LED slots that the firmware
# alternates between. Both slots must get the same colour, otherwise the key flickers.
MIRROR = {78: 13, 79: 14, 81: 29}                     # second slot -> primary LED

# Windows virtual-key codes, used to detect presses
_VK = {"Esc": 0x1B, "Tab": 0x09, "Caps": 0x14, "LShift": 0xA0, "RShift": 0xA1, "LCtrl": 0xA2,
       "RCtrl": 0xA3, "LAlt": 0xA4, "RAlt": 0xA5, "LWin": 0x5B, "Space": 0x20, "Enter": 0x0D,
       "Bksp": 0x08, "Del": 0x2E, "Ins": 0x2D, "PgUp": 0x21, "PgDn": 0x22, "Left": 0x25,
       "Up": 0x26, "Right": 0x27, "Down": 0x28, "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB,
       "]": 0xDD, "BSL": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
       "NumLk": 0x90, "KP/": 0x6F, "KP*": 0x6A, "KP-": 0x6D, "KP+": 0x6B, "KP.": 0x6E}
_VK.update({f"F{i}": 0x6F + i for i in range(1, 13)})
_VK.update({c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})
_VK.update({f"KP{i}": 0x60 + i for i in range(10)})
SLOT_VK = [(k, _VK[NAMES[led]]) for k, led in enumerate(LEDS) if NAMES[led] in _VK]


def slot_of(name):
    return SLOT[NAMES.index(name)]


def sample(grid, x=X, y=Y):
    """Bilinear sample of a (rows, cols[, ch]) grid spanning the W x H canvas at key positions."""
    rows, cols = grid.shape[:2]
    gx = np.clip(x / W * (cols - 1), 0, cols - 1)
    gy = np.clip(y / (H - 1) * (rows - 1), 0, rows - 1)
    x0, y0 = np.floor(gx).astype(int), np.floor(gy).astype(int)
    x1, y1 = np.minimum(x0 + 1, cols - 1), np.minimum(y0 + 1, rows - 1)
    fx, fy = gx - x0, gy - y0
    if grid.ndim == 3:
        fx, fy = fx[:, None], fy[:, None]
    top = grid[y0, x0] * (1 - fx) + grid[y0, x1] * fx
    bot = grid[y1, x0] * (1 - fx) + grid[y1, x1] * fx
    return top * (1 - fy) + bot * fy
