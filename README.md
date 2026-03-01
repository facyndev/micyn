# Micyn - Retraso de Micrófono para OBS 🎙️

Micyn es una herramienta de escritorio moderna diseñada para capturar la entrada de tu micrófono físico, aplicar un retraso matemático exacto en milisegundos y enviarlo a una salida virtual de audio. Ideal para sincronizar tu voz con transmisiones en directo (OBS) o chats de voz (Discord) que sufren de desincronización por red.

## Características ✨
* **Vúmetros con Anti-Aliasing (PIL):** Visualización reactiva a 60 FPS con curvaturas redondeadas para los monitores de sonido entrante y saliente, ahora con indicador de espera inteligente.
* **Interfaz Dinámica (CustomTkinter):** Menús desplegables sin fricción y controles intuitivos en _Dark Mode_.
* **Monitoreo en Tiempo Real:** Puedes escuchar tu propia voz a través de tus auriculares, tanto con o sin el delay aplicado.
* **Integración transparente en OBS:** Automáticamente crea y gestiona salidas virtuales (en Linux mediante PipeWire) para que otras aplicaciones capturen tu voz limpia y retrasada bajó el nombre `Micyn`.

## ⚙️ Requisitos y Compilación Local

Si cuentas con Python 3.8+ y deseas iniciar la aplicación en formato crudo, debes inicializar tu entorno virtual en la carpeta principal:

```bash
python3 -m venv .venv

# En Ubuntu:
./.venv/bin/pip install -r requirements.txt
# En Windows:
.\.venv\Scripts\pip install -r requirements.txt

# Ejecutar:
python main.py
```

### 📦 Construir tus propios Instalables Embebidos (Offline)
Para generar paquetes completamente nativos y portátiles que no requieran tener Python instalado, la aplicación incluye dos rutinas creadores de *Releases*.

*   **Para Usuarios Linux:** Abre tu terminal y ejecuta `./build_ubuntu.sh`. Te ensamblará la estructura nativa y generará un paquete `.deb` instalable dentro del directorio `releases/`.
*   **Para Usuarios Windows:** Haz doble clic en `build_windows.bat` desde una computadora Windows. PyInstaller comprimirá el código unificándolo en un moderno `.exe` portátil localizado en `releases\`.

---

## 🚀 Despliegue Automatizado (GitHub Actions)

¡Micyn está preparado para compilar sus instalables masivos e integrarlos automáticamente a tus "Releases" en GitHub sin que uses tu computadora!

Cuando realices modificaciones al código base y desees pre-compilar a internet tu actualización (`main.py` -> `__version__ = "X.Y.Z"`), simplemente sube tu código a GitHub etiquetándolo con un formato de versión semántica (Ej: **v1.0.1**):

```bash
git add .
git commit -m "Nueva actualización genial"
git tag v1.0.1
git push origin main
git push origin v1.0.1
```

Tras enviar la etiqueta `v1.0.1`, los laboratorios de **GitHub Actions** tomarán el control:
1. Despertarán un Servidor Windows y uno Ubuntu de manera simultánea en la nube.
2. Compilarán `build_windows.bat` y `build_ubuntu.sh` desde cero resolviendo dependencias internamente.
3. Construirán los binarios finales (`.exe` y `.deb`) y los publicarán automáticamente en la sección **Releases** de este repositorio.

---

## 📄 Licencia
Este proyecto está bajo la [Licencia MIT](LICENSE) - mira el archivo para más detalles.

Copyright (c) 2026 Facundo Grieco

