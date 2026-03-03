import threading
import json
import urllib.request
import urllib.error
import ssl
import sys
import os
import subprocess

from constants import APP_VERSION, GITHUB_REPO


def _make_ssl_context():
    """
    Crea un contexto SSL compatible con PyInstaller.
    En binarios compilados, urllib no encuentra los certs del sistema;
    intentamos con certifi primero, y si no hay, desactivamos verificación.
    """
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        return ctx
    except Exception:
        pass
    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        pass
    # Último recurso: sin verificación (mejor que fallar silenciosamente)
    ctx = ssl._create_unverified_context()
    return ctx


class Updater:
    def __init__(self, check_callback, update_found_callback, no_update_callback):
        self.check_callback      = check_callback
        self.update_found_callback = update_found_callback
        self.no_update_callback  = no_update_callback
        self.is_windows          = sys.platform == "win32"

    # ─────────────────────────────────────────────────
    #  Verificación de versión
    # ─────────────────────────────────────────────────

    def check(self):
        """Dispara la verificación de actualizaciones en segundo plano."""
        threading.Thread(target=self._run_network_check, daemon=True).start()

    def _version_tuple(self, v: str):
        """
        Convierte '1.2.3' o '1.3.0-beta.1' en una tupla comparable.
        Solo considera la parte numérica principal (antes del '-').
        """
        v = v.strip().lstrip("v").split("-")[0]
        try:
            return tuple(int(p) for p in v.split("."))
        except ValueError:
            return (0, 0, 0)

    def _run_network_check(self):
        """
        Consulta GitHub Releases y llama a los callbacks según resultado.
        - update_found_callback(version, download_url) si hay nueva versión.
        - no_update_callback() si ya está al día o hay error de red.
        """
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            ctx = _make_ssl_context()
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": f"Micyn-Updater/{APP_VERSION}",
                    "Accept":     "application/vnd.github+json",
                }
            )
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                data = json.loads(response.read().decode("utf-8"))

            latest_tag = data.get("tag_name", "").strip()
            if not latest_tag:
                print("[Updater] Respuesta de GitHub sin tag_name.")
                self.check_callback(self.no_update_callback)
                return

            current = self._version_tuple(APP_VERSION)
            latest  = self._version_tuple(latest_tag)

            print(
                f"[Updater] Versión instalada: {APP_VERSION}  "
                f"|  Última en GitHub: {latest_tag}  "
                f"|  {'ACTUALIZAR' if latest > current else 'al día'}"
            )

            if latest > current:
                # Buscar el asset correcto según plataforma
                file_ext    = ".exe" if self.is_windows else ".deb"
                download_url = None
                for asset in data.get("assets", []):
                    if asset.get("name", "").lower().endswith(file_ext):
                        download_url = asset["browser_download_url"]
                        break

                if download_url:
                    clean_version = latest_tag.lstrip("v")
                    print(f"[Updater] Descarga disponible: {download_url}")
                    self.check_callback(
                        lambda: self.update_found_callback(clean_version, download_url)
                    )
                    return
                else:
                    print(f"[Updater] Nueva versión pero no hay asset '{file_ext}' en el release.")

        except urllib.error.URLError as e:
            print(f"[Updater] Error de red: {e.reason}")
        except Exception as e:
            print(f"[Updater] Error inesperado al verificar: {type(e).__name__}: {e}")

        # Sin actualización disponible, o error → continuar normalmente
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
        filename      = "micyn_update.exe" if self.is_windows else "micyn_update.deb"
        download_path = os.path.join(temp_dir, filename)

        try:
            ctx = _make_ssl_context()
            req = urllib.request.Request(
                url,
                headers={"User-Agent": f"Micyn-Updater/{APP_VERSION}"}
            )
            with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
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
            print(f"[Updater] Error en descarga: {type(e).__name__}: {e}")
            progress_callback(f"Error al descargar: {e}")

    # ─────────────────────────────────────────────────
    #  Instalación
    # ─────────────────────────────────────────────────

    def execute_installer(self, download_path, root_destroy_callback):
        """
        Lanza la instalación del archivo descargado y cierra la app.

        - Linux  : pkexec dpkg -i <archivo.deb>  (actualiza el paquete instalado)
                   Fallback: xdg-open si pkexec no está disponible.
        - Windows: subprocess.Popen del .exe como proceso independiente.
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
        display     = env.get("DISPLAY", ":0")
        xauth       = env.get("XAUTHORITY", "")
        install_cmd = (
            f"pkexec env DISPLAY={display} XAUTHORITY={xauth} "
            f"dpkg -i '{deb_path}'"
        )
        print(f"[Updater] Ejecutando: {install_cmd}")
        try:
            proc = subprocess.Popen(install_cmd, shell=True)
            print(f"[Updater] dpkg iniciado (PID {proc.pid})")
        except Exception as e:
            print(f"[Updater] pkexec falló ({e}), abriendo con xdg-open...")
            subprocess.Popen(["xdg-open", deb_path])

    def _install_windows(self, exe_path):
        """Ejecuta el instalador .exe en Windows como proceso independiente."""
        print(f"[Updater] Lanzando instalador Windows: {exe_path}")
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            [exe_path],
            creationflags=DETACHED_PROCESS,
            close_fds=True
        )
