@echo off
REM Launcher for Windows: double-click this file to run the app locally

REM What this script does:
REM   1. Checks that Python 3.11 or newer is installed (the libraries need at least 3.11)
REM   2. The first time only, creates .venv and installs the libraries from requirements.txt
REM   3. Starts the app, which opens in the browser at http://localhost:8501

REM The database settings come from the .env file in the project folder (see README.md)
REM Run using: double-click in File Explorer

REM Go to the project folder (one level up from this file) so the paths below work wherever it's started from
cd /d "%~dp0.."

REM Step 1: check for Python 3.11+
REM -> mysql-connector-python 26.10 needs at least 3.11
python -c "import sys; sys.exit(sys.version_info < (3, 11))" 2>nul
if errorlevel 1 (
    echo Python 3.11 or newer is needed. Download it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" while installing, then run this again
    pause
    exit /b 1
)

REM Step 2: create .venv and install the libraries, only if it hasn't been done before
REM -> checking for streamlit.exe means a half-finished install gets redone
if not exist ".venv\Scripts\streamlit.exe" (
    echo First run: installing the libraries ^(takes a minute or two^)
    python -m venv .venv
    ".venv\Scripts\pip" install -q -r milestone3\requirements.txt
    if errorlevel 1 (
        echo Installing the libraries failed, see the error above
        pause
        exit /b 1
    )
)

REM Step 3: start the app
REM Streamlit opens the browser by itself, closing this window stops the app
echo Starting the app at http://localhost:8501 (close this window to stop it)
".venv\Scripts\streamlit" run milestone3\app.py
pause
