#!/bin/bash
set -e

echo "=== Compilador Micyn para Ubuntu (DEB) ==="

# Extraer version de constants.py
VERSION=$(grep -m 1 "^APP_VERSION" constants.py | cut -d '"' -f 2)
if [ -z "$VERSION" ]; then
    VERSION="1.0.0"
fi

APP_NAME="micyn"
PKG_NAME="${APP_NAME}_${VERSION}_amd64"
DEB_DIR="releases/${PKG_NAME}"
DIST_DIR="dist/${APP_NAME}"

echo "Versión detectada: $VERSION"
echo "Limpiando entornos anteriores..."
rm -rf build/ dist/ "$DEB_DIR"
mkdir -p releases

echo "Verificando/Instalando dependencias requeridas..."
if [ ! -d ".venv" ]; then
    echo "No se encontró un entorno virtual. Creando uno..."
    python3 -m venv .venv
fi
./.venv/bin/pip install -r requirements.txt

# Generar iconos si no existen
if [ ! -f "icon.png" ]; then
    echo "Generando icon.png..."
    ./.venv/bin/python3 -c "from PIL import Image; img = Image.open('micyn_logo.jpg'); img.save('icon.png')"
fi

echo "Compilando binario con PyInstaller (usando micyn.spec)..."
./.venv/bin/pyinstaller --noconfirm micyn.spec

echo "Armando estructura de paquete Debian..."
mkdir -p "$DEB_DIR/opt/$APP_NAME"
mkdir -p "$DEB_DIR/usr/share/applications"
mkdir -p "$DEB_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DEB_DIR/DEBIAN"

echo "Copiando binario a la carpeta de opt..."
cp -r $DIST_DIR/* "$DEB_DIR/opt/$APP_NAME/"

echo "Generando Desktop Entry (Lanzador)..."
cat << EOF > "$DEB_DIR/usr/share/applications/$APP_NAME.desktop"
[Desktop Entry]
Name=Micyn
Comment=Retraso de Micrófono para OBS
Exec=/opt/$APP_NAME/$APP_NAME
Icon=micyn
Terminal=false
Type=Application
Categories=AudioVideo;Audio;
StartupWMClass=micyn
EOF

echo "Copiando Icono (si existe)..."
if [ -f "icon.png" ]; then
    cp icon.png "$DEB_DIR/usr/share/icons/hicolor/256x256/apps/micyn.png"
fi

echo "Creando archivo Debian Control..."
cat << EOF > "$DEB_DIR/DEBIAN/control"
Package: $APP_NAME
Version: $VERSION
Section: sound
Priority: optional
Architecture: amd64
Maintainer: Facyn
Description: Micyn Audio Delay App - Herramienta para sincronizar retraso de Micrófono virtualmente.
EOF

# Permisos para el árbol de directorios de dpkg
chmod -R 0755 "$DEB_DIR"

echo "Construyendo paquete final (.deb)..."
dpkg-deb --build "$DEB_DIR"

# Renombrando el archivo base al standard release name y limpiando
mv "releases/${PKG_NAME}.deb" "releases/${APP_NAME}-${VERSION}.deb"
rm -rf "$DEB_DIR" build dist

echo "================================================="
echo "¡Éxito! Tu paquete Debian (.deb) se generó en:"
echo "releases/${APP_NAME}-${VERSION}.deb"
echo "================================================="
