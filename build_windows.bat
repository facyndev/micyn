@echo off
setlocal enabledelayedexpansion

echo Buscando version en constants.py...
for /f "tokens=2 delims==" %%a in ('findstr /B "APP_VERSION" constants.py') do set VERSION=%%~a
set VERSION=%VERSION: =%
set VERSION=%VERSION:"=%
if "%VERSION%"=="" set VERSION=1.0.0

set APP_NAME=micyn

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

if not exist "dist\%APP_NAME%" (
    echo Error: PyInstaller no genero la carpeta dist\%APP_NAME%
    goto end
)

echo.
echo ==============================================
echo Compilando instalador con Inno Setup...
echo ==============================================

:: Buscar ISCC.exe (compilador de Inno Setup) en rutas comunes
set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if %ISCC%=="" (
    echo.
    echo AVISO: No se encontro Inno Setup. Descargalo desde https://jrsoftware.org/isdl.php
    echo        El instalador (.exe con setup) NO fue generado.
    echo        Solo quedara disponible el binario portable en dist\%APP_NAME%\
    goto end
)

%ISCC% /DMyAppVersion=%VERSION% micyn_installer.iss

if exist "releases\Micyn-Setup-%VERSION%.exe" (
    echo.
    echo ==============================================
    echo ¡Listo! Instalador generado en:
    echo releases\Micyn-Setup-%VERSION%.exe
    echo ==============================================
) else (
    echo Error: Inno Setup no genero el instalador esperado.
)

echo.
echo Limpiando temporales...
if exist "build" rmdir /s /q build
if exist "dist"  rmdir /s /q dist

:end
pause
