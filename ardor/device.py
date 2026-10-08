"""The active keyboard backend, chosen at startup (see devices/__init__.py)."""
from .devices import BOARD, BOARDS, DeviceNotFound

Keyboard = BOARD.Keyboard
FRAME = BOARD.FRAME
MAX_FPS = BOARD.MAX_FPS
EXIT_MODES = BOARD.EXIT_MODES
