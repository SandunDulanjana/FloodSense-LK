@echo off
REM M1 Flood Exposure Demo - starts a local web server and opens the demo in your browser.
cd /d "%~dp0"
echo Starting local web server at http://localhost:8000  (close this window to stop)
start "" http://localhost:8000/index.html
python -m http.server 8000 || py -m http.server 8000 || (echo Python not found - just double-click index.html instead & pause)
