# platform/base.py
from abc import ABC, abstractmethod

class PlatformAudio(ABC):
    @abstractmethod
    def init_virtual_cable(self):
        """Inicializa los dispositivos vituales requeridos."""
        pass
    
    @abstractmethod
    def cleanup_virtual_cable(self):
        """Limpia los dispositivos creados."""
        pass
    
    @abstractmethod
    def get_output_device(self, outputs: list) -> int:
        """Devuelve el índice del dispositivo de salida físico correcto."""
        pass
    
    @abstractmethod
    def post_stream_setup(self, stream_out, main_stream_ids: list) -> list:
        """Operaciones posteriores al inicio del stream principal."""
        pass
    
    @abstractmethod
    def route_monitors(self, monitor_stream_ids: list):
        """Configuración de ruteo para streams de monitoreo."""
        pass
