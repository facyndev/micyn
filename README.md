# Delay de Micrófono (1 minuto) para OBS

Esta aplicación toma la entrada de tu micrófono y la retrasa exactamente 60 segundos antes de enviarla a tu salida de audio. Está diseñada principalmente para utilizarse en conjunto con OBS Studio.

## Requisitos
- Python 3.8 o superior.
- Virtual Audio Cable (para usar como salida hacia OBS, opcional pero muy recomendado en ambos OS para evitar escuchar tu propia voz).

## Instalación rápida (Linux/Ubuntu)
1. Instala `python3-venv`, `python3-tk` y `portaudio19-dev` (requerido por sounddevice):
   ```bash
   sudo apt update
   sudo apt install python3-venv python3-tk portaudio19-dev libportaudio2
   ```
2. Ejecuta instálalo mediante:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Ejecuta la app:
   ```bash
   python main.py
   ```

## Integración con OBS Studio
1. En Windows, puedes instalar herramientas como **VB-Audio Virtual Cable**.
2. En Ubuntu, puedes usar módulos de iteración combinada de PulseAudio (pactl load-module module-null-sink sink_name=Virtual_Sink).
3. En la aplicación de Delay de Audio:
   - **Microfono (Entrada):** Selecciona tu micrófono real.
   - **Salida de Audio:** Selecciona tu "Virtual Audio Cable" o "Virtual Sink".
4. En **OBS Studio**, añade una nueva **Captura de Salida de Audio** (Audio Output Capture) y selecciona como dispositivo tu Virtual Audio Cable. De este modo, OBS recibirá tu voz exactamente 1 minuto después.

## Compilar a Ejecutable
- **Ubuntu**: Ejecuta `bash compile_ubuntu.sh`. Te creará una carpeta en `dist/DelayMicrofono_Ubuntu` con el ejecutable listo para correr sin requerir Python.
- **Windows 10**: Haz doble clic en `compile_windows.bat`. Instalará y compilará la aplicación automáticamente creando una carpeta en `dist\DelayMicrofono_Windows`.
