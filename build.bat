@echo off
REM Build GrokStudio.exe (single file, windowed).
REM Run from a venv that has requirements.txt installed.

python scripts\fetch_font.py
if errorlevel 1 echo [warn] font download failed - app will fall back to Segoe UI

python scripts\generate_icon.py
if errorlevel 1 echo [warn] icon generation failed - install Pillow to regenerate

pyinstaller grok_studio.spec --noconfirm
if errorlevel 1 exit /b 1

echo.
echo Done: dist\GrokStudio.exe
