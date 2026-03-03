import numpy as np
import threading

class RingBuffer:
    def __init__(self, delay_seconds, samplerate, channels):
        self.buffer_size_frames = int(samplerate * delay_seconds)
        self.total_size = self.buffer_size_frames + samplerate  # Memoria extra para lectura/escritura segura
        self.data = np.zeros((self.total_size, channels), dtype=np.float32)
        
        # Punteros
        self.write_ptr = self.buffer_size_frames
        self.read_ptr = 0
        self.read_ptr_monitor = 0
        
        self.lock = threading.Lock()

    def write(self, indata, frames):
        """Escribe un chunk completo manejando el encolado circular."""
        with self.lock:
            end_ptr = self.write_ptr + frames
            if end_ptr <= self.total_size:
                self.data[self.write_ptr:end_ptr] = indata
            else:
                first_part = self.total_size - self.write_ptr
                self.data[self.write_ptr:] = indata[:first_part]
                second_part = frames - first_part
                self.data[:second_part] = indata[first_part:]
            self.write_ptr = end_ptr % self.total_size

    def read(self, frames) -> np.ndarray:
        """Lee el chunk desde el puntero principal (con delay completo)."""
        outdata = np.zeros((frames, self.data.shape[1]), dtype=np.float32)
        with self.lock:
            end_ptr = self.read_ptr + frames
            if end_ptr <= self.total_size:
                outdata[:] = self.data[self.read_ptr:end_ptr]
                # Limpiar la data ya leída para evitar basura ("ghosting")
                self.data[self.read_ptr:end_ptr] = 0.0
            else:
                first_part = self.total_size - self.read_ptr
                outdata[:first_part] = self.data[self.read_ptr:]
                self.data[self.read_ptr:] = 0.0
                
                second_part = frames - first_part
                outdata[first_part:] = self.data[:second_part]
                self.data[:second_part] = 0.0
                
            self.read_ptr = end_ptr % self.total_size
        return outdata

    def read_monitor(self, frames) -> np.ndarray:
        """Lee el chunk desde el puntero atrasado de monitoreo."""
        outdata_mon = np.zeros((frames, self.data.shape[1]), dtype=np.float32)
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
        return outdata_mon
