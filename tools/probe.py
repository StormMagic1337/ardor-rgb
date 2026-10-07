"""Lights LEDs one at a time so you can see which physical key each index drives.
Close Guardian first. For each index type what lit up (key name, 'nothing', or Enter to skip).
The frame is re-sent continuously: the keyboard drops out of stream mode when frames stop.
  python tools/probe.py              probe the default candidate indices
  python tools/probe.py 13 14 78     probe only these indices"""
import json, sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ardor.device import Keyboard, FRAME

CANDIDATES = [int(a) for a in sys.argv[1:]] or [13, 14, 29, 44, 57, 59, 78, 79, 81, 82, 83, 84] + list(range(105, 128))

kb = Keyboard()
kb.start_stream(4)
current = bytearray(FRAME)
stop = threading.Event()

def pump():
    while not stop.is_set():
        kb.send(bytes(current))
        time.sleep(1 / 30)

threading.Thread(target=pump, daemon=True).start()
results = {}
try:
    for i in CANDIDATES:
        frame = bytearray(FRAME)
        for j in range(128):                      # dim blue background to tell "off" from "lit"
            frame[3 * j + 2] = 25
        frame[3 * i:3 * i + 3] = b"\xff\xff\xff"
        current[:] = frame
        results[i] = input(f"LED {i:3d} lit white -> which key? ").strip() or "?"
finally:
    stop.set()
    time.sleep(0.1)
    kb.close()
    json.dump(results, open("probe_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved probe_result.json")
