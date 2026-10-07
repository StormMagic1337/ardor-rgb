"""Regenerates the effect catalogue in docs/EFFECTS.md and docs/EFFECTS.en.md from the code.
Parameter tables come from each effect's Param list, so they cannot drift from the app.
Only the part between the markers is replaced; the hand-written guide below it is kept.
  python tools/gen_effects_doc.py"""
import sys, types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    import hid  # noqa: F401
except ImportError:
    sys.modules["hid"] = types.SimpleNamespace(enumerate=lambda *a: [], device=None)

from ardor.effects import BY_NAME  # noqa: E402

START, END = "<!-- effects:start -->", "<!-- effects:end -->"

GROUPS = [
    (("Погода и стихии", "Weather and elements"), ["storm", "weather", "rain", "snow", "fire", "campfire"]),
    (("Под музыку", "Music"), ["music_eq", "music_pulse"]),
    (("Атмосфера", "Ambience"), ["meteors", "fireflies", "surf", "matrix", "glitch", "aurora", "liquid", "lavalamp"]),
    (("Режимы прошивки, переосмысленные", "Firmware modes, reimagined"),
     ["fw_wave", "fw_clouds", "fw_spectrum", "fw_vortex", "fw_rings", "fw_rainfall", "fw_scanner", "fw_arrow",
      "fw_mosaic", "fw_geometry", "fw_static"]),
    (("Простые", "Simple"), ["wave", "plasma", "ripple", "typing", "stars", "fire_classic", "breathe", "off"]),
]

GROUP_NOTES = {
    "fw_wave": ("Каждый режим из списка Guardian переписан как наш эффект: 60 кадров в секунду, плавное движение "
                "и настройки, которых у прошивки нет (8 направлений, радуга или один цвет, ширина). "
                "Прошивка в этих эффектах не участвует.",
                "Every mode from the Guardian app's list, rewritten as our own effect: 60 fps, smooth motion and "
                "options the firmware lacks (8 directions, rainbow or a single colour, width). "
                "The firmware takes no part in these effects."),
    "wave": ("Тоже собственные эффекты программы, просто устроены проще. Первые шесть перенесены из первой версии "
             "([`tools/legacy_ardor.py`](../tools/legacy_ardor.py)).",
             "Also the program's own effects, just simpler. The first six come from the very first version "
             "([`tools/legacy_ardor.py`](../tools/legacy_ardor.py))."),
}

# name: (ru description, ru key press, en title, en description, en key press); "" = no reaction
TEXT = {
    "storm": (
        "Тёмные облака из фрактального шума плывут по ветру. В них вспыхивают зарницы и бьют ветвистые молнии: "
        "ломаный путь сверху вниз с боковыми ветвями, 1–3 импульса с послесвечением. Поверх идёт дождь. "
        "Молнии можно привязать к басу музыки, а шторм — заставить циклически нарастать и стихать.",
        "молния бьёт точно в нажатую клавишу",
        "Storm",
        "Dark fractal-noise clouds drift with the wind. Sheet lightning glows inside them and branching bolts strike: "
        "a jagged path with side branches, 1–3 flashes with an afterglow. Rain falls on top. Lightning can follow "
        "the bass of the music, and the storm can be set to build up and calm down in cycles.",
        "lightning strikes the pressed key"),
    "weather": (
        "Показывает реальную погоду в выбранном городе (данные [Open-Meteo](https://open-meteo.com/), без ключей, "
        "обновление раз в 10 минут): дождь, снег или метель, грозу, ясное небо (днём тёплое с солнцем, ночью звёзды "
        "и метеоры), облачность, туман. Сила дождя и снега берётся из количества осадков, ветер — с улицы. "
        "Смена погоды перетекает плавно за 3 с, сводка видна в строке состояния. "
        "«Показать» позволяет вручную выбрать любую погоду (превью снято с «Ясно»).",
        "в дождь, снег и грозу — как в этих эффектах; при ясном небе, облаках и тумане реакции нет",
        "Weather outside",
        "Shows the actual weather in a chosen city (data from [Open-Meteo](https://open-meteo.com/), no API key, "
        "refreshed every 10 minutes): rain, snow or blizzard, thunderstorm, clear sky (warm with a sun by day, "
        "stars and meteors at night), clouds, fog. Rain and snow strength follow the precipitation, wind follows the "
        "real wind. Changes blend over 3 s; a summary is shown in the status bar. "
        "\"Показать\" lets you pick any weather by hand (the preview shows \"clear\").",
        "in rain, snow and thunderstorm, the same as those effects; none for clear sky, clouds and fog"),
    "rain": (
        "Капли со шлейфами разной скорости, снос ветром, брызги от удара о нижний ряд, мерцающие «лужи».",
        "брызги от нажатой клавиши",
        "Rain",
        "Drops with trails at different speeds, blown by the wind, splashing on the bottom row; shimmering puddles.",
        "a splash from the pressed key"),
    "snow": (
        "Снежинки разной скорости покачиваются и сносятся ветром, иногда налетают порывы метели — снег густеет и "
        "летит почти горизонтально. Упавший снег копится сугробами на нижних рядах и медленно тает.",
        "из клавиши вылетает облачко снега",
        "Snowfall / blizzard",
        "Flakes sway and drift with the wind; now and then a blizzard gust makes the snow thick and nearly "
        "horizontal. Fallen snow piles up in drifts on the bottom rows and slowly melts.",
        "a puff of snow bursts from the key"),
    "fire": (
        "Алгоритм «Doom fire» на сетке 30 × 80: жар поднимается со случайным сносом и остывает, получаются "
        "отдельные языки. Палитра «чёрный → красный → оранжевый → жёлтый → белый», искры, угли внизу. "
        "Симуляция идёт 45 шагов в секунду и не зависит от FPS.",
        "вспышка жара и 6 искр из клавиши",
        "Fire",
        "The \"Doom fire\" algorithm on a 30 × 80 grid: heat rises with random drift and cools, forming separate "
        "tongues. Black → red → orange → yellow → white palette, sparks, embers at the bottom. "
        "The simulation runs at 45 steps per second regardless of FPS.",
        "a burst of heat and 6 sparks from the key"),
    "campfire": (
        "Небольшое пламя по центру нижних рядов, тёплый мерцающий отсвет на соседних клавишах и редкие искры вверх. "
        "Уютнее, чем «Огонь».",
        "костёр разгорается сильнее",
        "Campfire",
        "A small flame in the middle of the bottom rows, a warm flickering glow on nearby keys and occasional sparks "
        "drifting up. Cosier than \"Fire\".",
        "the fire flares up"),
    "music_eq": (
        "19 полос спектра системного звука, по одной на столбец клавиатуры (басы слева). Верхняя клавиша загорается "
        "плавно, белые пики падают медленнее столбиков. Работает с любым звуком из колонок или наушников.",
        "",
        "Equalizer",
        "19 spectrum bands of the system audio, one per keyboard column (bass on the left). The top key fades in "
        "smoothly; white peaks fall slower than the bars. Works with anything playing on the speakers or headphones.",
        ""),
    "music_pulse": (
        "Клавиатура дышит басом из центра; на каждый удар баса расходится кольцо и сдвигается цвет. "
        "Высокие частоты рассыпают белые искры.",
        "",
        "Bass pulse",
        "The keyboard breathes with the bass from the centre; each kick sends out a ring and shifts the colour. "
        "High frequencies scatter white sparks.",
        ""),
    "meteors": (
        "Ночное небо с мерцающими звёздами; время от времени по диагонали пролетает метеор с ярким ядром и "
        "длинным хвостом.",
        "метеор прилетает в нажатую клавишу и вспыхивает",
        "Meteor shower",
        "A night sky with twinkling stars; every now and then a meteor with a bright head and a long tail flies "
        "across diagonally.",
        "a meteor hits the pressed key with a flash"),
    "fireflies": (
        "Тёплые точки медленно летают в темноте и мерцают каждая в своём ритме.",
        "светлячки слетаются к нажатой клавише",
        "Fireflies",
        "Warm dots wander slowly in the dark, each blinking at its own pace.",
        "the fireflies gather around the pressed key"),
    "surf": (
        "Волны накатывают снизу на «песок»: вода с пенной кромкой поднимается и отступает, оставляя мокрый песок.",
        "по воде расходится всплеск",
        "Surf",
        "Waves roll in from the bottom over the \"sand\": water with a foam edge rises and retreats, leaving wet sand.",
        "a splash spreads over the water"),
    "matrix": (
        "Потоки падают по столбцам с яркой головой и затухающим мерцающим хвостом.",
        "новый поток стартует с нажатой клавиши",
        "Matrix",
        "Streams fall down the columns with a bright head and a fading, flickering tail.",
        "a new stream starts at the pressed key"),
    "glitch": (
        "Две неоновые краски переливаются со сканирующими полосами, поверх — сбои: сдвиг ряда, блок случайных "
        "цветов, перестановка каналов, короткое выключение.",
        "сбой ряда нажатой клавиши",
        "Glitch / cyberpunk",
        "Two neon colours flow with scanlines, interrupted by glitches: a shifted row, a block of random colours, "
        "swapped channels, a brief blackout.",
        "a glitch on the pressed key's row"),
    "aurora": (
        "Волнистая занавесь с вертикальными лучами медленно колышется; низ одного цвета, верх другого, вокруг "
        "редкие звёзды.",
        "сияние вспыхивает над клавишей",
        "Aurora",
        "A wavy curtain with vertical rays sways slowly; one colour at the bottom, another at the top, a few stars "
        "around.",
        "the aurora flares above the key"),
    "liquid": (
        "Медленно текущая жидкость (шум с domain warping) в палитре океана или лавы.",
        "по поверхности расходится круг",
        "Ocean / lava",
        "Slowly flowing liquid (domain-warped noise) in an ocean or a lava palette.",
        "a ring spreads over the surface"),
    "lavalamp": (
        "Капли метабол медленно поднимаются и опускаются, растягиваются и сливаются, как в настоящей лампе.",
        "со дна всплывает новая капля",
        "Lava lamp",
        "Metaball blobs slowly rise and sink, stretch and merge like in a real lamp.",
        "a new blob rises from the key"),
    "fw_wave": ("Цветная волна в любом из 8 направлений, включая «от центра» и вращение. Прошивка: «Пульсация», «Волна».",
                "", "Colour wave",
                "A colour wave in any of 8 directions, including from the centre and rotating. Firmware: wave modes.", ""),
    "fw_clouds": ("Мягкие цветные пятна плывут по клавиатуре. Прошивка: «Импульс».", "", "Colour clouds",
                  "Soft colour patches drift across the keyboard. Firmware: \"cloud\" mode.", ""),
    "fw_spectrum": ("Вся клавиатура одним цветом плавно проходит радугу. Прошивка: «Радуга».", "", "Spectrum cycle",
                    "The whole keyboard cycles through the rainbow in one colour. Firmware: spectrum mode.", ""),
    "fw_vortex": ("Радужная спираль вращается вокруг центра. Прошивка: «Водопад».", "", "Vortex",
                  "A rainbow spiral turns around the centre. Firmware: \"vortex\" mode.", ""),
    "fw_rings": ("Радужные кольца расходятся от центра или сходятся к нему. Прошивка: «Радужные переливы».", "",
                 "Rainbow rings", "Rainbow rings spread from the centre or converge to it.", ""),
    "fw_rainfall": ("Радуга стекает сверху вниз или поднимается. Прошивка: «Радужный водопад».", "", "Rainbow fall",
                    "A rainbow flows down or up. Firmware: \"rainbow waterfall\".", ""),
    "fw_scanner": ("Луч ходит из стороны в сторону с плавным разворотом и шлейфом, можно вертикально. "
                   "Прошивка: «Из стороны в сторону».", "", "Scanner",
                   "A beam sweeps side to side with eased turns and a trail, optionally vertical. "
                   "Firmware: \"side to side\".", ""),
    "fw_arrow": ("От нажатой клавиши по её ряду разлетаются стрелы с хвостами; в спокойном режиме — сами. "
                 "Прошивка: «Стрела».", "стрелы от клавиши влево и вправо", "Arrow",
                 "Arrows with tails fly along the row from the pressed key; in calm mode they start on their own. "
                 "Firmware: \"arrow\".", "arrows fly left and right from the key"),
    "fw_mosaic": ("Клавиши плавно перетекают в новые случайные цвета. Прошивка: «Разноцветная мозаика».",
                  "клавиша меняет цвет", "Mosaic",
                  "Keys blend smoothly into new random colours. Firmware: \"mosaic\".", "the key changes colour"),
    "fw_geometry": ("Квадраты, ромбы или круги расходятся от центра. Прошивка: «Геометрический рисунок».", "",
                    "Geometry", "Squares, diamonds or circles expand from the centre. Firmware: \"geometric\".", ""),
    "fw_static": ("Один цвет с насыщенностью и яркостью или приглушённая радуга по клавишам. "
                  "Прошивка: «Статичный», «Приглушённая разноцветная», «Приглушённая белая».", "", "Static colour",
                  "One colour with saturation and level, or a dimmed rainbow across the keys. "
                  "Firmware: static and dimmed modes.", ""),
    "wave": ("Радуга бежит по диагонали.", "", "Rainbow wave", "A rainbow runs diagonally.", ""),
    "plasma": ("Сумма синусоид — переливающиеся цвета.", "", "Plasma", "Sum of sines — shifting colours.", ""),
    "ripple": ("Цветные кольца от клавиш; в спокойном режиме появляются сами.", "кольцо от клавиши", "Ripples",
               "Coloured rings from keys; in calm mode they appear on their own.", "a ring from the key"),
    "typing": ("Нажатая клавиша вспыхивает и гаснет.", "вспышка клавиши", "Typing flashes",
               "The pressed key flashes and fades.", "the key flashes"),
    "stars": ("Клавиши плавно загораются и гаснут в случайном порядке.", "", "Stars",
              "Keys fade in and out at random.", ""),
    "fire_classic": ("Нижние ряды «горят» случайной яркостью.", "", "Simple fire",
                     "The bottom rows \"burn\" with random brightness.", ""),
    "breathe": ("Один цвет плавно разгорается и гаснет, можно менять цвет на каждом вдохе. Включается и на экране "
                "блокировки.", "", "Breathing",
                "One colour fades in and out, optionally a new colour on every breath. Also used on the lock screen.", ""),
    "off": ("Всё чёрное; индикаторы и уведомления при этом работают.", "", "Off",
            "All dark; indicators and notifications still work.", ""),
}

KIND = {"float": ("число", "number"), "int": ("целое", "integer"), "hue": ("цвет", "hue"),
        "bool": ("вкл/выкл", "on/off"), "choice": ("выбор", "choice"), "text": ("текст", "text")}


def num(v, lang):
    s = f"{v:g}"
    return s.replace(".", ",") if lang == 0 else s


def param_rows(cls, lang):
    rows = []
    for p in cls.params:
        kind = KIND[p.kind][lang]
        if p.kind == "choice":
            rng = " / ".join(p.options)
            default = p.options[int(p.default)]
        elif p.kind == "text":
            rng, default = "—", p.default
        elif p.kind == "bool":
            rng, default = "0 / 1", str(int(p.default))
        else:
            rng = f"{num(p.lo, lang)} … {num(p.hi, lang)}"
            default = num(p.default, lang)
        rows.append(f"| `{p.name}` | {p.title} | {kind} | {rng} | {default} |")
    return rows


def catalogue(lang):
    out = []
    head = ("| Параметр | Название в окне | Тип | Диапазон | По умолчанию |" if lang == 0 else
            "| Parameter | Label in the app (RU) | Type | Range | Default |")
    press_label = "**Нажатие:**" if lang == 0 else "**Key press:**"
    for (titles, names) in GROUPS:
        out += [f"## {titles[lang]}", ""]
        if names[0] in GROUP_NOTES:
            out += [GROUP_NOTES[names[0]][lang], ""]
        for name in names:
            cls = BY_NAME[name]
            ru_d, ru_p, en_t, en_d, en_p = TEXT[name]
            title = cls.title if lang == 0 else f"{en_t} ({cls.title})"
            out += [f"### {title} — `{name}`", ""]
            if name != "off":
                out += [f"![{cls.title}](media/effects/{name}.webp)", ""]
            out += [ru_d if lang == 0 else en_d, ""]
            press = ru_p if lang == 0 else en_p
            if press:
                out += [f"{press_label} {press}.", ""]
            if cls.params:
                out += [head, "|---|---|---|---|---|"] + param_rows(cls, lang) + [""]
    return "\n".join(out)


def write(path, lang):
    text = path.read_text(encoding="utf-8")
    a, b = text.index(START) + len(START), text.index(END)
    path.write_text(text[:a] + "\n\n" + catalogue(lang) + "\n" + text[b:], encoding="utf-8")
    print("updated", path.relative_to(ROOT))


if __name__ == "__main__":
    missing = set(BY_NAME) - {n for _, ns in GROUPS for n in ns}
    if missing:
        sys.exit(f"effects without documentation: {sorted(missing)}")
    write(ROOT / "docs" / "EFFECTS.md", 0)
    write(ROOT / "docs" / "EFFECTS.en.md", 1)
