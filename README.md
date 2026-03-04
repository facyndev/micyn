# Micyn

Aplicación de escritorio para aplicar delay a tu micrófono y usarlo en OBS.

Micyn toma la señal de tu micrófono físico, la guarda en un buffer circular y la entrega en una salida virtual con el retraso configurado.

## Estado actual

- Enfoque de uso actual: `OBS`.
- Plataformas soportadas: `Windows` y `Linux (Ubuntu/PipeWire-Pulse)`.
- Versión actual: `1.5.3` (definida en `constants.py`).

## Funcionalidades principales

- Delay configurable con presets (`30s`, `1m`, `2m`, `5m`) o valor personalizado.
- Monitoreo opcional:
  - Escuchar sin delay.
  - Escuchar con delay.
- Vúmetros de entrada y salida en tiempo real.
- Verificación de actualizaciones al iniciar (GitHub Releases).

## Requisitos

### Windows

- Python `3.11+` para ejecutar desde código fuente.
- Driver `VB-Cable` instalado (obligatorio para enrutar la salida virtual).

Sin VB-Cable, la app muestra una pantalla de bloqueo con enlace de descarga.

### Linux (Ubuntu)

- Python `3.11+` para ejecutar desde código fuente.
- `pactl` disponible (PulseAudio/PipeWire-Pulse).
- Permisos para cargar/descargar módulos de audio con `pactl`.
- Dependencias de sistema recomendadas:

```bash
sudo apt-get install -y portaudio19-dev python3-tk
```

Micyn crea sinks/fuente virtuales al iniciar y los limpia al cerrar.

## Ejecución local (desarrollo)

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
python main.py
```

En Windows:

```bat
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
python main.py
```

## Uso con OBS

1. Abre Micyn y selecciona tu micrófono de entrada.
2. Elige el tiempo de delay (preset o personalizado).
3. Presiona `Iniciar retraso de audio`.
4. En OBS, selecciona el micrófono virtual:
   - Windows: `CABLE Output (VB-Audio Virtual Cable)`.
   - Linux: `Micyn`.

## Build de instalables

### Linux (.deb)

```bash
./build_ubuntu.sh
```

Genera: `releases/micyn-<version>.deb`

### Windows (.exe instalador)

```bat
build_windows.bat
```

Genera instalador con Inno Setup en `releases\` (si Inno Setup está instalado).

## Releases automáticos (GitHub Actions)

El workflow `.github/workflows/release.yml` compila para Ubuntu y Windows al hacer push de tags `v*`.

Ejemplo:

```bash
git tag v1.5.3
git push origin v1.5.3
```

Esto publica los artefactos en GitHub Releases (`.deb` y `.exe`).

## Estructura del proyecto

- `main.py`: entrada principal y control de instancia única.
- `app.py`: ciclo de vida de la app y orquestación de audio/UI.
- `audio/`: buffer circular, callbacks y loop de streams.
- `backends/`: integración por plataforma (`windows.py`, `linux.py`).
- `ui/`: splash, ventana principal y manual.
- `updater/`: chequeo/descarga/ejecución de actualización.
- `constants.py`: versión y constantes globales.

## Notas técnicas

- El sample rate de trabajo se ajusta al sample rate por defecto del dispositivo de entrada seleccionado.
- En Linux, el backend mueve sink-inputs con `pactl` para separar salida principal y monitoreo.
- La app evita múltiples instancias usando lock file en carpeta temporal.

## Solución rápida de problemas

- No aparece audio en OBS (Windows): verifica VB-Cable y que OBS use `CABLE Output`.
- No aparece `Micyn` en OBS (Linux): confirma que `pactl` funcione y que PipeWire-Pulse esté activo.
- No inicia una segunda instancia: es comportamiento esperado por el lock de instancia única.

## Licencia

MIT. Ver [LICENSE](LICENSE).

Copyright (c) 2026 Facundo Grieco
