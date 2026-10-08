"""USB protocol of the ARDOR GAMING Guardian keyboard (Telink/EVision, 320F:5055, usage page 0xFF1C).

Every packet is 64 bytes: [0x04, checksum_lo, checksum_hi, cmd, size, offset_lo, offset_hi, 0, data...],
checksum = sum of bytes 3..63. The keyboard echoes each packet back.

Commands seen from the vendor app:
  0x01 / 0x02   begin / end of a config transaction
  0x05 / 0x06   read / write the 0x22-byte lighting config (byte 1 = mode, byte 2 = brightness 0-4)
  0x07          read key matrix (3 bytes per LED: 0x20, modifier, HID usage)
  0x0B          write per-key colors of the "custom" mode (stored on the keyboard)
  0x12          stream a frame (RAM only); requires mode 0xFE and must be re-sent continuously,
                otherwise the keyboard falls back to its stored mode
"""
import os
from pathlib import Path
import hid
from . import DeviceNotFound

ID, TITLE = "guardian", "ARDOR GAMING Guardian"
VID, PID, USAGE_PAGE = 0x320F, 0x5055, 0xFF1C
USB_IDS = [(VID, PID)]
MAX_FPS = 60
EXIT_MODES = ("restore", "off", "static", "breathe", "wave", "snapshot")
_SAVED_CFG = Path(os.environ["APPDATA"]) / "ardor-rgb" / "hw_config.bin"
_EXIT_CFG = _SAVED_CFG.with_name("exit_config.bin")     # last mode we left the keyboard in ourselves
# static blue in "custom" mode, captured from the vendor app; used if nothing better is known
_FALLBACK_CFG = bytes.fromhex("00 13 04 00 00 00 31 53 ff 08 00 00 00 00 00 00 00 00 02 00 01").ljust(0x22, b"\0")
N_LEDS = 128
FRAME = N_LEDS * 3
MODE_STREAM = 0xFE
MODE_OFF = 0x14                 # "off" in the vendor app's mode list
MODE_WAVE, MODE_BREATHE, MODE_STATIC, MODE_CUSTOM = 0x01, 0x05, 0x06, 0x13
CHUNK = 0x38

# --- layout: 98% board, LED index -> key name and (x, y) position in key units, measured from a photo.
# x runs 0 (Esc) .. 18.4 (numpad right column), y runs 0 (F-row) .. 5.2 (bottom arrows).
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
W, H = 18.4, 6.2                                      # canvas size in key units
YMAX, CY = 5.2, 2.6                                   # bottom row, vertical centre

# 98% board: Del/PrtSc, Ins/Pause, PgUp/Home share a key but have two LED slots that the firmware
# alternates between. Both slots must get the same colour, otherwise the key flickers.
MIRROR = {78: 13, 79: 14, 81: 29}                     # second slot -> primary LED


# --- device --------------------------------------------------------------------------------------


class Keyboard:
    def __init__(self):
        devs = [d for d in hid.enumerate(VID, PID) if d["usage_page"] == USAGE_PAGE]
        if not devs:
            raise DeviceNotFound("ARDOR keyboard (320F:5055) not found - is it connected by cable?")
        self.h = hid.device()
        self.h.open_path(devs[0]["path"])
        self.saved = None

    def tx(self, cmd, size=0, off=0, data=b""):
        b = [0] * 64
        b[0], b[3], b[4], b[5], b[6] = 0x04, cmd, size, off & 0xFF, off >> 8
        b[8:8 + len(data)] = data
        cs = sum(b[3:]) & 0xFFFF
        b[1], b[2] = cs & 0xFF, cs >> 8
        if self.h.write(b) < 0:
            raise OSError("HID write failed")
        return bytes(self.h.read(64, 1000))

    def read_config(self):
        return self.tx(0x05, 0x22, 0)[8:8 + 0x22]

    def write_config(self, cfg):
        self.tx(0x01)
        self.tx(0x06, 0x22, 0, cfg)
        self.tx(0x02)

    def start_stream(self, brightness=4, known=None):
        """known: the mode to restore later, if the caller already knows it (e.g. after sleep)."""
        cfg = self.read_config()
        if known is not None:
            self.saved = known
        elif cfg[1] not in (MODE_STREAM, MODE_OFF) and not (_EXIT_CFG.exists() and cfg == _EXIT_CFG.read_bytes()):
            self.saved = cfg
            _SAVED_CFG.parent.mkdir(parents=True, exist_ok=True)
            _SAVED_CFG.write_bytes(cfg)
        else:                              # left in stream/off/exit mode by us earlier: use the last real mode
            self.saved = _SAVED_CFG.read_bytes() if _SAVED_CFG.exists() else _FALLBACK_CFG
        cfg = bytearray(self.saved)
        cfg[1], cfg[2] = MODE_STREAM, brightness
        self.write_config(bytes(cfg))

    def lights_off(self):
        """Hardware 'off' mode: stays dark without a running stream (used before sleep)."""
        cfg = bytearray(self.saved or self.read_config())
        cfg[1] = MODE_OFF
        self.write_config(bytes(cfg))

    def write_custom(self, frame):
        """Per-key colours of the firmware "custom" mode (0x13); stored in the keyboard."""
        for off in range(0, FRAME, CHUNK):
            self.tx(0x0B, min(CHUNK, FRAME - off), off, frame[off:off + CHUNK])

    def exit_to(self, cfg, custom_frame=None):
        """Leave the keyboard in a chosen firmware mode instead of the saved one."""
        try:
            if custom_frame is not None:
                self.write_custom(custom_frame)
            self.write_config(cfg)
            _EXIT_CFG.parent.mkdir(parents=True, exist_ok=True)
            _EXIT_CFG.write_bytes(cfg)
        finally:
            self.h.close()

    def leave(self, mode, rgb, frame):
        """Stops streaming and leaves the keyboard in a firmware mode (engine.EXIT_MODES)."""
        if mode == "restore" or not self.saved:
            self.close()
            return
        cfg = bytearray(self.saved)
        cfg[2] = 4
        custom = None
        if mode == "off":
            cfg[1] = MODE_OFF
        elif mode in ("static", "breathe"):
            cfg[1] = MODE_STATIC if mode == "static" else MODE_BREATHE
            cfg[5], cfg[6:9] = 0, rgb
        elif mode == "wave":
            cfg[1], cfg[5] = MODE_WAVE, 1
        elif mode == "snapshot":
            cfg[1] = MODE_CUSTOM
            custom = frame
        self.exit_to(bytes(cfg), custom)

    def send(self, frame):
        for off in range(0, FRAME, CHUNK):
            self.tx(0x12, min(CHUNK, FRAME - off), off, frame[off:off + CHUNK])

    def close(self, restore=True):
        try:
            if restore and self.saved:
                self.write_config(self.saved)
        finally:
            self.h.close()
