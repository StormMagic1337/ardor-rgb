"""Supported keyboards. Each module describes one board: USB protocol (class Keyboard), physical layout
(NAMES, POS, W, H, YMAX, CY, MIRROR), FRAME size, MAX_FPS and the EXIT_MODES it can leave behind.

The board is chosen once at startup, before the effects are imported (they precompute key positions):
the ARDOR_BOARD environment variable, then the "board" setting, then whichever keyboard is plugged in.
"""
import os
import hid


class DeviceNotFound(Exception):
    pass


from . import guardian, aula_f75          # noqa: E402  (they import DeviceNotFound from here)

BOARDS = {m.ID: m for m in (guardian, aula_f75)}
DEFAULT = guardian


def detect():
    """The first supported keyboard that is connected, or None."""
    for m in BOARDS.values():
        for vid, pid in m.USB_IDS:
            try:
                if hid.enumerate(vid, pid):
                    return m
            except Exception:
                pass
    return None


def _choose():
    want = os.environ.get("ARDOR_BOARD", "").strip()
    if not want:
        from ..settings import load
        want = str(load().get("board") or "auto")
    if want in BOARDS:
        return BOARDS[want]
    return detect() or DEFAULT


BOARD = _choose()
