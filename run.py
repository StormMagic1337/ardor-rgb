"""Console runner (until the GUI is ready).
  python run.py storm                    run an effect
  python run.py storm frequency=2 rain=0  with parameters
  python run.py storm --calm             no reaction to key presses
  python run.py fire --cpu --volume      with CPU (F-row) and volume (number row) indicators
  python run.py --list                   effects and their parameters
Ctrl+C stops and restores the keyboard's own lighting mode. Close Guardian first."""
import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from ardor.engine import Engine
from ardor.effects import ALL, BY_NAME
from ardor.overlays import CpuOverlay, VolumeOverlay


def main(argv):
    if not argv or "--list" in argv:
        for cls in ALL:
            ps = ", ".join(f"{p.name}={p.default} ({p.lo}..{p.hi})" for p in cls.params)
            print(f"{cls.name:<13} {cls.title:<20} {ps}")
        return
    name = argv[0]
    if name not in BY_NAME:
        sys.exit(f"unknown effect {name}; see --list")
    params = {k: float(v) for k, v in (a.split("=", 1) for a in argv[1:] if "=" in a)}
    eng = Engine(name, params={name: params})
    eng.calm = "--calm" in argv
    if "--cpu" in argv:
        eng.overlays.append(CpuOverlay())
    if "--volume" in argv:
        eng.overlays.append(VolumeOverlay())
    eng.start()
    print(f"{BY_NAME[name].title}: Ctrl+C to stop")
    status = None
    try:
        while True:
            if eng.status != status:
                status = eng.status
                print("keyboard:", status)
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        eng.stop()
        print("restored previous lighting")


if __name__ == "__main__":
    main(sys.argv[1:])
