# AULA F75 USB protocol

[Русская версия](PROTOCOL_AULA.md) · [Guardian protocol](PROTOCOL.en.md) · [← README](../README.en.md)

How ARDOR RGB drives the lighting of the **AULA F75** (75%, wired). Reconstructed from a log of the vendor app OemDrv.exe talking to the keyboard, captured with a proxy `hid.dll` ([`tools/aula_hidlog`](../tools/aula_hidlog)) and decoded with [`tools/aula_analyze_log.py`](../tools/aula_analyze_log.py). Implementation: [`ardor/devices/aula_f75.py`](../ardor/devices/aula_f75.py).

> Unofficial information, not affiliated with AULA. Use at your own risk — see the [disclaimer](../README.en.md#disclaimer).

## Device

| | |
|---|---|
| Controller | SinoWealth, USB name "BY Tech / Gaming Keyboard" |
| VID:PID | `0x258A:0x010C` (wired); the 2.4 GHz receiver `0x3554:0xFA09` is not supported |
| Interface | 1, collection **Col06**, usage page `0xFF00` |
| Report | **Feature, report ID 6, 520 bytes** (ID + 519), both directions |
| LEDs | 80 of 126 slots |

Of the three vendor collections (Col03 input ID 3, Col05 feature ID 5, Col06 feature ID 6) only Col06 is used. Windows exposes each collection as its own device, so open the path containing `col06`.

## Packet

`[0x06, cmd, page, 0x00, 0x01, 0x00, len_lo, len_hi, data...]`. No checksum. Bit `0x80` of `cmd` means read: send the header with no data, then `GET_FEATURE` (ID 6) returns the same header and the data from byte 8.

## Commands

| Command | Length | Purpose | Used by ARDOR RGB |
|---|---|---|---|
| `0x82` | 6 | device info (reply `03 00 00 00 00 cd`) | ❌ |
| `0x84` / `0x04` | 128 | read / write the lighting config | ✅ |
| `0x0A` | 512 | write the effect colour table | ✅ on exit to "Static colour" / "Breathing" |
| `0x06` | 384 | write per-key colours of the "custom" effect (stored) | ✅ on exit to "Effect snapshot" |
| `0x08` | 378 | **real-time frame** (RAM only) | ✅ |
| `0x03` | 512 × 3 pages | write the key map | ❌ |

**Config (128 bytes):** byte 9 = 1 in the custom effect; byte 10 = **effect** (`0x00` off, `0x01` static, `0x02` breathing, …, `0x15` custom); byte 24 = sleep time; `56 + 2·effect` = **brightness** 0–9 (verified for effects 1 and 2); `57 + 2·effect` = speed 0–4 in the high nibble, flags in the low one; bytes 126–127 = `5A A5`.

**Colour table (`0x0A`, 512 bytes):** 21 bytes (7 RGB colours) per effect, effect N at `21·N`; the first colour is the user's choice; bytes 506–507 = `5A A5`.

**Per-key colours (`0x06`, 384 bytes):** planes `R[0..125]`, `G[126..251]`, `B[252..377]`, then 6 zero bytes.

**Frame (`0x08`, 378 bytes):** RGB per slot, `[R0 G0 B0 R1 G1 B1 …]`. Tested on the keyboard: frames show **only while the stored effect is `0x00` (off)**; a couple of seconds after the last frame the keyboard returns to its stored effect, so frames are sent continuously; 25 fps is fine (OemDrv's music mode sends ~21), ARDOR RGB sends 30.

## LED indices

`LED = column · 6 + row` on a 15 × 6 grid of physical columns: Esc 0, ` 1, Tab 2, Caps 3, LShift 4, LCtrl 5, Q 8, A 9, F1 12, Space 35, Fn 53, Del 85, PgUp 86, PgDn 87, End 88, Right 89. The full list with positions is `_KEYS` in [`aula_f75.py`](../ardor/devices/aula_f75.py), taken from the `K…` entries of the vendor app's `Dev\kb\1\KB.ini`. The knob (84) has no LED.
