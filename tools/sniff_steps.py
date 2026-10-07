"""Guided USB sniffer for the Guardian app (run from an ADMIN PowerShell, close ARDOR RGB first).
Starts Guardian under Frida, then walks through steps; each Enter writes a marker into the log,
so every command can be matched to the setting that caused it.
  python tools\\sniff_steps.py"""
import os, sys, time, frida

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sniff_steps.log")
EXE = r"E:\Program Files\ARDOR GAMING Guardian\Guardian.exe"

STEPS = [
    "Ничего не трогай 5 секунд (фон)",
    "Открой вкладку «Прочие настройки» (или где блокировка Win) — пока ничего не меняй",
    "ВКЛЮЧИ блокировку клавиши Windows",
    "ВЫКЛЮЧИ блокировку клавиши Windows",
    "ВКЛЮЧИ переключатель W / WASD (замена WASD и стрелок), если он есть",
    "ВЫКЛЮЧИ его обратно",
    "Переключи Anti-ghosting / 6 клавиш (6KRO / NKRO) в другое положение",
    "Верни Anti-ghosting обратно",
    "Частота опроса USB: выбери 125 Гц",
    "Частота опроса: 250 Гц",
    "Частота опроса: 500 Гц",
    "Частота опроса: 1000 Гц",
    "Автоповтор: передвинь скорость повтора (Repeat Rate) в МИНИМУМ",
    "Автоповтор: скорость в МАКСИМУМ",
    "Задержка повтора: выбери самый первый вариант",
    "Задержка повтора: выбери последний вариант",
    "Верни скорость и задержку повтора как было",
    "Подсветка: выбери режим «Волна», скорость МИНИМУМ",
    "Скорость МАКСИМУМ",
    "Направление: «Слева направо»",
    "Направление: «Справа налево»",
    "Яркость подсветки в минимум, затем обратно в максимум",
    "Верни свой обычный режим подсветки",
]

JS = r"""
const hid = {};
function hex(p, n) { return Array.from(new Uint8Array(p.readByteArray(Math.min(n, 128)))).map(b => b.toString(16).padStart(2,'0')).join(' '); }
function exp(m, n) { try { return Process.getModuleByName(m).getExportByName(n); } catch (e) { return null; } }
Interceptor.attach(exp('kernelbase.dll','CreateFileW') || exp('kernel32.dll','CreateFileW'), {
  onEnter(a) { this.p = a[0].readUtf16String(); },
  onLeave(r) { if (this.p && /vid_320f/i.test(this.p) && r.toInt32() !== -1) { hid[r.toString()] = this.p; } }
});
Interceptor.attach(exp('kernelbase.dll','CloseHandle') || exp('kernel32.dll','CloseHandle'), {
  onEnter(a) { delete hid[a[0].toString()]; }
});
for (const name of ['WriteFile','ReadFile']) {
  Interceptor.attach(exp('kernelbase.dll', name) || exp('kernel32.dll', name), {
    onEnter(a) { this.h = a[0].toString(); this.b = a[1]; this.n = a[2].toInt32(); this.o = a[3]; },
    onLeave(r) {
      const path = hid[this.h]; if (!path) return;
      let n = this.n;
      if (name === 'ReadFile' && !this.o.isNull()) { const g = this.o.readU32(); if (g) n = g; }
      send({op: name[0], pid: /pid_(\w+)/i.exec(path)[1], col: (/col(\d+)/i.exec(path) || ['',''])[1], d: hex(this.b, n)});
    }
  });
}
for (const f of ['HidD_SetFeature','HidD_SetOutputReport']) {
  const p = exp('hid.dll', f);
  if (p) Interceptor.attach(p, { onEnter(a) { const path = hid[a[0].toString()] || ''; send({op: f, pid: path, col: '', d: hex(a[1], a[2].toInt32())}); } });
}
"""


def main():
    out = open(LOG, "w", encoding="utf-8")

    def on_msg(m, _):
        if m["type"] != "send":
            out.write(f"ERR {m}\n")
        else:
            p = m["payload"]
            out.write(f"{time.strftime('%H:%M:%S')} {p['op']} {p['pid']}:{p['col']} {p['d']}\n")
        out.flush()

    pid = frida.spawn([EXE])
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.on("message", on_msg)
    sc.load()
    frida.resume(pid)
    print("Guardian запущен. Делай шаги по очереди; после каждого жми Enter здесь.\n"
          "Если шага нет в программе — просто Enter.\n")
    time.sleep(4)
    for i, step in enumerate(STEPS, 1):
        out.write(f"=== STEP {i}: {step}\n")
        out.flush()
        input(f"[{i}/{len(STEPS)}] {step} ... Enter ")
        time.sleep(1.0)                      # let the app finish sending
    out.write("=== END\n")
    s.detach()
    out.close()
    print("Готово, лог:", LOG, "\nGuardian можно закрыть.")


if __name__ == "__main__":
    main()
