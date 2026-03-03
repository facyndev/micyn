import queue
import numpy as np
from constants import CHANNELS, CHUNK_SIZE

class AudioEngine:
    def __init__(self, ring_buffer, monitor_queue=None, monitor_active=False,
                 is_running=lambda: True, monitor_delay_ref=None):
        self.ring_buffer = ring_buffer
        self.monitor_queue = monitor_queue
        self.monitor_active = monitor_active
        self.is_running_cb = is_running
        self.monitor_delay_ref = monitor_delay_ref  # BooleanVar o None
        
        # Compartido para vúmetros
        self.current_in_amp = 0.0
        self.current_out_amp = 0.0

    def _audio_callback_in(self, indata, frames, time, status):
        """Lee del micrófono, envía al monitoreo si está activo y escribe en el buffer circular."""
        if not self.is_running_cb():
            return
            
        if status:
            pass # Ignorar underruns menores por performance
            
        if self.monitor_active and self.monitor_queue is not None:
            # Enviar copia inmediata para monitoreo directo 0ms de delay
            try:
                self.monitor_queue.put_nowait(indata.copy())
            except queue.Full:
                pass

        # Para vúmetros de entrada (tomar rms)
        rms = np.sqrt(np.mean(indata**2))
        self.current_in_amp = max(self.current_in_amp, float(rms))

        self.ring_buffer.write(indata, frames)

    def _audio_callback_out(self, outdata, frames, time, status):
        """Lee del buffer (que ya tiene el retraso por el desplazamiento de punteros) hacia la salida."""
        if not self.is_running_cb():
            outdata.fill(0)
            return
            
        if status:
            pass

        data = self.ring_buffer.read(frames)
        
        # Para vúmetros de salida
        rms = np.sqrt(np.mean(data**2))
        self.current_out_amp = float(rms)
        
        outdata[:] = data

    def _monitor_callback_out(self, outdata, frames, time, status):
        """Consume del Queue para monitoreo inmediato (auriculares)."""
        if not self.is_running_cb():
            outdata.fill(0)
            return
        try:
            data = self.monitor_queue.get_nowait()
            # Ajustar tamaño si no coincide perfectamente (poco probable pero seguro)
            if len(data) < frames:
                outdata[:len(data)] = data
                outdata[len(data):].fill(0)
            elif len(data) > frames:
                outdata[:] = data[:frames]
            else:
                outdata[:] = data
        except queue.Empty:
            outdata.fill(0)

    def _monitor_delay_callback_out(self, outdata, frames, time, status):
        """Consume desde el ring_buffer para escuchar el audio YA retrasado.
        Respeta el estado dinámico del switch de la UI: si se desactiva, silencia."""
        if not self.is_running_cb():
            outdata.fill(0)
            return

        # Consultar el estado actual del switch (puede cambiar durante la sesión)
        if self.monitor_delay_ref is not None:
            try:
                if not self.monitor_delay_ref.get():
                    outdata.fill(0)
                    return
            except Exception:
                pass

        data = self.ring_buffer.read_monitor(frames)
        outdata[:] = data
