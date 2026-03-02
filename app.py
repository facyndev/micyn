import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import sys
import random
from PIL import Image, ImageTk

from constants import APP_NAME, COLOR_BG, DELAY_OPTIONS
from utils.devices import populate_devices, get_sink_device_index
from utils.resources import resource_path

from platform.base import PlatformAudio
from platform.linux import LinuxAudio
from platform.windows import WindowsAudio

from audio.loop import start_audio_loop
from ui.splash import SplashScreen
from ui.main_window import MainWindowBuilder

# Configuración global
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AudioDelayApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.os_system = "Windows" if sys.platform == "win32" else "Linux"
        
        # Estado y lógica
        self.is_running = False
        self.audio_thread = None
        self.ring_buffer = None
        self.audio_engine = None  # Instancia que se inyecta desde audio/loop.py
        
        # Dispositivos y Plataforma
        self.inputs = []
        self.outputs = []
        
        if self.os_system == "Windows":
            self.platform_audio = WindowsAudio(check_ui_callback=self._recheck_cable_windows)
        else:
            self.platform_audio = LinuxAudio()
            
        self.platform_audio.app = self
        self.platform_audio.init_virtual_cable()
        
        # Ícono — debe aplicarse ANTES de withdraw para que el WM lo registre
        self._apply_icon()
        
        # Inicializar variables de vúmetros (listas usadas por _animate_bars)
        self.num_bars = 7
        self.in_bars  = []
        self.out_bars = []
        self.current_amplitudes     = [0.0] * self.num_bars
        self.target_amplitudes      = [0.0] * self.num_bars
        self.current_amplitudes_out = [0.0] * self.num_bars
        self.target_amplitudes_out  = [0.0] * self.num_bars
        self.audio_engine = None
        
        self.withdraw()
        self.splash = SplashScreen(self, self.on_splash_ready)

    def _apply_icon(self, window=None):
        """Aplica el ícono al widget indicado (o a self si no se pasa ninguno).
        Funciona tanto en modo script como compilado con PyInstaller."""
        target = window or self
        try:
            icon_path = resource_path("icon.png")
            import os
            if not os.path.exists(icon_path):
                return
            img = Image.open(icon_path).convert("RGBA")
            # X11 tiene un límite de tamaño para iconos — 64×64 es seguro en todos los WMs
            img = img.resize((64, 64), Image.LANCZOS)
            # Tkinter necesita una referencia viva a la imagen
            self._icon_tk = ImageTk.PhotoImage(img, master=self)
            target.iconphoto(True, self._icon_tk)
            if self.os_system == "Windows":
                ico_path = resource_path("icon.ico")
                if os.path.exists(ico_path):
                    try:
                        target.iconbitmap(ico_path)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[icon] No se pudo aplicar ícono: {e}")

    def on_splash_ready(self):
        self.deiconify()
        self.title(f"{APP_NAME}")
        self.geometry("900x700")
        self.minsize(700, 500)
        self.configure(fg_color=COLOR_BG)
        # Re-aplicar el ícono después de deiconify para asegurar que el WM lo muestre
        self._apply_icon()

        self._populate_devices()
        MainWindowBuilder(self).build()
        # _animate_bars llama self.in_bars / self.out_bars que ahora crea build()
        self._animate_bars()
        # Poblar dispositivos después de que los widgets existen
        self.after(500, self._populate_devices)

    def _populate_devices(self):
        from utils.devices import clean_device_name
        import sounddevice as sd
        
        self.inputs, self.outputs = populate_devices(self.os_system)
        
        if not hasattr(self, 'input_combobox'):
            return
        
        in_names = [clean_device_name(d['name']) for d in self.inputs]
        self.input_combobox.configure(values=in_names)
        
        if not in_names:
            return
        
        # Seleccionar el dispositivo por defecto
        try:
            default_in_idx = sd.default.device[0]
            all_devs = sd.query_devices()
            default_name = all_devs[default_in_idx]['name'] if default_in_idx is not None else ""
            for i, dev in enumerate(self.inputs):
                if dev['original_index'] == default_in_idx or dev['name'] == default_name:
                    self.input_combobox.set(in_names[i])
                    return
        except Exception:
            pass
        
        self.input_combobox.set(in_names[0])

    def _recheck_cable_windows(self):
        """Callback requerido por WindowsAudio para resetear app si no hay VB-Cable"""
        if isinstance(self.platform_audio, WindowsAudio):
            self.platform_audio._recheck_cable_windows(self.destroy)

    def _on_time_change(self, choice):
        if not hasattr(self, 'custom_time_entry'): return
        if choice == "Personalizado (Segundos)":
            self.custom_time_entry.configure(state="normal", fg_color="#18181A")
        else:
            self.custom_time_entry.configure(state="disabled", fg_color="#09090B")

    def play(self):
        if self.is_running: return
        
        from utils.devices import clean_device_name
        in_label = self.input_combobox.get()
        dev_in_id = next((d['original_index'] for d in self.inputs if clean_device_name(d['name']) == in_label), None)
        # Fallback: coincidencia parcial por si el nombre crudo coincide
        if dev_in_id is None:
            dev_in_id = next((d['original_index'] for d in self.inputs if d['name'] == in_label), None)
        
        if dev_in_id is None:
            messagebox.showwarning("Error", "Debes seleccionar un micrófono válido.")
            return

        out_device_id = self.platform_audio.get_output_device(self.outputs)
        
        # Tiempo
        delay_seconds = 60
        opt = self.time_combobox.get()
        if opt == "Personalizado (Segundos)":
            try:
                val = float(self.custom_time_entry.get())
                if val <= 0: raise ValueError
                delay_seconds = val
            except ValueError:
                messagebox.showerror("Error", "Ingresa un número válido de segundos mayor a 0.")
                return
        else:
            delay_seconds = DELAY_OPTIONS.get(opt, 60)

        # UI Updates
        self.is_running = True
        # Botón principal: mantiene azul con texto blanco mientras transmite
        self.start_btn.configure(
            state="disabled",
            fg_color="#4570F7",
            text_color="#FFFFFF",
            text="▶ Transmitiendo..."
        )
        self.input_combobox.configure(state="disabled")
        self.time_combobox.configure(state="disabled")
        self.custom_time_entry.configure(state="disabled", fg_color="#09090B")
        self.monitor_chk.configure(state="disabled")
        self.monitor_delay_chk.configure(state="disabled")
        
        self.status_dot.configure(text_color="#10B981")
        self.status_lbl.configure(text=f"ESTADO: GRABANDO (RETRASO: {delay_seconds}s)")
        
        listen_live = self.monitor_chk.get() == 1
        listen_delay = self.monitor_delay_chk.get() == 1

        monitor_device_id = None
        listen_delay_device_id = None
        
        import sounddevice as sd
        if listen_live or listen_delay:
            monitor_device_id = sd.default.device[1]
            listen_delay_device_id = sd.default.device[1]

        self.audio_thread = threading.Thread(
            target=start_audio_loop,
            args=(self, delay_seconds, dev_in_id, out_device_id, monitor_device_id, listen_delay_device_id, listen_live, listen_delay),
            daemon=True
        )
        self.audio_thread.start()
        
        # Botón secundario: fondo blanco, texto negro cuando está activo (sin rojo)
        self.stop_btn.configure(state="normal", fg_color="#FFFFFF", text_color="#000000")

    def stop(self):
        self.is_running = False

        for i in range(self.num_bars):
            self.target_amplitudes[i] = 0.0
            self.target_amplitudes_out[i] = 0.0

        if hasattr(self, 'start_btn') and self.start_btn.winfo_exists():
            self.start_btn.configure(state="normal", fg_color="#4570F7", text_color="#FFFFFF", text="▶  Iniciar retraso de audio")
            self.input_combobox.configure(state="readonly")
            self.time_combobox.configure(state="readonly")
            self._on_time_change(self.time_combobox.get())
            self.monitor_chk.configure(state="normal")
            self.monitor_delay_chk.configure(state="normal")
            self.stop_btn.configure(state="disabled", text_color="#7A8084", fg_color="#27272A")
            self.status_dot.configure(text_color="#A0AEC0")
            self.status_lbl.configure(text="ESTADO: APAGADO")

    def _stop_ui(self):
        self.stop()

    def _animate_bars(self):
        """Bucle de UI principal para animar Vumeters interpolando desde el audio_engine"""
        try:
            if not self.winfo_exists(): return
            
            if self.is_running and self.audio_engine:
                in_amp = self.audio_engine.current_in_amp
                out_amp = self.audio_engine.current_out_amp
                
                # Decaimiento y picos simulados
                self.audio_engine.current_in_amp *= 0.8
                self.audio_engine.current_out_amp *= 0.8

                active_bars_in = int(min(in_amp * 50, self.num_bars))
                active_bars_out = int(min(out_amp * 50, self.num_bars))

                # Smooth targeting
                for i in range(self.num_bars):
                    target_in = 1.0 if i < active_bars_in else (random.uniform(0.1, 0.3) if in_amp > 0.01 else 0.0)
                    self.target_amplitudes[i] = max(self.target_amplitudes[i] * 0.7, target_in)
                    self.current_amplitudes[i] += (self.target_amplitudes[i] - self.current_amplitudes[i]) * 0.3

                    target_out = 1.0 if i < active_bars_out else (random.uniform(0.1, 0.3) if out_amp > 0.01 else 0.0)
                    self.target_amplitudes_out[i] = max(self.target_amplitudes_out[i] * 0.7, target_out)
                    self.current_amplitudes_out[i] += (self.target_amplitudes_out[i] - self.current_amplitudes_out[i]) * 0.3

                for i, bar in enumerate(self.in_bars):
                    h = max(4, int(self.current_amplitudes[i] * 50))
                    bar.configure(height=h)

                for i, bar in enumerate(self.out_bars):
                    h = max(4, int(self.current_amplitudes_out[i] * 50))
                    bar.configure(height=h)
            else:
                for bar in self.in_bars + self.out_bars:
                    bar.configure(height=4)
                    
            self.after(30, self._animate_bars)
        except Exception:
            pass
