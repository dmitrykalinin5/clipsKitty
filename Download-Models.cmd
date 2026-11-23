@echo off
setlocal
cd /d "%~dp0"
echo Download Whisper models for Clips Kitty
echo 1 - small, CPU, about 0.5 GB
echo 2 - large-v3-turbo, NVIDIA GPU, about 1.6 GB
echo 3 - both, about 2.1 GB
choice /C 123 /N /M "Choose [1/2/3]: "
if errorlevel 255 exit /b 1
if not errorlevel 1 exit /b 0
set "MODEL=both"
if errorlevel 3 goto run
if errorlevel 2 (set "MODEL=large-v3-turbo") else (set "MODEL=small")
:run
set "CLIPSKITTY_SCRIPT_HOST=1"
"%~dp0resources\backend\api.exe" "%~dp0download_models.py" --model "%MODEL%"
if errorlevel 1 (echo Download failed. Check your connection and run this file again.)
pause
