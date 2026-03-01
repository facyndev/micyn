@echo off
echo Instalando dependencias y PyInstaller en Windows...
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller

echo Compilando para Windows 10...
pyinstaller --noconfirm --onedir --windowed --name "DelayMicrofono_Windows" "main.py"

echo ¡Compilación terminada! El ejecutable está en la carpeta 'dist\DelayMicrofono_Windows'.
pause
