# ARDOR GAMING Guardian USB protocol

[Русская версия](PROTOCOL.md) · [← README](../README.en.md)

How ARDOR RGB drives the keyboard's lighting. The protocol was reverse-engineered from USB traffic between the keyboard and the vendor app (Guardian). Everything here was verified on one model only: **ARDOR GAMING Guardian 95%, wired**. Implementation: [`ardor/device.py`](../ardor/device.py); a minimal self-contained 200-line example: [`tools/legacy_ardor.py`](../tools/legacy_ardor.py).

> Unofficial information, not affiliated with ARDOR GAMING / DNS. Use at your own risk — see the [disclaimer](../README.en.md#disclaimer).

## Device

| | |
|---|---|
| Controller | Telink / EVision |
| VID:PID | `0x320F:0x5055` |
| Interface | HID, **usage page `0xFF1C`** (vendor-defined) |
| Report size | 64 bytes both ways |
| LED slots per frame | 128 (97 used + 3 "mirror" slots) |

The keyboard exposes several HID interfaces; only the one with usage page `0xFF1C` controls the lighting:

```python
devs = [d for d in hid.enumerate(0x320F, 0x5055) if d["usage_page"] == 0xFF1C]
h = hid.device(); h.open_path(devs[0]["path"])
```

## Packet format

Every request is 64 bytes. The keyboard answers with a 64-byte report (an echo); the next packet is sent only after the answer is read.

| Byte | Meaning |
|---|---|
| 0 | `0x04`, always |
| 1 | checksum, low byte |
| 2 | checksum, high byte |
| 3 | command |
| 4 | data size in bytes |
| 5 | offset, low byte |
| 6 | offset, high byte |
| 7 | `0x00` |
| 8–63 | data (up to 56 = `0x38` bytes) |

**Checksum**: sum of bytes 3…63 modulo 65536, little-endian.

```python
def packet(cmd, size=0, off=0, data=b""):
    b = [0] * 64
    b[0], b[3], b[4], b[5], b[6] = 0x04, cmd, size, off & 0xFF, off >> 8
    b[8:8 + len(data)] = data
    cs = sum(b[3:]) & 0xFFFF
    b[1], b[2] = cs & 0xFF, cs >> 8
    return b
```

Read responses carry their data at the same offset 8.

## Commands

| Command | Purpose | Used by ARDOR RGB |
|---|---|---|
| `0x01` | begin a config write transaction | ✅ |
| `0x02` | end the transaction | ✅ |
| `0x05` | read the lighting config (`size=0x22`, `off=0`) | ✅ |
| `0x06` | write the lighting config (`size=0x22`, `off=0`) | ✅ |
| `0x07` | read the key matrix: 3 bytes per LED — `0x20`, modifier, HID usage | ❌ (used while building the LED map) |
| `0x0B` | write per-key colours of the "custom" mode (stored on the keyboard) | ❌ |
| `0x12` | send part of a frame in streaming mode (RAM only) | ✅ |

`0x07` and `0x0B` were observed in the vendor app's traffic and are listed for completeness; ARDOR RGB does not call them.

## Lighting config (34 bytes)

Read with `0x05`, written with the transaction `0x01` → `0x06` → `0x02`.

| Byte | Meaning |
|---|---|
| 1 | **mode** |
| 2 | **hardware brightness** 0…4 |
| others | mode parameters (speed, colour, …) — not decoded |

Known mode values:

| Mode | Value |
|---|---|
| `0xFE` | **streaming** — the keyboard shows frames sent with `0x12` |
| `0x14` | **off** ("off" in the vendor app's mode list) |
| `0x13` | "custom" — seen in a captured static-blue config |

ARDOR RGB never builds a config from scratch: it reads the current one, changes bytes 1–2 and writes it back. Other bytes are copied as-is, so their meaning does not matter.

Example (static blue in "custom" mode, captured from the vendor app; used as a last-resort restore value):

```
00 13 04 00 00 00 31 53 ff 08 00 00 00 00 00 00 00 00 02 00 01 00 00 00 00 00 00 00 00 00 00 00 00 00
```

## Streaming mode

```text
read_config()                      → save the original config
cfg[1] = 0xFE, cfg[2] = 4          → streaming mode, max hardware brightness
write_config(cfg)
loop:
    send_frame(384 bytes)          → 7 packets of 0x12
write_config(original)             → on exit
```

**A frame** is 384 bytes: 128 slots × RGB, one byte per channel, in LED-index order (see the map below). It is split into 56-byte chunks: command `0x12`, `size` = chunk length, `offset` = chunk offset within the frame.

| Packet | offset | size |
|---|---|---|
| 1 | 0 | 56 |
| 2 | 56 | 56 |
| … | … | … |
| 7 | 336 | 48 |

**Frames must be sent continuously.** When the stream stops, the keyboard falls back to the mode stored in its memory after a while. ARDOR RGB streams at 60 FPS, `probe.py` at 30. The exact timeout was not measured.

Hardware brightness is pinned to the maximum (4) in streaming mode; smooth brightness is done in software by scaling the frame.

### Restoring the original mode

- On start the original config is read and **saved to `%APPDATA%\ardor-rgb\hw_config.bin`**.
- If the keyboard is already in mode `0xFE` or `0x14` at start (left there by the app itself, e.g. after a crash), the config from `hw_config.bin` is used as the original; if there is no file, the static-blue fallback above.
- Before the PC sleeps the keyboard is switched to `0x14` (off) so it stays dark without a stream, and back to `0xFE` after resume. The original config is kept in memory meanwhile.

## LED map

LED index = position in the key matrix (same order as the `0x07` response). `_` = slot without a key. Indices 105…127 are unused.

| Indices | Keys |
|---|---|
| 0–14 | `0` Esc · `1` F1 · `2` F2 · `3` F3 · `4` F4 · `5` F5 · `6` F6 · `7` F7 · `8` F8 · `9` F9 · `10` F10 · `11` F11 · `12` F12 · `13` Del · `14` Ins |
| 15–29 | `15` \` · `16` 1 · `17` 2 · `18` 3 · `19` 4 · `20` 5 · `21` 6 · `22` 7 · `23` 8 · `24` 9 · `25` 0 · `26` - · `27` = · `28` Backspace · `29` PgUp |
| 30–44 | `30` Tab · `31` Q · `32` W · `33` E · `34` R · `35` T · `36` Y · `37` U · `38` I · `39` O · `40` P · `41` [ · `42` ] · `43` \\ · `44` PgDn |
| 45–59 | `45` Caps · `46` A · `47` S · `48` D · `49` F · `50` G · `51` H · `52` J · `53` K · `54` L · `55` ; · `56` ' · `57` _ · `58` Enter · `59` _ |
| 60–74 | `60` LShift · `61` Z · `62` X · `63` C · `64` V · `65` B · `66` N · `67` M · `68` , · `69` . · `70` / · `71` RShift · `72` ↑ · `73` Num1 · `74` NumEnter |
| 75–89 | `75` LCtrl · `76` Win · `77` LAlt · `78` *mirror of 13* · `79` *mirror of 14* · `80` Space · `81` *mirror of 29* · `82` _ · `83` _ · `84` Fn · `85` RCtrl · `86` _ · `87` ← · `88` ↓ · `89` → |
| 90–104 | `90` NumLock · `91` Num/ · `92` Num* · `93` Num- · `94` Num7 · `95` Num8 · `96` Num9 · `97` Num4 · `98` Num5 · `99` Num6 · `100` Num+ · `101` Num2 · `102` Num3 · `103` Num0 · `104` Num. |

### Mirror slots

On this layout three keys carry two functions: **Del/PrtSc**, **Ins/Pause**, **PgUp/Home**. Each has two LED slots and the firmware alternates between them. If the slots get different colours the key flickers, so the second slot is copied from the first before sending:

| Second slot | ← primary | Key |
|---|---|---|
| 78 | 13 | Del / PrtSc |
| 79 | 14 | Ins / Pause |
| 81 | 29 | PgUp / Home |

### How the map was verified

[`tools/probe.py`](../tools/probe.py) lights LEDs one at a time (white on a dim blue background) and asks which key lit up. Ambiguous indices (13, 14, 29, 44, 57, 59, 78, 79, 81–84 and 105–127) were checked this way. Key coordinates for effects (`ardor/layout.py`) were measured from a photo of the keyboard, in key-width units.

## Pitfalls

- **Close the vendor app.** It talks to the same interface; the two apps will fight.
- **Wired only.** Everything was verified over USB cable; wireless mode was not investigated.
- **Every packet waits for its echo.** Skipping the read desynchronises the exchange; reads use a 1 s timeout.
- **A failed write means the keyboard is gone.** `hid.write` returns −1 when the cable is pulled; the app closes the device and retries every 2 s.

## Use in other projects

The protocol description is MIT-licensed together with the code. If you add this keyboard to OpenRGB, SignalRGB or your own tool, a link back and reports about other `320F:5055` models are welcome.
