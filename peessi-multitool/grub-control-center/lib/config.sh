#!/bin/bash
# ============================================
# GRUB Control Center - Konfiguration
# ============================================

# Version
readonly VERSION="2.1.1"
readonly PROGRAM_NAME="GRUB Control Center"

# Verzeichnisse
readonly INSTALL_DIR="/usr/local/grub-master-center"
readonly THEME_DIR="/boot/grub/themes"
readonly CUSTOM_DIR="/boot/grub/custom"
readonly GRUB_FILE="/etc/default/grub"
readonly LOG_DIR="/var/log/grub-control-center"

# Bestimme aktuellen Benutzer
CURRENT_USER="${SUDO_USER:-${USER:-$(logname 2>/dev/null || echo root)}}"
if [ "$CURRENT_USER" = "root" ]; then
    # Versuche den originalen Benutzer zu finden
    if [ -n "$SUDO_USER" ]; then
        CURRENT_USER="$SUDO_USER"
    fi
fi

# Home-Verzeichnis
if [ -d "/home/$CURRENT_USER" ]; then
    HOME_DIR="/home/$CURRENT_USER"
else
    HOME_DIR="/root"
fi

# Log-Dateien
readonly USER_LOG="$HOME_DIR/grub-control-center.log"
readonly USER_ERR="$HOME_DIR/grub-control-center_errors.log"
readonly SYSTEM_LOG="$LOG_DIR/system.log"

# Farben für Terminal-Ausgabe
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Limits
readonly MAX_BACKUPS=10
readonly MAX_IMAGE_SIZE=5242880  # 5MB in bytes
readonly GIT_TIMEOUT=60

# Globale Arrays für Cleanup
declare -g -a TEMP_DIRS=()
declare -g -a TEMP_FILES=()

# Letzte Backup-Datei (für Rollback)
LAST_BACKUP=""

# Export wichtiger Variablen
export GRUB_FILE THEME_DIR CUSTOM_DIR LOG_DIR
export USER_LOG USER_ERR SYSTEM_LOG
export CURRENT_USER HOME_DIR
