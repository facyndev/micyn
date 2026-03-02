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
        is_running=lambda: app_context.is_running
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

        # 3. Stream de Salida Principal (Micyn)
        stream_out = sd.OutputStream(
            samplerate=SAMPLERATE, device=out_device_id, channels=CHANNELS,
            callback=engine._audio_callback_out, blocksize=CHUNK_SIZE
        )
        streams.append(stream_out)
        stream_out.start()

        # ---- Ruteos Específicos del OS POST-arranque de Salida ----
        main_stream_ids = []
        if app_context.os_system == 'Linux':
            import subprocess
            try:
                out = subprocess.check_output(
                    ["pactl", "list", "sink-inputs"], 
                    env=dict(os.environ, LC_ALL="C")
                ).decode()
                # Filtrar solo el último PID por si hay latencias (el último es el stream de salida base)
                # La lógica final se delega a PlatformAudio
            except: pass
            
        main_stream_ids = app_context.platform_audio.post_stream_setup(stream_out, main_stream_ids)
        
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
