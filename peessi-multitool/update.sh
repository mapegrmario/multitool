#!/bin/bash
# =============================================================================
# Peeßi's System Multitool – Direkt-Update-Script
# Kopiert die aktualisierten Dateien direkt nach /usr/local/lib/peessi-multitool/
# Aufruf: sudo bash update.sh
# =============================================================================

set -e

INSTALL_DIR="/usr/local/lib/peessi-multitool"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}Bitte mit sudo starten: sudo bash update.sh${RESET}"
    exit 1
fi

if [[ ! -d "${INSTALL_DIR}" ]]; then
    echo -e "${RED}${INSTALL_DIR} nicht gefunden. Bitte zuerst install-peessi-multitool.sh ausführen.${RESET}"
    exit 1
fi

echo -e "${YELLOW}Kopiere aktualisierte Dateien nach ${INSTALL_DIR}...${RESET}"

FILES=(
    "main.py"
    "gui_drives.py"
    "gui_system.py"
    "config.py"
    "gui_base.py"
    "models.py"
    "database.py"
    "security.py"
    "smart_engine.py"
    "wipe_engine.py"
    "recovery_engine.py"
)

for f in "${FILES[@]}"; do
    if [[ -f "${SCRIPT_DIR}/${f}" ]]; then
        cp "${SCRIPT_DIR}/${f}" "${INSTALL_DIR}/${f}"
        echo -e "${GREEN}  ✓ ${f}${RESET}"
    else
        echo -e "${YELLOW}  ⚠ ${f} nicht gefunden – übersprungen${RESET}"
    fi
done

# Wrapper aktualisieren (Display-Fix)
if [[ -f "${SCRIPT_DIR}/peessi-multitool-wrapper.sh" ]]; then
    cp "${SCRIPT_DIR}/peessi-multitool-wrapper.sh" /usr/local/bin/peessi-multitool
    chmod 755 /usr/local/bin/peessi-multitool
    echo -e "${GREEN}  ✓ /usr/local/bin/peessi-multitool (Wrapper)${RESET}"
fi
if [[ -f "${SCRIPT_DIR}/peessi-multitool-root-wrapper.sh" ]]; then
    cp "${SCRIPT_DIR}/peessi-multitool-root-wrapper.sh" /usr/local/bin/peessi-multitool-root
    chmod 755 /usr/local/bin/peessi-multitool-root
    echo -e "${GREEN}  ✓ /usr/local/bin/peessi-multitool-root (Root-Wrapper)${RESET}"
fi

# Prüfen ob _build_mint_installer_tab vorhanden ist
if grep -q "_build_mint_installer_tab" "${INSTALL_DIR}/gui_drives.py"; then
    echo -e "\n${GREEN}✅ Update erfolgreich! Methode _build_mint_installer_tab gefunden.${RESET}"
else
    echo -e "\n${RED}❌ Fehler: _build_mint_installer_tab nicht in gui_drives.py gefunden!${RESET}"
    exit 1
fi

echo -e "\n${GREEN}Starten mit: peessi-multitool${RESET}"
