import tkinter as tk
import customtkinter as ctk
import webbrowser
import os
from PIL import Image

from constants import DELAY_OPTIONS
from utils.resources import resource_path
from .manual import show_manual

class MainWindowBuilder:
    """Clase constructora del layout, asume poseer referencias de la app_context (AudioDelayApp)"""
    
    def __init__(self, app_context):
        self.app = app_context

    def build(self):
        """Construye todos los widgets bajo self.app.main_frame"""
        label_font = ctk.CTkFont(family="Google Sans", size=12, weight="bold")
        
        self.app.main_frame = ctk.CTkFrame(self.app, fg_color="#09090B")
        self.app.main_frame.pack(fill="both", expand=True)

        # -- ENCABEZADO --
        self.app.header_frame = ctk.CTkFrame(self.app.main_frame, fg_color="transparent", height=80)
        self.app.header_frame.pack(fill="x", padx=40, pady=(20, 10))
        
        logo_frame = ctk.CTkFrame(self.app.header_frame, fg_color="transparent")
        logo_frame.pack(side="left")
        
        try:
            logo_path = resource_path("icon.png")
            if not os.path.exists(logo_path):
                logo_path = "micyn_logo.jpg"
            img_pil = Image.open(logo_path).convert("RGBA")
            img_pil = img_pil.resize((50, 50), Image.LANCZOS)
            from PIL import ImageDraw
            mask = Image.new("L", (50, 50), 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle((0, 0, 50, 50), radius=12, fill=255)
            img_pil.putalpha(mask)
            self._logo_img = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(50, 50))
            ctk.CTkLabel(logo_frame, text="", image=self._logo_img).pack(side="left", padx=(0, 15))
        except: pass

        title_frame = ctk.CTkFrame(logo_frame, fg_color="transparent")
        title_frame.pack(side="left", fill="y", pady=5)
        # Quitar cursiva
        ctk.CTkLabel(title_frame, text="MICYN",
                     font=ctk.CTkFont(family="Google Sans", size=24, weight="bold"),
                     text_color="#FFFFFF").pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Retrasa tu audio al tiempo que quieras.",
                     font=ctk.CTkFont(family="Google Sans", size=13),
                     text_color="#A0AEC0").pack(anchor="w", pady=(0, 0))

        # Enlaces
        sub_font = ctk.CTkFont(family="Google Sans", size=13, underline=True)
        hf = ctk.CTkFrame(self.app.header_frame, fg_color="transparent")
        hf.pack(side="right", anchor="ne")
        nl = ctk.CTkLabel(hf, text="♥ by Facyn",
                          font=sub_font, text_color="#A0AEC0", cursor="hand2")
        nl.pack(pady=(5, 5))
        nl.bind("<Enter>",    lambda e: nl.configure(text_color="#FFFFFF"))
        nl.bind("<Leave>",    lambda e: nl.configure(text_color="#A0AEC0"))
        nl.bind("<Button-1>", lambda e: webbrowser.open("https://facyn.xyz"))
        
        hf.pack(pady=(0, 20))
        hl = ctk.CTkLabel(hf, text="? Manual de uso",
                          font=sub_font, text_color="#A0AEC0", cursor="hand2")
        hl.pack()
        hl.bind("<Enter>",    lambda e: hl.configure(text_color="#FFFFFF"))
        hl.bind("<Leave>",    lambda e: hl.configure(text_color="#A0AEC0"))
        hl.bind("<Button-1>", lambda e: show_manual(self.app))

        # -- WINDOWS VB-CABLE BLOQUEO DECLARATIVO --
        # Si la app corre en Windows, la inyección del bloqueo se debe realizar y retornar para evitar crear los controles.
        if self.app.os_system == "Windows" and not self.app.platform_audio.windows_cable_found:
            self.app.platform_audio.render_blocking_ui(self.app.main_frame, self.app.destroy)
            return

        # Helpers CustomTkinter Fixer
        def _bind_combo_open(cmb):
            def force_open(event):
                if cmb.cget("state") != "disabled":
                    if cmb._dropdown_menu.winfo_ismapped(): cmb._dropdown_menu.place_forget()
                    else: cmb._open_dropdown_menu()
            if hasattr(cmb, "_canvas"): cmb._canvas.bind("<Button-1>", force_open)
            if hasattr(cmb, "_text_label"): cmb._text_label.bind("<Button-1>", force_open)
            if hasattr(cmb, "_entry"): cmb._entry.bind("<Button-1>", force_open)

        # Entrada
        ctk.CTkLabel(self.app.main_frame, text="MICROFONO (ENTRADA)", font=label_font, text_color="#A0AEC0").pack(anchor="w", padx=40, pady=(0, 5))
        self.app.input_combobox = ctk.CTkComboBox(
            self.app.main_frame, width=280, height=45, corner_radius=10,
            font=ctk.CTkFont(family="Google Sans", size=14), dropdown_font=ctk.CTkFont(family="Google Sans", size=14),
            fg_color="#18181A", border_width=1, border_color="#27272A",
            button_color="#18181A", button_hover_color="#27272A",
            dropdown_fg_color="#18181A", text_color="#FFFFFF", state="readonly")
        self.app.input_combobox.pack(padx=40, pady=(0, 20), fill="x")
        _bind_combo_open(self.app.input_combobox)

        # Tiempo
        ctk.CTkLabel(self.app.main_frame, text="TIEMPO DE RETRASO", font=label_font, text_color="#A0AEC0").pack(anchor="w", padx=40, pady=(0, 5))
        self.app.time_combobox = ctk.CTkComboBox(
            self.app.main_frame, width=280, height=45, corner_radius=10,
            font=ctk.CTkFont(family="Google Sans", size=14), dropdown_font=ctk.CTkFont(family="Google Sans", size=14),
            fg_color="#18181A", border_width=1, border_color="#27272A",
            button_color="#18181A", button_hover_color="#27272A",
            values=list(DELAY_OPTIONS.keys()) + ["Personalizado (Segundos)"],
            dropdown_fg_color="#18181A", text_color="#FFFFFF", state="readonly",
            command=self.app._on_time_change)
        self.app.time_combobox.pack(padx=40, pady=(0, 5), fill="x")
        self.app.time_combobox.set("1 Minuto")
        _bind_combo_open(self.app.time_combobox)

        self.app.custom_time_entry = ctk.CTkEntry(
            self.app.main_frame, width=280, height=40, corner_radius=10,
            font=ctk.CTkFont(family="Google Sans", size=14), placeholder_text="Ej: 15 (segundos)",
            border_color="#27272A")
        self.app.custom_time_entry.pack(padx=40, pady=(0, 15), fill="x")
        self.app.custom_time_entry.configure(state="disabled", fg_color="#09090B")

        # Monitores
        ctk.CTkLabel(self.app.main_frame, text="ESCUCHAR MI PROPIA VOZ (solo auriculares, no afecta la salida Micyn)", font=label_font, text_color="#A0AEC0").pack(anchor="w", padx=40, pady=(0, 5))

        mc = ctk.CTkFrame(self.app.main_frame, height=60, fg_color="transparent")
        mc.pack(padx=40, pady=(0, 20), fill="x")
        
        mf1 = ctk.CTkFrame(mc, height=60, fg_color="#18181A", corner_radius=12)
        mf1.pack_propagate(False)
        mf1.pack(side="left", expand=True, fill="both", padx=(0, 5))
        self.app.monitor_var = ctk.BooleanVar(value=False)
        self.app.monitor_chk = ctk.CTkSwitch(
            mf1, text="Escuchar sin delay", variable=self.app.monitor_var,
            font=ctk.CTkFont(family="Google Sans", size=12, weight="bold"),
            text_color="#FFFFFF", progress_color="#4570F7",
            button_color="#FFFFFF", button_hover_color="#3F3F46",
            fg_color="#27272A", switch_width=36, switch_height=18)
        self.app.monitor_chk.pack(expand=True, padx=10, pady=10)

        mf2 = ctk.CTkFrame(mc, height=60, fg_color="#18181A", corner_radius=12)
        mf2.pack_propagate(False)
        mf2.pack(side="right", expand=True, fill="both", padx=(5, 0))
        self.app.monitor_delay_var = ctk.BooleanVar(value=False)
        self.app.monitor_delay_chk = ctk.CTkSwitch(
            mf2, text="Escuchar con delay", variable=self.app.monitor_delay_var,
            font=ctk.CTkFont(family="Google Sans", size=12, weight="bold"),
            text_color="#FFFFFF", progress_color="#4570F7",
            button_color="#FFFFFF", button_hover_color="#3F3F46",
            fg_color="#27272A", switch_width=36, switch_height=18)
        self.app.monitor_delay_chk.pack(expand=True, padx=10, pady=10)

        # Medidores (VUs) en layout horizontal ocupando el espacio restante
        vumeters_container = ctk.CTkFrame(self.app.main_frame, fg_color="transparent")
        vumeters_container.pack(padx=40, pady=(0, 20), fill="x")

        # Vumetro: Entrada
        vu_in_frame = ctk.CTkFrame(vumeters_container, fg_color="transparent")
        vu_in_frame.pack(side="left", expand=True, fill="both", padx=(0, 5))
        ctk.CTkLabel(vu_in_frame, text="ENTRADA MIC", font=label_font, text_color="#A0AEC0").pack(anchor="center", pady=(0, 5))
        abg_in = ctk.CTkFrame(vu_in_frame, fg_color="#18181A", corner_radius=15, height=80)
        abg_in.pack_propagate(False)
        abg_in.pack(fill="x")
        self.app.vumeter_in_container = ctk.CTkFrame(abg_in, width=130, height=60, fg_color="transparent")
        self.app.vumeter_in_container.place(relx=0.5, rely=0.5, anchor="center")

        # Vumetro: Salida Virtual
        vu_out_frame = ctk.CTkFrame(vumeters_container, fg_color="transparent")
        vu_out_frame.pack(side="right", expand=True, fill="both", padx=(5, 0))
        out_lbl = "SALIDA: CABLE" if self.app.os_system == "Windows" else "SALIDA MICYN"
        ctk.CTkLabel(vu_out_frame, text=out_lbl, font=label_font, text_color="#A0AEC0").pack(anchor="center", pady=(0, 5))
        abg_out = ctk.CTkFrame(vu_out_frame, fg_color="#18181A", corner_radius=15, height=80)
        abg_out.pack_propagate(False)
        abg_out.pack(fill="x")
        self.app.vumeter_out_container = ctk.CTkFrame(abg_out, width=130, height=60, fg_color="transparent")
        self.app.vumeter_out_container.place(relx=0.5, rely=0.5, anchor="center")
        
        self.app.waiting_label_out = ctk.CTkLabel(
            abg_out, text="ESPERANDO...", 
            font=ctk.CTkFont(family="Google Sans", size=12, weight="bold"),
            text_color="#F59E0B"
        )

        bar_width = 6
        spacing   = 6
        total_w   = self.app.num_bars * bar_width + (self.app.num_bars - 1) * spacing
        offset_x  = (130 - total_w) // 2

        self.app.in_bars = []
        self.app.out_bars = []

        # Dibujar barras de Entrada (Azul) y Salida (Verde) con CTkFrame renderizado
        for i in range(self.app.num_bars):
            xc = offset_x + i * (bar_width + spacing)
            
            bar_in = ctk.CTkFrame(self.app.vumeter_in_container, width=bar_width, height=6, corner_radius=3, fg_color="#4570F7")
            bar_in.place(x=xc, rely=0.5, anchor="center")
            self.app.in_bars.append(bar_in)
            
            bar_out = ctk.CTkFrame(self.app.vumeter_out_container, width=bar_width, height=6, corner_radius=3, fg_color="#10B981")
            bar_out.place(x=xc, rely=0.5, anchor="center")
            self.app.out_bars.append(bar_out)

        # Layout Botones
        btn_font = ctk.CTkFont(family="Google Sans", size=17, weight="bold")
        self.app.start_btn = ctk.CTkButton(
            self.app.main_frame, text="▶  Iniciar retraso de audio",
            font=btn_font, width=280, height=50, corner_radius=25,
            fg_color="#4570F7", hover_color="#2F52CC", text_color="#FFFFFF",
            command=self.app.play)
        self.app.start_btn.pack(padx=40, pady=(0, 15), fill="x")

        self.app.stop_btn = ctk.CTkButton(
            self.app.main_frame, text="■  Detener",
            font=btn_font, width=280, height=50, corner_radius=25,
            fg_color="#27272A", hover_color="#E0E0E0", text_color="#7A8084",
            state="disabled", command=self.app.stop)
        self.app.stop_btn.pack(padx=40, pady=(0, 30), fill="x")

        # Status
        ctk.CTkFrame(self.app.main_frame, height=1, fg_color="#27272A").pack(pady=(10, 20), fill="x", padx=40)
        self.app.status_frame = ctk.CTkFrame(self.app.main_frame, fg_color="#09090B", corner_radius=15, height=50)
        self.app.status_frame.pack(pady=(0, 10))
        self.app.status_dot = ctk.CTkLabel(
            self.app.status_frame, text="●", text_color="#A0AEC0",
            font=ctk.CTkFont(size=22))
        self.app.status_dot.pack(side="left", padx=(20, 10))
        self.app.status_lbl = ctk.CTkLabel(
            self.app.status_frame, text="ESTADO: DETENIDO",
            font=ctk.CTkFont(family="Google Sans", size=20, weight="bold"),
            text_color="#A0AEC0")
        self.app.status_lbl.pack(side="left", padx=(0, 25))
