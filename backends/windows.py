import sys
import os
import subprocess
import sounddevice as sd
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import webbrowser

from .base import PlatformAudio
from constants import WINDOWS_CABLE_KEYWORDS

class WindowsAudio(PlatformAudio):
    def __init__(self, check_ui_callback=None):
        self.windows_cable_found = False
        self.windows_cable_index = None
        self.check_ui_callback = check_ui_callback
        self.app = None

    def init_virtual_cable(self):
        try:
            from utils.devices import _get_mme_hostapi_index
            devices = sd.query_devices()
            mme_idx = _get_mme_hostapi_index()

            # Log diagnóstico: mostrar todos los dispositivos MME para debugging
            print("[WindowsAudio] === Dispositivos MME disponibles ===")
            for i, d in enumerate(devices):
                if mme_idx is not None and d.get('hostapi') != mme_idx:
                    continue
                in_ch  = d['max_input_channels']
                out_ch = d['max_output_channels']
                print(f"  [{i:2}] IN={in_ch} OUT={out_ch}  {d['name']}")
            print("[WindowsAudio] ==========================================")

            # Primera pasada: priorizar "CABLE Input" en MME
            for i, d in enumerate(devices):
                if mme_idx is not None and d.get('hostapi') != mme_idx:
                    continue
                if d['max_output_channels'] > 0:
                    name_lower = d['name'].lower()
                    if any(kw in name_lower for kw in WINDOWS_CABLE_KEYWORDS) and 'input' in name_lower:
                        self.windows_cable_found = True
                        self.windows_cable_index = i
                        print(f"[WindowsAudio] CABLE Input detectado (Index {i}): {d['name']}")
                        return

            # Segunda pasada: cualquier cable en MME (fallback)
            for i, d in enumerate(devices):
                if mme_idx is not None and d.get('hostapi') != mme_idx:
                    continue
                if d['max_output_channels'] > 0:
                    name_lower = d['name'].lower()
                    if any(kw in name_lower for kw in WINDOWS_CABLE_KEYWORDS):
                        self.windows_cable_found = True
                        self.windows_cable_index = i
                        print(f"[WindowsAudio] Cable Virtual detectado (fallback, Index {i}): {d['name']}")
                        return

            print("[WindowsAudio] No se detectó ningún cable virtual.")
        except Exception as e:
            print(f"[WindowsAudio] Error detectando cable: {e}")

    def cleanup_virtual_cable(self):
        # En Windows no manejamos drivers virtuales de forma nativa.
        pass

    def get_output_device(self, outputs: list) -> int:
        if self.windows_cable_index is not None:
            return self.windows_cable_index
        return outputs[0]['original_index'] if outputs else None

    def post_stream_setup(self, stream_out, main_stream_ids: list) -> list:
        # En Windows la selección de dispositivo lo hace todo
        return []

    def route_monitors(self, monitor_stream_ids: list):
        pass

    def render_blocking_ui(self, main_frame, destroy_app_callback):
        """Muestra la UI de bloqueo usando los recursos de la app."""
        blocking_frame = ctk.CTkFrame(main_frame, fg_color="#09090B")
        blocking_frame.pack(fill="both", expand=True)

        content = ctk.CTkFrame(blocking_frame, fg_color="transparent")
        content.place(relx=0.5, rely=0.45, anchor="center")

        from utils.resources import resource_path
        try:
            from PIL import Image, ImageTk
            warn_path = resource_path("icon.png")
            img = Image.open(warn_path).convert("RGBA")
            img = img.resize((100, 100), Image.LANCZOS)
            _warn_img = ctk.CTkImage(light_image=img, dark_image=img, size=(100, 100))
            ctk.CTkLabel(content, text="", image=_warn_img).pack(pady=(0, 20))
        except:
            ctk.CTkLabel(content, text="⚠️", font=("Google Sans", 64)).pack(pady=(0, 20))

        ctk.CTkLabel(content, text="ACCESO BLOQUEADO", 
                     font=ctk.CTkFont(family="Google Sans", size=24, weight="bold"),
                     text_color="#FF4B4B").pack()
        
        ctk.CTkLabel(content, text="No se ha detectado el controlador de audio VB-Cable.\nEste componente es OBLIGATORIO para que Micyn funcione.", 
                     font=ctk.CTkFont(family="Google Sans", size=14),
                     text_color="#A0AEC0", justify="center").pack(pady=15)

        btn_f = ctk.CTkFont(family="Google Sans", size=14, weight="bold")
        
        ctk.CTkButton(content, text="📥 Descargar VB-Cable (Gratis)", width=280, height=45, corner_radius=22,
                      fg_color="#4570F7", hover_color="#2F52CC", font=btn_f,
                      command=lambda: webbrowser.open("https://vb-audio.com/Cable/")).pack(pady=5)
        
        def do_restart():
            self._recheck_cable_windows(destroy_app_callback)

        ctk.CTkButton(content, text="🔄 Reintentar detección", width=280, height=45, corner_radius=22,
                      fg_color="#27272A", hover_color="#3F3F46", text_color="#FFFFFF", font=btn_f,
                      command=do_restart).pack(pady=5)

    def _recheck_cable_windows(self, destroy_app_callback):
        """Reinicia la aplicación por completo."""
        try:
            from utils.resources import _app_lock_file, release_lock
            release_lock()

            executable = sys.executable
            args = sys.argv[:]
            
            destroy_app_callback()
            
            # DETACHED_PROCESS = 0x00000008, independiza el subproceso hijo
            subprocess.Popen([executable] + args, creationflags=0x00000008)
            os._exit(0) # Forzar cierre agresivo
                
        except Exception as e:
            print(f"Error reiniciando: {e}")
            os._exit(1)
