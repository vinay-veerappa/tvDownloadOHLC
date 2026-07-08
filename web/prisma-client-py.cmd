@echo off
REM prisma-client-py wrapper — bridges Node.js Prisma CLI to Python prisma generator
REM
REM The Node.js Prisma CLI spawns this as the "prisma-client-py" provider.
REM It sets PRISMA_GENERATOR_INVOCATION and calls python -m prisma which
REM runs Generator.invoke() to process the JSON-RPC generation requests.
REM
REM This file must be in node_modules/.bin/ (copied there after npm install).
REM The source lives at web/prisma-client-py.cmd in the project root.

setlocal enabledelayedexpansion

REM Resolve the project root from this script's location.
REM node_modules/.bin/prisma-client-py.cmd -> ../../ -> web/ -> ../../ -> project root
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\..\"
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

REM The Prisma CLI sets PRISMA_GENERATOR_INVOCATION env var when calling generators
REM But we need to ensure it's set for the Python generator to accept the invocation
if not defined PRISMA_GENERATOR_INVOCATION set "PRISMA_GENERATOR_INVOCATION=1"

"%PYTHON_EXE%" -m prisma %*