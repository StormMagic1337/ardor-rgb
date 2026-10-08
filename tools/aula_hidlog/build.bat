@echo off
rem Builds hid.dll (32-bit, for the AULA vendor app OemDrv.exe) with MSVC Build Tools 2022.
rem Put hid.dll next to OemDrv.exe, use the app, then read %LOCALAPPDATA%\AULA-F75\hid_log.txt
rem and decode it with tools\aula_analyze_log.py. Delete hid.dll afterwards.
cd /d "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 1
cl /nologo /O2 /W3 /MT /LD /GS- /D_CRT_SECURE_NO_WARNINGS hidlog.c /Fe:hid.dll /link /DEF:hid.def kernel32.lib || exit /b 1
del hidlog.obj hid.exp hid.lib 2>nul
