"""Screen capture for the "Screen" effect: grabs a monitor ~30 times a second and averages it down to a small
colour grid. DXGI Desktop Duplication (dxcam) is fast and also sees borderless games; GDI (mss) is the
fallback. The capture runs only while the effect is drawn and is released 2 s after it stops being used."""
import threading, time
import numpy as np

ROWS, COLS = 12, 32
FPS = 30
IDLE = 2.0


class Screen:
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = Screen()
        return cls._inst

    def __init__(self):
        self.grid = None                 # (ROWS, COLS, 3) float 0..1, latest frame
        self.monitor = 0
        self.used = 0.0
        self.status = "захват не запущен"
        threading.Thread(target=self._loop, name="ardor-screen", daemon=True).start()

    def want(self, monitor):
        """Called by the effect every frame: keeps the capture alive on this monitor."""
        self.monitor, self.used = int(monitor), time.perf_counter()

    # --- backends -------------------------------------------------------------
    def _open(self, monitor):
        try:
            import dxcam
            try:
                cam = dxcam.create(output_idx=monitor, output_color="RGB")
            except IndexError:
                monitor = 0
                cam = dxcam.create(output_idx=0, output_color="RGB")
            return "DXGI", cam, cam.grab, cam.release, monitor
        except Exception:
            pass
        import mss
        sct = mss.mss()
        mons = sct.monitors[1:]
        if monitor >= len(mons):
            monitor = 0

        def grab():
            return np.asarray(sct.grab(mons[monitor]))[:, :, 2::-1]       # BGRA -> RGB
        return "GDI", sct, grab, sct.close, monitor

    @staticmethod
    def _pool(frame):
        f = frame[::4, ::4]
        h, w = f.shape[0] // ROWS * ROWS, f.shape[1] // COLS * COLS
        f = f[:h, :w].reshape(ROWS, h // ROWS, COLS, w // COLS, 3)
        return f.mean((1, 3), dtype=np.float32) / 255

    def _loop(self):
        cam = None
        cur = None
        while True:
            now = time.perf_counter()
            if now - self.used > IDLE:
                if cam is not None:
                    cam[3]()
                    cam = None
                    self.grid = None
                    self.status = "захват остановлен"
                time.sleep(0.2)
                continue
            try:
                if cam is None or cur != self.monitor:
                    if cam is not None:
                        cam[3]()
                    cur = self.monitor
                    cam = self._open(cur)
                    self.status = f"{cam[0]}, монитор {cam[4] + 1}"
                frame = cam[2]()
                if frame is not None:                # DXGI returns None while the screen did not change
                    self.grid = self._pool(frame)
            except Exception as e:                   # resolution change, exclusive fullscreen, no monitor...
                self.status = f"нет захвата ({type(e).__name__})"
                try:
                    if cam is not None:
                        cam[3]()
                except Exception:
                    pass
                cam = None
                time.sleep(1.0)
                continue
            time.sleep(max(0.0, 1 / FPS - (time.perf_counter() - now)))
