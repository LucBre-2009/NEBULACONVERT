NEBULACONVERT
=============

A local-first Windows desktop file converter built with Python and PySide6.


Requirements
- Windows 10 or Windows 11
- Python 3.11 or 3.12 (64-bit recommended)
- Internet connection for the first dependency installation


Quick start
1. Download the NEBULACONVERT.zip from https://github.com/LucBre-2009/NEBULACONVERT/releases
2. Extract the entire ZIP to a folder.
3. Install Python from https://www.python.org/downloads/windows/ if it is not already installed. During setup, enable **Add python.exe to PATH**.
4. Right-click `Install-NEBULACONVERT-Dependencies.ps1` and choose **Run with PowerShell**, or open PowerShell in this folder and run:

```powershell
.\Install-NEBULACONVERT-Dependencies.ps1 
```
<div style="background-color: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 16px; display: flex; justify-content: space-between; align-items: center; max-width: 400px;">
  <code id="mein-text-id" style="font-family: monospace; color: #24292f;">Dein Text hier</code>
  <clipboard-copy for="mein-text-id" aria-label="Kopieren" style="cursor: pointer; display: flex; align-items: center;">
    <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" style="fill: #57606a;">
      <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path>
      <path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path>
    </svg>
  </clipboard-copy>
</div>



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
