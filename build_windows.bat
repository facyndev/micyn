@echo off
setlocal enabledelayedexpansion

echo Buscando version en main.py...
for /f "tokens=2 delims=^""" %%a in ('findstr "__version__" main.py') do set VERSION=%%a
if "%VERSION%"=="" set VERSION=1.0.0

set APP_NAME=micyn
set OUT_EXE=releases\%APP_NAME%-%VERSION%.exe

echo ==============================================
echo Compilando %APP_NAME% v%VERSION% para Windows...
echo ==============================================

if not exist "releases" mkdir releases

:: Ejecutar el PyInstaller del entorno de Windows (--onefile para portabilidad)
python -m PyInstaller --noconfirm --onefile --windowed --name "%APP_NAME%" "main.py"

if exist "dist\%APP_NAME%.exe" (
    echo.
    echo Moviendo ejecutable a carpeta releases...
    move /y "dist\%APP_NAME%.exe" "%OUT_EXE%"
) else (
    echo Error: PyInstaller no genero el archivo dist\%APP_NAME%.exe
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
