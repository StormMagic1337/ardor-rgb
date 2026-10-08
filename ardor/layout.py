"""Physical layout of the active keyboard (see devices/): LED index -> key name and (x, y) position in
key units. x runs 0 (Esc) .. W, y runs 0 (F-row) .. YMAX (bottom row)."""
import numpy as np
from .devices import BOARD

NAMES = BOARD.NAMES                                   # LED index -> key name, "_" = no key / no LED
POS = BOARD.POS                                       # LED index -> (x, y)
W, H = BOARD.W, BOARD.H                               # canvas size in key units
YMAX, CY = BOARD.YMAX, BOARD.CY                       # bottom row, vertical centre
MIRROR = BOARD.MIRROR                                 # second LED slot -> primary LED (same colour)
SIZE = getattr(BOARD, "SIZE", {})                     # LED -> (w, h) of the key cap, if the board knows it
TITLE = BOARD.TITLE

LEDS = np.array(sorted(POS), dtype=int)               # LED indices that exist, in render order
X = np.array([POS[i][0] for i in LEDS])
Y = np.array([POS[i][1] for i in LEDS])
N = len(LEDS)
SLOT = {int(led): k for k, led in enumerate(LEDS)}    # LED index -> position in arrays above

# Windows virtual-key codes, used to detect presses
_VK = {"Esc": 0x1B, "Tab": 0x09, "Caps": 0x14, "LShift": 0xA0, "RShift": 0xA1, "LCtrl": 0xA2,
       "RCtrl": 0xA3, "LAlt": 0xA4, "RAlt": 0xA5, "LWin": 0x5B, "Space": 0x20, "Enter": 0x0D,
       "Bksp": 0x08, "Del": 0x2E, "Ins": 0x2D, "PgUp": 0x21, "PgDn": 0x22, "End": 0x23, "Left": 0x25,
       "Up": 0x26, "Right": 0x27, "Down": 0x28, "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB,
       "]": 0xDD, "BSL": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
       "NumLk": 0x90, "KP/": 0x6F, "KP*": 0x6A, "KP-": 0x6D, "KP+": 0x6B, "KP.": 0x6E}
_VK.update({f"F{i}": 0x6F + i for i in range(1, 13)})
_VK.update({c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})
_VK.update({f"KP{i}": 0x60 + i for i in range(10)})
SLOT_VK = [(k, _VK[NAMES[led]]) for k, led in enumerate(LEDS) if NAMES[led] in _VK]


def slot_of(name):
    return SLOT[list(NAMES).index(name)]


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
