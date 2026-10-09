NEBULACONVERT
=============

A local-first Windows desktop file converter built with Python and PySide6.


Requirements
- Windows 10 or Windows 11
- Python 3.11 or 3.12 (64-bit recommended)
- Internet connection for the first dependency installation


Quick start
1. Extract the entire ZIP to a folder.
2. Install Python from https://www.python.org/downloads/windows/ if it is not already installed. During setup, enable **Add python.exe to PATH**.
3. Right-click `Install-NEBULACONVERT-Dependencies.ps1` and choose **Run with PowerShell**, or open PowerShell in this folder and run:

   ```powershell
   .\Install-NEBULACONVERT-Dependencies.ps1
   ```

4. Start the app from this folder with:

   ```powershell
   py -3 main.py
   ```

The PowerShell script installs only the Python packages listed in `requirements.txt`. It does not build an EXE or install optional external conversion engines.


Optional conversion engines
- **Audio/video:** place a trusted Windows FFmpeg executable at `bin\ffmpeg.exe`.
- **Some Office/document conversions:** install LibreOffice separately.

FFmpeg and LibreOffice are not included in this ZIP. Supported conversions depend on the source format and locally available engines.


Privacy
Files are processed locally by the application. Installing Python dependencies requires downloading packages from the Python package index. Avoid opening files you do not trust.


Project files
- `main.py` — application source
- `requirements.txt` — Python dependencies
- `Install-NEBULACONVERT-Dependencies.ps1` — dependency setup helper
- `assets/` — application icon files
