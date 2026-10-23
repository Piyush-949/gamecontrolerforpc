@echo off
title PhonePad install
cd /d "%~dp0"
pip install -r requirements.txt
echo.
echo Gamepad mode also needs the ViGEmBus driver:
echo https://github.com/nefarius/ViGEmBus/releases/latest
echo.
echo Then run start.bat
pause
