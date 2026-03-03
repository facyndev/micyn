from utils.resources import resource_path, check_single_instance
from app import AudioDelayApp
import os, sys, tkinter as tk
from tkinter import messagebox

if __name__ == "__main__":
    if not check_single_instance():
        root = tk.Tk(); root.withdraw()
        messagebox.showwarning("Micyn ya está abierto", "La aplicación ya se encuentra en ejecución.")
        os._exit(0)
    
    app = AudioDelayApp()
    
    def on_closing():
        try: app.stop()
        except: pass
        app.platform_audio.cleanup_virtual_cable()
        app.destroy()
        os._exit(0)
    
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()