"""Render loop: runs the active effect, cross-fades between effects, applies overlays and brightness,
streams frames to the keyboard and reconnects if the cable is pulled."""
import ctypes, threading, time
import numpy as np
from . import layout
from .device import Keyboard, DeviceNotFound, FRAME, MAX_FPS, EXIT_MODES as _BOARD_EXIT_MODES
from .effects.base import hsv
from .effects import BY_NAME

FADE = 0.5
_EXIT_TITLES = {"restore": "Как было до запуска", "off": "Выключено", "static": "Статичный цвет",
                "breathe": "Дыхание", "wave": "Радужная волна (прошивка)", "snapshot": "Снимок текущего эффекта"}
EXIT_MODES = {k: v for k, v in _EXIT_TITLES.items() if k in _BOARD_EXIT_MODES}    # what this keyboard can do
_gaks = ctypes.windll.user32.GetAsyncKeyState


def cut_dark(out, level):
    """Keys darker than `level` go fully off; a soft knee up to 2.5x level avoids hard edges."""
    lum = out.max(1)
    k = np.clip((lum - level) / (level * 1.5), 0, 1)
    return out * (k * k * (3 - 2 * k))[:, None]


class Engine:
    def __init__(self, effect="storm", fps=60, params=None):
        self.fps = min(fps, MAX_FPS)
        self.params = params or {}          # {effect_name: {param: value}}
        self.brightness = 1.0               # software brightness 0..1
        self.enabled = True
        self.calm = False                   # manual calm (Ctrl+Alt+Home)
        self.auto_calm = False              # set while a fullscreen game runs
        self.override = None                # effect name forced by lock screen etc.
        self.profile = None                 # profiles.Active of the program in front, set by the app
        self.overlays = []
        self.status = "запуск"
        self.frame = np.zeros((layout.N, 3))   # last rendered frame, read by the preview
        self._lock = threading.Lock()
        self._effects = {}
        self._current = effect              # chosen in the window
        self._shown = effect                # actually rendered (lock screen / profile may differ)
        self._fading_from, self._fade_t0 = None, 0.0
        self._prev_keys = np.zeros(len(layout.SLOT_VK), bool)
        self._stop = threading.Event()
        self._thread = None
        self._kb = None
        self._hw_saved = None           # keyboard's own lighting config, restored on exit
        self._paused = False
        self.exit_mode = "restore"      # what the keyboard shows after we stop, see EXIT_MODES
        self.true_black = False         # switch LEDs fully off where the effect is meant to be dark
        self.black_level = 0.08
        self.exit_hue = 0.6

    # --- control (thread-safe) ------------------------------------------------
    @property
    def effect(self):
        return self._current

    def effect_obj(self, name):
        with self._lock:
            return self._get(name)

    def _get(self, key):
        """key is an effect name, or "<name>#<profile id>" for a profile's own instance with its own params."""
        if key not in self._effects:
            self._effects[key] = BY_NAME[key.split("#")[0]](**self.params.get(key, {}))
        return self._effects[key]

    def set_effect(self, name):
        with self._lock:
            self._current = name

    def step_effect(self, delta):
        names = [n for n in BY_NAME if n != "off"]
        i = names.index(self._current) if self._current in names else 0
        self.set_effect(names[(i + delta) % len(names)])

    def set_param(self, effect, name, value):
        self.params.setdefault(effect, {})[name] = value
        with self._lock:
            if effect in self._effects:
                self._effects[effect].set(name, value)

    # --- lifecycle ------------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._run, name="ardor-engine", daemon=True)
        self._thread.start()

    def pause(self):
        """Before system sleep: switch the keyboard's LEDs off and release it."""
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(2)

    def _connect(self):
        try:
            self._kb = Keyboard()
            self._kb.start_stream(4, known=self._hw_saved)
            self._hw_saved = self._kb.saved
            self.status = "подключено"
        except (DeviceNotFound, OSError) as e:
            self._kb = None
            self.status = "нет клавиатуры" if isinstance(e, DeviceNotFound) else f"ошибка: {e}"

    def _presses(self):
        down = np.array([bool(_gaks(vk) & 0x8000) for _, vk in layout.SLOT_VK])
        new = down & ~self._prev_keys
        self._prev_keys = down
        return [layout.SLOT_VK[k][0] for k in np.flatnonzero(new)]

    def _render(self, t, dt):
        prof = self.profile
        calm = self.calm or self.auto_calm
        if prof and prof.calm is not None:
            calm = prof.calm
        presses = self._presses()
        if presses:
            for ov in self.overlays:
                if hasattr(ov, "pressed"):
                    ov.pressed()
        if calm:
            presses = []
        with self._lock:
            name = self.override or (prof and prof.effect) or self._current
            if name != self._shown:
                self._fading_from, self._fade_t0, self._shown = self._shown, time.perf_counter(), name
            out = self._get(name).render(t, dt, presses, calm)
            if self._fading_from:
                a = (time.perf_counter() - self._fade_t0) / FADE
                if a >= 1:
                    self._fading_from = None
                else:
                    old = self._get(self._fading_from).render(t, dt, [], calm)
                    out = old * (1 - a) + out * a
        if self.true_black:
            out = cut_dark(out, self.black_level)
        if prof and not self.override:
            out = prof.apply(out)
        for ov in self.overlays:
            if ov.enabled or ov.busy():
                out = ov.apply(out, t, dt)
        if not self.enabled:
            out = np.zeros_like(out)
        bright = prof.brightness if prof and prof.brightness is not None else self.brightness
        return np.clip(out * bright, 0, 1)

    def _run(self):
        t0 = last = time.perf_counter()
        next_try = 0.0
        while not self._stop.is_set():
            start = time.perf_counter()
            t, dt = start - t0, min(0.1, start - last)
            last = start
            if self._paused:
                if self._kb is not None:
                    try:
                        self._kb.lights_off()
                        self._kb.close(restore=False)
                    except OSError:
                        pass
                    self._kb = None
                    self.status = "сон"
                self._stop.wait(0.2)
                continue
            if self._kb is None and start >= next_try:
                self._connect()
                next_try = start + 2
            out = self._render(t, dt)
            self.frame = out
            if self._kb is not None:
                try:
                    self._kb.send(self._to_bytes(out))
                except OSError:
                    self.status = "клавиатура отключена"
                    try:
                        self._kb.close(restore=False)
                    except OSError:
                        pass
                    self._kb = None
            self._stop.wait(max(0.0, 1 / self.fps - (time.perf_counter() - start)))
        if self._kb is not None:
            try:
                self._leave_keyboard()
            except OSError:
                pass
            self.status = "остановлено"

    def _to_bytes(self, out):
        buf = np.zeros((FRAME // 3, 3), np.uint8)
        buf[layout.LEDS] = (out * 255 + 0.5).astype(np.uint8)
        for dst, src in layout.MIRROR.items():
            buf[dst] = buf[src]
        return buf.tobytes()

    def _leave_keyboard(self):
        mode = self.exit_mode if self.exit_mode in EXIT_MODES else "restore"
        rgb = bytes((hsv(np.array([self.exit_hue]), 1, 1)[0] * 255).astype(np.uint8))
        self._kb.leave(mode, rgb, self._to_bytes(self.frame))
