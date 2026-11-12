#!/bin/bash
# Launcher for Mac: double-click this file to run the app locally

# What this script does:
#   1. Checks that Python 3.11 or newer is installed (the libraries need at least 3.11)
#   2. The first time only, creates .venv and installs the libraries from requirements.txt
#   3. Starts the app, which opens in the browser at http://localhost:8501

# The database settings come from the .env file in the project folder (see README.md)
# Run using: double-click in Finder, or ./milestone3/run_app.command in a terminal
# (if macOS blocks it the first time, right-click it -> Open -> Open)

# Go to the project folder (one level up from this file) so the paths below work wherever it's started from
cd "$(dirname "$0")/.." || exit 1

# Step 1: check for Python 3.11+
# -> mysql-connector-python 26.10 needs at least 3.11, and older Macs come with 3.9
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    echo "Python 3.11 or newer is needed. Download it from https://www.python.org/downloads/ then run this again"
    read -r -p "Press Enter to close"
    exit 1
fi

# Step 2: create .venv and install the libraries, only if it hasn't been done before
# -> checking for .venv/bin/streamlit means a half-finished install gets redone
if [ ! -x .venv/bin/streamlit ]; then
    echo "First run: installing the libraries (takes a minute or two)"
    python3 -m venv .venv && .venv/bin/pip install -q -r milestone3/requirements.txt || {
        echo "Installing the libraries failed, see the error above"
        read -r -p "Press Enter to close"
        exit 1
    }
fi

# Step 3: start the app
# Streamlit opens the browser by itself, closing this window stops the app
echo "Starting the app at http://localhost:8501 (close this window to stop it)"
.venv/bin/streamlit run milestone3/app.py
