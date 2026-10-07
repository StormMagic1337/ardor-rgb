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

VID, PID, USAGE_PAGE = 0x320F, 0x5055, 0xFF1C
_SAVED_CFG = Path(os.environ["APPDATA"]) / "ardor-rgb" / "hw_config.bin"
# static blue in "custom" mode, captured from the vendor app; used if nothing better is known
_FALLBACK_CFG = bytes.fromhex("00 13 04 00 00 00 31 53 ff 08 00 00 00 00 00 00 00 00 02 00 01").ljust(0x22, b"\0")
N_LEDS = 128
FRAME = N_LEDS * 3
MODE_STREAM = 0xFE
MODE_OFF = 0x14                 # "off" in the vendor app's mode list
CHUNK = 0x38


class DeviceNotFound(Exception):
    pass


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
        elif cfg[1] not in (MODE_STREAM, MODE_OFF):
            self.saved = cfg
            _SAVED_CFG.parent.mkdir(parents=True, exist_ok=True)
            _SAVED_CFG.write_bytes(cfg)
        else:                              # left in stream/off mode by us earlier: use the last real mode
            self.saved = _SAVED_CFG.read_bytes() if _SAVED_CFG.exists() else _FALLBACK_CFG
        cfg = bytearray(self.saved)
        cfg[1], cfg[2] = MODE_STREAM, brightness
        self.write_config(bytes(cfg))

    def lights_off(self):
        """Hardware 'off' mode: stays dark without a running stream (used before sleep)."""
        cfg = bytearray(self.saved or self.read_config())
        cfg[1] = MODE_OFF
        self.write_config(bytes(cfg))

    def send(self, frame):
        for off in range(0, FRAME, CHUNK):
            self.tx(0x12, min(CHUNK, FRAME - off), off, frame[off:off + CHUNK])

    def close(self, restore=True):
        try:
            if restore and self.saved:
                self.write_config(self.saved)
        finally:
            self.h.close()
