import numpy as np
import threading

class RingBuffer:
    def __init__(self, delay_seconds, fallback_samplerate=44100):
        self.delay_seconds = delay_seconds
        self.samplerate = fallback_samplerate
        self.buffer_size_frames = int(self.samplerate * delay_seconds)
        self.total_size = self.buffer_size_frames + self.samplerate
        self.data = None
        self.channels = 1
        
        # Punteros
        self.write_ptr = 0 # Inicializará desplazado cuando sepamos el samplerate exacto
        self.read_ptr = 0
        self.read_ptr_monitor = 0
        self.is_initialized = False
        
        self.lock = threading.Lock()

    def write(self, indata, frames):
        """Escribe un chunk completo manejando el encolado circular."""
        with self.lock:
            if not self.is_initialized:
                # Inicializamos el buffer con las especificaciones reales del hardware (WASAPI / ALSA dinámico)
                self.channels = indata.shape[1] if len(indata.shape) > 1 else 1
                
                # Asumimos que el samplerate verdadero empuja X frames por callback consistentemente
                # pero dependemos de delay_seconds y la app_context general. 
                # Usaremos el fallback_samplerate estático por ahora
                self.data = np.zeros((self.total_size, self.channels), dtype=np.float32)
                self.write_ptr = self.buffer_size_frames
                self.is_initialized = True

            # Si nos llega algo mono y estabamos en stereo, lo clonamos, o viceversa no debería ocurrir
            if indata.ndim == 2 and indata.shape[1] != self.channels:
                if indata.shape[1] == 1 and self.channels == 2:
                    indata = np.repeat(indata, 2, axis=1) # upmix mono to stereo
                elif indata.shape[1] == 2 and self.channels == 1:
                    indata = np.mean(indata, axis=1, keepdims=True) # downmix

            end_ptr = self.write_ptr + frames
            if end_ptr <= self.total_size:
                self.data[self.write_ptr:end_ptr] = indata
            else:
                first_part = self.total_size - self.write_ptr
                self.data[self.write_ptr:] = indata[:first_part]
                second_part = frames - first_part
                self.data[:second_part] = indata[first_part:]
            self.write_ptr = end_ptr % self.total_size

    def read(self, frames, out_channels=None) -> np.ndarray:
        """Lee el chunk desde el puntero principal. Soporta conversión de canales al vuelo."""
        if not self.is_initialized:
            c = out_channels if out_channels else 1
            return np.zeros((frames, c), dtype=np.float32)

        outdata = np.zeros((frames, self.channels), dtype=np.float32)
        with self.lock:
            end_ptr = self.read_ptr + frames
            if end_ptr <= self.total_size:
                outdata[:] = self.data[self.read_ptr:end_ptr]
                self.data[self.read_ptr:end_ptr] = 0.0
            else:
                first_part = self.total_size - self.read_ptr
                outdata[:first_part] = self.data[self.read_ptr:]
                self.data[self.read_ptr:] = 0.0
                
                second_part = frames - first_part
                outdata[first_part:] = self.data[:second_part]
                self.data[:second_part] = 0.0
                
            self.read_ptr = end_ptr % self.total_size

        return self._remix_channels(outdata, out_channels)

    def _remix_channels(self, data, out_channels):
        if out_channels is None or data.shape[1] == out_channels:
            return data
        if data.shape[1] == 1 and out_channels == 2:
            return np.repeat(data, 2, axis=1)
        elif data.shape[1] == 2 and out_channels == 1:
            return np.mean(data, axis=1, keepdims=True)
        return data[:, :out_channels]

    def read_monitor(self, frames, out_channels=None) -> np.ndarray:
        """Lee el chunk desde el puntero atrasado de monitoreo."""
        if not self.is_initialized:
            c = out_channels if out_channels else 1
            return np.zeros((frames, c), dtype=np.float32)

        outdata_mon = np.zeros((frames, self.channels), dtype=np.float32)
        with self.lock:
            end_ptr = self.read_ptr_monitor + frames
            if end_ptr <= self.total_size:
                outdata_mon[:] = self.data[self.read_ptr_monitor:end_ptr]
            else:
                first_part = self.total_size - self.read_ptr_monitor
                outdata_mon[:first_part] = self.data[self.read_ptr_monitor:]
                second_part = frames - first_part
                outdata_mon[first_part:] = self.data[:second_part]
                
            self.read_ptr_monitor = end_ptr % self.total_size
        return self._remix_channels(outdata_mon, out_channels)
