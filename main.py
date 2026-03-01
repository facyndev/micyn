import customtkinter as ctk
import tkinter as tk
import sounddevice as sd
import numpy as np
import threading
import time
import sys
import platform
import subprocess
from PIL import Image, ImageTk

# Configuración global de CustomTkinter
ctk.set_appearance_mode("dark")  # Forzar a modo claro como en el diseño
ctk.set_default_color_theme("blue")

class AudioDelayApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Micyn")
        # Iniciar Maximizado (Linux/Windows)
        try:
            self.attributes('-zoomed', True)
        except:
            self.state('zoomed')
        
        # Color de fondo global blanco limpio
        self.configure(fg_color="#09090B")
        
        # --- Variables de Animación ---
        self.bars = []
        self.num_bars = 7
        self.current_amplitudes = [0] * self.num_bars
        self.target_amplitudes = [0] * self.num_bars
        self.bar_canvas = None
        
        # Configuración de Audio
        self.samplerate = 44100
        self.channels = 1
        self.chunk_size = 2048
        
        # Buffer Estático Circular (Se inicializa al dar Start)
        self.delay_seconds = 60
        self.total_buffer_size = 0
        self.ring_buffer = None
        
        self.write_ptr = 0
        self.read_ptr = 0
        
        # Variables de estado
        self.is_running = False
        self.audio_thread = None
        self.stream_in = None
        self.stream_out = None
        
        # Módulos virtuales generados (solo Linux)
        self.linux_module_sink_id = None
        self.linux_module_source_id = None
        self.os_system = platform.system()
        
        # Limpieza inicial preventiva por si hubo un cierre forzoso antes
        self._cleanup_virtual_cable()
        
        # Configurar Icono
        try:
            pil_img = Image.open("micyn_logo.jpg")
            pil_img.thumbnail((256, 256))
            icon_img = ImageTk.PhotoImage(pil_img)
            self.iconphoto(True, icon_img)
            # En Windows también setear bitmap si está disponible (.ico), pero el jpg por ahora bastará.
        except Exception as e:
            print("Logo no cargado como icono:", e)
        
        self._create_widgets()
        self._init_virtual_cable()
        self.after(500, self._populate_devices)
        
    def _init_virtual_cable(self):
        if self.os_system == 'Linux':
            try:
                # 1. Sink oculto que recibe el audio con delay
                cmd_sink = ["pactl", "load-module", "module-null-sink",
                            "sink_name=DelaySinkInternal",
                            "sink_properties=device.description='DelaySinkInternal'"]
                res_sink = subprocess.run(cmd_sink, check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_sink_id = res_sink.stdout.strip()

                # 2. Sink virtual que OBS verá como micrófono
                cmd_virtual = ["pactl", "load-module", "module-null-sink",
                               "sink_name=MicynOutput",
                               "sink_properties=device.description='Micyn - Retraso de audio'"]
                res_virtual = subprocess.run(cmd_virtual, check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_virtual_id = res_virtual.stdout.strip()

                # 3. Loopback: DelaySinkInternal.monitor → MicynOutput
                #    Esto hace que todo lo que entre al sink de delay
                #    aparezca en MicynOutput.monitor (que OBS usa como source)
                cmd_loop = ["pactl", "load-module", "module-loopback",
                            "source=DelaySinkInternal.monitor",
                            "sink=MicynOutput",
                            "latency_msec=1"]
                res_loop = subprocess.run(cmd_loop, check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_loopback_id = res_loop.stdout.strip()

                self.linux_backend = 'pactl'
                print("Cables virtuales creados correctamente.")

            except FileNotFoundError:
                print("PulseAudio/PipeWire no disponible.")
            except Exception as e:
                print(f"Error creando cables virtuales: {e}")
            
    def _create_widgets(self):
        # --- Cabecera ---
        sub_font = ctk.CTkFont(family="Google Sans", size=15)
        label_font = ctk.CTkFont(family="Google Sans", size=12, weight="bold")
        combo_font = ctk.CTkFont(family="Google Sans", size=14)
        
        try:
            from PIL import ImageDraw
            # Cargar y redimensionar el logo
            logo_pil = Image.open("micyn_logo.jpg").convert("RGBA")
            logo_size = 100
            logo_pil = logo_pil.resize((logo_size, logo_size), Image.LANCZOS)
            
            # Aplicar bordes redondeados al logo
            mask = Image.new("L", (logo_size, logo_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle((0, 0, logo_size, logo_size), radius=20, fill=255)
            logo_pil.putalpha(mask)
            
            logo_ctk = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(logo_size, logo_size))
            self.title_lbl = ctk.CTkLabel(self, text="", image=logo_ctk)
            self.title_lbl.pack(pady=(25, 5))
        except Exception as e:
            title_font = ctk.CTkFont(family="Google Sans", size=22, weight="bold")
            self.title_lbl = ctk.CTkLabel(self, text="Micyn", font=title_font, text_color="#FFFFFF")
            self.title_lbl.pack(pady=(25, 5))
            print("No se encontró el logo:", e)
        
        desc_frame = ctk.CTkFrame(self, fg_color="transparent")
        desc_frame.pack(pady=(0, 20))
        
        self.desc_lbl1 = ctk.CTkLabel(desc_frame, text="Retrasar audio - ", font=sub_font, text_color="#A0AEC0")
        self.desc_lbl1.pack(side="left")
        
        self.desc_lbl2 = ctk.CTkLabel(desc_frame, text="@facyndev.", font=sub_font, text_color="#4570F7", cursor="hand2")
        self.desc_lbl2.pack(side="left")
        
        def _open_link(event):
            import webbrowser
            webbrowser.open("https://www.facyn.xyz")
            
        self.desc_lbl2.bind("<Button-1>", _open_link)
        
        # --- Entradas ---
        self.in_lbl = ctk.CTkLabel(self, text="MICRÓFONO (ENTRADA)", font=label_font, text_color="#A0AEC0")
        self.in_lbl.pack(anchor="w", padx=40, pady=(0, 5))
        
        self.input_combobox = ctk.CTkComboBox(self, width=280, height=45, corner_radius=10, font=combo_font, dropdown_font=combo_font,
                                              fg_color="#18181A", border_width=1, border_color="#27272A",
                                              button_color="#18181A", button_hover_color="#27272A",
                                              dropdown_fg_color="#18181A", text_color="#FFFFFF", state="readonly")
        self.input_combobox.pack(padx=40, pady=(0, 20), fill="x")
        

        
        # --- Selector de Tiempo ---
        self.time_lbl = ctk.CTkLabel(self, text="TIEMPO DE RETRASO", font=label_font, text_color="#A0AEC0")
        self.time_lbl.pack(anchor="w", padx=40, pady=(0, 5))
        
        self.time_combobox = ctk.CTkComboBox(self, width=280, height=45, corner_radius=10, font=combo_font, dropdown_font=combo_font,
                                              fg_color="#18181A", border_width=1, border_color="#27272A",
                                              button_color="#18181A", button_hover_color="#27272A",
                                              values=["30 Segundos", "1 Minuto", "2 Minutos", "5 Minutos", "Personalizado (Segundos)"],
                                              dropdown_fg_color="#18181A", text_color="#FFFFFF", state="readonly",
                                              command=self._on_time_change)
        self.time_combobox.pack(padx=40, pady=(0, 5), fill="x")
        self.time_combobox.set("1 Minuto")
        
        self.custom_time_entry = ctk.CTkEntry(self, width=280, height=40, corner_radius=10, font=combo_font,
                                              placeholder_text="Ej: 15 (segundos)", border_color="#27272A")
        self.custom_time_entry.pack(padx=40, pady=(0, 15), fill="x")
        self.custom_time_entry.configure(state="disabled", fg_color="#09090B") # Apagado por defecto
        
        # --- Monitor Card ---
        self.monitor_frame = ctk.CTkFrame(self, width=280, height=70, fg_color="#18181A", corner_radius=12)
        self.monitor_frame.pack_propagate(False)
        self.monitor_frame.pack(padx=40, pady=(0, 30), fill="x")
        
        label_frame = ctk.CTkFrame(self.monitor_frame, fg_color="transparent")
        label_frame.pack(side="left", padx=15, pady=10)
        
        self.mon_title = ctk.CTkLabel(label_frame, text="Escuchar mi propia voz", font=ctk.CTkFont(family="Google Sans", size=14, weight="bold"), text_color="#FFFFFF")
        self.mon_title.pack(anchor="w")
        
        self.mon_sub = ctk.CTkLabel(label_frame, text="Monitor de retorno sin delay", font=ctk.CTkFont(family="Google Sans", size=12), text_color="#A0AEC0")
        self.mon_sub.pack(anchor="w", pady=(0, 0))
        
        self.monitor_var = ctk.BooleanVar(value=False)
        self.monitor_chk = ctk.CTkSwitch(self.monitor_frame, text="", variable=self.monitor_var,
                                         progress_color="#4570F7", button_color="#FFFFFF",
                                         button_hover_color="#3F3F46", fg_color="#27272A", switch_width=45, switch_height=22)
        self.monitor_chk.pack(side="right", padx=15)
        
        # --- Área de Animación Vúmetro (Microfóno) ---
        anim_frame_bg = ctk.CTkFrame(self, fg_color="#18181A", corner_radius=15, height=80, width=280)
        anim_frame_bg.pack_propagate(False)
        anim_frame_bg.pack(padx=40, pady=(0, 20), fill="x")
        
        self.bar_canvas = tk.Canvas(anim_frame_bg, width=200, height=60, bg="#18181A", highlightthickness=0)
        self.bar_canvas.pack(expand=True)
        
        # Inicializar barras visuales (Blancas)
        bar_width = 8
        spacing = 15
        total_w = (self.num_bars * bar_width) + ((self.num_bars - 1) * spacing)
        offset_x = (200 - total_w) // 2
        
        for i in range(self.num_bars):
            x1 = offset_x + i * (bar_width + spacing)
            # Altura por defecto minima (4px)
            y1 = 30 - 2
            x2 = x1 + bar_width
            y2 = 30 + 2
            
            # Crear rectángulo con tags
            bar_id = self.bar_canvas.create_rectangle(x1, y1, x2, y2, fill="#4570F7", outline="", tags=f"bar_{i}")
            self.bars.append(bar_id)
            
        # Programar la actualización visual a 60 FPS
        self._animate_bars()
        
        # --- Botones ---
        btn_font = ctk.CTkFont(family="Google Sans", size=17, weight="bold")
        
        self.start_btn = ctk.CTkButton(self, text="▶  Iniciar retraso de audio", font=btn_font, width=280, height=50, 
                                       corner_radius=25, fg_color="#4570F7", hover_color="#2F52CC", text_color="#FFFFFF", command=self.start)
        self.start_btn.pack(padx=40, pady=(0, 15), fill="x")
        
        self.stop_btn = ctk.CTkButton(self, text="■  Detener", font=btn_font, width=280, height=50, 
                                      corner_radius=25, fg_color="#27272A", hover_color="#E0E0E0", text_color="#7A8084", state="disabled", command=self.stop)
        self.stop_btn.pack(padx=40, pady=(0, 30), fill="x")
        
        # --- Divisor Inferior ---
        self.sep = ctk.CTkFrame(self, height=1, fg_color="#EAECEE", width=240)
        self.sep.pack(pady=(10, 20))
        
        # --- Píldora de Estado ---
        self.status_frame = ctk.CTkFrame(self, fg_color="#09090B", corner_radius=15, height=30)
        self.status_frame.pack(pady=(0, 10))
        
        # Un puntito literal para estado
        self.status_dot = ctk.CTkLabel(self.status_frame, text="●", text_color="#A0AEC0", font=ctk.CTkFont(size=14))
        self.status_dot.pack(side="left", padx=(15, 5), pady=0)
        
        self.status_lbl = ctk.CTkLabel(self.status_frame, text="ESTADO: DETENIDO", font=label_font, text_color="#A0AEC0")
        self.status_lbl.pack(side="left", padx=(0, 15), pady=0)
        
    def _on_time_change(self, choice):
        if choice == "Personalizado (Segundos)":
            self.custom_time_entry.configure(state="normal", fg_color="#18181A", border_color="#4570F7")
        else:
            self.custom_time_entry.configure(state="disabled", fg_color="#09090B")
            
    def _get_selected_delay(self):
        choice = self.time_combobox.get()
        if choice == "30 Segundos": return 30
        if choice == "1 Minuto": return 60
        if choice == "2 Minutos": return 120
        if choice == "5 Minutos": return 300
        if choice == "Personalizado (Segundos)":
            val = self.custom_time_entry.get()
            try:
                sec = int(val)
                if sec < 1: return 1
                return sec
            except:
                return -1 # error
        return 60
        
    def _clean_device_name(self, name):
        if ',' in name: name = name.split(',')[0]
        if '(hw:' in name: name = name.split('(hw:')[0].strip()
        if name.lower() == 'default': name = 'Dispositivo Principal (Predeterminado)'
        if name.lower() in ['pipewire', 'pulse']: name = f'Servidor de Audio ({name})'
        if len(name) > 40: name = name[:37] + "..."
        return name

    def _animate_bars(self):
        """ Bucle de de renderizado visual a 60 FPS (Lerp Suavizado) """
        if self.is_running:
            for i in range(self.num_bars):
                current = self.current_amplitudes[i]
                target = self.target_amplitudes[i]
                
                lerp_speed = 0.4 if target > current else 0.15
                self.current_amplitudes[i] = current + (target - current) * lerp_speed
                
                height = float(4 + (self.current_amplitudes[i] * 46))
                y1 = float(30 - (height / 2))
                y2 = float(30 + (height / 2))
                
                x_coords = self.bar_canvas.coords(self.bars[i])
                if x_coords:
                    self.bar_canvas.coords(self.bars[i], x_coords[0], y1, x_coords[2], y2)
                    
        else:
            for i in range(self.num_bars):
                if self.current_amplitudes[i] > 0.01:
                    self.current_amplitudes[i] *= 0.8
                    height = float(4 + (self.current_amplitudes[i] * 46))
                    y1 = float(30 - (height / 2))
                    y2 = float(30 + (height / 2))
                    
                    x_coords = self.bar_canvas.coords(self.bars[i])
                    if x_coords:
                        self.bar_canvas.coords(self.bars[i], x_coords[0], y1, x_coords[2], y2)

        self.after(16, self._animate_bars)
        
    def _populate_devices(self):
        try:
            devices = sd.query_devices()
            
            # Filtros de palabras clave de sistemas / subdispositivos confusos en Linux/Windows
            exclude_keywords = ['iec958', 'spdif', 'surround', 'dmix', 'dsnoop', 'sysdefault', 'front:', 'rear:', 'center_lfe']
            
            self.inputs = []
            self.outputs = []
            
            for i, d in enumerate(devices):
                d['original_index'] = i
                name_lower = d['name'].lower()
                
                # Omitir virtuales ruidosos si es ALSA
                if any(k in name_lower for k in exclude_keywords):
                    continue
                    
                if d['max_input_channels'] > 0:
                    self.inputs.append(d)
                if d['max_output_channels'] > 0:
                    self.outputs.append(d)
            
            in_names = [self._clean_device_name(d['name']) for d in self.inputs]
            self.input_combobox.configure(values=in_names)
            
            default_in = sd.default.device[0]
            default_out = sd.default.device[1]
            
            for i, dev in enumerate(self.inputs):
                if dev['original_index'] == default_in or dev['name'] == devices[default_in]['name']:
                    self.input_combobox.set(in_names[i])
                    break
            else:
                if self.inputs: self.input_combobox.set(in_names[0])
                
        except Exception as e:
            print(f"No se pudieron cargar dispositivos: {e}")

    def _audio_callback_in(self, indata, frames, time_info, status):
        # 1. Copiar bytes al Buffer
        remaining = self.total_buffer_size - self.write_ptr
        if frames <= remaining:
            self.ring_buffer[self.write_ptr:self.write_ptr+frames] = indata
        else:
            self.ring_buffer[self.write_ptr:self.total_buffer_size] = indata[:remaining]
            self.ring_buffer[0:frames-remaining] = indata[remaining:]
        self.write_ptr = (self.write_ptr + frames) % self.total_buffer_size
        
        # (Fix) Evitar que el buffer acumule más delay del solicitado si el output se suspende (ej. virtual sink idle en OBS)
        # Esto mantiene el read_ptr siempre a lo sumo 'buffer_size_frames' detrás del write_ptr
        available = (self.write_ptr - self.read_ptr) % self.total_buffer_size
        if available > self.buffer_size_frames:
            self.read_ptr = (self.write_ptr - self.buffer_size_frames) % self.total_buffer_size
        
        # 2. Calcular RMS para animación (Nivel de volumen general del frame)
        # indata tiene forma (frames, channels), lo achatamos a vector
        rms = np.sqrt(np.mean(indata**2))
        
        # Convertir a escala Logarítmica suave (Decibeles aprox) y delimitar a [0.0 - 1.0]
        db = 20 * np.log10(rms + 1e-6)
        # Rango mapeado: -40dB (silencio) a 0dB (clipping alto)
        min_db = -40
        max_db = 0
        norm_amp = (db - min_db) / (max_db - min_db)
        norm_amp = max(0.0, min(1.0, norm_amp))
        
        # Distribuir la amplitud principal usando una función seno para la típica forma de "montaña" en el centro
        for i in range(self.num_bars):
            # i va del 0 a 6, normalizamos al centro que es 3
            dist = abs(i - 3) 
            # El centro recibe 100% de la fuerza, los extremos menos
            weight = max(0.2, 1.0 - (dist * 0.25)) 
            
            # Añadir pequeña onda de desplazamiento dinámico para no verse rígido
            ripple = np.sin((time.time() * 5) + i) * 0.1 
            
            # Amplitud Meta ("target") final de esa barra en este frame
            self.target_amplitudes[i] = float(max(0.0, min(1.0, (norm_amp * weight) + ripple * norm_amp)))

    def _audio_callback_out(self, outdata, frames, time_info, status):
        available = (self.write_ptr - self.read_ptr) % self.total_buffer_size
        if available >= frames:
            remaining = self.total_buffer_size - self.read_ptr
            if frames <= remaining:
                outdata[:] = self.ring_buffer[self.read_ptr:self.read_ptr+frames]
            else:
                outdata[:remaining] = self.ring_buffer[self.read_ptr:self.total_buffer_size]
                outdata[remaining:] = self.ring_buffer[0:frames-remaining]
            self.read_ptr = (self.read_ptr + frames) % self.total_buffer_size
        else:
            outdata[:] = np.zeros((frames, self.channels), dtype=np.float32)

    def _audio_loop(self):
        in_name_sel = self.input_combobox.get()
        
        in_idx = -1
        out_idx = -1
        use_virtual_sink = False
        out_device = None
        
        for i, d in enumerate(self.inputs):
            if self._clean_device_name(d['name']).startswith(in_name_sel.replace('...','')):
                in_idx = i; break
                
        if self.os_system == 'Linux':
            use_virtual_sink = True
            out_idx = 1  # dummy para pasar el check
            
            # Buscar el índice real de DelaySinkInternal en sounddevice
            out_device = None
            try:
                devices = sd.query_devices()
                for i, d in enumerate(devices):
                    if 'delaysinkinternal' in d['name'].lower() or 'delaySinkInternal' in d['name']:
                        if d['max_output_channels'] > 0:
                            out_device = i
                            break
                # Fallback: buscar por pactl el nombre del monitor
                if out_device is None:
                    res = subprocess.run(['pactl', 'list', 'short', 'sinks'], stdout=subprocess.PIPE, text=True)
                    for line in res.stdout.splitlines():
                        if 'DelaySinkInternal' in line:
                            # El monitor aparece en ALSA/PipeWire como "DelaySinkInternal.monitor"
                            for i, d in enumerate(devices):
                                if 'delaysink' in d['name'].lower():
                                    out_device = i
                                    break

            except Exception as e:
                print(f"No se pudo resolver DelaySinkInternal: {e}")
                out_device = sd.default.device[1]  # fallback al default
        else:
            # En windows si no hay selector de salida, tomamos la por defecto o creamos un driver VB_CABLE a futuro
            for i, d in enumerate(self.outputs):
                if "Virtual" in d['name'] or "CABLE" in d['name']:
                    out_device = self.outputs[i]['index']
                    out_idx = i; break
            if out_idx == -1 and len(self.outputs) > 0:
                out_device = self.outputs[0]['index']
                out_idx = 0
                
        if in_idx == -1 or out_idx == -1:
            print("Error: Dispositivo seleccionado no coincide con la lista.")
            self.after(0, self.stop)
            return
            
        in_device = self.inputs[in_idx]['index']
        
        self.ring_buffer.fill(0)
        self.write_ptr = self.buffer_size_frames
        self.read_ptr = 0
        
        monitor_enabled = self.monitor_var.get()
            
        try:
            self.stream_in = sd.InputStream(device=in_device, samplerate=self.samplerate,
                                            blocksize=self.chunk_size, channels=self.channels,
                                            dtype=np.float32, callback=self._audio_callback_in)
                                            
            def get_sink_inputs():
                try:
                    res = subprocess.run(['pactl', 'list', 'short', 'sink-inputs'], stdout=subprocess.PIPE, text=True)
                    return set(line.split()[0] for line in res.stdout.strip().splitlines() if line.strip())
                except: return set()
                
            before_inputs = set()
            if use_virtual_sink:
                before_inputs = get_sink_inputs()
                
            out_device_arg = out_device if use_virtual_sink else out_device
                
            self.stream_out = sd.OutputStream(device=out_device_arg, samplerate=self.samplerate,
                                              blocksize=self.chunk_size, channels=self.channels,
                                              dtype=np.float32, callback=self._audio_callback_out)
                                              
            self.stream_out.start()
            self.stream_in.start()
            
            if use_virtual_sink:
                time.sleep(0.3)
                after_inputs = get_sink_inputs()
                for inp in (after_inputs - before_inputs):
                    subprocess.run(['pactl', 'move-sink-input', inp, 'DelaySinkInternal'])
                                              
            if monitor_enabled:
                default_out = sd.default.device[1] 
                def _monitor_callback(indata, outdata, frames, time_info, status):
                    if len(indata) == frames: outdata[:] = indata
                    elif len(indata) < frames:
                        outdata[:len(indata)] = indata
                        outdata[len(indata):] = 0
                self.stream_monitor = sd.Stream(device=(in_device, default_out), samplerate=self.samplerate,
                                                blocksize=self.chunk_size, channels=self.channels,
                                                dtype=np.float32, callback=_monitor_callback)
                self.stream_monitor.start()
            while self.is_running: time.sleep(0.5)
                
        except Exception as e:
            self.after(0, self.stop)
            print(f"Error streams: {e}")
        finally:
            if self.stream_in: self.stream_in.stop(); self.stream_in.close()
            if self.stream_out: self.stream_out.stop(); self.stream_out.close()
            if hasattr(self, 'stream_monitor') and self.stream_monitor:
                self.stream_monitor.stop(); self.stream_monitor.close()
                self.stream_monitor = None

    def start(self):
        in_val = self.input_combobox.get()
        if not in_val: return
        
        delay_s = self._get_selected_delay()
        if delay_s == -1:
            self.status_lbl.configure(text="ERROR: TIEMPO INVÁLIDO", text_color="red")
            self.status_dot.configure(text_color="red")
            return
            
        self.delay_seconds = delay_s
        
        # Recalcular Ring Buffer On-Demand
        buffer_size_frames = int(self.samplerate * self.delay_seconds)
        buffer_margin = int(self.samplerate * 1)
        self.total_buffer_size = buffer_size_frames + buffer_margin
        self.ring_buffer = np.zeros((self.total_buffer_size, self.channels), dtype=np.float32)
        self.buffer_size_frames = buffer_size_frames
            
        self.is_running = True
        self.start_btn.configure(state="disabled", fg_color="#222222", text=" Procesando...")
        self.input_combobox.configure(state="disabled")
        self.time_combobox.configure(state="disabled")
        self.custom_time_entry.configure(state="disabled")
        self.monitor_chk.configure(state="disabled")
        
        # Stop color se prende
        self.stop_btn.configure(state="normal", text_color="#000000", fg_color="#FFFFFF")
        
        self.status_dot.configure(text_color="#4CAF50")
        self.status_lbl.configure(text=f"ESTADO: ATRASANDO {self.delay_seconds}S")
        
        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.audio_thread.start()

    def stop(self):
        self.is_running = False
        
        # Devolver todos los targets de animación a 0 al parar
        for i in range(self.num_bars):
            self.target_amplitudes[i] = 0.0
            
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=1.0)
            
        self.start_btn.configure(state="normal", fg_color="#4570F7", text="▶  Iniciar Grabación/Retraso")
        self.input_combobox.configure(state="readonly")
        self.time_combobox.configure(state="readonly")
        if self.time_combobox.get() == "Personalizado (Segundos)":
            self.custom_time_entry.configure(state="normal")
        self.monitor_chk.configure(state="normal")
        
        self.stop_btn.configure(state="disabled", text_color="#7A8084", fg_color="#27272A")
        self.status_dot.configure(text_color="#A0AEC0")
        self.status_lbl.configure(text="ESTADO: DETENIDO")

    def _cleanup_virtual_cable(self):
        if self.os_system == 'Linux':
            try:
                res = subprocess.run(['pactl', 'list', 'short', 'modules'],
                                    stdout=subprocess.PIPE, text=True)
                for line in res.stdout.splitlines():
                    if any(k in line for k in ['DelaySinkInternal', 'MicynOutput',
                                            'Micyn - Retraso', 'Micrófono_OBS_Retraso']):
                        mod_id = line.split()[0]
                        subprocess.run(['pactl', 'unload-module', mod_id])
            except Exception as e:
                print(f"Error limpiando cables virtuales: {e}")

if __name__ == "__main__":
    app = AudioDelayApp()
    def on_closing():
        app.stop()
        app._cleanup_virtual_cable()
        app.destroy()
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()

