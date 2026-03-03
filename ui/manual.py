import customtkinter as ctk

def show_manual(parent):
    top = ctk.CTkToplevel(parent)
    top.title("Manual de Uso - Micyn")
    top.geometry("600x500")
    top.resizable(False, False)
    top.attributes('-topmost', True)
    
    top.update_idletasks()
    w, h = 600, 500
    sw = top.winfo_screenwidth()
    sh = top.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    top.geometry(f"{w}x{h}+{x}+{y}")

    sf = ctk.CTkScrollableFrame(top, fg_color="#09090B", width=600, height=500)
    sf.pack(fill="both", expand=True, padx=20, pady=20)
    
    ttl_font = ctk.CTkFont(family="Google Sans", size=20, weight="bold")
    hd_font = ctk.CTkFont(family="Google Sans", size=16, weight="bold")
    txt_font = ctk.CTkFont(family="Google Sans", size=14)

    ctk.CTkLabel(sf, text="¿Cómo usar Micyn con OBS / Discord?", font=ttl_font, text_color="#FFFFFF", anchor="w").pack(fill="x", pady=(0, 15))
    
    ctk.CTkLabel(sf, text="1. Inicio Básico", font=hd_font, text_color="#4570F7", anchor="w").pack(fill="x", pady=(10, 5))
    ctk.CTkLabel(sf, text="- Selecciona tu micrófono real en la lista (ej: HyperX QuadCast).\n- Elige o escribe el tiempo de retraso deseado en segundos.\n- Presiona 'Iniciar retraso de audio' y la aplicación empezará a grabar su búfer.", 
                 font=txt_font, text_color="#A0AEC0", justify="left").pack(fill="x")

    ctk.CTkLabel(sf, text="2. Configuración en Windows", font=hd_font, text_color="#4570F7", anchor="w").pack(fill="x", pady=(20, 5))
    ctk.CTkLabel(sf, text="Windows requiere instalar el driver gratuito 'VB-Cable'. Micyn no funcionará sin él.\n\n⚠️  En Windows, la salida de audio NO se llamará 'Micyn', sino\n'CABLE Output (VB-Audio Virtual Cable)'  — ese nombre lo pone el driver\ny no se puede cambiar desde la app.\n\nUna vez que inicies el retraso, ve a tu programa (OBS, Discord, etc) y selecciona\ncomo micrófono/entrada el dispositivo  'CABLE Output (VB-Audio Virtual Cable)'.\nEse dispositivo emitirá el audio con el retraso configurado.", 
                 font=txt_font, text_color="#A0AEC0", justify="left").pack(fill="x")

    ctk.CTkLabel(sf, text="3. Configuración en Linux (Ubuntu)", font=hd_font, text_color="#4570F7", anchor="w").pack(fill="x", pady=(20, 5))
    ctk.CTkLabel(sf, text="En Linux la integración es automática.\nSolo ve a tu programa favorito, como OBS, Discord o los Ajustes de Sonido, y busca un micrófono virtual nuevo llamado 'Micyn'. ¡Elígelo y listo!", 
                 font=txt_font, text_color="#A0AEC0", justify="left").pack(fill="x")
    
    btn = ctk.CTkButton(sf, text="Entendido", width=200, height=40, font=ctk.CTkFont(family="Google Sans", weight="bold"), command=top.destroy)
    btn.pack(pady=30)
