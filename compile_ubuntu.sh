#!/bin/bash
# Forzar siempre la ruta interna del VENV en lugar de depender del sistema global (Evita PEP-668)

echo "Verificando instalación de PyInstaller en el entorno virtual..."
./venv/bin/pip install pyinstaller Pillow customtkinter sounddevice numpy

echo "Compilando aplicación..."
./venv/bin/pyinstaller --noconfirm --onedir --windowed --name "Micyn_Ubuntu" "main.py"

echo "¡Proceso terminado exitosamente!"
echo "Puedes encontrar el ejecutable dentro de la carpeta 'dist/Micyn_Ubuntu'."
