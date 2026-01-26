@echo off
setlocal
cd /d %~dp0

python -m pip install --upgrade pyinstaller >nul
pyinstaller --onefile --noconsole --name GOP3BotLauncher --add-data "gop3_config.py;." gui_launcher.py

echo.
echo Build complete. See dist\GOP3BotLauncher.exe
pause
