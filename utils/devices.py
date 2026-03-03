import sounddevice as sd
from constants import LINUX_DISPLAY_NAME, WINDOWS_CABLE_KEYWORDS, EXCLUDE_DEVICE_KEYWORDS

def clean_device_name(name):
    # Quitar sufijo técnico de ALSA: "HDA Intel PCH, ALC256 Analog (hw:0,0)" → "HDA Intel PCH"
    if ',' in name:
        name = name.split(',')[0].strip()
    # Quitar parte del tipo "(hw:X,Y)" si quedó
    if '(hw:' in name:
        name = name.split('(hw:')[0].strip()
    # Nombres especiales → texto amigable
    nl = name.lower()
    if nl == 'default':
        name = 'Dispositivo Principal (Predeterminado)'
    elif nl in ('pipewire', 'pulse'):
        name = f'Servidor de Audio ({name})'
    # Truncar si es muy largo
    if len(name) > 40:
        name = name[:37] + "..."
    return name or "Dispositivo Desconocido"

def populate_devices(os_system):
    """
    Busca y procesa los dispositivos físicos del sistema.
    Devuelve un tuple: (inputs, outputs).
    """
    inputs = []
    outputs = []
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            name_lower = d['name'].lower()
            
            # Requisito especial Windows: Nombrar salida como Cable Output
            # if os_system == "Windows" and any(kw in name_lower for kw in WINDOWS_CABLE_KEYWORDS):
            #     d['name'] = "CABLE Output (VB-Audio Virtual Cable)"
                
            if any(kw in name_lower for kw in EXCLUDE_DEVICE_KEYWORDS):
                continue
                
            d_copy = d.copy()
            d_copy['original_index'] = i
            
            if d['max_input_channels'] > 0:
                inputs.append(d_copy)
            if d['max_output_channels'] > 0:
                outputs.append(d_copy)
                
    except Exception as e:
        print(f"No se pudieron consultar dispositivos: {e}")
        
    return inputs, outputs

def get_sink_device_index(outputs, target_name):
    """
    Busca por un nombre específico entre la lista de salidas.
    """
    for out in outputs:
        if target_name.lower() in out['name'].lower():
            return out['original_index']
    return None
