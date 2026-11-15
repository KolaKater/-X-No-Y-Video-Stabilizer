@echo off
REM Lanch_stablizer_gui.bat - start stabilizer GUI, no console window
REM Put this file in D:\3D\Easy3D\ffmpeg\ next to bin\
cd /d "%~dp0"
if not exist "bin\ffmpeg.exe" (
    echo ERROR: bin\ffmpeg.exe not found.
    echo Expected: D:\3D\Easy3D\ffmpeg\bin\ffmpeg.exe
    pause
    exit /b 1
)
if not exist "stablizer_gui.py" (
    echo ERROR: stablizer_gui.py not found in %CD%
    pause
    exit /b 1
)
REM Drag & Drop needs tkinterdnd2 - auto install once if missing
python -c "import tkinterdnd2" 2>nul
if errorlevel 1 (
    echo Installing tkinterdnd2 for drag and drop...
    python -m pip install --quiet tkinterdnd2 opencv-python numpy
)
REM Use pythonw.exe = no CMD window. BAT exits immediately, GUI stays.
if exist "venv\Scripts\pythonw.exe" (
    start "" /min "venv\Scripts\pythonw.exe" stablizer_gui.py
) else if exist "venv\Scripts\python.exe" (
    start "" /min "venv\Scripts\python.exe" stablizer_gui.py
) else (
    start "" /min pythonw stablizer_gui.py
)
exit /b 0
