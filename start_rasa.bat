@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "RASA_DIR=%ROOT_DIR%rasa"
set "RASA_PYTHON=%RASA_DIR%\.venv\Scripts\python.exe"
set "RASA_MODEL="

if not exist "%RASA_PYTHON%" (
	echo Rasa virtual environment Python not found at "%RASA_PYTHON%"
	echo Create it first, then install Rasa dependencies.
	pause
	exit /b 1
)

for /f "delims=" %%F in ('dir /b /a-d /o-d "%RASA_DIR%\models\*.tar.gz" 2^>nul') do (
	if not defined RASA_MODEL set "RASA_MODEL=%RASA_DIR%\models\%%F"
)

if not defined RASA_MODEL (
	echo No trained Rasa model found in "%RASA_DIR%\models"
	echo Run "python -m rasa train" from the rasa folder first.
	pause
	exit /b 1
)

echo Cleaning old listeners on ports 5005 and 5055...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports=@(5005,5055); foreach($p in $ports){ Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }"

echo Starting Rasa action server on port 5055...
start "Rasa Actions" /D "%RASA_DIR%" "%RASA_PYTHON%" -m rasa_sdk --actions actions.actions -p 5055

cd /d "%RASA_DIR%"
echo Starting Rasa API server on port 5005 with model:
echo %RASA_MODEL%
"%RASA_PYTHON%" -m rasa run --enable-api --cors * --model "%RASA_MODEL%"