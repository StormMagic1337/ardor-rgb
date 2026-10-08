# Изменения / Changelog

[README](README.md) · [README (English)](README.en.md)

## 0.3.0 — 2026-10-08

### Русский

**Новая клавиатура: AULA F75** (75%, кабель, `258A:010C`)
- Все эффекты, индикаторы и уведомления работают на AULA F75: 80 клавиш, 30 кадров в секунду.
- Протокол восстановлен по обмену фирменной программы OemDrv с клавиатурой и проверен на живой клавиатуре — [PROTOCOL_AULA.md](docs/PROTOCOL_AULA.md).
- Режимы «когда программа закрыта»: как было, выключено, статичный цвет, дыхание, снимок эффекта (радужной волны прошивки у AULA нет).
- Инструменты: `tools/aula_hidlog` — подменная `hid.dll`, записывающая обмен фирменной программы; `tools/aula_analyze_log.py` — разбор лога по шагам.

**Программа**
- **Готовый `ARDOR-RGB.exe`** в Releases — без установки Python; сборка — `tools/build_exe.bat`.
- Клавиатура определяется автоматически; если подключены обе — выбор через `"board"` в `settings.json` или переменную `ARDOR_BOARD`. Название клавиатуры — в заголовке окна и подсказке трея.
- Код клавиатур вынесен в `ardor/devices/` (протокол, раскладка, режимы выхода); эффекты больше не содержат размеров конкретной клавиатуры. На Guardian все эффекты дают те же кадры, что и раньше (проверено побайтно).

### English

**New keyboard: AULA F75** (75%, wired, `258A:010C`)
- All effects, overlays and notifications work on the AULA F75: 80 keys, 30 fps.
- Protocol reverse-engineered from the vendor app OemDrv and tested on a real keyboard — [PROTOCOL_AULA.en.md](docs/PROTOCOL_AULA.en.md).
- "When closed" modes: as before, off, static colour, breathing, effect snapshot (the AULA has no firmware rainbow wave).
- Tools: `tools/aula_hidlog`, a proxy `hid.dll` that logs the vendor app's traffic; `tools/aula_analyze_log.py` to decode the log step by step.

**App**
- **Standalone `ARDOR-RGB.exe`** in Releases — no Python needed; build with `tools/build_exe.bat`.
- The keyboard is detected automatically; with both connected, choose with `"board"` in `settings.json` or the `ARDOR_BOARD` variable. The keyboard's name is shown in the window title and tray tooltip.
- Keyboard code moved to `ardor/devices/` (protocol, layout, exit modes); effects no longer hard-code one keyboard's dimensions. On the Guardian every effect renders the same frames as before (checked byte for byte).

## 0.2.0

### Русский

**Новые эффекты (19)**
- **Погода за окном** — реальная погода в выбранном городе через [Open-Meteo](https://open-meteo.com/): дождь, снег, метель, гроза, ясное небо днём и звёзды ночью, облака, туман. Сводка погоды — в строке состояния окна.
- **Атмосфера:** Снегопад / метель (с сугробами), Звездопад, Светлячки, Прибой, Костёр, Глитч / киберпанк, Лавовая лампа.
- **Режимы прошивки, переосмысленные:** все режимы из списка Guardian переписаны как наши эффекты — 60 кадров в секунду, плавное движение и настройки, которых нет у прошивки: Цветная волна (8 направлений), Импульс, Радуга, Водоворот, Радужные круги, Радужный водопад, Из стороны в сторону, Стрела, Мозаика, Геометрия, Статичный цвет.

**Улучшения эффектов**
- **Гроза:** молнии в такт басу музыки; циклы — шторм сам нарастает и стихает (длина цикла настраивается).
- **Дыхание:** вариант «новый цвет на каждом вдохе».

**Программа**
- **Уведомления:** сообщение в Telegram или Discord — волна цвета приложения по клавиатуре; в полноэкранной игре мигает только `Esc` (минимум 4 с). Список приложений, шаблоны и цвета — в окне «Уведомления».
- **Настоящая темнота:** гасит полностью то, что в эффекте задумано чёрным; порог настраивается.
- **«Когда программа закрыта»:** прежний режим, выключено, статичный цвет, дыхание, радужная волна или снимок текущего эффекта, записанный в клавиатуру.
- В окне появились выпадающие списки и текстовые поля для параметров эффектов.

**Протокол и инструменты**
- Разобраны байты конфигурации подсветки (цвет, флаг «разноцветный») и номера режимов прошивки.
- Проверен радиоканал (донгл `320F:5088`): протокол работает, ~14 кадров в секунду; в программе пока не поддерживается.
- `tools/sniff_steps.py` — пошаговый перехват обмена Guardian для разбора новых команд.
- `tools/render_previews.py --all` — анимации всех эффектов (WebP); `tools/gen_effects_doc.py` — каталог эффектов на двух языках генерируется из кода.
- Документация: каталог эффектов на английском (`docs/EFFECTS.en.md`), обновлены протокол, архитектура и README; уточнено, что все эффекты собственные, а не взяты из прошивки.

### English

**New effects (19)**
- **Weather outside**: the real weather in a chosen city via [Open-Meteo](https://open-meteo.com/): rain, snow, blizzard, thunderstorm, clear sky by day and stars at night, clouds, fog. A weather summary is shown in the window's status bar.
- **Ambience:** Snowfall / blizzard (with drifts), Meteor shower, Fireflies, Surf, Campfire, Glitch / cyberpunk, Lava lamp.
- **Firmware modes, reimagined:** every mode from the Guardian app rewritten as our own effect with 60 fps, smooth motion and options the firmware lacks: Colour wave (8 directions), Colour clouds, Spectrum, Vortex, Rainbow rings, Rainbow fall, Scanner, Arrow, Mosaic, Geometry, Static colour.

**Effect improvements**
- **Storm:** lightning on the bass of the music; cycles in which the storm builds up and calms down on its own (adjustable length).
- **Breathing:** optional new colour on every breath.

**App**
- **Notifications:** a message in Telegram or Discord sends a wave of the app's colour across the keyboard; in a fullscreen game only `Esc` blinks (at least 4 s). Apps, patterns and colours are set in the "Notifications" dialog.
- **True black:** switches off completely whatever an effect means to be black; adjustable threshold.
- **"When the app is closed":** previous mode, off, static colour, breathing, rainbow wave or a snapshot of the current effect written into the keyboard.
- Drop-down lists and text fields for effect parameters in the window.

**Protocol and tools**
- Decoded lighting-config bytes (colour, multicolour flag) and the firmware mode numbers.
- Verified the radio link (dongle `320F:5088`): the protocol works at ~14 fps; not supported by the app yet.
- `tools/sniff_steps.py`: guided capture of the Guardian app's traffic for decoding new commands.
- `tools/render_previews.py --all`: animations of every effect (WebP); `tools/gen_effects_doc.py`: the bilingual effect catalogue is generated from the code.
- Docs: English effect catalogue (`docs/EFFECTS.en.md`), updated protocol, architecture and READMEs; made clear that all effects are original, not taken from the firmware.

## 0.1.0

Первая публичная версия / first public version: 15 эффектов / effects, окно и трей / window and tray, индикаторы CPU и громкости / CPU and volume overlays, горячие клавиши / hotkeys, автозапуск / autostart.
