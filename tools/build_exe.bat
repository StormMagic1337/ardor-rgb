@echo off
rem Builds dist\ARDOR-RGB.exe: one file, no Python needed. Requires: pip install -r requirements.txt pyinstaller
rem The keyboard is detected at start (Guardian or AULA F75), so one exe serves both.
cd /d "%~dp0.."
python -m PyInstaller --noconfirm --clean --onefile --windowed --name ARDOR-RGB ^
  --hidden-import pyaudiowpatch --hidden-import pycaw.pycaw --hidden-import comtypes.stream ^
  --collect-submodules comtypes --collect-submodules dxcam --hidden-import mss ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets ^
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml ^
  --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtPdf ^
  --exclude-module tkinter --exclude-module PIL ^
  --workpath build --specpath build --distpath dist app.py
