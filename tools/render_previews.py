"""Renders the README media without a keyboard: animated GIFs of effects and a screenshot of the window.
The GIFs are drawn by the same KeyboardPreview widget the app shows, so they are previews, not photos.
  python tools/render_previews.py            README GIFs + window screenshot into docs/media
  python tools/render_previews.py --all      animated WebP of every effect into docs/media/effects
                                             (WebP is 3-5x smaller than GIF for full-board motion)
  python tools/render_previews.py storm fire only these effects (no screenshot)
Needs Pillow in addition to requirements.txt. hidapi / pycaw / PyAudioWPatch are not needed."""
import io, json, sys, threading, types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    import hid  # noqa: F401
except ImportError:                                   # the window imports the device module; no USB is used here
    sys.modules["hid"] = types.SimpleNamespace(enumerate=lambda *a: [], device=None)
threading.excepthook = lambda args: None              # overlay pollers may lack pycaw on a dev machine

import numpy as np
from PIL import Image
from PySide6.QtCore import QBuffer, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import app
from ardor import audio, settings
from ardor.effects import BY_NAME
from ardor.engine import Engine
from ardor.overlays import ALL as OVERLAYS

OUT = ROOT / "docs" / "media"
FPS, SECONDS, WARMUP = 20, 4.0, 2.0
GIFS = ["storm", "fire", "rain", "music_eq", "matrix", "aurora"]
# Effects whose look depends on the outside world get fixed parameters for the preview.
PREVIEW_PARAMS = {"weather": {"force": 1}}          # weather: a clear day instead of live data
SKIP = {"off"}
TYPING = "W A S D Space J K L Enter Q E R".split()     # fake key presses for reactive effects


class FakeAudio:
    """Synthetic 120 BPM track: kick on every beat, a slowly moving melody, hi-hats on off-beats."""

    def __init__(self):
        self.t, self.levels = 0.0, np.zeros(audio.N_BANDS)
        self.bass, self.beat, self._last = 0.0, False, -1

    def update(self, dt, sensitivity=1.0):
        self.t += dt
        beat_no, phase = divmod(self.t * 2, 1.0)
        bands = np.arange(audio.N_BANDS)
        kick = np.exp(-phase * 6) * np.exp(-bands / 2.5)
        melody = 0.85 * np.exp(-((bands - 8 - 4 * np.sin(self.t * 0.7)) / 2.5) ** 2) * (0.7 + 0.3 * np.sin(self.t * 5))
        hats = 0.7 * np.exp(-abs(phase - 0.5) * 12) * (bands > 12)
        target = np.clip((kick + melody + hats) * sensitivity, 0, 1)
        self.levels += (target - self.levels) * np.where(target > self.levels, 0.6, 0.15)
        self.beat, self._last = beat_no != self._last, beat_no
        self.bass = float(self.levels[:4].mean())
        return self.levels


def pump(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def to_pil(widget):
    buf = QBuffer()
    buf.open(QBuffer.ReadWrite)
    widget.grab().save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGB")


def render_gif(name, out_dir=OUT, fps=FPS, seconds=SECONDS, webp=False):
    audio.Audio._inst = FakeAudio()
    eff = BY_NAME[name](**PREVIEW_PARAMS.get(name, {}))
    engine = types.SimpleNamespace(frame=np.zeros((app.layout.N, 3)))
    view = app.KeyboardPreview(engine)
    view.resize(640, 204)
    rng = np.random.default_rng(7)
    dt, frames, t = 1 / fps, [], 0.0
    for i in range(int((WARMUP + seconds) * fps)):
        presses = []
        if rng.random() < dt * 1.2:                    # occasional key press, like light typing
            presses = [app.layout.slot_of(rng.choice(TYPING))]
        engine.frame = eff.render(t, dt, presses, False)
        t += dt
        if t > WARMUP:
            img = to_pil(view)
            frames.append(img if webp else img.quantize(colors=64, method=Image.Quantize.MEDIANCUT))
    path = out_dir / f"{name}.{'webp' if webp else 'gif'}"
    extra = dict(quality=55, method=6) if webp else dict(optimize=True)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, **extra)
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")


def screenshot():
    cfg = json.loads(json.dumps(settings.DEFAULTS))
    cfg["effect"] = "fire"
    Engine._connect = lambda self: setattr(self, "status", "подключено")   # preview: no hardware attached
    engine = Engine("fire", params={})
    engine.overlays = [cls(enabled=cfg["overlays"].get(cls.__name__, False)) for cls in OVERLAYS]
    engine.start()
    win = app.MainWindow(engine, cfg, app.Bridge())
    win.show()
    pump(2500)
    path = OUT / "window.png"
    to_pil(win).save(path)
    print(f"{path.relative_to(ROOT)}")
    engine.stop()
    win.quitting = True
    win.close()


def main(argv):
    qt = QApplication(sys.argv)
    qt.setStyleSheet(app.STYLE)
    OUT.mkdir(parents=True, exist_ok=True)
    if argv == ["--all"]:
        out = OUT / "effects"
        out.mkdir(exist_ok=True)
        for name in BY_NAME:
            if name not in SKIP:
                render_gif(name, out, fps=15, seconds=3.0, webp=True)
        return
    for name in argv or GIFS:
        render_gif(name)
    if not argv:
        screenshot()


if __name__ == "__main__":
    main(sys.argv[1:])
