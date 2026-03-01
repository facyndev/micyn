import customtkinter as ctk
import tkinter as tk
import sounddevice as sd
import numpy as np
import threading
import time
import sys
import platform
import subprocess
import os
from PIL import Image, ImageTk

# Configuración global de CustomTkinter
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
        
        # Buffer Estático Circular
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
        self.stream_monitor = None
        
        # Módulos virtuales generados (solo Linux)
        self.linux_module_sink_id = None
        self.linux_module_virtual_id = None
        self.linux_module_loopback_id = None
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
        except Exception as e:
            print("Logo no cargado como icono:", e)
        
        self._create_widgets()
        self._init_virtual_cable()
        self.after(500, self._populate_devices)
        
    # ─────────────────────────────────────────────
    #   CABLES VIRTUALES
    # ─────────────────────────────────────────────

    def _init_virtual_cable(self):
        """
        Crea en PipeWire/PulseAudio:
          1. DelaySinkInternal  → sink oculto que recibe el audio con delay
          2. MicynOutput        → sink intermedio
          3. module-loopback    → DelaySinkInternal.monitor → MicynOutput
          4. MicynMic           → source virtual expuesto como MICRÓFONO
                                  (aparece como entrada en Discord, Zoom, Meet, etc.)

        Flujo:
          Micrófono → ring buffer (delay) → DelaySinkInternal
              → loopback → MicynOutput → MicynOutput.monitor
              → virtual-source → "Micyn - Retraso de audio"  ← seleccionar como mic
        """
        if self.os_system == 'Linux':
            try:
                # 1. Sink oculto receptor del audio con delay
                cmd_sink = ["pactl", "load-module", "module-null-sink",
                            "sink_name=DelaySinkInternal",
                            "sink_properties=device.description='DelaySinkInternal'"]
                res = subprocess.run(cmd_sink, check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_sink_id = res.stdout.strip()

                # 2. Sink intermedio visible para el loopback
                cmd_virtual = ["pactl", "load-module", "module-null-sink",
                               "sink_name=MicynOutput",
                               "sink_properties=device.description='MicynOutput'"]
                res = subprocess.run(cmd_virtual, check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_virtual_id = res.stdout.strip()

                # 3. Loopback activo: DelaySinkInternal.monitor → MicynOutput
                cmd_loop = ["pactl", "load-module", "module-loopback",
                            "source=DelaySinkInternal.monitor",
                            "sink=MicynOutput",
                            "latency_msec=1"]
                res = subprocess.run(cmd_loop, check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_loopback_id = res.stdout.strip()

                # 4. Source virtual expuesto como MICRÓFONO de entrada
                #    Aparece como "Micyn - Retraso de audio" en la lista de micrófonos
                #    de cualquier aplicación (Discord, Zoom, Meet, OBS, etc.)
                cmd_source = ["pactl", "load-module", "module-virtual-source",
                              "source_name=MicynMic",
                              "master=MicynOutput.monitor",
                              "source_properties=device.description='Micyn - Retraso de audio'"]
                res = subprocess.run(cmd_source, check=True, stdout=subprocess.PIPE, text=True)
                self.linux_module_source_id = res.stdout.strip()

                print("Cables virtuales creados correctamente.")
                print("  → Seleccioná 'Micyn - Retraso de audio' como MICRÓFONO en cualquier app.")

            except FileNotFoundError:
                print("PulseAudio/PipeWire no disponible.")
            except Exception as e:
                print(f"Error creando cables virtuales: {e}")

        elif self.os_system == 'Windows':
            pass

    def _cleanup_virtual_cable(self):
        if self.os_system == 'Linux':
            try:
                res = subprocess.run(['pactl', 'list', 'short', 'modules'],
                                     stdout=subprocess.PIPE, text=True)
                for line in res.stdout.splitlines():
                    if any(k in line for k in ['DelaySinkInternal', 'MicynOutput', 'MicynMic',
                                               'Micyn - Retraso', 'Micrófono_OBS_Retraso']):
                        mod_id = line.split()[0]
                        subprocess.run(['pactl', 'unload-module', mod_id])
                        print(f"Módulo {mod_id} eliminado.")
            except Exception as e:
                print(f"Error limpiando cables virtuales: {e}")

    # ─────────────────────────────────────────────
    #   AUDIO
    # ─────────────────────────────────────────────

    def _get_sink_device_index(self, sink_name):
        """
        Busca el índice de sounddevice para un sink de PipeWire.
        Si no lo encuentra directamente (sounddevice usa ALSA),
        devuelve el índice del dispositivo 'pipewire' o 'pulse' como fallback
        y luego usamos pactl move-sink-input para redirigir el stream.
        Retorna: (indice, necesita_redireccion)
        """
        devices = sd.query_devices()

        # Intento directo por nombre
        for i, d in enumerate(devices):
            if sink_name.lower() in d['name'].lower() and d['max_output_channels'] > 0:
                return i, False

        # Fallback: backend pipewire/pulse + redirección posterior via pactl
        for i, d in enumerate(devices):
            if d['name'].lower() in ['pipewire', 'pulse'] and d['max_output_channels'] > 0:
                print(f"'{sink_name}' no visible en ALSA, usando '{d['name']}' + redirección pactl.")
                return i, True

        return None, False

    def _redirect_sink_input(self, target_sink='DelaySinkInternal', ignore_inputs=None):
        """Mueve los sink-inputs activos al sink virtual indicado, ignorando preexistentes."""
        if ignore_inputs is None:
            ignore_inputs = set()
        try:
            time.sleep(0.5)
            res = subprocess.run(['pactl', 'list', 'short', 'sink-inputs'],
                                 stdout=subprocess.PIPE, text=True)
            for line in res.stdout.strip().splitlines():
                parts = line.split()
                if parts:
                    sink_input_id = parts[0]
                    if sink_input_id not in ignore_inputs:
                        subprocess.run(['pactl', 'move-sink-input', sink_input_id, target_sink])
                        print(f"Sink-input {sink_input_id} → {target_sink}")
        except Exception as e:
            print(f"Error redirigiendo sink-input: {e}")

    def _audio_callback_in(self, indata, frames, time_info, status):
        # Escribir en el buffer circular
        remaining = self.total_buffer_size - self.write_ptr
        if frames <= remaining:
            self.ring_buffer[self.write_ptr:self.write_ptr + frames] = indata
        else:
            self.ring_buffer[self.write_ptr:self.total_buffer_size] = indata[:remaining]
            self.ring_buffer[0:frames - remaining] = indata[remaining:]
        self.write_ptr = (self.write_ptr + frames) % self.total_buffer_size

        # Evitar acumulación extra si el output se suspende
        available = (self.write_ptr - self.read_ptr) % self.total_buffer_size
        if available > self.buffer_size_frames:
            self.read_ptr = (self.write_ptr - self.buffer_size_frames) % self.total_buffer_size

        # Animación vúmetro
        rms = np.sqrt(np.mean(indata ** 2))
        db = 20 * np.log10(rms + 1e-6)
        norm_amp = max(0.0, min(1.0, (db - (-40)) / (0 - (-40))))

        for i in range(self.num_bars):
            dist = abs(i - 3)
            weight = max(0.2, 1.0 - (dist * 0.25))
            ripple = np.sin((time.time() * 5) + i) * 0.1
            self.target_amplitudes[i] = float(max(0.0, min(1.0, (norm_amp * weight) + ripple * norm_amp)))

    def _audio_callback_out(self, outdata, frames, time_info, status):
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

        in_device = self.inputs[in_idx]['index']
        out_device = None
        needs_redirect = False

        if self.os_system == 'Linux':
            out_device, needs_redirect = self._get_sink_device_index('DelaySinkInternal')
            if out_device is None:
                print("Error: No se encontró ningún backend de audio compatible.")
                self.after(0, self.stop)
                return
            print(f"Salida → índice sounddevice: {out_device} (redirección pactl: {needs_redirect})")
        else:
            # Windows: buscar VB-Cable o usar default
            for i, d in enumerate(self.outputs):
                if "Virtual" in d['name'] or "CABLE" in d['name']:
                    out_device = self.outputs[i]['index']
                    break
            if out_device is None and self.outputs:
                out_device = self.outputs[0]['index']
            if out_device is None:
                print("Error: No se encontró dispositivo de salida.")
                self.after(0, self.stop)
                return

        self.ring_buffer.fill(0)
        self.write_ptr = self.buffer_size_frames
        self.read_ptr = 0

        monitor_enabled = self.monitor_var.get()

        before_inputs = set()
        if needs_redirect:
            try:
                res = subprocess.run(['pactl', 'list', 'short', 'sink-inputs'], stdout=subprocess.PIPE, text=True)
                before_inputs = set(line.split()[0] for line in res.stdout.strip().splitlines() if line.strip())
            except:
                pass

        try:
            self.stream_in = sd.InputStream(
                device=in_device,
                samplerate=self.samplerate,
                blocksize=self.chunk_size,
                channels=self.channels,
                dtype=np.float32,
                callback=self._audio_callback_in
            )

            self.stream_out = sd.OutputStream(
                device=out_device,
                samplerate=self.samplerate,
                blocksize=self.chunk_size,
                channels=self.channels,
                dtype=np.float32,
                callback=self._audio_callback_out
            )

            self.stream_out.start()
            self.stream_in.start()

            # Si sounddevice usa pipewire/pulse genérico, redirigir el stream via pactl
            if needs_redirect:
                self._redirect_sink_input('DelaySinkInternal', ignore_inputs=before_inputs)

            print("Flujo activo: Micrófono → delay → DelaySinkInternal → loopback → MicynOutput → MicynMic")

            # Monitor de retorno (escuchar la propia voz sin delay)
            if monitor_enabled:
                default_out = sd.default.device[1]

                def _monitor_callback(indata, outdata, frames, time_info, status):
                    if len(indata) == frames:
                        outdata[:] = indata
                    elif len(indata) < frames:
                        outdata[:len(indata)] = indata
                        outdata[len(indata):] = 0

                self.stream_monitor = sd.Stream(
                    device=(in_device, default_out),
                    samplerate=self.samplerate,
                    blocksize=self.chunk_size,
                    channels=self.channels,
                    dtype=np.float32,
                    callback=_monitor_callback
                )
                self.stream_monitor.start()

            while self.is_running:
                time.sleep(0.5)

        except Exception as e:
            self.after(0, self.stop)
            print(f"Error streams: {e}")
        finally:
            if self.stream_in:
                self.stream_in.stop()
                self.stream_in.close()
            if self.stream_out:
                self.stream_out.stop()
                self.stream_out.close()
            if self.stream_monitor:
                self.stream_monitor.stop()
                self.stream_monitor.close()
                self.stream_monitor = None

    # ─────────────────────────────────────────────
    #   CONTROLES
    # ─────────────────────────────────────────────

    def start(self):
        in_val = self.input_combobox.get()
        if not in_val:
            return

        delay_s = self._get_selected_delay()
        if delay_s == -1:
            self.status_lbl.configure(text="ERROR: TIEMPO INVÁLIDO", text_color="red")
            self.status_dot.configure(text_color="red")
            return

        self.delay_seconds = delay_s

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
        self.stop_btn.configure(state="normal", text_color="#000000", fg_color="#FFFFFF")

        self.status_dot.configure(text_color="#4CAF50")
        self.status_lbl.configure(text=f"ESTADO: ATRASANDO {self.delay_seconds}S")

        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.audio_thread.start()

    def stop(self):
        self.is_running = False

        for i in range(self.num_bars):
            self.target_amplitudes[i] = 0.0

        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=1.0)

        self.start_btn.configure(state="normal", fg_color="#4570F7", text="▶  Iniciar retraso de audio")
        self.input_combobox.configure(state="readonly")
        self.time_combobox.configure(state="readonly")
        if self.time_combobox.get() == "Personalizado (Segundos)":
            self.custom_time_entry.configure(state="normal")
        self.monitor_chk.configure(state="normal")

        self.stop_btn.configure(state="disabled", text_color="#7A8084", fg_color="#27272A")
        self.status_dot.configure(text_color="#A0AEC0")
        self.status_lbl.configure(text="ESTADO: APAGADO")

    # ─────────────────────────────────────────────
    #   UI
    # ─────────────────────────────────────────────

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
                return max(1, sec)
            except:
                return -1
        return 60

    def _clean_device_name(self, name):
        if ',' in name: name = name.split(',')[0]
        if '(hw:' in name: name = name.split('(hw:')[0].strip()
        if name.lower() == 'default': name = 'Dispositivo Principal (Predeterminado)'
        if name.lower() in ['pipewire', 'pulse']: name = f'Servidor de Audio ({name})'
        if len(name) > 40: name = name[:37] + "..."
        return name

    def _animate_bars(self):
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

            exclude_keywords = ['iec958', 'spdif', 'surround', 'dmix', 'dsnoop', 'sysdefault',
                                 'front:', 'rear:', 'center_lfe',
                                 'delaysinkinternal', 'micynoutput', 'micynmic']

            self.inputs = []
            self.outputs = []

            for i, d in enumerate(devices):
                d['original_index'] = i
                name_lower = d['name'].lower()
                if any(k in name_lower for k in exclude_keywords):
                    continue
                if d['max_input_channels'] > 0:
                    self.inputs.append(d)
                if d['max_output_channels'] > 0:
                    self.outputs.append(d)

            in_names = [self._clean_device_name(d['name']) for d in self.inputs]
            self.input_combobox.configure(values=in_names)

            default_in = sd.default.device[0]
            devices_all = sd.query_devices()

            for i, dev in enumerate(self.inputs):
                if dev['original_index'] == default_in or dev['name'] == devices_all[default_in]['name']:
                    self.input_combobox.set(in_names[i])
                    break
            else:
                if self.inputs:
                    self.input_combobox.set(in_names[0])

        except Exception as e:
            print(f"No se pudieron cargar dispositivos: {e}")

    def _create_widgets(self):
        sub_font   = ctk.CTkFont(family="Google Sans", size=15)
        label_font = ctk.CTkFont(family="Google Sans", size=12, weight="bold")
        combo_font = ctk.CTkFont(family="Google Sans", size=14)

        try:
            from PIL import ImageDraw
            logo_pil  = Image.open("micyn_logo.jpg").convert("RGBA")
            logo_size = 100
            logo_pil  = logo_pil.resize((logo_size, logo_size), Image.LANCZOS)
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

        # Entrada
        self.in_lbl = ctk.CTkLabel(self, text="MICRÓFONO (ENTRADA)", font=label_font, text_color="#A0AEC0")
        self.in_lbl.pack(anchor="w", padx=40, pady=(0, 5))
        self.input_combobox = ctk.CTkComboBox(
            self, width=280, height=45, corner_radius=10, font=combo_font, dropdown_font=combo_font,
            fg_color="#18181A", border_width=1, border_color="#27272A",
            button_color="#18181A", button_hover_color="#27272A",
            dropdown_fg_color="#18181A", text_color="#FFFFFF", state="readonly"
        )
        self.input_combobox.pack(padx=40, pady=(0, 20), fill="x")

        # Tiempo
        self.time_lbl = ctk.CTkLabel(self, text="TIEMPO DE RETRASO", font=label_font, text_color="#A0AEC0")
        self.time_lbl.pack(anchor="w", padx=40, pady=(0, 5))
        self.time_combobox = ctk.CTkComboBox(
            self, width=280, height=45, corner_radius=10, font=combo_font, dropdown_font=combo_font,
            fg_color="#18181A", border_width=1, border_color="#27272A",
            button_color="#18181A", button_hover_color="#27272A",
            values=["30 Segundos", "1 Minuto", "2 Minutos", "5 Minutos", "Personalizado (Segundos)"],
            dropdown_fg_color="#18181A", text_color="#FFFFFF", state="readonly",
            command=self._on_time_change
        )
        self.time_combobox.pack(padx=40, pady=(0, 5), fill="x")
        self.time_combobox.set("1 Minuto")
        self.custom_time_entry = ctk.CTkEntry(
            self, width=280, height=40, corner_radius=10, font=combo_font,
            placeholder_text="Ej: 15 (segundos)", border_color="#27272A"
        )
        self.custom_time_entry.pack(padx=40, pady=(0, 15), fill="x")
        self.custom_time_entry.configure(state="disabled", fg_color="#09090B")

        # Monitor Card
        self.monitor_frame = ctk.CTkFrame(self, width=280, height=70, fg_color="#18181A", corner_radius=12)
        self.monitor_frame.pack_propagate(False)
        self.monitor_frame.pack(padx=40, pady=(0, 30), fill="x")
        label_frame = ctk.CTkFrame(self.monitor_frame, fg_color="transparent")
        label_frame.pack(side="left", padx=15, pady=10)
        self.mon_title = ctk.CTkLabel(
            label_frame, text="Escuchar mi propia voz",
            font=ctk.CTkFont(family="Google Sans", size=14, weight="bold"), text_color="#FFFFFF"
        )
        self.mon_title.pack(anchor="w")
        self.mon_sub = ctk.CTkLabel(
            label_frame, text="Monitor de retorno sin delay",
            font=ctk.CTkFont(family="Google Sans", size=12), text_color="#A0AEC0"
        )
        self.mon_sub.pack(anchor="w")
        self.monitor_var = ctk.BooleanVar(value=False)
        self.monitor_chk = ctk.CTkSwitch(
            self.monitor_frame, text="", variable=self.monitor_var,
            progress_color="#4570F7", button_color="#FFFFFF",
            button_hover_color="#3F3F46", fg_color="#27272A", switch_width=45, switch_height=22
        )
        self.monitor_chk.pack(side="right", padx=15)

        # Vúmetro
        anim_frame_bg = ctk.CTkFrame(self, fg_color="#18181A", corner_radius=15, height=80, width=280)
        anim_frame_bg.pack_propagate(False)
        anim_frame_bg.pack(padx=40, pady=(0, 20), fill="x")
        self.bar_canvas = tk.Canvas(anim_frame_bg, width=200, height=60, bg="#18181A", highlightthickness=0)
        self.bar_canvas.pack(expand=True)
        bar_width = 8
        spacing   = 15
        total_w   = (self.num_bars * bar_width) + ((self.num_bars - 1) * spacing)
        offset_x  = (200 - total_w) // 2
        for i in range(self.num_bars):
            x1 = offset_x + i * (bar_width + spacing)
            x2 = x1 + bar_width
            bar_id = self.bar_canvas.create_rectangle(x1, 28, x2, 32, fill="#4570F7", outline="", tags=f"bar_{i}")
            self.bars.append(bar_id)
        self._animate_bars()

        # Botones
        btn_font = ctk.CTkFont(family="Google Sans", size=17, weight="bold")
        self.start_btn = ctk.CTkButton(
            self, text="▶  Iniciar retraso de audio", font=btn_font, width=280, height=50,
            corner_radius=25, fg_color="#4570F7", hover_color="#2F52CC", text_color="#FFFFFF",
            command=self.start
        )
        self.start_btn.pack(padx=40, pady=(0, 15), fill="x")
        self.stop_btn = ctk.CTkButton(
            self, text="■  Detener", font=btn_font, width=280, height=50,
            corner_radius=25, fg_color="#27272A", hover_color="#E0E0E0", text_color="#7A8084",
            state="disabled", command=self.stop
        )
        self.stop_btn.pack(padx=40, pady=(0, 30), fill="x")

        # Divisor y estado
        ctk.CTkFrame(self, height=1, fg_color="#27272A").pack(pady=(10, 20), fill="x", padx=40)
        self.status_frame = ctk.CTkFrame(self, fg_color="#09090B", corner_radius=15, height=30)
        self.status_frame.pack(pady=(0, 10))
        self.status_dot = ctk.CTkLabel(self.status_frame, text="●", text_color="#A0AEC0",
                                       font=ctk.CTkFont(size=14))
        self.status_dot.pack(side="left", padx=(15, 5))
        self.status_lbl = ctk.CTkLabel(self.status_frame, text="ESTADO: DETENIDO",
                                       font=label_font, text_color="#A0AEC0")
        self.status_lbl.pack(side="left", padx=(0, 15))


if __name__ == "__main__":
    app = AudioDelayApp()

    def on_closing():
        app.stop()
        app._cleanup_virtual_cable()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()