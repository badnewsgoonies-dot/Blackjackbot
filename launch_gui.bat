@echo off
setlocal
cd /d %~dp0

REM Launch the Tkinter GUI without a console window.
REM Uses GOP3_CONFIG_PATH so GUI/calibration/bot all edit/read the same config file.
set "GOP3_CONFIG_PATH=%cd%\gop3_config.py"

set "PYW="
for /f "delims=" %%I in ('where pythonw 2^>nul') do (
  set "PYW=%%I"
  goto :have_pyw
)

for /f "delims=" %%I in ('where pyw 2^>nul') do (
  set "PYW=%%I"
  goto :have_pyw
)

:have_pyw
if not "%PYW%"=="" (
  start "" "%PYW%" gui_launcher.py
  exit /b 0
)

REM Fallback: this may open a console window, but at least starts the GUI.
start "" python gui_launcher.py
exit /b 0

