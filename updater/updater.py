import threading
import json
import urllib.request
import sys
import os
import subprocess
import tkinter as tk
from tkinter import messagebox
from constants import APP_VERSION, GITHUB_REPO

class Updater:
    def __init__(self, check_callback, update_found_callback, no_update_callback):
        self.check_callback = check_callback
        self.update_found_callback = update_found_callback
        self.no_update_callback = no_update_callback
        self.os_system_is_windows = sys.platform == "win32"

    def check(self):
        """Dispara la verificación en segundo plano."""
        threading.Thread(target=self._run_network_check, daemon=True).start()

    def _run_network_check(self):
        """
        Consulta la versión en GitHub. Llama a los callbacks correspondientes.
        """
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest = data.get("tag_name", "").lstrip("v")
                
                # Comparar versión semántica simple
                current_parts = [int(p) for p in APP_VERSION.split('.')]
                latest_parts = [int(p) for p in latest.split('.')]
                
                is_newer = False
                for c, l in zip(current_parts, latest_parts):
                    if l > c:
                        is_newer = True
                        break
                    elif l < c:
                        is_newer = False
                        break
                        
                if is_newer:
                    assets = data.get("assets", [])
                    download_url = None
                    file_ext = ".exe" if self.os_system_is_windows else ".deb"
                    
                    for asset in assets:
                        if asset["name"].endswith(file_ext):
                            download_url = asset["browser_download_url"]
                            break
                            
                    if download_url:
                        self.check_callback(lambda: self.update_found_callback(latest, download_url))
                        return
                        
        except Exception as e:
            print(f"Error comprobando actualizaciones: {e}")
            
        self.check_callback(self.no_update_callback)

    def download_and_install(self, asset_url, temp_dir, progress_callback, complete_callback):
        """Inicia el proceso de descarga."""
        threading.Thread(target=self._run_download, args=(asset_url, temp_dir, progress_callback, complete_callback), daemon=True).start()

    def _run_download(self, url, temp_dir, progress_callback, complete_callback):
        """Descarga e invoca el callback de finalización."""
        filename = "micyn_update.exe" if self.os_system_is_windows else "micyn_update.deb"
        download_path = os.path.join(temp_dir, filename)
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                total_size = int(response.info().get('Content-Length', 0))
                downloaded = 0
                chunk_size = 8192
                with open(download_path, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk: break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = downloaded / total_size
                            progress_callback(percent)
                            
            complete_callback(download_path)
            
        except Exception as e:
            progress_callback(-1) # Error status
            import tkinter as tk
            from tkinter import messagebox
            error_msg = str(e)
            # Callbacks must be thread safe
            progress_callback(f"Error: {e}")

    def execute_installer(self, download_path, root_destroy_callback):
        """Abre el archivo y finaliza el proceso."""
        try:
            from utils.resources import release_lock
            release_lock()

            if self.os_system_is_windows: 
                os.startfile(download_path)
            else:
                try:
                    install_cmd = f"pkexec env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY dpkg -i '{download_path}'"
                    subprocess.Popen(install_cmd, shell=True)
                except Exception:
                    subprocess.Popen(["xdg-open", download_path])
        except Exception as e:
            print(f"Error al intentar ejecutar el instalador: {e}")
        finally:
            root_destroy_callback()
