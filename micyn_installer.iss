; ============================================================
;  Micyn — Script de Inno Setup
;  Genera un instalador nativo de Windows (.exe)
;  El archivo de salida se llama: Micyn-Setup-{version}.exe
;
;  REQUISITO DE BUILD: tener Inno Setup instalado en la máquina
;  de compilación. Descarga: https://jrsoftware.org/isdl.php
; ============================================================

#define MyAppName      "Micyn"
#define MyAppPublisher "Facyn"
#define MyAppURL       "https://facyn.xyz"
#define MyAppExeName   "micyn.exe"
; La versión se inyecta desde build_windows.bat via /DMyAppVersion=...
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
; Identificador único de la aplicación — NO cambiar entre versiones
AppId={{B8F2A1C7-4D3E-4F9A-8B6C-2E0D5A7F3C91}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
; Sin panel de bienvenida en modo silencioso
DisableWelcomePage=no
; Icono del instalador
SetupIconFile=icon.ico
; Nombre del instalador resultante
OutputDir=releases
OutputBaseFilename=Micyn-Setup-{#MyAppVersion}
; Compresión LZMA para menor tamaño
Compression=lzma
SolidCompression=yes
; Soporte drag-and-drop moderno en Windows 11
WizardStyle=modern
; Solicitar permisos de administrador
PrivilegesRequired=admin

[Languages]
Name: "spanish";   MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english";   MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"

[Files]
; PyInstaller en Windows genera un único micyn.exe (modo onefile)
Source: "dist\micyn.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";          Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Lanzar la app al terminar la instalación (incluso en actualizaciones silenciosas)
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; \
  Flags: nowait postinstall

[UninstallRun]
; No hay nada extra que desinstalar

[Registry]
; Registrar en "Agregar o quitar programas" con información adicional
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1"; \
  ValueType: string; ValueName: "DisplayName"; ValueData: "{#MyAppName} {#MyAppVersion}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1"; \
  ValueType: string; ValueName: "Publisher"; ValueData: "{#MyAppPublisher}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1"; \
  ValueType: string; ValueName: "URLInfoAbout"; ValueData: "{#MyAppURL}"
