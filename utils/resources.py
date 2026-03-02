import os
import sys
import tempfile

_app_lock_file = None

def check_single_instance():
    """Create a lock file to ensure only one instance of the app is running."""
    global _app_lock_file
    lock_file = os.path.join(tempfile.gettempdir(), 'micyn_app.lock')
    
    if sys.platform == "win32":
        try:
            import msvcrt
            _app_lock_file = open(lock_file, 'w')
            msvcrt.locking(_app_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except (IOError, OSError):
            return False
    else:
        try:
            import fcntl
            _app_lock_file = open(lock_file, 'w')
            fcntl.flock(_app_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
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
