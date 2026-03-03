# constants.py
APP_VERSION = "1.3.9"
APP_NAME = "Micyn"
SAMPLERATE = 44100
CHANNELS = 1
CHUNK_SIZE = 2048
NUM_BARS = 7

COLOR_BG = "#09090B"
COLOR_CARD = "#18181A"
COLOR_BORDER = "#27272A"
COLOR_PRIMARY = "#4570F7"
COLOR_PRIMARY_HOVER = "#2F52CC"
COLOR_TEXT = "#FFFFFF"
COLOR_TEXT_MUTED = "#A0AEC0"
COLOR_SUCCESS = "#10B981"
COLOR_WARNING = "#F59E0B"
COLOR_ERROR = "#FF4B4B"

GITHUB_REPO = "facyndev/micyn"
DELAY_OPTIONS = {
    "30 Segundos": 30, 
    "1 Minuto": 60, 
    "2 Minutos": 120, 
    "5 Minutos": 300
}

LINUX_SINK_NAME = "DelaySinkInternal"
LINUX_OUTPUT_SINK = "MicynOutput"
LINUX_SOURCE_NAME = "MicynMic"
LINUX_DISPLAY_NAME = "Micyn"

WINDOWS_CABLE_KEYWORDS = ["cable", "virtual", "vb-audio", "voicemeeter"]
EXCLUDE_DEVICE_KEYWORDS = [
    'iec958', 'spdif', 'surround', 'dmix', 'dsnoop',
    'sysdefault', 'front:', 'rear:', 'center_lfe',
    'delaysinkinternal', 'micynoutput', 'micynmic', 'micyn'
]
