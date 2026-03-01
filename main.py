import customtkinter as ctk
import tkinter as tk
import sounddevice as sd
import numpy as np
import threading
import queue
import time
import platform
import subprocess
import os
from PIL import Image, ImageTk

__version__ = "1.0.0"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AudioDelayApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Micyn")
        try:
            self.attributes('-zoomed', True)
        except:
            self.state('zoomed')

        self.configure(fg_color="#09090B")

        # Animacion
        self.bars = []
        self.num_bars = 7
        self.current_amplitudes = [0] * self.num_bars
        self.target_amplitudes  = [0] * self.num_bars
        self.bar_canvas = None
        
        self.bars_out = []
        self.current_amplitudes_out = [0.0] * self.num_bars
        self.target_amplitudes_out  = [0.0] * self.num_bars
        self.bar_canvas_out = None

        # Audio config
        self.samplerate  = 44100
        self.channels    = 1
        self.chunk_size  = 2048

        # Ring buffer
        self.delay_seconds      = 60
        self.total_buffer_size  = 0
        self.ring_buffer        = None
        self.buffer_size_frames = 0
        self.write_ptr          = 0
        self.read_ptr           = 0
        self.read_ptr_monitor   = 0

        # Cola para monitor en tiempo real
        self.monitor_queue = queue.Queue(maxsize=20)

        # Streams
        self.is_running           = False
        self.audio_thread         = None
        self.stream_in            = None
        self.stream_out           = None
        self.stream_monitor_rt    = None
        self.stream_monitor_delay = None

        # Linux virtual cable IDs
        self.linux_module_sink_id     = None
        self.linux_module_virtual_id  = None
        self.linux_module_loopback_id = None
        self.linux_module_source_id   = None
        self.os_system = platform.system()

        self._cleanup_virtual_cable()

        try:
            pil_img  = Image.open("micyn_logo.jpg")
            pil_img.thumbnail((256, 256))
            icon_img = ImageTk.PhotoImage(pil_img)
            self.iconphoto(True, icon_img)
        except Exception as e:
            print("Logo no cargado como icono:", e)

        self._create_widgets()
        self._init_virtual_cable()
        self.after(500, self._populate_devices)

    # ─────────────────────────────────────────────
    #   CABLES VIRTUALES
    # ─────────────────────────────────────────────

    def _init_virtual_cable(self):
        if self.os_system == 'Linux':
            try:
                res = subprocess.run(
                    ["pactl", "load-module", "module-null-sink",
                     "sink_name=DelaySinkInternal",
                     "sink_properties=device.description='DelaySinkInternal'"],
                    check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_sink_id = res.stdout.strip()

                res = subprocess.run(
                    ["pactl", "load-module", "module-null-sink",
                     "sink_name=MicynOutput",
                     "sink_properties=device.description='MicynOutput'"],
                    check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_virtual_id = res.stdout.strip()

                res = subprocess.run(
                    ["pactl", "load-module", "module-loopback",
                     "source=DelaySinkInternal.monitor",
                     "sink=MicynOutput", "latency_msec=1"],
                    check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_loopback_id = res.stdout.strip()

                res = subprocess.run(
                    ["pactl", "load-module", "module-virtual-source",
                     "source_name=MicynMic",
                     "master=MicynOutput.monitor",
                     "source_properties=device.description='Micyn'"],
                    check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_source_id = res.stdout.strip()

                print("Cables virtuales OK. Selecciona 'Micyn' como mic en cualquier app.")

            except FileNotFoundError:
                print("PulseAudio/PipeWire no disponible.")
            except Exception as e:
                print(f"Error creando cables virtuales: {e}")

    def _cleanup_virtual_cable(self):
        if self.os_system == 'Linux':
            try:
                res = subprocess.run(['pactl', 'list', 'short', 'modules'],
                                     stdout=subprocess.PIPE, text=True)
                for line in res.stdout.splitlines():
                    if any(k in line for k in ['DelaySinkInternal', 'MicynOutput', 'MicynMic',
                                               'Micyn', 'Microfono_OBS_Retraso']):
                        mod_id = line.split()[0]
                        subprocess.run(['pactl', 'unload-module', mod_id])
                        print(f"Modulo {mod_id} eliminado.")
            except Exception as e:
                print(f"Error limpiando cables virtuales: {e}")

    # ─────────────────────────────────────────────
    #   CALLBACKS DE AUDIO
    # ─────────────────────────────────────────────

    def _audio_callback_in(self, indata, frames, time_info, status):
        """
        Unico punto de captura del microfono fisico.
        Hace DOS cosas:
          1. Escribe en el ring buffer → fuente del delay para la salida Micyn.
          2. Copia en monitor_queue  → para el monitor en tiempo real (auriculares).
        """
        # Escribir en ring buffer
        remaining = self.total_buffer_size - self.write_ptr
        if frames <= remaining:
            self.ring_buffer[self.write_ptr:self.write_ptr + frames] = indata
        else:
            self.ring_buffer[self.write_ptr:self.total_buffer_size] = indata[:remaining]
            self.ring_buffer[0:frames - remaining]                  = indata[remaining:]
        self.write_ptr = (self.write_ptr + frames) % self.total_buffer_size

        # Evitar desborde del puntero de salida Micyn
        if (self.write_ptr - self.read_ptr) % self.total_buffer_size > self.buffer_size_frames:
            self.read_ptr = (self.write_ptr - self.buffer_size_frames) % self.total_buffer_size

        # Evitar desborde del puntero del monitor-delay
        if (self.write_ptr - self.read_ptr_monitor) % self.total_buffer_size > self.buffer_size_frames:
            self.read_ptr_monitor = (self.write_ptr - self.buffer_size_frames) % self.total_buffer_size

        # Audio crudo para monitor en tiempo real
        try:
            self.monitor_queue.put_nowait(indata.copy())
        except queue.Full:
            pass

        # Vumetro
        rms      = np.sqrt(np.mean(indata ** 2))
        db       = 20 * np.log10(rms + 1e-6)
        norm_amp = max(0.0, min(1.0, (db + 40) / 40))
        for i in range(self.num_bars):
            dist   = abs(i - 3)
            weight = max(0.2, 1.0 - dist * 0.25)
            ripple = np.sin((time.time() * 5) + i) * 0.1
            self.target_amplitudes[i] = float(
                max(0.0, min(1.0, norm_amp * weight + ripple * norm_amp)))

    def _audio_callback_out(self, outdata, frames, time_info, status):
        """
        SALIDA MICYN — siempre activa, siempre con delay.
        Lee del ring buffer y escribe en DelaySinkInternal.
        """
        available = (self.write_ptr - self.read_ptr) % self.total_buffer_size
        if available >= frames:
            remaining = self.total_buffer_size - self.read_ptr
            if frames <= remaining:
                outdata[:] = self.ring_buffer[self.read_ptr:self.read_ptr + frames]
            else:
                outdata[:remaining] = self.ring_buffer[self.read_ptr:self.total_buffer_size]
                outdata[remaining:] = self.ring_buffer[0:frames - remaining]
            self.read_ptr = (self.read_ptr + frames) % self.total_buffer_size
        else:
            outdata[:] = np.zeros((frames, self.channels), dtype=np.float32)

        # Vumetro de salida (después de aplicar el delay / silencio)
        rms = np.sqrt(np.mean(outdata ** 2))
        db = 20 * np.log10(rms + 1e-6)
        norm_amp = max(0.0, min(1.0, (db + 40) / 40))
        
        if norm_amp < 0.01:
            # Modo Loading / En Espera
            self.is_waiting_audio = True
            for i in range(self.num_bars):
                self.target_amplitudes_out[i] = 0.0
        else:
            # Modo Activo
            self.is_waiting_audio = False
            for i in range(self.num_bars):
                dist = abs(i - 3)
                weight = max(0.2, 1.0 - dist * 0.25)
                ripple = np.sin((time.time() * 5) + i) * 0.1
                self.target_amplitudes_out[i] = float(
                    max(0.0, min(1.0, norm_amp * weight + ripple * norm_amp)))

    # ─────────────────────────────────────────────
    #   AUDIO LOOP
    # ─────────────────────────────────────────────

    def _get_default_physical_sink(self):
        """Devuelve el nombre del dispositivo sink por defecto al que apunta PipeWire."""
        try:
            res = subprocess.run(['pactl', 'get-default-sink'], 
                                 stdout=subprocess.PIPE, text=True)
            return res.stdout.strip()
        except:
            return None

    def _move_my_sink_inputs(self, target_sink, ignore_ids=None):
        """
        Busca los sink-inputs bajo el PID actual y los mueve al target_sink especificado.
        Ignora los IDs presentes en la lista ignore_ids.
        Retorna la lista de sink-input IDs que fueron movidos exitosamente.
        """
        if ignore_ids is None:
            ignore_ids = []
            
        moved_ids = []
        try:
            pid = str(os.getpid())
            res = subprocess.run(['pactl', 'list', 'sink-inputs'],
                                 stdout=subprocess.PIPE, text=True)

            # Dividir en bloques por sink-input
            import re
            blocks = re.split(r'\n(?=Entrada del destino #|Sink Input #)', res.stdout)

            for block in blocks:
                # Comprobar si el bloque pertenece al proceso actual (PID oFallback nombre python)
                if (f'application.process.id = "{pid}"' in block or 
                    ('python3' in block and 'mono' in block and '44100' in block)):
                    
                    m = re.search(r'(?:Entrada del destino|Sink Input) #(\d+)', block)
                    if m:
                        sink_input_id = m.group(1)
                        if sink_input_id not in ignore_ids:
                            result = subprocess.run(
                                ['pactl', 'move-sink-input', sink_input_id, target_sink],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                            
                            if result.returncode == 0:
                                print(f"  OK: sink-input {sink_input_id} → {target_sink}")
                                moved_ids.append(sink_input_id)
                            else:
                                print(f"  ERROR moviendo {sink_input_id}: {result.stderr.strip()}")

            if not moved_ids:
                print(f"ADVERTENCIA: No se movieron sink-inputs hacia {target_sink}.")

        except Exception as e:
            print(f"Error en _move_my_sink_inputs: {e}")
            
        return moved_ids

    def _get_sink_device_index(self, sink_name):
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if sink_name.lower() in d['name'].lower() and d['max_output_channels'] > 0:
                return i, False
        for i, d in enumerate(devices):
            if d['name'].lower() in ['pipewire', 'pulse'] and d['max_output_channels'] > 0:
                print(f"'{sink_name}' no visible en ALSA, usando '{d['name']}' + PULSE_SINK.")
                return i, True
        return None, False

    def _audio_loop(self):
        in_name_sel = self.input_combobox.get()

        in_idx = -1
        for i, d in enumerate(self.inputs):
            if self._clean_device_name(d['name']).startswith(in_name_sel.replace('...', '')):
                in_idx = i
                break

        if in_idx == -1:
            print("Error: Dispositivo de entrada no encontrado.")
            self.after(0, self.stop)
            return

        in_device      = self.inputs[in_idx]['original_index']
        out_device     = None
        needs_redirect = False

        if self.os_system == 'Linux':
            out_device, needs_redirect = self._get_sink_device_index('DelaySinkInternal')
            if out_device is None:
                print("Error: No se encontro backend de audio compatible.")
                self.after(0, self.stop)
                return
        else:
            for d in self.outputs:
                if "Virtual" in d['name'] or "CABLE" in d['name']:
                    out_device = d['original_index']
                    break
            if out_device is None and self.outputs:
                out_device = self.outputs[0]['original_index']
            if out_device is None:
                print("Error: No se encontro dispositivo de salida.")
                self.after(0, self.stop)
                return

        # Inicializar buffer y punteros
        self.ring_buffer.fill(0)
        self.write_ptr        = self.buffer_size_frames
        self.read_ptr         = 0
        self.read_ptr_monitor = 0

        # Vaciar cola
        while not self.monitor_queue.empty():
            try: self.monitor_queue.get_nowait()
            except: break

        # Leer preferencias ANTES de entrar al hilo
        monitor_rt_enabled    = self.monitor_var.get()
        monitor_delay_enabled = self.monitor_delay_var.get()
        default_out           = sd.default.device[1]

        self.stream_in            = None
        self.stream_out           = None
        self.stream_monitor_rt    = None
        self.stream_monitor_delay = None

        try:
            # ── 1. Captura del microfono fisico ──
            self.stream_in = sd.InputStream(
                device=in_device, samplerate=self.samplerate,
                blocksize=self.chunk_size, channels=self.channels,
                dtype=np.float32, callback=self._audio_callback_in)

            # ── 2. Salida con delay → DelaySinkInternal (SIEMPRE ACTIVA) ──
            # sounddevice/ALSA ignora PULSE_SINK, así que creamos el stream
            # apuntando al backend 'pipewire' (índice 15) y luego movemos
            # el sink-input al destino correcto con pactl move-sink-input.
            self.stream_out = sd.OutputStream(
                device=out_device, samplerate=self.samplerate,
                blocksize=self.chunk_size, channels=self.channels,
                dtype=np.float32, callback=self._audio_callback_out)

            # Arrancar ANTES de mover, porque el sink-input no existe hasta
            # que el stream está activo.
            self.stream_out.start()
            time.sleep(0.3)  # darle tiempo a PipeWire para registrar el stream

            # Mover el sink-input de python3 a DelaySinkInternal y registrar el ID
            main_stream_ids = []
            physical_sink_name = None
            if self.os_system == 'Linux':
                physical_sink_name = self._get_default_physical_sink()
                main_stream_ids = self._move_my_sink_inputs('DelaySinkInternal')

            # ── 3. Monitor en tiempo real (opcional) ──
            # Lee de monitor_queue → no necesita un segundo InputStream
            if monitor_rt_enabled:
                self.monitor_accum = np.zeros((0, self.channels), dtype=np.float32)

                def _cb_monitor_rt(outdata, frames, time_info, status):
                    # Rellenar acumulador si nos falta audio
                    while len(self.monitor_accum) < frames:
                        try:
                            chunk = self.monitor_queue.get_nowait()
                            self.monitor_accum = np.vstack((self.monitor_accum, chunk))
                        except queue.Empty:
                            break
                    
                    # Consumir del acumulador lo que la placa pide (frames)
                    if len(self.monitor_accum) >= frames:
                        outdata[:] = self.monitor_accum[:frames]
                        self.monitor_accum = self.monitor_accum[frames:]
                    else:
                        outdata[:len(self.monitor_accum)] = self.monitor_accum
                        outdata[len(self.monitor_accum):] = 0
                        self.monitor_accum = np.zeros((0, self.channels), dtype=np.float32)

                self.stream_monitor_rt = sd.OutputStream(
                    device=default_out, samplerate=self.samplerate,
                    blocksize=self.chunk_size, channels=self.channels,
                    dtype=np.float32, callback=_cb_monitor_rt)

            # ── 4. Monitor con delay (opcional) ──
            # Lee del ring buffer con su propio puntero independiente
            if monitor_delay_enabled:
                def _cb_monitor_delay(outdata, frames, time_info, status):
                    available = (self.write_ptr - self.read_ptr_monitor) % self.total_buffer_size
                    if available >= frames:
                        remaining = self.total_buffer_size - self.read_ptr_monitor
                        if frames <= remaining:
                            outdata[:] = self.ring_buffer[self.read_ptr_monitor:self.read_ptr_monitor + frames]
                        else:
                            outdata[:remaining] = self.ring_buffer[self.read_ptr_monitor:self.total_buffer_size]
                            outdata[remaining:]  = self.ring_buffer[0:frames - remaining]
                        self.read_ptr_monitor = (self.read_ptr_monitor + frames) % self.total_buffer_size
                    else:
                        outdata[:] = np.zeros((frames, self.channels), dtype=np.float32)

                self.stream_monitor_delay = sd.OutputStream(
                    device=default_out, samplerate=self.samplerate,
                    blocksize=self.chunk_size, channels=self.channels,
                    dtype=np.float32, callback=_cb_monitor_delay)

            # ── Arrancar Monitores ──
            self.stream_in.start()
            if self.stream_monitor_rt:    self.stream_monitor_rt.start()
            if self.stream_monitor_delay: self.stream_monitor_delay.start()

            # Forzar los monitores hacia el dispositivo de salida físico (ej. auriculares)
            if self.os_system == 'Linux' and physical_sink_name and (monitor_rt_enabled or monitor_delay_enabled):
                time.sleep(0.3) # Esperar al registro de PipeWire
                self._move_my_sink_inputs(physical_sink_name, ignore_ids=main_stream_ids)

            print("Activo: Mic → ring buffer → DelaySinkInternal → MicynMic (siempre con delay)")
            if monitor_rt_enabled:    print("  Monitor RT: ON    → escuchas tu voz sin delay en auriculares")
            if monitor_delay_enabled: print("  Monitor Delay: ON → escuchas tu voz con delay en auriculares")

            while self.is_running:
                time.sleep(0.5)

        except Exception as e:
            self.after(0, self.stop)
            print(f"Error streams: {e}")
        finally:
            for stream in [self.stream_in, self.stream_out,
                           self.stream_monitor_rt, self.stream_monitor_delay]:
                if stream:
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
            self.stream_in = self.stream_out = self.stream_monitor_rt = self.stream_monitor_delay = None

    # ─────────────────────────────────────────────
    #   CONTROLES
    # ─────────────────────────────────────────────

    def start(self):
        if not self.input_combobox.get():
            return

        delay_s = self._get_selected_delay()
        if delay_s == -1:
            self.status_lbl.configure(text="ERROR: TIEMPO INVALIDO", text_color="red")
            self.status_dot.configure(text_color="red")
            return

        self.delay_seconds      = delay_s
        self.buffer_size_frames = int(self.samplerate * self.delay_seconds)
        self.total_buffer_size  = self.buffer_size_frames + int(self.samplerate)
        self.ring_buffer        = np.zeros((self.total_buffer_size, self.channels), dtype=np.float32)

        self.is_running = True
        self.start_btn.configure(state="disabled", fg_color="#222222", text=" Procesando...")
        self.input_combobox.configure(state="disabled")
        self.time_combobox.configure(state="disabled")
        self.custom_time_entry.configure(state="disabled")
        self.monitor_chk.configure(state="disabled")
        self.monitor_delay_chk.configure(state="disabled")
        self.stop_btn.configure(state="normal", text_color="#000000", fg_color="#FFFFFF")
        self.status_dot.configure(text_color="#4CAF50")
        self.status_lbl.configure(text=f"ESTADO: ATRASANDO {self.delay_seconds}S")

        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.audio_thread.start()

    def stop(self):
        self.is_running = False

        for i in range(self.num_bars):
            self.target_amplitudes[i] = 0.0
            self.target_amplitudes_out[i] = 0.0

        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=1.0)

        self.start_btn.configure(state="normal", fg_color="#4570F7", text="▶  Iniciar retraso de audio")
        self.time_combobox.configure(state="readonly")
        
        # Validar la habilitación del Custom Entry en función del valor actual
        self._on_time_change(self.time_combobox.get())

        self.monitor_chk.configure(state="normal")
        self.monitor_delay_chk.configure(state="normal")
        self.stop_btn.configure(state="disabled", text_color="#7A8084", fg_color="#27272A")
        self.status_dot.configure(text_color="#A0AEC0")
        self.status_lbl.configure(text="ESTADO: APAGADO")

    # ─────────────────────────────────────────────
    #   UI HELPERS
    # ─────────────────────────────────────────────

    def _on_time_change(self, choice):
        if choice == "Personalizado (Segundos)":
            self.custom_time_entry.configure(state="normal", fg_color="#18181A", border_color="#4570F7")
        else:
            self.custom_time_entry.configure(state="disabled", fg_color="#09090B")

    def _get_selected_delay(self):
        choice = self.time_combobox.get()
        if choice == "30 Segundos":  return 30
        if choice == "1 Minuto":     return 60
        if choice == "2 Minutos":    return 120
        if choice == "5 Minutos":    return 300
        if choice == "Personalizado (Segundos)":
            try:   return max(1, int(self.custom_time_entry.get()))
            except: return -1
        return 60

    def _clean_device_name(self, name):
        if ',' in name:    name = name.split(',')[0]
        if '(hw:' in name: name = name.split('(hw:')[0].strip()
        if name.lower() == 'default':             name = 'Dispositivo Principal (Predeterminado)'
        if name.lower() in ['pipewire', 'pulse']: name = f'Servidor de Audio ({name})'
        if len(name) > 40: name = name[:37] + "..."
        return name

    def _animate_bars(self):
        if self.is_running:
            for i in range(self.num_bars):
                # Micrófono
                current    = self.current_amplitudes[i]
                target     = self.target_amplitudes[i]
                lerp_speed = 0.4 if target > current else 0.15
                self.current_amplitudes[i] = current + (target - current) * lerp_speed
                height = max(6, int(4 + self.current_amplitudes[i] * 46))
                y_pos = 30 - height // 2
                self.bars[i].configure(height=height)
                self.bars[i].place(y=y_pos)
                    
                # Salida Micyn
                c_out = self.current_amplitudes_out[i]
                t_out = self.target_amplitudes_out[i]
                l_speed_out = 0.4 if t_out > c_out else 0.15
                self.current_amplitudes_out[i] = c_out + (t_out - c_out) * l_speed_out
                h_out = max(6, int(4 + self.current_amplitudes_out[i] * 46))
                y_pos_o = 30 - h_out // 2
                self.bars_out[i].configure(height=h_out)
                self.bars_out[i].place(y=y_pos_o)
                
            # Gestionar indicador de Espera
            if getattr(self, "is_waiting_audio", False):
                self.vumeter_out_container.place_forget()
                # Animación parpadeo leve (opcional)
                if int(time.time() * 3) % 2 == 0:
                    self.waiting_label_out.place(relx=0.5, rely=0.5, anchor="center")
                else:
                    self.waiting_label_out.place_forget()
            else:
                self.waiting_label_out.place_forget()
                self.vumeter_out_container.place(relx=0.5, rely=0.5, anchor="center")
                
        else:
            self.waiting_label_out.place_forget()
            self.vumeter_out_container.place(relx=0.5, rely=0.5, anchor="center")
            
            for i in range(self.num_bars):
                # Descenso suave micrófono
                if self.current_amplitudes[i] > 0.01:
                    self.current_amplitudes[i] *= 0.8
                    height = max(6, int(4 + self.current_amplitudes[i] * 46))
                    y_pos = 30 - height // 2
                    self.bars[i].configure(height=height)
                    self.bars[i].place(y=y_pos)
                
                # Descenso suave salida
                if self.current_amplitudes_out[i] > 0.01:
                    self.current_amplitudes_out[i] *= 0.8
                    h_out = max(6, int(4 + self.current_amplitudes_out[i] * 46))
                    y_pos_o = 30 - h_out // 2
                    self.bars_out[i].configure(height=h_out)
                    self.bars_out[i].place(y=y_pos_o)
        self.after(16, self._animate_bars)

    def _show_manual(self, event=None):
        win = ctk.CTkToplevel(self)
        win.title("Manual de uso")
        win.geometry("500x400")
        win.configure(fg_color="#09090B")
        win.attributes("-topmost", True)
        win.update_idletasks()
        x = self.winfo_x() + self.winfo_width()  // 2 - 250
        y = self.winfo_y() + self.winfo_height() // 2 - 200
        win.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            win, text="Como usar Micyn",
            font=ctk.CTkFont(family="Google Sans", size=18, weight="bold"),
            text_color="#FFFFFF"
        ).pack(pady=(20, 15), padx=20)

        info = (
            "1. En Micyn:\n"
            "   - Selecciona tu microfono fisico en 'MICROFONO (ENTRADA)'.\n"
            "   - Elige el tiempo de retraso.\n"
            "   - Presiona Iniciar.\n\n"
            "2. En la otra app (OBS, Discord, Meet, Zoom...):\n"
            "   - Ve a Configuracion > Audio > Microfono.\n"
            "   - Selecciona 'Micyn'.\n\n"
            "3. Monitores (solo para tus auriculares, NO afectan la salida Micyn):\n"
            "   - Sin delay  → escuchas tu voz en tiempo real para guiarte.\n"
            "   - Con delay  → escuchas tu voz con el delay para verificar\n"
            "                  como llega a la otra aplicacion.\n\n"
            "La salida 'Micyn' SIEMPRE entrega el audio con el delay configurado,\n"
            "independientemente de que opcion de monitor uses."
        )

        tb = ctk.CTkTextbox(
            win, font=ctk.CTkFont(family="Google Sans", size=13),
            fg_color="#18181A", text_color="#A0AEC0",
            wrap="word", corner_radius=10, border_width=1, border_color="#27272A")
        tb.pack(expand=True, fill="both", padx=20, pady=(0, 20))
        tb.insert("1.0", info)
        tb.configure(state="disabled")

    def _populate_devices(self):
        try:
            devices = sd.query_devices()
            exclude = ['iec958', 'spdif', 'surround', 'dmix', 'dsnoop', 'sysdefault',
                       'front:', 'rear:', 'center_lfe',
                       'delaysinkinternal', 'micynoutput', 'micynmic', 'micyn']

            self.inputs  = []
            self.outputs = []

            for i, d in enumerate(devices):
                d['original_index'] = i
                nl = d['name'].lower()
                if any(k in nl for k in exclude):
                    continue
                if d['max_input_channels']  > 0: self.inputs.append(d)
                if d['max_output_channels'] > 0: self.outputs.append(d)

            in_names = [self._clean_device_name(d['name']) for d in self.inputs]
            self.input_combobox.configure(values=in_names)

            default_in  = sd.default.device[0]
            devices_all = sd.query_devices()
            for i, dev in enumerate(self.inputs):
                if dev['original_index'] == default_in or \
                   dev['name'] == devices_all[default_in]['name']:
                    self.input_combobox.set(in_names[i])
                    break
            else:
                if self.inputs:
                    self.input_combobox.set(in_names[0])

        except Exception as e:
            print(f"No se pudieron cargar dispositivos: {e}")

    # ─────────────────────────────────────────────
    #   WIDGETS
    # ─────────────────────────────────────────────

    def _create_widgets(self):
        sub_font   = ctk.CTkFont(family="Google Sans", size=15)
        label_font = ctk.CTkFont(family="Google Sans", size=12, weight="bold")
        combo_font = ctk.CTkFont(family="Google Sans", size=14)

        def _bind_combo_open(cmb):
            """Vincula el clic genérico en la caja para abrir el drop-down si no está deshabilitado."""
            def force_open(e):
                if cmb.cget("state") != "disabled":
                    cmb._clicked()
            cmb.bind("<Button-1>", force_open)
            if hasattr(cmb, "_entry"):
                cmb._entry.bind("<Button-1>", force_open)

        # Logo
        try:
            from PIL import ImageDraw
            logo_pil  = Image.open("micyn_logo.jpg").convert("RGBA")
            logo_size = 100
            logo_pil  = logo_pil.resize((logo_size, logo_size), Image.LANCZOS)
            mask = Image.new("L", (logo_size, logo_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle((0, 0, logo_size, logo_size), radius=20, fill=255)
            logo_pil.putalpha(mask)
            logo_ctk = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil,
                                    size=(logo_size, logo_size))
            ctk.CTkLabel(self, text="", image=logo_ctk).pack(pady=(25, 5))
        except Exception as e:
            ctk.CTkLabel(self, text="Micyn",
                         font=ctk.CTkFont(family="Google Sans", size=22, weight="bold"),
                         text_color="#FFFFFF").pack(pady=(25, 5))
            print("Logo no encontrado:", e)

        # Creditos
        desc_frame = ctk.CTkFrame(self, fg_color="transparent")
        desc_frame.pack(pady=(0, 5))
        ctk.CTkLabel(desc_frame, text="Retrasar audio - ",
                     font=sub_font, text_color="#A0AEC0").pack(side="left")
        lnk = ctk.CTkLabel(desc_frame, text="@facyndev.",
                            font=sub_font, text_color="#4570F7", cursor="hand2")
        lnk.pack(side="left")
        lnk.bind("<Button-1>", lambda e: __import__("webbrowser").open("https://www.facyn.xyz"))

        # Manual
        hf = ctk.CTkFrame(self, fg_color="transparent")
        hf.pack(pady=(0, 20))
        hl = ctk.CTkLabel(hf, text="? Manual de uso",
                          font=sub_font, text_color="#A0AEC0", cursor="hand2")
        hl.pack()
        hl.bind("<Enter>",    lambda e: hl.configure(text_color="#FFFFFF"))
        hl.bind("<Leave>",    lambda e: hl.configure(text_color="#A0AEC0"))
        hl.bind("<Button-1>", self._show_manual)

        # Entrada
        ctk.CTkLabel(self, text="MICROFONO (ENTRADA)",
                     font=label_font, text_color="#A0AEC0").pack(anchor="w", padx=40, pady=(0, 5))
        self.input_combobox = ctk.CTkComboBox(
            self, width=280, height=45, corner_radius=10,
            font=combo_font, dropdown_font=combo_font,
            fg_color="#18181A", border_width=1, border_color="#27272A",
            button_color="#18181A", button_hover_color="#27272A",
            dropdown_fg_color="#18181A", text_color="#FFFFFF", state="readonly")
        self.input_combobox.pack(padx=40, pady=(0, 20), fill="x")
        _bind_combo_open(self.input_combobox)

        # Tiempo
        ctk.CTkLabel(self, text="TIEMPO DE RETRASO",
                     font=label_font, text_color="#A0AEC0").pack(anchor="w", padx=40, pady=(0, 5))
        self.time_combobox = ctk.CTkComboBox(
            self, width=280, height=45, corner_radius=10,
            font=combo_font, dropdown_font=combo_font,
            fg_color="#18181A", border_width=1, border_color="#27272A",
            button_color="#18181A", button_hover_color="#27272A",
            values=["30 Segundos", "1 Minuto", "2 Minutos", "5 Minutos", "Personalizado (Segundos)"],
            dropdown_fg_color="#18181A", text_color="#FFFFFF", state="readonly",
            command=self._on_time_change)
        self.time_combobox.pack(padx=40, pady=(0, 5), fill="x")
        self.time_combobox.set("1 Minuto")
        _bind_combo_open(self.time_combobox)

        self.custom_time_entry = ctk.CTkEntry(
            self, width=280, height=40, corner_radius=10,
            font=combo_font, placeholder_text="Ej: 15 (segundos)",
            border_color="#27272A")
        self.custom_time_entry.pack(padx=40, pady=(0, 15), fill="x")
        self.custom_time_entry.configure(state="disabled", fg_color="#09090B")

        # Monitores
        ctk.CTkLabel(self, text="ESCUCHAR MI PROPIA VOZ (solo auriculares, no afecta la salida Micyn)",
                     font=label_font, text_color="#A0AEC0").pack(anchor="w", padx=40, pady=(0, 5))

        mc = ctk.CTkFrame(self, fg_color="transparent")
        mc.pack(padx=40, pady=(0, 20), fill="x")

        mf1 = ctk.CTkFrame(mc, height=60, fg_color="#18181A", corner_radius=12)
        mf1.pack_propagate(False)
        mf1.pack(side="left", expand=True, fill="both", padx=(0, 5))
        self.monitor_var = ctk.BooleanVar(value=False)
        self.monitor_chk = ctk.CTkSwitch(
            mf1, text="Sin delay", variable=self.monitor_var,
            font=ctk.CTkFont(family="Google Sans", size=12, weight="bold"),
            text_color="#FFFFFF", progress_color="#4570F7",
            button_color="#FFFFFF", button_hover_color="#3F3F46",
            fg_color="#27272A", switch_width=36, switch_height=18)
        self.monitor_chk.pack(expand=True, padx=10, pady=10)

        mf2 = ctk.CTkFrame(mc, height=60, fg_color="#18181A", corner_radius=12)
        mf2.pack_propagate(False)
        mf2.pack(side="right", expand=True, fill="both", padx=(5, 0))
        self.monitor_delay_var = ctk.BooleanVar(value=False)
        self.monitor_delay_chk = ctk.CTkSwitch(
            mf2, text="Con delay", variable=self.monitor_delay_var,
            font=ctk.CTkFont(family="Google Sans", size=12, weight="bold"),
            text_color="#FFFFFF", progress_color="#4570F7",
            button_color="#FFFFFF", button_hover_color="#3F3F46",
            fg_color="#27272A", switch_width=36, switch_height=18)
        self.monitor_delay_chk.pack(expand=True, padx=10, pady=10)

        # Vumetros Container (Lado a Lado)
        vumeters_container = ctk.CTkFrame(self, fg_color="transparent")
        vumeters_container.pack(padx=40, pady=(0, 20), fill="x")

        # Vumetro: Entrada
        vu_in_frame = ctk.CTkFrame(vumeters_container, fg_color="transparent")
        vu_in_frame.pack(side="left", expand=True, fill="both", padx=(0, 5))
        ctk.CTkLabel(vu_in_frame, text="ENTRADA MIC", font=label_font, text_color="#A0AEC0").pack(anchor="center", pady=(0, 5))
        abg_in = ctk.CTkFrame(vu_in_frame, fg_color="#18181A", corner_radius=15, height=80)
        abg_in.pack_propagate(False)
        abg_in.pack(fill="x")
        self.vumeter_in_container = ctk.CTkFrame(abg_in, width=130, height=60, fg_color="transparent")
        self.vumeter_in_container.place(relx=0.5, rely=0.5, anchor="center")

        # Vumetro: Salida Virtual
        vu_out_frame = ctk.CTkFrame(vumeters_container, fg_color="transparent")
        vu_out_frame.pack(side="right", expand=True, fill="both", padx=(5, 0))
        ctk.CTkLabel(vu_out_frame, text="SALIDA MICYN", font=label_font, text_color="#A0AEC0").pack(anchor="center", pady=(0, 5))
        abg_out = ctk.CTkFrame(vu_out_frame, fg_color="#18181A", corner_radius=15, height=80)
        abg_out.pack_propagate(False)
        abg_out.pack(fill="x")
        self.vumeter_out_container = ctk.CTkFrame(abg_out, width=130, height=60, fg_color="transparent")
        self.vumeter_out_container.place(relx=0.5, rely=0.5, anchor="center")
        
        self.waiting_label_out = ctk.CTkLabel(
            abg_out, text="ESPERANDO...", 
            font=ctk.CTkFont(family="Google Sans", size=12, weight="bold"),
            text_color="#F59E0B"
        )

        bar_width = 6
        spacing   = 6
        total_w   = self.num_bars * bar_width + (self.num_bars - 1) * spacing
        offset_x  = (130 - total_w) // 2

        self.bars.clear()
        self.bars_out.clear()

        # Dibujar barras de Entrada (Azul) y Salida (Verde) con CTkFrame renderizado
        for i in range(self.num_bars):
            xc = offset_x + i * (bar_width + spacing)
            
            bar_in = ctk.CTkFrame(self.vumeter_in_container, width=bar_width, height=6, corner_radius=3, fg_color="#4570F7")
            bar_in.place(x=xc, y=27)
            self.bars.append(bar_in)
            
            bar_out = ctk.CTkFrame(self.vumeter_out_container, width=bar_width, height=6, corner_radius=3, fg_color="#10B981")
            bar_out.place(x=xc, y=27)
            self.bars_out.append(bar_out)

        self._animate_bars()

        # Botones
        btn_font = ctk.CTkFont(family="Google Sans", size=17, weight="bold")
        self.start_btn = ctk.CTkButton(
            self, text="▶  Iniciar retraso de audio",
            font=btn_font, width=280, height=50, corner_radius=25,
            fg_color="#4570F7", hover_color="#2F52CC", text_color="#FFFFFF",
            command=self.start)
        self.start_btn.pack(padx=40, pady=(0, 15), fill="x")

        self.stop_btn = ctk.CTkButton(
            self, text="■  Detener",
            font=btn_font, width=280, height=50, corner_radius=25,
            fg_color="#27272A", hover_color="#E0E0E0", text_color="#7A8084",
            state="disabled", command=self.stop)
        self.stop_btn.pack(padx=40, pady=(0, 30), fill="x")

        # Estado
        ctk.CTkFrame(self, height=1, fg_color="#27272A").pack(pady=(10, 20), fill="x", padx=40)
        self.status_frame = ctk.CTkFrame(self, fg_color="#09090B", corner_radius=15, height=50)
        self.status_frame.pack(pady=(0, 10))
        self.status_dot = ctk.CTkLabel(
            self.status_frame, text="●", text_color="#A0AEC0",
            font=ctk.CTkFont(size=22))
        self.status_dot.pack(side="left", padx=(20, 10))
        self.status_lbl = ctk.CTkLabel(
            self.status_frame, text="ESTADO: DETENIDO",
            font=ctk.CTkFont(family="Google Sans", size=20, weight="bold"),
            text_color="#A0AEC0")
        self.status_lbl.pack(side="left", padx=(0, 25))


if __name__ == "__main__":
    app = AudioDelayApp()

    def on_closing():
        app.stop()
        app._cleanup_virtual_cable()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()