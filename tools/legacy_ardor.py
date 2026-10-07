"""Custom RGB animations for ARDOR GAMING Guardian (Telink/EVision, USB 320F:5055).

The first single-file version, kept as a minimal example of the protocol.
The LED layout here is approximate; the app uses ardor/layout.py.

Usage:  python tools/legacy_ardor.py <effect> [--fps 60] [--brightness 0-4]
Effects: wave, plasma, fire, ripple, typing, stars
Ctrl+C stops and restores the keyboard's previous lighting mode.
Close the Guardian app first, otherwise it fights for the keyboard.
"""
import argparse, colorsys, ctypes, math, random, sys, time
import hid

VID, PID, USAGE_PAGE = 0x320F, 0x5055, 0xFF1C
N_LEDS, FRAME = 128, 384
MODE_STREAM = 0xFE

# --- protocol ---------------------------------------------------------------
class Keyboard:
    def __init__(self):
        devs = [d for d in hid.enumerate(VID, PID) if d["usage_page"] == USAGE_PAGE]
        if not devs:
            sys.exit("Keyboard not found (cable 320F:5055). Is it connected by wire?")
        self.h = hid.device()
        self.h.open_path(devs[0]["path"])
        self.saved = None

    def tx(self, cmd, size=0, off=0, data=b""):
        b = [0] * 64
        b[0], b[3], b[4], b[5], b[6] = 0x04, cmd, size, off & 0xFF, off >> 8
        b[8:8 + len(data)] = data
        cs = sum(b[3:]) & 0xFFFF
        b[1], b[2] = cs & 0xFF, cs >> 8
        self.h.write(b)
        return bytes(self.h.read(64, 1000))

    def read_config(self):
        return self.tx(0x05, 0x22, 0)[8:8 + 0x22]

    def write_config(self, cfg):
        self.tx(0x01)
        self.tx(0x06, 0x22, 0, cfg)
        self.tx(0x02)

    def start_stream(self, brightness=4):
        self.saved = self.read_config()
        cfg = bytearray(self.saved)
        cfg[1], cfg[2] = MODE_STREAM, brightness
        self.write_config(bytes(cfg))

    def send(self, frame):
        for off in range(0, FRAME, 0x38):
            self.tx(0x12, min(0x38, FRAME - off), off, frame[off:off + 0x38])

    def close(self):
        if self.saved:
            self.write_config(self.saved)
        self.h.close()

# --- layout: LED index -> name, (x, y) in key units --------------------------
NAMES = ("Esc F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 Del Ins "
         "` 1 2 3 4 5 6 7 8 9 0 - = Bksp PgUp "
         "Tab Q W E R T Y U I O P [ ] \\ PgDn "
         "Caps A S D F G H J K L ; ' _ Enter _ "
         "LShift Z X C V B N M , . / RShift Up KP1 KPEnter "
         "LCtrl LWin LAlt _ _ Space _ _ _ _ RCtrl RAlt Left Down Right "
         "NumLk KP/ KP* KP- KP7 KP8 KP9 KP4 KP5 KP6 KP+ KP2 KP3 KP0 KP.").split()

def _pos():
    p = {}
    for r in range(5):
        for c in range(15):
            p[r * 15 + c] = (c + (0.5 if r else 0), r)
    p[72] = (13.5, 4)                                           # Up
    for i, x in zip((75, 76, 77, 80, 85, 86, 87, 88, 89),
                    (0, 1.25, 2.5, 6, 10, 11, 12.5, 13.5, 14.5)):
        p[i] = (x, 5)
    for i, x in zip(range(90, 94), (16, 17, 18, 19)):
        p[i] = (x, 1)
    for i, (x, y) in zip(range(94, 105), [(16, 2), (17, 2), (18, 2), (16, 3), (17, 3), (18, 3),
                                         (19, 2.5), (17, 4), (18, 4), (16.5, 5), (18, 5)]):
        p[i] = (x, y)
    p[73], p[74] = (16, 4), (19, 4.5)
    return {i: v for i, v in p.items() if i < len(NAMES) and NAMES[i] != "_"}

POS = _pos()

# Windows virtual-key codes for reactive effects
VK = {"Esc": 0x1B, "Tab": 0x09, "Caps": 0x14, "LShift": 0xA0, "RShift": 0xA1, "LCtrl": 0xA2,
      "RCtrl": 0xA3, "LAlt": 0xA4, "RAlt": 0xA5, "LWin": 0x5B, "Space": 0x20, "Enter": 0x0D,
      "Bksp": 0x08, "Del": 0x2E, "Ins": 0x2D, "PgUp": 0x21, "PgDn": 0x22, "Left": 0x25,
      "Up": 0x26, "Right": 0x27, "Down": 0x28, "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB,
      "]": 0xDD, "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
      "NumLk": 0x90, "KP/": 0x6F, "KP*": 0x6A, "KP-": 0x6D, "KP+": 0x6B, "KP.": 0x6E, "KPEnter": 0x0D}
VK.update({f"F{i}": 0x6F + i for i in range(1, 13)})
VK.update({c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})
VK.update({f"KP{i}": 0x60 + i for i in range(10)})
LED_VK = {i: VK[NAMES[i]] for i in POS if NAMES[i] in VK}
_gaks = ctypes.windll.user32.GetAsyncKeyState

def pressed_now(prev):
    """Returns LED indices whose key went down since the last call."""
    hits = []
    for i, vk in LED_VK.items():
        down = bool(_gaks(vk) & 0x8000)
        if down and not prev.get(i):
            hits.append(i)
        prev[i] = down
    return hits

def hsv(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, max(0.0, min(1.0, v)))
    return int(r * 255), int(g * 255), int(b * 255)

# --- effects: each is a generator factory yielding {led: (r,g,b)} per frame ---
def wave(t, state):
    return {i: hsv((x + y * 0.6) / 20 - t * 0.35) for i, (x, y) in POS.items()}

def plasma(t, state):
    out = {}
    for i, (x, y) in POS.items():
        v = math.sin(x * 0.45 + t) + math.sin(y * 0.8 - t * 1.3) + math.sin((x + y) * 0.3 + t * 0.7)
        out[i] = hsv(v / 6 + t * 0.05, 1, 0.75 + 0.25 * math.sin(v))
    return out

def fire(t, state):
    heat = state.setdefault("heat", {i: 0.0 for i in POS})
    for i, (x, y) in POS.items():
        target = (y / 5) ** 1.6 * random.uniform(0.6, 1.25)
        heat[i] += (target - heat[i]) * 0.25
    return {i: hsv(0.09 * h, 1, h) for i, h in heat.items()}

def ripple(t, state):
    rings = state.setdefault("rings", [])
    prev = state.setdefault("prev", {})
    for i in pressed_now(prev):
        rings.append((POS[i], t, random.random()))
    rings[:] = [r for r in rings if t - r[1] < 1.6]
    out = {}
    for i, (x, y) in POS.items():
        best, hue = 0.0, 0.0
        for (cx, cy), t0, h in rings:
            d = math.hypot(x - cx, (y - cy) * 1.1)
            front = (t - t0) * 11
            v = max(0.0, 1 - abs(d - front) / 1.3) * max(0.0, 1 - (t - t0) / 1.6)
            if v > best:
                best, hue = v, h
        out[i] = hsv(hue, 1, best) if best > 0.02 else hsv(0.6 + 0.03 * math.sin(t + x * 0.3), 1, 0.08)
    return out

def typing(t, state):
    glow = state.setdefault("glow", {})
    prev = state.setdefault("prev", {})
    for i in pressed_now(prev):
        glow[i] = (1.0, t * 0.1)
    out = {}
    for i in POS:
        v, h = glow.get(i, (0.0, 0.0))
        out[i] = hsv(h, 1 - v * 0.6, 0.05 + v) if v > 0.01 else (0, 0, 12)
        if i in glow:
            glow[i] = (v * 0.93, h)
    return out

def stars(t, state):
    s = state.setdefault("s", {})
    if random.random() < 0.35:
        s[random.choice(list(POS))] = [0.0, random.random()]
    out = {i: (0, 0, 6) for i in POS}
    for i, (ph, h) in list(s.items()):
        ph += 0.025
        if ph >= 1:
            del s[i]
            continue
        s[i][0] = ph
        out[i] = hsv(h, 0.4, math.sin(ph * math.pi))
    return out

EFFECTS = {f.__name__: f for f in (wave, plasma, fire, ripple, typing, stars)}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("effect", choices=EFFECTS)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--brightness", type=int, default=4, choices=range(5))
    a = ap.parse_args()

    kb = Keyboard()
    kb.start_stream(a.brightness)
    fx, state, t0 = EFFECTS[a.effect], {}, time.perf_counter()
    print(f"{a.effect} running, Ctrl+C to stop")
    try:
        while True:
            start = time.perf_counter()
            colors = fx(start - t0, state)
            frame = bytearray(FRAME)
            for i, (r, g, b) in colors.items():
                frame[3 * i:3 * i + 3] = bytes((r, g, b))
            kb.send(frame)
            time.sleep(max(0.0, 1 / a.fps - (time.perf_counter() - start)))
    except KeyboardInterrupt:
        pass
    finally:
        kb.close()
        print("restored previous lighting")

if __name__ == "__main__":
    main()
