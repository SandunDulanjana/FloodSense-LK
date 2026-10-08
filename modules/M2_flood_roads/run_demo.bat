@echo off
REM M2 localhost demo launcher (Windows). Double-click, or run from this folder in a terminal.
REM Needs: Python 3.10+ (Anaconda is fine) and the app_data\ folder next to app\.
cd /d "%~dp0"
if not exist app_data\road_summary.json (
  echo [!] app_data\ is missing. Download M2_app_data.zip from Google Drive ^(MyDrive\M2_flood_roads\^) and unzip it here.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo Creating virtual environment ^(first run only, needs internet, about 3-5 minutes^)...
  python -m venv .venv || (echo [!] Python not found on PATH. Open "Anaconda Prompt", cd to this folder and run run_demo.bat again. & pause & exit /b 1)
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install -r app\requirements.txt || (echo [!] Package install failed - check Python is 3.10 or newer: python --version & pause & exit /b 1)
)
echo Starting the app at http://localhost:8501 ...
.venv\Scripts\python.exe -m streamlit run app\app.py --server.headless false
pause
