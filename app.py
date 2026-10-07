"""ARDOR RGB - window + tray app.
  pythonw app.py           open the window
  pythonw app.py --tray    start hidden in the tray (used by autostart)
Close Guardian before using it: both talk to the same keyboard interface."""
import sys, time
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QRectF, QAbstractNativeEventFilter
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap, QLinearGradient, QFont
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QPushButton, QSlider,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from ardor import layout, settings, winsys
from ardor.engine import Engine
from ardor.effects import ALL as EFFECTS, BY_NAME
from ardor.overlays import ALL as OVERLAYS

APP_ID = "ardor-rgb-single-instance"
HOTKEY_HELP = ("Ctrl+Alt+← / → — эффект    Ctrl+Alt+↑ / ↓ — яркость    "
               "Ctrl+Alt+End — вкл/выкл    Ctrl+Alt+Home — спокойный режим")

STYLE = """
* { font-family: 'Segoe UI'; font-size: 10pt; color: #e6e6eb; }
QMainWindow, QWidget#root { background: #15161a; }
QListWidget { background: #1d1f25; border: 1px solid #2a2d35; border-radius: 8px; padding: 4px; }
QListWidget::item { padding: 7px 10px; border-radius: 6px; }
QListWidget::item:selected { background: #c8102e; color: white; }
QListWidget::item:hover:!selected { background: #262932; }
QGroupBox { border: 1px solid #2a2d35; border-radius: 8px; margin-top: 14px; padding: 10px 8px 6px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #9aa0ad; }
QSlider::groove:horizontal { height: 4px; background: #2c2f38; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #c8102e; border-radius: 2px; }
QSlider::handle:horizontal { background: #f2f2f5; width: 14px; margin: -6px 0; border-radius: 7px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #555a66; background: #1d1f25; }
QCheckBox::indicator:checked { background: #c8102e; border-color: #c8102e; }
QPushButton { background: #262932; border: 1px solid #343843; border-radius: 6px; padding: 5px 12px; }
QPushButton:hover { background: #2f333d; }
QLabel#status { color: #9aa0ad; }
QMenu { background: #1d1f25; border: 1px solid #2a2d35; }
QMenu::item:selected { background: #c8102e; }
"""

# key sizes in key units (default 1x1)
WIDE = {"Bksp": 2.0, "Tab": 1.5, "BSL": 1.5, "Caps": 1.75, "Enter": 2.25, "LShift": 2.25, "RShift": 1.75,
        "Space": 6.0, "LCtrl": 1.25, "LWin": 1.25, "LAlt": 1.25, "RCtrl": 1.25}
TALL = {"KP+": 2.0, "KPEnter": 2.0}
LABEL = {"BSL": "\\", "LShift": "Shift", "RShift": "Shift", "LCtrl": "Ctrl", "RCtrl": "Ctrl", "LAlt": "Alt",
         "LWin": "Win", "Bksp": "⟵", "Left": "←", "Right": "→", "Up": "↑", "Down": "↓", "NumLk": "Num",
         "KPEnter": "↵", "Space": "", "PgUp": "PU", "PgDn": "PD"}


def make_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 64, 64)
    for i, c in enumerate(("#ff2a55", "#ffb000", "#29e3ff", "#9b4dff")):
        g.setColorAt(i / 3, QColor(c))
    p.setBrush(g)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 14, 56, 36, 8, 8)
    p.setBrush(QColor("#15161a"))
    for r in range(3):
        for c in range(6):
            p.drawRoundedRect(9 + c * 8, 19 + r * 9, 6, 6, 1.5, 1.5)
    p.end()
    return QIcon(pm)


class KeyboardPreview(QWidget):
    """Live copy of what the keyboard shows."""

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setMinimumSize(640, 210)
        timer = QTimer(self)
        timer.timeout.connect(self.update)
        timer.start(33)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101114"))
        unit = min((self.width() - 20) / (layout.W + 1.2), (self.height() - 20) / (layout.H + 0.2))
        ox = (self.width() - unit * (layout.W + 1)) / 2
        oy = (self.height() - unit * layout.H) / 2
        frame = self.engine.frame
        font = QFont("Segoe UI", max(6, int(unit * 0.22)))
        p.setFont(font)
        for k, led in enumerate(layout.LEDS):
            name = layout.NAMES[led]
            x, y = layout.POS[led]
            w, h = WIDE.get(name, 1.0), TALL.get(name, 1.0)
            rect = QRectF(ox + (x + 0.5 - w / 2) * unit + 2, oy + (y + 0.5 - h / 2) * unit + 2,
                          w * unit - 4, h * unit - 4)
            r, g, b = (frame[k] * 255).astype(int) if k < len(frame) else (0, 0, 0)
            p.setPen(QColor(42, 44, 52))
            p.setBrush(QColor(int(r), int(g), int(b)))
            p.drawRoundedRect(rect, unit * 0.12, unit * 0.12)
            p.setPen(QColor(255, 255, 255, 150) if r + g + b < 380 else QColor(0, 0, 0, 160))
            p.drawText(rect, Qt.AlignCenter, LABEL.get(name, name))


class ParamPanel(QGroupBox):
    """Controls built from an effect's Param list."""

    def __init__(self, engine, on_change):
        super().__init__("Настройки эффекта")
        self.engine, self.on_change = engine, on_change
        self.form = QFormLayout(self)
        self.form.setLabelAlignment(Qt.AlignLeft)

    def show_effect(self, name):
        while self.form.rowCount():
            self.form.removeRow(0)
        eff = self.engine.effect_obj(name)
        if not eff.params:
            self.form.addRow(QLabel("У этого эффекта нет настроек"))
            return
        for pr in eff.params:
            value = eff.p[pr.name]
            if pr.kind == "bool":
                w = QCheckBox()
                w.setChecked(bool(value))
                w.toggled.connect(lambda v, n=pr.name: self._set(name, n, int(v)))
            else:
                w = QSlider(Qt.Horizontal)
                steps = int(pr.hi - pr.lo) if pr.kind == "int" else 200
                w.setRange(0, steps)
                w.setValue(round((value - pr.lo) / (pr.hi - pr.lo) * steps))
                if pr.kind == "hue":
                    stops = ", ".join(f"stop:{i / 6:.3f} hsv({int(i * 60) % 360}, 255, 230)" for i in range(7))
                    w.setStyleSheet("QSlider::groove:horizontal { height: 8px; border-radius: 4px; "
                                    f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {stops}); }}"
                                    "QSlider::sub-page:horizontal { background: transparent; }")
                w.valueChanged.connect(lambda v, n=pr.name, lo=pr.lo, hi=pr.hi, s=steps:
                                       self._set(name, n, lo + (hi - lo) * v / s))
            self.form.addRow(pr.title, w)
        reset = QPushButton("Сбросить")
        reset.clicked.connect(lambda: self._reset(name))
        self.form.addRow("", reset)

    def _set(self, effect, param, value):
        self.engine.set_param(effect, param, value)
        self.on_change()

    def _reset(self, effect):
        for pr in BY_NAME[effect].params:
            self.engine.set_param(effect, pr.name, pr.default)
        self.on_change()
        self.show_effect(effect)


class Bridge(QObject):
    hotkey = Signal(str)
    power = Signal(int)


class PowerFilter(QAbstractNativeEventFilter):
    """Forwards WM_POWERBROADCAST (sleep / resume) to the GUI."""
    WM_POWERBROADCAST = 0x0218

    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge

    def nativeEventFilter(self, etype, message):
        if etype == b"windows_generic_MSG":
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == self.WM_POWERBROADCAST:
                self.bridge.power.emit(int(msg.wParam))
        return False, 0


class MainWindow(QMainWindow):
    def __init__(self, engine, cfg, bridge):
        super().__init__()
        self.engine, self.cfg = engine, cfg
        self.quitting = False
        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self._save)
        self.setWindowTitle("ARDOR RGB")
        self.setWindowIcon(make_icon())
        self.resize(1100, 640)

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)

        self.list = QListWidget()
        self.list.setFixedWidth(220)
        for cls in EFFECTS:
            it = QListWidgetItem(cls.title)
            it.setData(Qt.UserRole, cls.name)
            self.list.addItem(it)
        self.list.currentItemChanged.connect(self._pick)
        outer.addWidget(self.list)

        right = QVBoxLayout()
        outer.addLayout(right, 1)
        right.addWidget(KeyboardPreview(engine), 3)

        row = QHBoxLayout()
        right.addLayout(row, 2)
        self.params = ParamPanel(engine, self._save_later)
        row.addWidget(self.params, 3)

        glob = QGroupBox("Общие")
        g = QFormLayout(glob)
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(0, 100)
        self.bright.setValue(int(engine.brightness * 100))
        self.bright.valueChanged.connect(self._brightness)
        g.addRow("Яркость", self.bright)
        self.chk_on = self._check(g, "Подсветка включена", engine.enabled, self._toggle_on)
        self.chk_calm = self._check(g, "Спокойный режим (без реакции на нажатия)", engine.calm, self._calm)
        self._check(g, "В полноэкранных играх — спокойный режим", cfg["game_calm"],
                    lambda v: self._cfg("game_calm", v))
        self._check(g, "При блокировке ПК — медленное дыхание", cfg["lock_breathe"],
                    lambda v: self._cfg("lock_breathe", v))
        for ov in engine.overlays:
            self._check(g, ov.title, ov.enabled, lambda v, o=ov: self._overlay(o, v))
        self._check(g, "Запускать вместе с Windows (в трее)", winsys.autostart_enabled(), winsys.set_autostart)
        row.addWidget(glob, 2)

        self.status = QLabel(objectName="status")
        right.addWidget(self.status)
        help_ = QLabel(HOTKEY_HELP, objectName="status")
        help_.setWordWrap(True)
        right.addWidget(help_)

        self._select(engine.effect)
        t = QTimer(self, interval=500, timeout=self._watch)
        t.start()
        bridge.hotkey.connect(self.on_hotkey)
        bridge.power.connect(self.on_power)

    # --- helpers --------------------------------------------------------------
    def _check(self, form, text, value, slot):
        c = QCheckBox(text)
        c.setChecked(bool(value))
        c.toggled.connect(slot)
        form.addRow(c)
        return c

    def _select(self, name):
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == name:
                self.list.setCurrentRow(i)
                return

    def _pick(self, item, _prev):
        if item:
            name = item.data(Qt.UserRole)
            self.engine.set_effect(name)
            self.params.show_effect(name)
            self._save_later()

    def _brightness(self, v):
        self.engine.brightness = v / 100
        self._save_later()

    def _toggle_on(self, v):
        self.engine.enabled = v

    def _calm(self, v):
        self.engine.calm = v
        self._save_later()

    def _overlay(self, ov, v):
        ov.enabled = v
        self._save_later()

    def _cfg(self, key, v):
        self.cfg[key] = v
        self._save_later()

    def _save_later(self):
        self._save_timer.start()

    def _save(self):
        e = self.engine
        self.cfg.update(effect=e.effect, brightness=e.brightness, calm=e.calm, params=e.params,
                        overlays={type(o).__name__: o.enabled for o in e.overlays})
        settings.save(self.cfg)

    # --- system state ---------------------------------------------------------
    def _watch(self):
        e = self.engine
        locked = winsys.is_locked()
        e.override = "breathe" if locked and self.cfg["lock_breathe"] else None
        e.auto_calm = self.cfg["game_calm"] and not locked and winsys.fullscreen_app()
        mode = " · игра: спокойный режим" if e.auto_calm else (" · ПК заблокирован" if locked else "")
        self.status.setText(f"Клавиатура: {e.status}{mode}")

    def on_hotkey(self, action):
        e = self.engine
        if action in ("next", "prev"):
            e.step_effect(1 if action == "next" else -1)
            self._select(e.effect)
        elif action in ("brighter", "dimmer"):
            self.bright.setValue(max(0, min(100, self.bright.value() + (10 if action == "brighter" else -10))))
        elif action == "toggle_off":
            self.chk_on.setChecked(not e.enabled)
        elif action == "toggle_calm":
            self.chk_calm.setChecked(not e.calm)

    def on_power(self, event):
        if event == 0x4:                     # PBT_APMSUSPEND
            self.engine.pause()
        elif event in (0x7, 0x12):           # PBT_APMRESUMESUSPEND / PBT_APMRESUMEAUTOMATIC
            self.engine.resume()

    def closeEvent(self, ev):
        if self.quitting:
            ev.accept()
            return
        ev.ignore()
        self.hide()


def build_tray(app, win, engine):
    tray = QSystemTrayIcon(make_icon(), app)
    tray.setToolTip("ARDOR RGB")
    menu = QMenu()
    menu.addAction("Открыть окно", lambda: (win.showNormal(), win.activateWindow()))
    fx = menu.addMenu("Эффект")
    group = QActionGroup(fx)
    actions = {}
    for cls in EFFECTS:
        a = QAction(cls.title, fx, checkable=True)
        a.triggered.connect(lambda _=False, n=cls.name: win._select(n))
        group.addAction(a)
        fx.addAction(a)
        actions[cls.name] = a
    fx.aboutToShow.connect(lambda: actions[engine.effect].setChecked(True))
    menu.addAction("Вкл / выкл подсветку", lambda: win.on_hotkey("toggle_off"))
    menu.addAction("Спокойный режим", lambda: win.on_hotkey("toggle_calm"))
    menu.addSeparator()

    def quit_app():
        win._save()
        win.quitting = True
        engine.stop()
        tray.hide()
        app.quit()

    menu.addAction("Выход", quit_app)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda r: (win.showNormal(), win.activateWindow())
                           if r == QSystemTrayIcon.Trigger else None)
    tray.show()
    app.aboutToQuit.connect(lambda: engine.stop())
    return tray


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLE)

    probe = QLocalSocket()                       # already running? ask it to show itself
    probe.connectToServer(APP_ID)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.waitForBytesWritten(300)
        return
    QLocalServer.removeServer(APP_ID)
    server = QLocalServer()
    server.listen(APP_ID)

    cfg = settings.load()
    engine = Engine(cfg["effect"] if cfg["effect"] in BY_NAME else "storm", params=cfg["params"])
    engine.brightness, engine.calm = cfg["brightness"], cfg["calm"]
    engine.overlays = [cls(enabled=cfg["overlays"].get(cls.__name__, False)) for cls in OVERLAYS]
    engine.start()

    bridge = Bridge()
    power_filter = PowerFilter(bridge)
    app.installNativeEventFilter(power_filter)
    win = MainWindow(engine, cfg, bridge)
    tray = build_tray(app, win, engine)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), win.showNormal(), win.activateWindow()))

    failed = winsys.start_hotkeys(bridge.hotkey.emit)
    if failed:
        tray.showMessage("ARDOR RGB", "Не удалось занять горячие клавиши: " + ", ".join(failed))
    if "--tray" not in sys.argv:
        win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
