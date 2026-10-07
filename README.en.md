# ARDOR RGB

**Live lighting for the ARDOR GAMING Guardian keyboard.** A thunderstorm whose lightning strikes the key you press, the actual weather outside, fire that flares up as you type, an equalizer for any audio playing on your PC, a wave across the keys when someone writes to you in Telegram or Discord, CPU-load and volume indicators right on the keys.

[Русская версия](README.md) · [All effects](docs/EFFECTS.en.md) · [USB protocol](docs/PROTOCOL.en.md) · [Changelog](CHANGELOG.md)

> The app UI and the architecture / contributing docs are in Russian. This page, the effect catalogue, the protocol description and the changelog are in English.

| Storm | Fire | Rain |
|---|---|---|
| ![Storm](docs/media/storm.gif) | ![Fire](docs/media/fire.gif) | ![Rain](docs/media/rain.gif) |
| **Equalizer** | **Matrix** | **Aurora** |
| ![Equalizer](docs/media/music_eq.gif) | ![Matrix](docs/media/matrix.gif) | ![Aurora](docs/media/aurora.gif) |

<sub>Previews rendered by the app itself, not filmed. Key presses and music in them are synthetic. **Animations of all 34 effects are in the [effect catalogue](docs/EFFECTS.en.md).**</sub>

## What it is

The stock Guardian app only switches between the lighting modes built into the keyboard's firmware. ARDOR RGB renders every frame on the PC instead — 60 times per second — and streams it to the keyboard, so an effect can be anything: a fire simulation, procedural clouds, a reaction to sound, to key presses or to the system state.

## Features

- **34 original effects** (plus an "Off" mode), all written from scratch and rendered frame by frame by the program; none of them comes from the keyboard firmware:
  - weather and elements: Storm, Weather outside, Rain, Snowfall / blizzard, Fire, Campfire;
  - music-reactive: Equalizer, Bass Pulse;
  - ambience: Meteor shower, Fireflies, Surf, Matrix, Glitch / cyberpunk, Aurora, Ocean / Lava, Lava lamp;
  - firmware modes, reimagined: every mode from the Guardian app rewritten from scratch with 60 fps, smooth motion, 8 directions, rainbow or a single colour (Colour wave, Colour clouds, Spectrum, Vortex, Rainbow rings, Rainbow fall, Scanner, Arrow, Mosaic, Geometry, Static colour);
  - simple ones: Rainbow Wave, Plasma, Ripples, Typing Flashes, Stars, Simple Fire, Breathing.
- **Key-press reactions**: lightning strikes the pressed key, sparks fly out of it, rain splashes from it, a meteor hits it, fireflies gather around it.
- **Weather outside**: the real weather in your city ([Open-Meteo](https://open-meteo.com/), no sign-up): rain, snow, blizzard, thunderstorm, clear sky by day and stars at night, clouds, fog.
- **Storm 2.0**: lightning on the bass of the music, and a storm that builds up and calms down in cycles.
- **Notifications**: a message in Telegram or Discord sends a wave of the app's colour across the keyboard; in a fullscreen game only `Esc` blinks. Apps and colours are configurable.
- **True black**: LEDs glow even at 1–3 %; this option switches off completely whatever an effect means to be black (sky between clouds, night). The threshold is adjustable.
- **What stays on when the app is closed**: the previous mode, off, a static colour, breathing, a rainbow wave or a snapshot of the current effect written into the keyboard.
- **System audio**: music effects listen to whatever plays on the default output device (WASAPI loopback). No microphone needed.
- **Overlays on top of any effect**: CPU load on F1–F12, a volume bar on the number row that pops up when the volume changes, notifications.
- **Per-effect settings** with sliders, live keyboard preview, settings are saved.
- **Smart modes**: no key reactions while a fullscreen game is running, slow breathing on the lock screen, lights off while the PC sleeps.
- **Global hotkeys**, tray icon, start with Windows.
- **Safe exit**: the keyboard's own lighting mode (or the one you chose) is restored when the app closes. Reconnects automatically if the cable is pulled.

## Compatibility

| Keyboard | USB VID:PID | Connection | Status |
|---|---|---|---|
| ARDOR GAMING Guardian (98%) | `320F:5055` | wired | ✅ tested |
| ARDOR GAMING Guardian (98%) | `320F:5088` (dongle) | 2.4 GHz | 🔬 protocol works, not in the app yet |
| Other Telink / EVision `320F:5055` boards | `320F:5055` | wired | ❓ protocol likely the same, LED map will differ |

Windows 10 / 11 only. The app works over the cable. Over the radio the protocol was verified (about 14 full frames per second versus 60 over the cable, see the [protocol](docs/PROTOCOL.en.md#wireless-24-ghz)); support is planned. For another model, the LED map can be captured with `tools/probe.py` — see [CONTRIBUTING](docs/CONTRIBUTING.md) (in Russian) or open an issue.

## Install

Python 3.10+ (tested on 3.12):

```powershell
git clone https://github.com/StormMagic1337/ardor-rgb.git
cd ardor-rgb
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The USB package is **`hidapi`** (imported as `hid`). Do not install the unrelated `hid` package from PyPI.

## Run

**Close the Guardian app first** — both talk to the same keyboard interface.

```powershell
pythonw app.py           # window
pythonw app.py --tray    # start hidden in the tray
python run.py --list     # console runner: list effects and parameters
python run.py storm frequency=2 rain=0
```

| Hotkey | Action |
|---|---|
| `Ctrl+Alt+→` / `←` | next / previous effect |
| `Ctrl+Alt+↑` / `↓` | brightness ±10 % |
| `Ctrl+Alt+End` | lighting on / off |
| `Ctrl+Alt+Home` | calm mode (no key reactions) |

## How it works

On start the app reads the keyboard's lighting config, saves it and switches the keyboard into **streaming mode**. A render thread then computes each frame with NumPy (one vectorised expression for all keys), applies overlays and brightness, and sends it as seven 64-byte HID reports. On exit the saved config (or the chosen "when closed" mode) is written back. Nothing is flashed — see the [protocol description](docs/PROTOCOL.en.md).

Stack: Python, PySide6 (Qt 6), hidapi, NumPy, psutil, pycaw, PyAudioWPatch, WinAPI via ctypes.

Settings live in `%APPDATA%\ardor-rgb\`.

Privacy:
- **Key states** are polled only to animate the current frame; they are never stored or sent anywhere.
- **Network** is used only by the "Weather outside" effect: the city name and its coordinates go to [Open-Meteo](https://open-meteo.com/) every 10 minutes while the effect is on. The app makes no other network requests.
- **Notifications** are detected through the Windows notification database, opened read-only. Only the system name of the app is read; message text is not.

## Disclaimer

- **This is an unofficial project.** It is not affiliated with, endorsed or supported by ARDOR GAMING, DNS or the controller vendor. ARDOR GAMING, Guardian and other names are trademarks of their owners and are used only to state compatibility.
- The protocol was reverse-engineered from USB traffic between the keyboard and the vendor app for interoperability. The firmware is never read or modified.
- The app writes the lighting-mode config (command `0x06`, exactly what the vendor app does when you pick a mode) and colour frames into the keyboard's RAM (command `0x12`, lost on power-off). With the "effect snapshot" exit mode it also writes per-key colours once on exit (command `0x0B`, as the vendor app does when saving a custom mode). The original mode is restored on exit unless you chose another one.
- Provided "as is", without warranty of any kind (see [LICENSE](LICENSE)). Use at your own risk.

## Roadmap

- [ ] Standalone `.exe` (PyInstaller) in Releases — no Python needed. *Priority.*
- [ ] Video of the real keyboard.
- [ ] Radio (2.4 GHz) support: sending only the changed parts of a frame, a battery indicator.
- [ ] Keyboard settings in the window: Win lock, WASD ↔ arrows, anti-ghosting, polling rate, key repeat (commands are captured with `tools/sniff_steps.py`).
- [ ] Support for other `320F:5055` models.

## License

[MIT](LICENSE) © 2026 StormMagic1337
