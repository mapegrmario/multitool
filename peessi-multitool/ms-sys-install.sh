#!/bin/bash

# 1. Vorbereitung
BUILD_DIR="$HOME/ms-sys-direct"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "--- Installiere benötigte Pakete ---"
sudo apt install -y build-essential gettext wget

# 2. Download mit dem direkten Mirror-Link
echo "--- Lade ms-sys 2.8.0 vom Mirror herunter ---"
wget "https://sf-eu-introserv-1.dl.sourceforge.net/project/ms-sys/ms-sys%20stable/2.8.0/ms-sys-2.8.0.tar.gz?viasf=1" -O ms-sys-2.8.0.tar.gz

# 3. Entpacken
echo "--- Entpacke Archiv ---"
tar -xzvf ms-sys-2.8.0.tar.gz
cd ms-sys-2.8.0

# 4. Kompilieren und Installieren
echo "--- Kompiliere und installiere ---"
make
sudo make install

# 5. Abschlussprüfung
if command -v ms-sys &> /dev/null; then
    echo "------------------------------------------------"
    echo "ERFOLG: ms-sys ist installiert!"
    ms-sys --version
    echo "------------------------------------------------"
else
    echo "Installation fehlgeschlagen."
fi

# Aufräumen
cd ~
rm -rf "$BUILD_DIR"
