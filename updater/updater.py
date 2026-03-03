import threading
import json
import urllib.request
import sys
import os
import subprocess

from constants import APP_VERSION, GITHUB_REPO


class Updater:
    def __init__(self, check_callback, update_found_callback, no_update_callback):
        self.check_callback = check_callback
        self.update_found_callback = update_found_callback
        self.no_update_callback = no_update_callback
        self.is_windows = sys.platform == "win32"

    # ─────────────────────────────────────────────────
    #  Verificación de versión
    # ─────────────────────────────────────────────────

    def check(self):
        """Dispara la verificación de actualizaciones en segundo plano."""
        threading.Thread(target=self._run_network_check, daemon=True).start()

    def _version_tuple(self, v: str):
        """Convierte '1.2.3' o '1.3.0-beta.1' en una tupla comparable."""
        # Tomar solo la parte numérica principal antes del '-'
        v = v.strip().lstrip("v").split("-")[0]
        try:
            return tuple(int(p) for p in v.split("."))
        except ValueError:
            return (0, 0, 0)

    def _run_network_check(self):
        """
        Consulta GitHub Releases y llama a los callbacks según resultado.
        - update_found_callback(version, download_url) si hay nueva versión.
        - no_update_callback() si está al día o hay error de red.
        """
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "Micyn-Updater/1.0"})
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())

            latest_tag = data.get("tag_name", "").strip()
            if not latest_tag:
                raise ValueError("tag_name vacío en respuesta de GitHub")

            current = self._version_tuple(APP_VERSION)
            latest  = self._version_tuple(latest_tag)

            print(f"[Updater] Versión instalada: {APP_VERSION}  |  Última en GitHub: {latest_tag}")

            if latest > current:
                # Buscar el asset correspondiente a la plataforma
                file_ext = ".exe" if self.is_windows else ".deb"
                download_url = None
                for asset in data.get("assets", []):
                    if asset["name"].lower().endswith(file_ext):
                        download_url = asset["browser_download_url"]
                        break

                if download_url:
                    clean_version = latest_tag.lstrip("v")
                    print(f"[Updater] Nueva versión disponible: {clean_version}  |  URL: {download_url}")
                    self.check_callback(lambda: self.update_found_callback(clean_version, download_url))
                    return
                else:
                    print(f"[Updater] Nueva versión detectada pero no hay asset '{file_ext}' en el release.")
            else:
                print("[Updater] La aplicación está al día.")

        except Exception as e:
            print(f"[Updater] Error comprobando actualizaciones: {e}")

        # Sin actualización o error → continuar normalmente
        self.check_callback(self.no_update_callback)

    # ─────────────────────────────────────────────────
    #  Descarga
    # ─────────────────────────────────────────────────

    def download_and_install(self, asset_url, temp_dir, progress_callback, complete_callback):
        """Inicia la descarga del asset en segundo plano."""
        threading.Thread(
            target=self._run_download,
            args=(asset_url, temp_dir, progress_callback, complete_callback),
            daemon=True
        ).start()

    def _run_download(self, url, temp_dir, progress_callback, complete_callback):
        """Descarga el archivo con reporte de progreso (0.0 → 1.0)."""
        filename = "micyn_update.exe" if self.is_windows else "micyn_update.deb"
        download_path = os.path.join(temp_dir, filename)

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Micyn-Updater/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.info().get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536  # 64 KB

                with open(download_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress_callback(downloaded / total_size)

            print(f"[Updater] Descarga completa: {download_path}")
            complete_callback(download_path)

        except Exception as e:
            print(f"[Updater] Error en descarga: {e}")
            progress_callback(f"Error al descargar: {e}")

    # ─────────────────────────────────────────────────
    #  Instalación
    # ─────────────────────────────────────────────────

    def execute_installer(self, download_path, root_destroy_callback):
        """
        Lanza la instalación del archivo descargado y cierra la app.

        - Linux  : pkexec dpkg -i <archivo.deb>  (actualiza el paquete instalado)
                   Fallback: xdg-open para que el usuario lo abra manualmente.
        - Windows: subprocess.Popen del .exe  (el instalador sobreescribe el ejecutable)
        """
        try:
            from utils.resources import release_lock
            release_lock()
        except Exception:
            pass

        try:
            if self.is_windows:
                self._install_windows(download_path)
            else:
                self._install_linux(download_path)
        except Exception as e:
            print(f"[Updater] Error lanzando instalador: {e}")
        finally:
            root_destroy_callback()

    def _install_linux(self, deb_path):
        """Instala el .deb con permisos de administrador vía pkexec."""
        env = os.environ.copy()
        # Pasar DISPLAY y XAUTHORITY para que pkexec pueda mostrarse en pantalla
        install_cmd = (
            f"pkexec env "
            f"DISPLAY={env.get('DISPLAY', ':0')} "
            f"XAUTHORITY={env.get('XAUTHORITY', '')} "
            f"dpkg -i '{deb_path}'"
        )
        print(f"[Updater] Ejecutando: {install_cmd}")
        result = subprocess.Popen(install_cmd, shell=True)
        # No esperamos — la app se cierra y dpkg sigue corriendo
        print(f"[Updater] Instalador dpkg lanzado (PID {result.pid})")

    def _install_windows(self, exe_path):
        """Ejecuta el instalador .exe en Windows."""
        print(f"[Updater] Lanzando instalador Windows: {exe_path}")
        # DETACHED_PROCESS para que el instalador sobreviva al cierre de la app
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            [exe_path],
            creationflags=DETACHED_PROCESS,
            close_fds=True
        )
