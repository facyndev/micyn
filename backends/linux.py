import os
import sys
import subprocess
import sounddevice as sd
import re

from .base import PlatformAudio
from constants import (
    LINUX_SINK_NAME, LINUX_OUTPUT_SINK, LINUX_SOURCE_NAME, LINUX_DISPLAY_NAME
)

class LinuxAudio(PlatformAudio):
    def __init__(self):
        self.linux_module_sink_id     = None
        self.linux_module_virtual_id  = None
        self.linux_module_loopback_id = None
        self.linux_module_source_id   = None

    # ────────────────────────────────────────────────
    #  Helpers internos
    # ────────────────────────────────────────────────

    def _run(self, cmd, **kwargs):
        """Ejecuta pactl devolviendo stdout (str) o None si falla."""
        try:
            res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, **kwargs)
            return res.stdout.strip()
        except Exception as e:
            print(f"[LinuxAudio] Error: {e}")
            return None

    def _get_default_physical_sink(self):
        """Devuelve el nombre del sink físico por defecto (ignora los virtuales de Micyn)."""
        try:
            out = subprocess.check_output(["pactl", "get-default-sink"],
                                          stderr=subprocess.STDOUT).decode().strip()
            # Si el default ya es uno de nuestros sinks, buscar el primero físico
            skip = [LINUX_SINK_NAME.lower(), LINUX_OUTPUT_SINK.lower(), "micyn"]
            if not any(k in out.lower() for k in skip):
                return out
            # Fallback: listar todos y devolver el primero no-micyn
            lines = subprocess.check_output(["pactl", "list", "short", "sinks"],
                                            stderr=subprocess.STDOUT).decode().splitlines()
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[1]
                    if not any(k in name.lower() for k in skip):
                        return name
        except Exception as e:
            print(f"[LinuxAudio] Error obteniendo sink físico: {e}")
        return None

    # ────────────────────────────────────────────────
    #  API PlatformAudio
    # ────────────────────────────────────────────────

    def init_virtual_cable(self):
        """Crea la cadena de módulos virtuales idéntica al backup original."""
        print("[LinuxAudio] Iniciando cables virtuales...")
        self.cleanup_virtual_cable()   # limpiar restos de sesiones anteriores

        # 1. Sink interno que recibe el audio CON delay (sounddevice escribe aquí)
        out = self._run([
            "pactl", "load-module", "module-null-sink",
            f"sink_name={LINUX_SINK_NAME}",
            f"sink_properties=device.description='{LINUX_SINK_NAME}'"
        ])
        self.linux_module_sink_id = out

        # 2. Sink de salida virtual al que OBS / apps apuntan (fuente mic)
        out = self._run([
            "pactl", "load-module", "module-null-sink",
            f"sink_name={LINUX_OUTPUT_SINK}",
            f"sink_properties=device.description='{LINUX_OUTPUT_SINK}'"
        ])
        self.linux_module_virtual_id = out

        # 3. Loopback: DelaySinkInternal.monitor → MicynOutput  (lleva el audio retrasado)
        out = self._run([
            "pactl", "load-module", "module-loopback",
            f"source={LINUX_SINK_NAME}.monitor",
            f"sink={LINUX_OUTPUT_SINK}",
            "latency_msec=1"
        ])
        self.linux_module_loopback_id = out

        # 4. Fuente virtual: MicynOutput.monitor como mic "Micyn" que ve OBS
        out = self._run([
            "pactl", "load-module", "module-virtual-source",
            f"source_name={LINUX_SOURCE_NAME}",
            f"master={LINUX_OUTPUT_SINK}.monitor",
            f"source_properties=device.description='{LINUX_DISPLAY_NAME}'"
        ])
        self.linux_module_source_id = out

        # Restaurar el sink físico por defecto (sounddevice puede haberlo cambiado)
        physical = self._get_default_physical_sink()
        if physical:
            os.system(f"pactl set-default-sink {physical}")

        print(f"[LinuxAudio] Cables virtuales OK. Selecciona '{LINUX_DISPLAY_NAME}' como mic en OBS.")

    def cleanup_virtual_cable(self):
        """Descarga los módulos cargados por Micyn, limpiando toda la cadena."""
        try:
            out = subprocess.check_output(
                ["pactl", "list", "short", "modules"]
            ).decode()
            for line in out.splitlines():
                if any(k in line for k in [
                    LINUX_SINK_NAME, LINUX_OUTPUT_SINK,
                    LINUX_SOURCE_NAME, LINUX_DISPLAY_NAME,
                    "DelaySinkInternal", "MicynOutput", "MicynMic",
                    "Microfono_OBS_Retraso"
                ]):
                    mod_id = line.split()[0]
                    subprocess.run(["pactl", "unload-module", mod_id],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(f"[LinuxAudio] Módulo {mod_id} eliminado.")
        except Exception as e:
            print(f"[LinuxAudio] Error limpiando módulos: {e}")

    def get_output_device(self, outputs: list) -> int:
        """Busca el índice del sink DelaySinkInternal (destino del stream con delay)."""
        # Primero por nombre exacto
        for d in outputs:
            if LINUX_SINK_NAME.lower() in d['name'].lower():
                return d['original_index']
        # Fallback a pipewire/pulse para que pactl mueva luego
        for d in outputs:
            if d['name'].lower() in ('pipewire', 'pulse'):
                print(f"[LinuxAudio] '{LINUX_SINK_NAME}' no visible en ALSA, usando '{d['name']}' + pactl.")
                return d['original_index']
        return outputs[0]['original_index'] if outputs else None

    def post_stream_setup(self, stream_out, main_stream_ids: list) -> list:
        """Mueve el sink-input de Python/sounddevice hacia DelaySinkInternal."""
        import time
        time.sleep(0.5)   # dar tiempo a PipeWire para registrar el stream

        # A post_stream_setup, loop.py le pasa los IDs pre-existentes de los auriculares.
        # En _move_my_sink_inputs hay que ignorarlos.
        moved = self._move_my_sink_inputs(LINUX_SINK_NAME, ignore_ids=main_stream_ids)
        print(f"[LinuxAudio] Sink-inputs movidos a {LINUX_SINK_NAME}: {moved}")
        return moved

    def route_monitors(self, monitor_stream_ids: list):
        """Mueve los streams de monitor hacia el sink físico."""
        if not monitor_stream_ids:
            return
        physical = self._get_default_physical_sink()
        if not physical:
            return
        for sid in monitor_stream_ids:
            os.system(f"pactl move-sink-input {sid} {physical}")

    # ────────────────────────────────────────────────
    #  Utilidad: mover sink-inputs del proceso actual
    # ────────────────────────────────────────────────

    def _move_my_sink_inputs(self, target_sink, ignore_ids=None):
        """
        Encuentra los sink-inputs de este proceso (por PID) y los mueve a target_sink.
        Devuelve la lista de IDs que se movieron con éxito.
        """
        if ignore_ids is None:
            ignore_ids = []

        moved = []
        env = {**os.environ, "LC_ALL": "C"}

        try:
            pid = str(os.getpid())
            current_bin = os.path.basename(sys.executable).lower()

            out = subprocess.run(
                ["pactl", "list", "sink-inputs"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
            ).stdout

            blocks = re.split(r'\n(?=Sink Input #)', out)
            for block in blocks:
                is_mine = (
                    f'application.process.id = "{pid}"' in block
                    or f'application.name = "{current_bin}"' in block
                    or ("python" in block.lower() and ("44100" in block or "mono" in block))
                )
                if not is_mine:
                    continue

                m = re.search(r'Sink Input #(\d+)', block)
                if not m:
                    continue
                sid = m.group(1)
                if sid in ignore_ids:
                    continue

                result = subprocess.run(
                    ["pactl", "move-sink-input", sid, target_sink],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
                )
                if result.returncode == 0:
                    print(f"  ✓ sink-input {sid} → {target_sink}")
                    moved.append(sid)
                else:
                    print(f"  ✗ Error moviendo {sid}: {result.stderr.strip()}")

            if not moved:
                print(f"[LinuxAudio] AVISO: no se encontraron sink-inputs del proceso (PID {pid}).")

        except Exception as e:
            print(f"[LinuxAudio] Error en _move_my_sink_inputs: {e}")

        return moved
