"""USB protocol of the AULA F75 (SinoWealth, 258A:010C, wired), reconstructed from the vendor app OemDrv.

All traffic is one 520-byte HID feature report, id 6, on collection Col06 (interface 1, usage page 0xFF00):
    [0x06, cmd, page, 0, 0x01, 0, len_lo, len_hi, data...]
Reads have bit 0x80 set: send the header, then GET_FEATURE returns the same header followed by the data.
  0x84 / 0x04   read / write the 128-byte lighting config: byte 10 = effect, byte 9 = 1 in the per-key
                effect 0x15, 56 + 2*effect = brightness 0-9, 57 + 2*effect = speed << 4 | flags, 126-127 = 5A A5
  0x0A          write the 512-byte effect colour table: 7 RGB colours per effect, 21 bytes each
  0x06          write per-key colours of effect 0x15 (stored): planes R[126] G[126] B[126]
  0x08          stream a frame (RAM only): RGB per LED. Shown only while the stored effect is 0 ("off"),
                and must be re-sent continuously: a couple of seconds after the last frame the keyboard
                goes back to its stored effect
LED index = column * 6 + row.
"""
import os
import re
from pathlib import Path
import hid
from . import DeviceNotFound

ID, TITLE = "aula_f75", "AULA F75"
VID, PID, USAGE_PAGE = 0x258A, 0x010C, 0xFF00
USB_IDS = [(VID, PID)]
REPORT_ID, REPORT_LEN = 6, 520
N_LEDS = 126
FRAME = N_LEDS * 3
MAX_FPS = 30                    # the vendor app streams at ~21 fps; 25 fps was tested on the keyboard
EXIT_MODES = ("restore", "off", "static", "breathe", "snapshot")
EFFECT_OFF, EFFECT_STATIC, EFFECT_BREATHE, EFFECT_CUSTOM = 0x00, 0x01, 0x02, 0x15

_SAVED_CFG = Path(os.environ["APPDATA"]) / "ardor-rgb" / "aula_hw_config.bin"
_EXIT_CFG = _SAVED_CFG.with_name("aula_exit_config.bin")   # last effect we left the keyboard in ourselves
# static red, read from a real keyboard; used if nothing better is known
_FALLBACK_CFG = bytes.fromhex(
    "00 03 03 01 00 00 04 04 07 00 01 20 01 00 00 00 00 00 03 00 02 01 00 ff 0a 00 00 00 01 00 03 01"
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ff ff 09 40 09 47 09 47"
    "09 47 09 47 09 47 09 47 09 47 09 47 09 47 09 47 09 47 09 47 09 47 09 47 09 47 00 00 09 37 09 37"
    "09 37 07 47 07 47 07 44 07 44 07 44 07 44 07 44 07 44 07 44 04 09 04 04 04 04 04 04 04 04 5a a5")
_PALETTE = bytes.fromhex("ff0000 00ff00 0000ff ffff00 ff00ff 00ffff ffffff")   # vendor default per effect

# --- layout --------------------------------------------------------------------------------------
# name, LED, key rectangle in the vendor app's keyboard picture (pixels; Dev\kb\1\KB.ini, [KEY])
_KEYS = [
    ("Esc", 0, 30, 30, 55, 57), ("F1", 12, 107, 30, 132, 57), ("F2", 18, 144, 30, 169, 57),
    ("F3", 24, 183, 30, 208, 57), ("F4", 30, 222, 30, 247, 57), ("F5", 36, 269, 30, 294, 57),
    ("F6", 42, 305, 30, 330, 57), ("F7", 48, 343, 30, 368, 57), ("F8", 54, 388, 30, 413, 57),
    ("F9", 60, 439, 30, 464, 57), ("F10", 66, 477, 30, 502, 57), ("F11", 72, 516, 30, 541, 57),
    ("F12", 78, 555, 30, 580, 57),
    ("`", 1, 31, 81, 56, 108), ("1", 7, 70, 81, 95, 108), ("2", 13, 108, 81, 133, 108),
    ("3", 19, 147, 81, 172, 108), ("4", 25, 184, 81, 209, 108), ("5", 31, 223, 81, 248, 108),
    ("6", 37, 262, 81, 287, 108), ("7", 43, 300, 80, 325, 107), ("8", 49, 338, 81, 363, 108),
    ("9", 55, 377, 81, 402, 108), ("0", 61, 416, 81, 441, 108), ("-", 67, 453, 81, 478, 108),
    ("=", 73, 491, 81, 516, 108), ("Bksp", 79, 531, 81, 591, 108), ("Del", 85, 604, 81, 629, 108),
    ("Tab", 2, 34, 120, 78, 147), ("Q", 8, 89, 119, 114, 146), ("W", 14, 127, 119, 152, 146),
    ("E", 20, 165, 119, 190, 146), ("R", 26, 204, 119, 229, 146), ("T", 32, 242, 119, 267, 146),
    ("Y", 38, 280, 119, 305, 146), ("U", 44, 318, 119, 343, 146), ("I", 50, 356, 119, 381, 146),
    ("O", 56, 395, 119, 420, 146), ("P", 62, 433, 119, 458, 146), ("[", 68, 471, 120, 496, 147),
    ("]", 74, 509, 119, 534, 146), ("BSL", 80, 549, 119, 593, 146), ("PgUp", 86, 605, 120, 630, 147),
    ("Caps", 3, 33, 158, 85, 185), ("A", 9, 98, 158, 123, 185), ("S", 15, 136, 158, 161, 185),
    ("D", 21, 174, 158, 199, 185), ("F", 27, 213, 158, 238, 185), ("G", 33, 252, 158, 277, 185),
    ("H", 39, 290, 158, 315, 185), ("J", 45, 327, 158, 352, 185), ("K", 51, 366, 158, 391, 185),
    ("L", 57, 405, 158, 430, 185), (";", 63, 443, 158, 468, 185), ("'", 69, 481, 158, 506, 185),
    ("Enter", 81, 521, 158, 591, 185), ("PgDn", 87, 604, 159, 629, 186),
    ("LShift", 4, 33, 195, 105, 222), ("Z", 10, 116, 195, 141, 222), ("X", 16, 155, 195, 180, 222),
    ("C", 22, 193, 195, 218, 222), ("V", 28, 232, 195, 257, 222), ("B", 34, 270, 196, 295, 223),
    ("N", 40, 309, 195, 334, 222), ("M", 46, 347, 195, 372, 222), (",", 52, 384, 195, 409, 222),
    (".", 58, 424, 195, 449, 222), ("/", 64, 463, 195, 488, 222), ("RShift", 70, 502, 195, 558, 222),
    ("Up", 82, 567, 195, 592, 222), ("End", 88, 605, 195, 630, 222),
    ("LCtrl", 5, 34, 234, 69, 261), ("LWin", 11, 79, 234, 114, 261), ("LAlt", 17, 122, 235, 157, 262),
    ("Space", 35, 174, 235, 400, 262), ("Fn", 53, 414, 235, 449, 262), ("RCtrl", 59, 463, 236, 497, 263),
    ("Left", 77, 529, 234, 554, 261), ("Down", 83, 568, 234, 593, 261), ("Right", 89, 605, 234, 630, 261),
]
_UNIT, _X0, _Y0 = 38.5, 42.5, 43.5          # pixels per key; centre of Esc

NAMES = ["_"] * N_LEDS
POS, SIZE = {}, {}                          # LED -> key centre / key size, in key units
for _name, _led, _x0, _y0, _x1, _y1 in _KEYS:
    NAMES[_led] = _name
    POS[_led] = (round(((_x0 + _x1) / 2 - _X0) / _UNIT, 2), round(((_y0 + _y1) / 2 - _Y0) / _UNIT, 2))
    SIZE[_led] = (round((_x1 - _x0 + 13.5) / _UNIT, 2), 1.0)
W = max(x for x, _ in POS.values())             # 14.94
YMAX = max(y for _, y in POS.values())          # 5.34
H, CY = YMAX + 1, YMAX / 2
MIRROR = {}


# --- device --------------------------------------------------------------------------------------
def _find_path():
    for d in hid.enumerate(VID, PID):
        if d["usage_page"] == USAGE_PAGE and re.search(rb"col06", d["path"], re.I):
            return d["path"]
    return None


def _colour_table(effect, rgb):
    t = bytearray(512)
    for e in range(1, 14):
        t[21 * e:21 * e + 21] = _PALETTE
    t[21 * effect:21 * effect + 3] = rgb
    t[506:508] = b"\x5a\xa5"
    return bytes(t)


class Keyboard:
    def __init__(self):
        path = _find_path()
        if not path:
            raise DeviceNotFound("AULA F75 (258A:010C) not found - is it connected by cable?")
        self.h = hid.device()
        self.h.open_path(path)
        self.saved = None

    def _send(self, cmd, data=b"", length=None):
        n = len(data) if length is None else length
        buf = bytearray(REPORT_LEN)
        buf[0:8] = bytes((REPORT_ID, cmd, 0, 0, 0x01, 0, n & 0xFF, n >> 8))
        buf[8:8 + len(data)] = data
        if self.h.send_feature_report(bytes(buf)) < 0:
            raise OSError("HID feature write failed")

    def read_config(self):
        self._send(0x84, length=0x80)
        r = bytes(self.h.get_feature_report(REPORT_ID, REPORT_LEN))
        if len(r) < 8 + 0x80 or r[1] != 0x84 or r[8 + 126:8 + 128] != b"\x5a\xa5":
            raise OSError(f"unexpected config reply: {r[:8].hex(' ')}")
        return r[8:8 + 0x80]

    def write_config(self, cfg):
        assert len(cfg) == 0x80 and cfg[126:128] == b"\x5a\xa5"
        self._send(0x04, cfg)

    def _with_effect(self, cfg, effect):
        cfg = bytearray(cfg)
        cfg[9], cfg[10] = (1 if effect == EFFECT_CUSTOM else 0), effect
        return bytes(cfg)

    def start_stream(self, brightness=4, known=None):
        """Remembers the stored effect and switches to "off", the only effect streamed frames show over.
        known: the config to restore later, if the caller already knows it (e.g. after sleep).
        brightness is the Guardian's hardware brightness and is not used here."""
        cfg = self.read_config()
        if known is not None:
            self.saved = known
        elif cfg[10] != EFFECT_OFF and not (_EXIT_CFG.exists() and cfg == _EXIT_CFG.read_bytes()):
            self.saved = cfg
            _SAVED_CFG.parent.mkdir(parents=True, exist_ok=True)
            _SAVED_CFG.write_bytes(cfg)
        else:                              # left in off/exit effect by us earlier: use the last real one
            self.saved = _SAVED_CFG.read_bytes() if _SAVED_CFG.exists() else _FALLBACK_CFG
        self.write_config(self._with_effect(self.saved, EFFECT_OFF))

    def send(self, frame):
        self._send(0x08, bytes(frame[:FRAME]).ljust(FRAME, b"\0"))

    def lights_off(self):
        """Stored effect "off": stays dark once the stream stops (used before sleep)."""
        self.write_config(self._with_effect(self.saved or self.read_config(), EFFECT_OFF))

    def write_custom(self, frame):
        """Per-key colours of effect 0x15, stored on the keyboard. frame: RGB per LED."""
        planes = bytes(frame[3 * i + c] for c in range(3) for i in range(N_LEDS))
        self._send(0x06, planes.ljust(384, b"\0"))

    def leave(self, mode, rgb, frame):
        """Stops streaming and leaves the keyboard in a firmware effect (engine.EXIT_MODES)."""
        if mode == "restore" or not self.saved:
            self.close()
            return
        try:
            effect = {"off": EFFECT_OFF, "static": EFFECT_STATIC, "breathe": EFFECT_BREATHE,
                      "snapshot": EFFECT_CUSTOM}[mode]
            cfg = bytearray(self._with_effect(self.saved, effect))
            if effect in (EFFECT_STATIC, EFFECT_BREATHE):
                cfg[56 + 2 * effect] = 9                    # full brightness (offset verified for these two)
            cfg = bytes(cfg)
            self.write_config(cfg)
            if mode in ("static", "breathe"):
                self._send(0x0A, _colour_table(effect, rgb))
            elif mode == "snapshot":
                self.write_custom(frame)
            _EXIT_CFG.parent.mkdir(parents=True, exist_ok=True)
            _EXIT_CFG.write_bytes(cfg)
        finally:
            self.h.close()

    def close(self, restore=True):
        try:
            if restore and self.saved:
                self.write_config(self.saved)
        finally:
            self.h.close()
