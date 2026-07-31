@echo off
setlocal enabledelayedexpansion
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set OUT=C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\NinjaTrader.Custom.dll
set SOURCES=run_csc_sources.txt
set REFS=run_csc_refs.txt
set LOG=csc_out.txt

if not exist "%SOURCES%" (
    echo ERROR: %SOURCES% not found. Run make_csc_lists.ps1 first.
    exit /b 1
)
if not exist "%REFS%" (
    echo ERROR: %REFS% not found. Run make_csc_lists.ps1 first.
    exit /b 1
)

set REFARGS=
for /f "usebackq tokens=*" %%r in ("%REFS%") do (
    set REFARGS=!REFARGS! /r:"%%r"
)

echo Starting csc build at %date% %time% > "%LOG%"
echo Sources: %SOURCES% >> "%LOG%"
echo Refs: %REFS% >> "%LOG%"

"%CSC%" /target:library /out:"%OUT%" /unsafe /optimize+ /platform:x64 /define:NT8 %REFARGS% @"%SOURCES%" >> "%LOG%" 2>&1
set EXITCODE=%ERRORLEVEL%
echo csc finished with code %EXITCODE% at %date% %time% >> "%LOG%"
exit /b %EXITCODE%
