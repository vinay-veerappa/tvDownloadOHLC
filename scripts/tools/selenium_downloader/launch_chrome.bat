@echo off
echo Launching Chrome with Remote Debugging Port 9222...
echo Please close all other Chrome instances before running this!
echo.
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\vinay\tvDownloadOHLC\chrome_profile"
pause
