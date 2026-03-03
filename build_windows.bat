@echo off
setlocal enabledelayedexpansion

echo Buscando version en constants.py...
for /f "tokens=2 delims==" %%a in ('findstr /B "APP_VERSION" constants.py') do set VERSION=%%~a
set VERSION=%VERSION: =%
set VERSION=%VERSION:"=%
if "%VERSION%"=="" set VERSION=1.0.0

set APP_NAME=micyn
set OUT_EXE=releases\%APP_NAME%-%VERSION%.exe

echo ==============================================
echo Compilando %APP_NAME% v%VERSION% para Windows...
echo ==============================================

if not exist "releases" mkdir releases

echo Verificando dependencias...
if not exist ".venv" (
    echo Creando entorno virtual Windows...
    python -m venv .venv
)
.\.venv\Scripts\pip install -r requirements.txt

:: Generar iconos si no existen
if not exist "icon.ico" (
    echo Generando icon.ico e icon.png...
    .\.venv\Scripts\python -c "from PIL import Image; img = Image.open('micyn_logo.jpg'); img.save('icon.png'); img.save('icon.ico', sizes=[(256,256)])"
)

:: Ejecutar el PyInstaller usando el spec (incluye hiddenimports correctos)
.venv\Scripts\pyinstaller --noconfirm micyn.spec

if exist "dist\%APP_NAME%\%APP_NAME%.exe" (
    echo.
    echo Moviendo ejecutable a carpeta releases...
    move /y "dist\%APP_NAME%\%APP_NAME%.exe" "%OUT_EXE%"
) else (
    echo Error: PyInstaller no genero el ejecutable
    goto end
)

echo.
echo Limpiando temporales...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo.
echo ==============================================
echo ¡Listo! Archivo ejecutable .exe generado en:
echo %OUT_EXE%
echo ==============================================

:end
pause
