import os
import sounddevice as sd
import queue
import time
from tkinter import messagebox

from constants import SAMPLERATE, CHANNELS, CHUNK_SIZE
from .buffer import RingBuffer
from .callbacks import AudioEngine

def start_audio_loop(
    app_context, 
    delay_seconds, 
    in_device_id, 
    out_device_id, 
    monitor_device_id, 
    listen_delay_device_id, 
    listen_live, 
    listen_delay
):
    """
    Función que bloquea y mantiene viva la sesión de SoundDevice.
    Debe correr en su propio hilo.
    """
    app_context.ring_buffer = RingBuffer(delay_seconds, SAMPLERATE, CHANNELS)
    monitor_q = queue.Queue(maxsize=10) if listen_live else None

    # Inicializar estado general compartido de la instancia activa
    engine = AudioEngine(
        ring_buffer=app_context.ring_buffer,
        monitor_queue=monitor_q,
        monitor_active=listen_live,
        is_running=lambda: app_context.is_running,
        monitor_delay_ref=getattr(app_context, 'monitor_delay_var', None)
    )
    
    # Asignar a la app para vúmetros
    app_context.audio_engine = engine

    streams = []
    
    try:
        # 1. Módulo Monitor Directo (0ms latency, personal headphones)
        if listen_live and monitor_device_id is not None:
            stream_mon = sd.OutputStream(
                samplerate=SAMPLERATE, device=monitor_device_id, channels=CHANNELS,
                callback=engine._monitor_callback_out, blocksize=CHUNK_SIZE
            )
            streams.append(stream_mon)
            stream_mon.start()

        # 2. Módulo Monitor Retrasado
        if listen_delay and listen_delay_device_id is not None:
            stream_mon_d = sd.OutputStream(
                samplerate=SAMPLERATE, device=listen_delay_device_id, channels=CHANNELS,
                callback=engine._monitor_delay_callback_out, blocksize=CHUNK_SIZE
            )
            streams.append(stream_mon_d)
            stream_mon_d.start()

        # ---- Ruteos Específicos del OS POST-arranque de Monitores ----
        # Capturar IDs de sink-inputs de monitor (ya abiertos) ANTES de abrir el stream principal
        monitor_stream_ids = []
        if app_context.os_system == 'Linux':
            time.sleep(0.5) # dar tiempo a PipeWire para registrar los monitores
            import subprocess, re as _re
            try:
                env = dict(os.environ, LC_ALL="C")
                out_pa = subprocess.check_output(["pactl", "list", "sink-inputs"], env=env).decode()
                pid = str(os.getpid())
                for block in _re.split(r'\n(?=Sink Input #)', out_pa):
                    if pid in block or "python" in block.lower():
                        m = _re.search(r'Sink Input #(\d+)', block)
                        if m:
                            monitor_stream_ids.append(m.group(1))
            except Exception:
                pass

        # 3. Stream de Salida Principal (Micyn)
        stream_out = sd.OutputStream(
            samplerate=SAMPLERATE, device=out_device_id, channels=CHANNELS,
            callback=engine._audio_callback_out, blocksize=CHUNK_SIZE
        )
        streams.append(stream_out)
        stream_out.start()

        # Aislar y rutear
        main_stream_ids = app_context.platform_audio.post_stream_setup(
            stream_out, monitor_stream_ids
        )

        # En Linux: los streams de monitor deben ir al sink FÍSICO, nunca al virtual
        if app_context.os_system == 'Linux' and monitor_stream_ids:
            app_context.platform_audio.route_monitors(monitor_stream_ids)

        # 4. Stream de Entrada (Micrófono)
        stream_in = sd.InputStream(
            samplerate=SAMPLERATE, device=in_device_id, channels=CHANNELS,
            callback=engine._audio_callback_in, blocksize=CHUNK_SIZE
        )
        streams.append(stream_in)
        stream_in.start()

        # Mantener con vida hasta que cambie is_running
        while app_context.is_running:
            time.sleep(0.1)

    except Exception as e:
        app_context.is_running = False
        import tkinter as tk
        app_context.after(0, lambda: messagebox.showerror("Error de Audio", str(e)))
    finally:
        for s in reversed(streams):
            try:
                s.stop()
                s.close()
            except: pass
        app_context.after(0, app_context._stop_ui)
