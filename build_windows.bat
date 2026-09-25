@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY_CMD=py -3"
) else (
    set "PY_CMD=python"
)

%PY_CMD% -m pip install ".[build]"
if errorlevel 1 exit /b %errorlevel%

%PY_CMD% -m PyInstaller --noconfirm --clean CafePOS.spec
if errorlevel 1 exit /b %errorlevel%

set "RELEASE_DIR=dist\CafePOS"
if not exist "%RELEASE_DIR%\logs" mkdir "%RELEASE_DIR%\logs"

if exist "cafepos.db" (
    copy /Y "cafepos.db" "%RELEASE_DIR%\cafepos.db" >nul
) else (
    %PY_CMD% -c "import sqlite3; sqlite3.connect(r'dist/CafePOS/cafepos.db').close()"
)
if errorlevel 1 exit /b %errorlevel%

if exist "config.json" copy /Y "config.json" "%RELEASE_DIR%\config.json" >nul
if exist "default_menu.json" copy /Y "default_menu.json" "%RELEASE_DIR%\default_menu.json" >nul
copy /Y "release_files\Create Desktop Shortcut.bat" "%RELEASE_DIR%\" >nul
if errorlevel 1 exit /b %errorlevel%
copy /Y "release_files\README.txt" "%RELEASE_DIR%\" >nul
if errorlevel 1 exit /b %errorlevel%

if exist "local_whatsapp" (
    echo Copying Local WhatsApp server files...
    robocopy "local_whatsapp" "%RELEASE_DIR%\local_whatsapp" /E /XD ".wwebjs_auth" "test_auth" ".puppeteer_cache" /XF "debug.log" >nul
    rem robocopy uses its own exit codes: 0-7 mean success, 8+ means a real error.
    if errorlevel 8 exit /b 1
)

%PY_CMD% work\verify_packaging.py
if errorlevel 1 exit /b %errorlevel%

echo.
echo CafePOS package created in %RELEASE_DIR%
echo cafepos.db, config.json, and logs are external to CafePOS.exe.
echo local_whatsapp holds the WhatsApp bridge - the client's PC needs Node.js and Chrome or Edge installed to use it.
