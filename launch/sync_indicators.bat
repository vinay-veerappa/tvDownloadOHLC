@echo off
REM sync_indicators.bat — Sync Vinay + RedTail indicators from repo to NT8 Custom\Indicators
REM Run from anywhere. Uses subfolders matching namespace structure.

set REPO=C:\Users\vinay\tvDownloadOHLC\scripts\ninjatrader\indicators
set NT8=%USERPROFILE%\Documents\NinjaTrader 8\bin\Custom\Indicators

echo Syncing Vinay indicators...
if not exist "%NT8%\Vinay" mkdir "%NT8%\Vinay"
copy /Y "%REPO%\vinay\*.cs" "%NT8%\Vinay\" >nul

echo Syncing RedTail indicators...
if not exist "%NT8%\RedTail" mkdir "%NT8%\RedTail"
copy /Y "%REPO%\redtail\*.cs" "%NT8%\RedTail\" >nul

echo Done. Vinay -^> %NT8%\Vinay\
echo Done. RedTail -^> %NT8%\RedTail\
echo.
echo Run nt_compile to build.