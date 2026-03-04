import os
import sys
import tempfile

_app_lock_file = None

def _is_pid_alive(pid: int) -> bool:
    """Verifica si un PID sigue vivo en el sistema."""
    try:
        os.kill(pid, 0)  # señal 0 = solo verificar, no matar
        return True
    except (ProcessLookupError, PermissionError):
        return False  # ProcessLookupError → no existe; PermissionError → existe pero no es nuestro
    except Exception:
        return True   # ante la duda, asumir que está vivo

def check_single_instance():
    """Create a lock file to ensure only one instance of the app is running.
    
    Escribe el PID en el archivo de lock para poder detectar locks stale
    (proceso anterior que murió sin liberar el lock).
    """
    global _app_lock_file
    lock_file = os.path.join(tempfile.gettempdir(), 'micyn_app.lock')

    if sys.platform == "win32":
        try:
            import msvcrt
            _app_lock_file = open(lock_file, 'w')
            _app_lock_file.write(str(os.getpid()))
            _app_lock_file.flush()
            msvcrt.locking(_app_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except (IOError, OSError):
            return False
    else:
        try:
            import fcntl

            # Si ya existe un lock, verificar si el PID que lo creó sigue vivo
            if os.path.exists(lock_file):
                try:
                    with open(lock_file, 'r') as f:
                        old_pid = int(f.read().strip())
                    if not _is_pid_alive(old_pid):
                        # Lock stale: el proceso anterior ya murió, limpiar
                        print(f"[Lock] Lock stale detectado (PID {old_pid} ya no existe). Limpiando.")
                        os.remove(lock_file)
                except Exception:
                    # No se pudo leer o parsear — intentar eliminar igual
                    try:
                        os.remove(lock_file)
                    except Exception:
                        pass

            _app_lock_file = open(lock_file, 'w')
            fcntl.flock(_app_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _app_lock_file.write(str(os.getpid()))
            _app_lock_file.flush()
            return True
        except (IOError, OSError):
            return False

def release_lock():
    global _app_lock_file
    if _app_lock_file:
        if sys.platform == "win32":
            import msvcrt
            try: msvcrt.locking(_app_lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            except: pass
        else:
            import fcntl
            try: fcntl.flock(_app_lock_file.fileno(), fcntl.LOCK_UN)
            except: pass
        try: _app_lock_file.close()
        except: pass
        _app_lock_file = None

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def set_windows_app_id():
    """Identidad de la aplicación (Windows Taskbar Icon Fix)."""
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = 'facyndev.micyn.app.1_0' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass
