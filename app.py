"""ARDOR RGB - window + tray app.
  pythonw app.py           open the window
  pythonw app.py --tray    start hidden in the tray (used by autostart)
Close the vendor app (Guardian, OemDrv) before using it: both talk to the same keyboard interface."""
import sys, time
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QRectF, QAbstractNativeEventFilter
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap, QLinearGradient, QFont
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QLineEdit, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSlider,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from ardor import __version__, layout, profiles, settings, winsys
from ardor.engine import Engine, EXIT_MODES
from ardor.effects import ALL as EFFECTS, BY_NAME
from ardor.overlays import ALL as OVERLAYS, NotifyOverlay
from ardor.notifications import NotificationWatcher, DEFAULT_APPS

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
QLineEdit { background: #1d1f25; border: 1px solid #343843; border-radius: 6px; padding: 4px 8px; }
QComboBox { background: #1d1f25; border: 1px solid #343843; border-radius: 6px; padding: 4px 8px; }
QComboBox QAbstractItemView { background: #1d1f25; selection-background-color: #c8102e; }
QPushButton { background: #262932; border: 1px solid #343843; border-radius: 6px; padding: 5px 12px; }
QPushButton:hover { background: #2f333d; }
QLabel#status { color: #9aa0ad; }
QMenu { background: #1d1f25; border: 1px solid #2a2d35; }
QMenu::item:selected { background: #c8102e; }
"""

_STOPS = ", ".join(f"stop:{i / 6:.3f} hsv({int(i * 60) % 360}, 255, 230)" for i in range(7))
HUE_GROOVE = ("QSlider::groove:horizontal { height: 8px; border-radius: 4px; "
              f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {_STOPS}); }}"
              "QSlider::sub-page:horizontal { background: transparent; }")

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
            w, h = layout.SIZE.get(led) or (WIDE.get(name, 1.0), TALL.get(name, 1.0))
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
            if pr.kind == "button":
                w = QPushButton(pr.title)
                w.clicked.connect(lambda _=False, n=pr.name, q=pr.options: self._action(name, n, q))
                self.form.addRow("", w)
                continue
            if pr.kind == "bool":
                w = QCheckBox()
                w.setChecked(bool(value))
                w.toggled.connect(lambda v, n=pr.name: self._set(name, n, int(v)))
            elif pr.kind == "text":
                w = QLineEdit(str(value))
                w.setMaxLength(200)
                w.textChanged.connect(lambda v, n=pr.name: self._set(name, n, v))
            elif pr.kind == "choice":
                w = QComboBox()
                w.addItems(pr.options)
                w.setCurrentIndex(int(value))
                w.currentIndexChanged.connect(lambda v, n=pr.name: self._set(name, n, v))
            else:
                w = QSlider(Qt.Horizontal)
                steps = int(pr.hi - pr.lo) if pr.kind == "int" else 200
                w.setRange(0, steps)
                w.setValue(round((value - pr.lo) / (pr.hi - pr.lo) * steps))
                if pr.kind == "hue":
                    w.setStyleSheet(HUE_GROOVE)
                w.valueChanged.connect(lambda v, n=pr.name, lo=pr.lo, hi=pr.hi, s=steps:
                                       self._set(name, n, lo + (hi - lo) * v / s))
            self.form.addRow(pr.title, w)
        reset = QPushButton("Сбросить")
        reset.clicked.connect(lambda: self._reset(name))
        self.form.addRow("", reset)

    def _set(self, effect, param, value):
        self.engine.set_param(effect, param, value)
        self.on_change()

    def _action(self, effect, param, confirm):
        if confirm and QMessageBox.question(self, "ARDOR RGB", confirm[0]) != QMessageBox.Yes:
            return
        self.engine.effect_obj(effect).action(param)

    def _reset(self, effect):
        for pr in BY_NAME[effect.split("#")[0]].params:
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


class NotifyDialog(QDialog):
    """Apps whose notifications light up the keyboard: name, match pattern (regex on the app id), colour."""

    def __init__(self, parent, apps, overlay, watcher, on_change):
        super().__init__(parent)
        self.setWindowTitle("Уведомления")
        self.apps, self.overlay, self.watcher, self.on_change = apps, overlay, watcher, on_change
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        hint = QLabel("Шаблон ищется в системном имени приложения (регулярное выражение, без учёта регистра).",
                      objectName="status")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.grid = QGridLayout()
        lay.addLayout(self.grid)
        self.last = QLabel(objectName="status")
        self.last.setWordWrap(True)
        lay.addWidget(self.last)
        add = QPushButton("Добавить приложение")
        add.clicked.connect(self._add)
        lay.addWidget(add)
        self._rebuild()
        QTimer(self, interval=1000, timeout=self._show_last).start()

    def _show_last(self):
        app_id = self.watcher.last_app_id
        self.last.setText(f"Последнее уведомление пришло от: {app_id}" if app_id else
                          "Пока не было новых уведомлений с момента запуска.")

    def _rebuild(self):
        while self.grid.count():
            self.grid.takeAt(0).widget().deleteLater()
        for c, h in enumerate(("Название", "Шаблон", "Цвет", "", "")):
            self.grid.addWidget(QLabel(h, objectName="status"), 0, c)
        for r, app in enumerate(self.apps, 1):
            name, match = QLineEdit(app["name"]), QLineEdit(app["match"])
            name.textChanged.connect(lambda v, a=app: self._set(a, "name", v))
            match.textChanged.connect(lambda v, a=app: self._set(a, "match", v))
            hue = QSlider(Qt.Horizontal)
            hue.setRange(0, 200)
            hue.setValue(int(app["hue"] * 200))
            hue.setStyleSheet(HUE_GROOVE)
            hue.valueChanged.connect(lambda v, a=app: self._set(a, "hue", v / 200))
            test = QPushButton("Проверить")
            test.clicked.connect(lambda _=False, a=app: self.overlay.notify(a))
            rm = QPushButton("✕")
            rm.clicked.connect(lambda _=False, a=app: self._remove(a))
            for c, w in enumerate((name, match, hue, test, rm)):
                self.grid.addWidget(w, r, c)

    def _set(self, app, key, value):
        app[key] = value
        self.on_change()

    def _add(self):
        self.apps.append({"name": "Новое", "match": "", "hue": 0.0})
        self.on_change()
        self._rebuild()

    def _remove(self, app):
        self.apps.remove(app)
        self.on_change()
        self._rebuild()


class ProfilesDialog(QDialog):
    """Per-app profiles: list on the left, the selected profile's settings on the right."""

    def __init__(self, parent, cfg, engine, on_change):
        super().__init__(parent)
        self.setWindowTitle("Профили приложений и игр")
        self.engine, self.on_change = engine, on_change
        self.items = cfg["profiles"]
        self.setMinimumSize(880, 580)
        outer = QVBoxLayout(self)
        hint = QLabel("Пока окно программы активно, клавиатура показывает её профиль. Свернули игру или "
                      "переключились (Alt+Tab) — подсветка возвращается к обычной.", objectName="status")
        hint.setWordWrap(True)
        outer.addWidget(hint)
        body = QHBoxLayout()
        outer.addLayout(body, 1)

        left = QVBoxLayout()
        body.addLayout(left)
        self.list = QListWidget()
        self.list.setFixedWidth(220)
        self.list.currentRowChanged.connect(self._show)
        left.addWidget(self.list, 1)
        add = QPushButton("Добавить профиль")
        add.clicked.connect(self._add)
        left.addWidget(add)
        self.rm = QPushButton("Удалить профиль")
        self.rm.clicked.connect(self._remove)
        left.addWidget(self.rm)

        self.box = QGroupBox("Профиль")
        body.addWidget(self.box, 1)
        f = QFormLayout(self.box)
        self.enabled = QCheckBox("Профиль включён")
        self.enabled.toggled.connect(lambda v: self._set("enabled", v))
        f.addRow(self.enabled)
        self.name = QLineEdit()
        self.name.textChanged.connect(self._rename)
        f.addRow("Название", self.name)
        exe_row = QHBoxLayout()
        self.exe = QLineEdit()
        self.exe.setPlaceholderText("cod.exe (несколько — через запятую)")
        self.exe.textChanged.connect(lambda v: self._set("exe", v))
        exe_row.addWidget(self.exe, 1)
        pick = QPushButton("Выбрать окно…")
        pick.clicked.connect(self._pick_window)
        exe_row.addWidget(pick)
        f.addRow("Программа", exe_row)

        fx_row = QHBoxLayout()
        self.effect = QComboBox()
        self.effect.addItem("Не менять (как в главном окне)", "")
        for cls in EFFECTS:
            self.effect.addItem(cls.title, cls.name)
        self.effect.currentIndexChanged.connect(self._effect)
        fx_row.addWidget(self.effect, 1)
        self.fx_params = QPushButton("Настройки эффекта…")
        self.fx_params.clicked.connect(self._effect_params)
        fx_row.addWidget(self.fx_params)
        f.addRow("Эффект", fx_row)

        br_row = QHBoxLayout()
        self.own_bright = QCheckBox("своя")
        self.own_bright.toggled.connect(self._bright_mode)
        br_row.addWidget(self.own_bright)
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(0, 100)
        self.bright.valueChanged.connect(lambda v: self._set("brightness", v / 100))
        br_row.addWidget(self.bright, 1)
        f.addRow("Яркость", br_row)
        self.calm = QComboBox()
        self.calm.addItems(profiles.CALM_CHOICES)
        self.calm.currentIndexChanged.connect(lambda v: self._set("calm", v))
        f.addRow("Спокойный режим", self.calm)

        self.highlight = QCheckBox("Подсвечивать рабочие клавиши поверх эффекта")
        self.highlight.toggled.connect(lambda v: self._set("highlight", v))
        f.addRow(self.highlight)
        preset_row = QHBoxLayout()
        for title in profiles.PRESETS:
            b = QPushButton(f"Набор «{title}»")
            b.clicked.connect(lambda _=False, t=title: self._preset(t))
            preset_row.addWidget(b)
        preset_row.addStretch(1)
        f.addRow("Заполнить", preset_row)
        self.group_keys, self.group_hue = [], []
        for i in range(profiles.GROUPS):
            row = QHBoxLayout()
            keys = QLineEdit()
            keys.textChanged.connect(lambda v, i=i: self._group(i, "keys", v))
            hue = QSlider(Qt.Horizontal)
            hue.setRange(0, 200)
            hue.setFixedWidth(150)
            hue.setStyleSheet(HUE_GROOVE)
            hue.valueChanged.connect(lambda v, i=i: self._group(i, "hue", v / 200))
            row.addWidget(keys, 1)
            row.addWidget(hue)
            self.group_keys.append(keys)
            self.group_hue.append(hue)
            f.addRow(f"Группа {i + 1}", row)
        self.unknown = QLabel(objectName="status")
        self.unknown.setWordWrap(True)
        f.addRow(self.unknown)
        self.dim = QSlider(Qt.Horizontal)
        self.dim.setRange(0, 100)
        self.dim.valueChanged.connect(lambda v: self._set("dim", v / 100))
        f.addRow("Остальные клавиши, яркость", self.dim)
        keys_hint = QLabel("Клавиши — через пробел: W A S D Shift Ctrl Space Tab Q E R F1 Esc…", objectName="status")
        keys_hint.setWordWrap(True)
        f.addRow(keys_hint)

        self._loading = False
        self._refill(0)

    # --- list -----------------------------------------------------------------
    def _refill(self, row):
        self.list.blockSignals(True)
        self.list.clear()
        for p in self.items:
            self.list.addItem(p["name"])
        self.list.blockSignals(False)
        self.box.setEnabled(bool(self.items))
        self.rm.setEnabled(bool(self.items))
        if self.items:
            self.list.setCurrentRow(min(max(row, 0), len(self.items) - 1))
        self._show(self.list.currentRow())

    def _cur(self):
        r = self.list.currentRow()
        return self.items[r] if 0 <= r < len(self.items) else None

    def _show(self, _row):
        p = self._cur()
        if p is None:
            return
        self._loading = True
        self.enabled.setChecked(p.get("enabled", True))
        self.name.setText(p["name"])
        self.exe.setText(p["exe"])
        self.effect.setCurrentIndex(max(0, self.effect.findData(p.get("effect", ""))))
        self.fx_params.setEnabled(bool(p.get("effect")))
        own = p.get("brightness") is not None
        self.own_bright.setChecked(own)
        self.bright.setEnabled(own)
        self.bright.setValue(int((p["brightness"] if own else self.engine.brightness) * 100))
        self.calm.setCurrentIndex(int(p.get("calm", 0)))
        self.highlight.setChecked(bool(p.get("highlight")))
        groups = p.setdefault("groups", [])
        while len(groups) < profiles.GROUPS:
            groups.append({"keys": "", "hue": 0.0})
        for i, g in enumerate(groups[:profiles.GROUPS]):
            self.group_keys[i].setText(g["keys"])
            self.group_hue[i].setValue(int(g["hue"] * 200))
        self.dim.setValue(int(p.get("dim", 0.2) * 100))
        self._loading = False
        self._check_keys()

    # --- edits ----------------------------------------------------------------
    def _set(self, key, value):
        p = self._cur()
        if p is None or self._loading:
            return
        p[key] = value
        self.on_change()

    def _rename(self, v):
        self._set("name", v)
        if not self._loading and self.list.currentItem():
            self.list.currentItem().setText(v)

    def _group(self, i, key, value):
        p = self._cur()
        if p is None or self._loading:
            return
        p["groups"][i][key] = value
        self._check_keys()
        self.on_change()

    def _check_keys(self):
        bad = []
        for g in (self._cur() or {}).get("groups", []):
            bad += profiles.parse_keys(g["keys"])[1]
        self.unknown.setText(("Нет на этой клавиатуре: " + ", ".join(bad)) if bad else "")

    def _preset(self, title):
        p = self._cur()
        p["groups"] = [{"keys": k, "hue": h} for k, h in profiles.PRESETS[title]]
        p["highlight"] = True
        self._show(None)
        self.on_change()

    def _bright_mode(self, own):
        if self._loading:
            return
        self.bright.setEnabled(own)
        self._set("brightness", self.bright.value() / 100 if own else None)

    def _effect(self, _i):
        p = self._cur()
        if p is None or self._loading:
            return
        name = self.effect.currentData()
        p["effect"] = name
        self.fx_params.setEnabled(bool(name))
        key = profiles.effect_key(p)
        if key and key not in self.engine.params:            # start from the main window's settings
            self.engine.params[key] = dict(self.engine.params.get(name, {}))
        self.on_change()

    def _effect_params(self):
        p = self._cur()
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{p['name']}: {BY_NAME[p['effect']].title}")
        dlg.setMinimumWidth(460)
        panel = ParamPanel(self.engine, self.on_change)
        panel.show_effect(profiles.effect_key(p))
        QVBoxLayout(dlg).addWidget(panel)
        dlg.exec()

    def _pick_window(self):
        menu = QMenu(self)
        for exe, title in winsys.open_windows():
            if exe in ("python.exe", "pythonw.exe", "ardor-rgb.exe", "explorer.exe", "applicationframehost.exe"):
                continue
            short = title if len(title) < 60 else title[:57] + "…"
            menu.addAction(f"{exe}  —  {short}", lambda e=exe, t=title: self._use_window(e, t))
        menu.exec(self.exe.mapToGlobal(self.exe.rect().bottomLeft()))

    def _use_window(self, exe, title):
        self.exe.setText(exe)
        if self.name.text() in ("", "Новая игра"):
            self.name.setText(title[:40] or exe)

    def _add(self):
        self.items.append(profiles.new_profile())
        self.on_change()
        self._refill(len(self.items) - 1)

    def _remove(self):
        p = self._cur()
        if p is None:
            return
        self.items.remove(p)
        for k in [k for k in self.engine.params if k.endswith("#" + p["id"])]:
            del self.engine.params[k]
        self.on_change()
        self._refill(self.list.currentRow())


class MainWindow(QMainWindow):
    def __init__(self, engine, cfg, bridge):
        super().__init__()
        self.engine, self.cfg = engine, cfg
        self.quitting = False
        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self._save)
        self.setWindowTitle(f"ARDOR RGB {__version__} — {layout.TITLE}")
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
        self._check(g, "Настоящая темнота (гасить почти чёрные места)", engine.true_black, self._true_black)
        self.black = QSlider(Qt.Horizontal)
        self.black.setRange(1, 25)
        self.black.setValue(int(engine.black_level * 100))
        self.black.valueChanged.connect(self._black_level)
        g.addRow("Порог темноты", self.black)
        self._check(g, "В полноэкранных играх — спокойный режим", cfg["game_calm"],
                    lambda v: self._cfg("game_calm", v))
        self._check(g, "При блокировке ПК — медленное дыхание", cfg["lock_breathe"],
                    lambda v: self._cfg("lock_breathe", v))
        for ov in engine.overlays:
            self._check(g, ov.title, ov.enabled, lambda v, o=ov: self._overlay(o, v))
        self._check(g, "Считать нажатия для тепловой карты (только на этом ПК)", engine.count_keys, self._count_keys)
        self._check(g, "Запускать вместе с Windows (в трее)", winsys.autostart_enabled(), winsys.set_autostart)
        notif = QPushButton("Уведомления: приложения и цвета…")
        notif.clicked.connect(self._notify_dialog)
        g.addRow(notif)
        prof = QPushButton("Профили приложений и игр…")
        prof.clicked.connect(lambda: ProfilesDialog(self, self.cfg, self.engine, self._save_later).exec())
        g.addRow(prof)
        self.exit_combo = QComboBox()
        self.exit_combo.addItems(EXIT_MODES.values())
        self.exit_combo.setCurrentIndex(list(EXIT_MODES).index(engine.exit_mode))
        self.exit_combo.currentIndexChanged.connect(self._exit_mode)
        g.addRow("Когда программа закрыта", self.exit_combo)
        self.exit_hue = QSlider(Qt.Horizontal)
        self.exit_hue.setRange(0, 200)
        self.exit_hue.setValue(int(engine.exit_hue * 200))
        self.exit_hue.setStyleSheet(HUE_GROOVE)
        self.exit_hue.valueChanged.connect(self._exit_hue)
        g.addRow("Цвет для этого режима", self.exit_hue)
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

    def _true_black(self, v):
        self.engine.true_black = v
        self._save_later()

    def _black_level(self, v):
        self.engine.black_level = v / 100
        self._save_later()

    def _count_keys(self, v):
        self.engine.count_keys = v
        self._save_later()

    def _calm(self, v):
        self.engine.calm = v
        self._save_later()

    def _overlay(self, ov, v):
        ov.enabled = v
        self._save_later()

    def _notify_dialog(self):
        ov = next(o for o in self.engine.overlays if isinstance(o, NotifyOverlay))
        NotifyDialog(self, self.cfg["notify_apps"], ov, self.watcher, self._save_later).exec()

    def _exit_mode(self, i):
        self.engine.exit_mode = list(EXIT_MODES)[i]
        self._save_later()

    def _exit_hue(self, v):
        self.engine.exit_hue = v / 200
        self._save_later()

    def _cfg(self, key, v):
        self.cfg[key] = v
        self._save_later()

    def _save_later(self):
        self._save_timer.start()

    def _save(self):
        e = self.engine
        self.cfg.update(effect=e.effect, brightness=e.brightness, calm=e.calm, params=e.params,
                        exit_mode=e.exit_mode, exit_hue=e.exit_hue, true_black=e.true_black,
                        black_level=e.black_level, count_keys=e.count_keys,
                        overlays={type(o).__name__: o.enabled for o in e.overlays})
        settings.save(self.cfg)

    # --- system state ---------------------------------------------------------
    def _watch(self):
        e = self.engine
        locked = winsys.is_locked()
        e.locked = locked
        e.override = "breathe" if locked and self.cfg["lock_breathe"] else None
        e.auto_calm = self.cfg["game_calm"] and not locked and winsys.fullscreen_app()
        prof = None if locked else profiles.match(self.cfg["profiles"], winsys.foreground_exe())
        e.profile = profiles.Active(prof) if prof else None
        mode = " · игра: спокойный режим" if e.auto_calm else (" · ПК заблокирован" if locked else "")
        if prof:
            mode += f" · профиль: {prof['name']}"
        info = e.effect_obj(e.effect).info()
        self.status.setText(f"Клавиатура: {e.status}{mode}" + (f"   ·   {info}" if info else ""))

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
    tray.setToolTip(f"ARDOR RGB {__version__} — {layout.TITLE}")
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
    engine.exit_mode = cfg["exit_mode"] if cfg["exit_mode"] in EXIT_MODES else "restore"
    engine.exit_hue = cfg["exit_hue"]
    engine.true_black, engine.black_level = cfg["true_black"], cfg["black_level"]
    engine.count_keys = cfg["count_keys"]
    engine.overlays = [cls(enabled=cfg["overlays"].get(cls.__name__, False)) for cls in OVERLAYS]
    engine.start()

    bridge = Bridge()
    power_filter = PowerFilter(bridge)
    app.installNativeEventFilter(power_filter)
    if not cfg.get("notify_apps"):
        cfg["notify_apps"] = [dict(a) for a in DEFAULT_APPS]
    notify_ov = next(o for o in engine.overlays if isinstance(o, NotifyOverlay))
    notify_ov.in_game = lambda: engine.auto_calm
    watcher = NotificationWatcher(cfg["notify_apps"], lambda app: notify_ov.enabled and notify_ov.notify(app))
    win = MainWindow(engine, cfg, bridge)
    win.watcher = watcher
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
