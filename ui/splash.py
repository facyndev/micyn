import os
import tkinter as tk
import customtkinter as ctk
import tempfile
import webbrowser

from utils.resources import resource_path
from updater.updater import Updater

class SplashScreen(ctk.CTkToplevel):
    def __init__(self, parent, on_ready_callback):
        super().__init__(parent)
        self.parent = parent
        self.on_ready_callback = on_ready_callback
        
        self.title("Micyn")
        self.geometry("400x320")
        self.resizable(False, False)
        self.configure(fg_color="#09090B")
        self.attributes('-topmost', True)

        # Centrar splash en pantalla
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw // 2) - 200
        y = (sh // 2) - 160
        self.geometry(f"+{x}+{y}")

        self._create_widgets()

        # Aplicar ícono al splash también (usando la imagen ya cargada en el padre)
        try:
            self.parent._apply_icon(self)
        except Exception:
            pass

        # Iniciar verificador de actualizaciones
        self.updater = Updater(
            check_callback=self._safe_updater_call,
            update_found_callback=self._on_update_found,
            no_update_callback=self.on_ready
        )
        self.updater.check()

    def _safe_updater_call(self, func):
        """Asegura que las llamadas a la UI desde el hilo de descarga se hagan en mainloop."""
        if self.winfo_exists():
            self.after(0, func)

    def _create_widgets(self):
        # Frame principal centrado verticalmente
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.place(relx=0.5, rely=0.5, anchor="center")

        try:
            from PIL import Image, ImageDraw
            logo_path = resource_path("icon.png")
            if not os.path.exists(logo_path):
                logo_path = "micyn_logo.jpg"
                
            img = Image.open(logo_path).convert("RGBA")
            img = img.resize((120, 120), Image.LANCZOS)
            
            mask = Image.new("L", (120, 120), 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle((0, 0, 120, 120), radius=25, fill=255)
            img.putalpha(mask)
            
            self._logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 120))
            ctk.CTkLabel(self.container, text="", image=self._logo_img).pack(pady=(0, 12))
        except:
            ctk.CTkLabel(self.container, text="Micyn", font=("Google Sans", 32, "bold"), text_color="#FFFFFF").pack(pady=(0, 12))

        self.status_label = ctk.CTkLabel(self.container, text="Buscando actualizaciones...", font=("Google Sans", 14), text_color="#A0AEC0")
        self.status_label.pack(pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(self.container, width=280, height=4, corner_radius=2, progress_color="#4570F7", fg_color="#18181A")
        self.progress_bar.pack(pady=(0, 10))
        self.progress_bar.set(0)
        self.progress_bar.start()

    def _on_update_found(self, version, download_url):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

        # Actualizar ventana al nuevo tamaño
        self.geometry("400x400")
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw // 2) - 200
        y = (sh // 2) - 200
        self.geometry(f"400x400+{x}+{y}")

        # Actualizar el texto de estado (ya existe en el container)
        self.status_label.configure(
            text=f"¡NUEVA VERSIÓN: v{version}!",
            text_color="#FFFFFF",
            font=("Google Sans", 16, "bold")
        )

        # Botones dentro del mismo container (debajo de imagen y texto)
        btn_font = ctk.CTkFont(family="Google Sans", size=15, weight="bold")

        update_btn = ctk.CTkButton(
            self.container, text="⚡ Actualizar ahora",
            width=280, height=50, corner_radius=25,
            fg_color="#4570F7", hover_color="#2F52CC", text_color="#FFFFFF",
            font=btn_font,
            command=lambda: self._start_download(download_url, update_btn, skip_btn)
        )
        update_btn.pack(pady=(20, 8))

        skip_btn = ctk.CTkButton(
            self.container, text="Omitir por ahora",
            width=280, height=50, corner_radius=25,
            fg_color="#27272A", hover_color="#3F3F46", text_color="#7A8084",
            font=btn_font,
            command=self.on_ready
        )
        skip_btn.pack(pady=(0, 10))


    def _start_download(self, url, btn1, btn2):
        btn1.pack_forget()
        btn2.pack_forget()
        self.status_label.configure(text="Descargando actualización...", text_color="#4570F7")
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=20)
        
        self.updater.download_and_install(
            asset_url=url,
            temp_dir=tempfile.gettempdir(),
            progress_callback=self._update_progress_ui,
            complete_callback=self._on_download_complete
        )

    def _update_progress_ui(self, percent_or_error):
        if not self.winfo_exists(): return
        
        if isinstance(percent_or_error, float):
            def up():
                self.progress_bar.set(percent_or_error)
            self.after(0, up)
        else:
            # Es un mensaje de error
            self.after(0, lambda: self.status_label.configure(text="Error de conexión.", text_color="#FF4B4B"))
            self.after(2000, self.on_ready)

    def _on_download_complete(self, download_path):
        if not self.winfo_exists(): return
        self.after(0, lambda: self.status_label.configure(text="Iniciando instalador...", text_color="#10B981"))
        self.after(500, lambda: self.updater.execute_installer(download_path, self.parent.destroy))

    def on_ready(self):
        """Notifica al orquestador principal que el inicio puede continuar."""
        if self.winfo_exists():
            self.destroy()
        self.parent.after(0, self.on_ready_callback)
