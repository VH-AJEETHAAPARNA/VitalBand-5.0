@echo off
REM ===========================================================================
REM VitalBand - compile and flash the wrist patch firmware
REM
REM Usage:   flash.bat            (auto-detect the ESP32 port)
REM          flash.bat COM7       (force a specific port)
REM
REM Everything is already installed: arduino-cli, the esp32 core, and both
REM libraries. You only need the board plugged in over a DATA USB cable.
REM ===========================================================================

setlocal
set CLI=%USERPROFILE%\.arduino-cli-dl\arduino-cli.exe
set SKETCH=%~dp0wristband_max30102
set FQBN=esp32:esp32:esp32

if not exist "%CLI%" (
  echo [ERROR] arduino-cli not found at %CLI%
  exit /b 1
)

echo.
echo === Boards detected ===
"%CLI%" board list
echo.

set PORT=%1
if "%PORT%"=="" (
  for /f "tokens=1" %%p in ('"%CLI%" board list ^| findstr /r "^COM"') do (
    if not defined PORT set PORT=%%p
  )
)

if "%PORT%"=="" (
  echo [ERROR] No ESP32 serial port found.
  echo.
  echo   - Use a DATA USB cable, not a charge-only one
  echo   - Install the CP210x or CH340 driver for your board
  echo   - Check Device Manager -^> Ports ^(COM ^& LPT^)
  echo   - Then re-run:  flash.bat        or   flash.bat COM7
  exit /b 1
)

echo Using port: %PORT%
echo.
echo === Compiling ===
"%CLI%" compile --fqbn %FQBN% "%SKETCH%"
if errorlevel 1 (
  echo [ERROR] Compile failed.
  exit /b 1
)

echo.
echo === Uploading ===
"%CLI%" upload -p %PORT% --fqbn %FQBN% "%SKETCH%"
if errorlevel 1 (
  echo [ERROR] Upload failed.
  echo   Hold the BOOT button while upload starts, then release.
  exit /b 1
)

echo.
echo === Done. Opening serial monitor at 115200 ^(Ctrl+C to exit^) ===
"%CLI%" monitor -p %PORT% --config baudrate=115200

endlocal
