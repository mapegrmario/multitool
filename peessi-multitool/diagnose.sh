#!/bin/bash
# =============================================================================
# Peeßi's System Multitool – Diagnose & Analyse Script
# Prüft Installation, Dateiversionen, Methoden und Umgebung
# Aufruf: bash diagnose.sh
# =============================================================================

INSTALL_DIR="/usr/local/lib/peessi-multitool"
BIN_WRAPPER="/usr/local/bin/peessi-multitool"
BIN_ROOT_WRAPPER="/usr/local/bin/peessi-multitool-root"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
BOLD='\033[1m'
RESET='\033[0m'

OK()   { echo -e "  ${GREEN}✅  $*${RESET}"; }
FAIL() { echo -e "  ${RED}❌  $*${RESET}"; ((ERRORS++)); }
WARN() { echo -e "  ${YELLOW}⚠️   $*${RESET}"; ((WARNINGS++)); }
INFO() { echo -e "  ${CYAN}ℹ️   $*${RESET}"; }
HEAD() { echo -e "\n${BOLD}${BLUE}══  $*  ══${RESET}"; }

ERRORS=0
WARNINGS=0

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║    Peeßi's System Multitool – Diagnose Script       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"
echo "  Datum:     $(date '+%d.%m.%Y %H:%M:%S')"
echo "  Benutzer:  $(whoami)  (EUID=$EUID)"
echo "  Skript:    ${SCRIPT_DIR}"

# ═══════════════════════════════════════════════════════════
HEAD "1  INSTALLATIONSVERZEICHNIS"
# ═══════════════════════════════════════════════════════════

if [[ -d "${INSTALL_DIR}" ]]; then
    OK "${INSTALL_DIR} existiert"
else
    FAIL "${INSTALL_DIR} NICHT GEFUNDEN – bitte install-peessi-multitool.sh ausführen"
fi

if [[ -f "${BIN_WRAPPER}" ]]; then
    OK "${BIN_WRAPPER} existiert"
else
    FAIL "${BIN_WRAPPER} NICHT GEFUNDEN"
fi

if [[ -f "${BIN_ROOT_WRAPPER}" ]]; then
    OK "${BIN_ROOT_WRAPPER} existiert"
else
    FAIL "${BIN_ROOT_WRAPPER} NICHT GEFUNDEN"
fi

# ═══════════════════════════════════════════════════════════
HEAD "2  DATEI-VERGLEICH  (Quelle vs. Installiert)"
# ═══════════════════════════════════════════════════════════

PY_FILES=(
    "main.py"
    "config.py"
    "gui_base.py"
    "gui_drives.py"
    "gui_system.py"
    "models.py"
    "database.py"
    "security.py"
    "smart_engine.py"
    "wipe_engine.py"
    "recovery_engine.py"
)

printf "  %-28s %8s %8s  %s\n" "Datei" "Src-Z." "Inst-Z." "Status"
printf "  %-28s %8s %8s  %s\n" "────────────────────────────" "────────" "────────" "──────────────"

for f in "${PY_FILES[@]}"; do
    SRC="${SCRIPT_DIR}/${f}"
    INST="${INSTALL_DIR}/${f}"

    if [[ ! -f "${SRC}" ]]; then
        printf "  %-28s %8s %8s  " "${f}" "fehlt" "-"
        echo -e "${YELLOW}⚠️  Quelldatei nicht im aktuellen Ordner${RESET}"
        continue
    fi

    SRC_LINES=$(wc -l < "${SRC}")
    SRC_MD5=$(md5sum "${SRC}" | cut -d' ' -f1)

    if [[ ! -f "${INST}" ]]; then
        printf "  %-28s %8s %8s  " "${f}" "${SRC_LINES}" "fehlt"
        echo -e "${RED}❌  Nicht installiert${RESET}"
        ((ERRORS++))
        continue
    fi

    INST_LINES=$(wc -l < "${INST}")
    INST_MD5=$(md5sum "${INST}" | cut -d' ' -f1)

    if [[ "${SRC_MD5}" == "${INST_MD5}" ]]; then
        printf "  %-28s %8s %8s  " "${f}" "${SRC_LINES}" "${INST_LINES}"
        echo -e "${GREEN}✅  Identisch${RESET}"
    else
        printf "  %-28s %8s %8s  " "${f}" "${SRC_LINES}" "${INST_LINES}"
        echo -e "${RED}❌  UNTERSCHIEDLICH – installierte Datei ist veraltet!${RESET}"
        ((ERRORS++))
    fi
done

# ═══════════════════════════════════════════════════════════
HEAD "3  KRITISCHE METHODEN  (in installierter Datei)"
# ═══════════════════════════════════════════════════════════

METHODS=(
    "gui_drives.py:_build_mint_installer_tab"
    "gui_drives.py:_build_eggs_tab"
    "gui_drives.py:_mint_import"
    "gui_drives.py:_eggs_check_status"
    "gui_system.py:HilfeTab"
    "gui_system.py:_read_wlan_passwords"
    "gui_system.py:_refresh_connections"
    "main.py:HilfeTab"
)

for entry in "${METHODS[@]}"; do
    FILE="${entry%%:*}"
    METHOD="${entry##*:}"
    INST="${INSTALL_DIR}/${FILE}"
    if [[ ! -f "${INST}" ]]; then
        FAIL "${FILE}: Datei fehlt → ${METHOD} nicht prüfbar"
        continue
    fi
    COUNT=$(grep -c "${METHOD}" "${INST}" 2>/dev/null || echo 0)
    if [[ "${COUNT}" -gt 0 ]]; then
        OK "${FILE}: ${METHOD}  (${COUNT}×)"
    else
        FAIL "${FILE}: ${METHOD} FEHLT – Datei ist veraltet!"
    fi
done

# ═══════════════════════════════════════════════════════════
HEAD "4  PYTHON & ABHÄNGIGKEITEN"
# ═══════════════════════════════════════════════════════════

VENV_PYTHON="${INSTALL_DIR}/venv/bin/python3"

if [[ -x "${VENV_PYTHON}" ]]; then
    VER=$("${VENV_PYTHON}" --version 2>&1)
    OK "venv-Python: ${VER}"
    PY="${VENV_PYTHON}"
elif command -v python3 &>/dev/null; then
    VER=$(python3 --version 2>&1)
    WARN "venv nicht gefunden, nutze System-Python: ${VER}"
    PY="python3"
else
    FAIL "Kein Python3 gefunden!"
    PY=""
fi

if [[ -n "${PY}" ]]; then
    for mod in tkinter sqlite3 subprocess threading; do
        if "${PY}" -c "import ${mod}" 2>/dev/null; then
            OK "import ${mod}"
        else
            FAIL "import ${mod} FEHLGESCHLAGEN"
        fi
    done

    if "${PY}" -c "from PIL import Image" 2>/dev/null; then
        OK "Pillow (PIL) verfügbar – Avatar-Foto wird angezeigt"
    else
        WARN "Pillow nicht verfügbar – Avatar wird als Platzhalter angezeigt (kein Fehler)"
    fi
fi

# ═══════════════════════════════════════════════════════════
HEAD "5  DISPLAY / X11 / WAYLAND"
# ═══════════════════════════════════════════════════════════

if [[ -n "${DISPLAY}" ]]; then
    OK "DISPLAY=${DISPLAY}"
else
    WARN "DISPLAY nicht gesetzt (normal wenn direkt als Root)"
fi

if [[ -n "${WAYLAND_DISPLAY}" ]]; then
    OK "WAYLAND_DISPLAY=${WAYLAND_DISPLAY}"
else
    INFO "WAYLAND_DISPLAY nicht gesetzt (X11-Modus)"
fi

if command -v xhost &>/dev/null; then
    OK "xhost verfügbar"
    if [[ $EUID -ne 0 ]]; then
        XHOST_OUT=$(xhost 2>/dev/null)
        if echo "${XHOST_OUT}" | grep -q "localuser:root"; then
            OK "Root hat X11-Zugriff (xhost)"
        else
            WARN "Root hat noch keinen X11-Zugriff → xhost +SI:localuser:root"
        fi
    fi
else
    WARN "xhost nicht gefunden – X11-Zugriff für Root evtl. nicht möglich"
fi

# Wrapper prüfen ob Display-Fix enthalten
if [[ -f "${BIN_WRAPPER}" ]]; then
    if grep -q "PEESSI_ENV_FILE\|xhost" "${BIN_WRAPPER}"; then
        OK "${BIN_WRAPPER} enthält Display-Fix"
    else
        FAIL "${BIN_WRAPPER} enthält KEINEN Display-Fix – veraltet!"
    fi
fi

# ═══════════════════════════════════════════════════════════
HEAD "6  SYSTEM-TOOLS"
# ═══════════════════════════════════════════════════════════

TOOLS=(
    "pkexec:PolicyKit"
    "nmcli:NetworkManager"
    "ss:Netzwerk-Verbindungen"
    "smartctl:SMART-Diagnose"
    "ddrescue:Datenrettung"
    "photorec:Datei-Wiederherstellung"
    "lsblk:Laufwerkserkennung"
    "efibootmgr:EFI-Boot-Manager (optional)"
    "eggs:Penguins-Eggs (optional)"
    "git:Git (für fresh-eggs)"
    "xdg-open:Datei/URL öffnen"
)

for entry in "${TOOLS[@]}"; do
    CMD="${entry%%:*}"
    DESC="${entry##*:}"
    if command -v "${CMD}" &>/dev/null; then
        VER=$(${CMD} --version 2>/dev/null | head -1 | cut -c1-50 || echo "")
        OK "${CMD}  ${VER:+(${VER})}"
    else
        if echo "${DESC}" | grep -q "optional"; then
            WARN "${CMD} fehlt  [${DESC}]"
        else
            FAIL "${CMD} fehlt  [${DESC}]"
        fi
    fi
done

# ═══════════════════════════════════════════════════════════
HEAD "7  IMPORT-TEST der installierten Module"
# ═══════════════════════════════════════════════════════════

if [[ -n "${PY}" && -d "${INSTALL_DIR}" ]]; then
    "${PY}" - << PYTEST 2>&1 | while IFS= read -r line; do echo "  ${line}"; done
import sys
sys.path.insert(0, "${INSTALL_DIR}")
modules = [
    ("config",           "config.py"),
    ("models",           "models.py"),
    ("database",         "database.py"),
    ("security",         "security.py"),
    ("smart_engine",     "smart_engine.py"),
    ("wipe_engine",      "wipe_engine.py"),
    ("recovery_engine",  "recovery_engine.py"),
    ("gui_base",         "gui_base.py"),
    ("gui_drives",       "gui_drives.py"),
    ("gui_system",       "gui_system.py"),
]
errors = 0
for mod, fname in modules:
    try:
        m = __import__(mod)
        print(f"✅  {fname}")
    except Exception as e:
        print(f"❌  {fname}: {e}")
        errors += 1

# Kritische Methode prüfen
try:
    from gui_drives import DrivesTabs
    if hasattr(DrivesTabs, '_build_mint_installer_tab'):
        print("✅  DrivesTabs._build_mint_installer_tab vorhanden")
    else:
        print("❌  DrivesTabs._build_mint_installer_tab FEHLT – FALSCHE DATEI!")
        errors += 1
except Exception as e:
    print(f"❌  DrivesTabs Import: {e}")
    errors += 1

try:
    from gui_system import HilfeTab
    print("✅  HilfeTab vorhanden")
except Exception as e:
    print(f"❌  HilfeTab: {e}")
    errors += 1

sys.exit(errors)
PYTEST
fi

# ═══════════════════════════════════════════════════════════
HEAD "8  REPARATUR (automatisch wenn Fehler gefunden)"
# ═══════════════════════════════════════════════════════════

if [[ ${ERRORS} -gt 0 ]]; then
    echo -e "\n  ${RED}${BOLD}${ERRORS} Fehler gefunden.${RESET}"

    # Prüfen ob Quelldateien im aktuellen Ordner sind
    if [[ -f "${SCRIPT_DIR}/gui_drives.py" ]]; then
        SRC_MD5=$(md5sum "${SCRIPT_DIR}/gui_drives.py" | cut -d' ' -f1)
        INST_MD5=$(md5sum "${INSTALL_DIR}/gui_drives.py" 2>/dev/null | cut -d' ' -f1 || echo "")

        if [[ "${SRC_MD5}" != "${INST_MD5}" ]]; then
            echo ""
            echo -e "  ${YELLOW}Quelldateien gefunden. Soll die Reparatur jetzt durchgeführt werden?${RESET}"
            echo -e "  ${YELLOW}(Kopiert alle .py-Dateien + Wrapper nach ${INSTALL_DIR})${RESET}"
            echo ""
            read -r -p "  Jetzt reparieren? [j/N] " ANSWER
            if [[ "${ANSWER,,}" == "j" ]]; then
                if [[ $EUID -ne 0 ]]; then
                    echo -e "  ${YELLOW}Root-Rechte benötigt → starte mit sudo...${RESET}"
                    exec sudo bash "${BASH_SOURCE[0]}" --repair
                else
                    bash "${BASH_SOURCE[0]}" --repair
                fi
            fi
        fi
    else
        echo ""
        echo -e "  ${YELLOW}Tipp: Dieses Script im selben Ordner wie die .py-Dateien ausführen${RESET}"
        echo -e "  ${YELLOW}für automatische Reparatur.${RESET}"
    fi
else
    echo -e "\n  ${GREEN}${BOLD}Keine Fehler – Installation sieht korrekt aus.${RESET}"
fi

# ═══════════════════════════════════════════════════════════
# REPARATUR-MODUS (aufgerufen mit --repair)
# ═══════════════════════════════════════════════════════════
if [[ "${1}" == "--repair" ]]; then
    HEAD "REPARATUR"
    if [[ $EUID -ne 0 ]]; then
        FAIL "Root-Rechte benötigt für Reparatur"
        exit 1
    fi

    COPIED=0
    for f in "${PY_FILES[@]}"; do
        if [[ -f "${SCRIPT_DIR}/${f}" ]]; then
            cp "${SCRIPT_DIR}/${f}" "${INSTALL_DIR}/${f}"
            OK "Kopiert: ${f}"
            ((COPIED++))
        fi
    done

    for sh in "peessi-multitool-wrapper.sh" "peessi-multitool-root-wrapper.sh"; do
        if [[ -f "${SCRIPT_DIR}/${sh}" ]]; then
            if [[ "${sh}" == *root* ]]; then
                cp "${SCRIPT_DIR}/${sh}" "${BIN_ROOT_WRAPPER}"
                chmod 755 "${BIN_ROOT_WRAPPER}"
                OK "Wrapper: ${BIN_ROOT_WRAPPER}"
            else
                cp "${SCRIPT_DIR}/${sh}" "${BIN_WRAPPER}"
                chmod 755 "${BIN_WRAPPER}"
                OK "Wrapper: ${BIN_WRAPPER}"
            fi
        fi
    done

    echo ""
    # Verifikation
    COUNT=$(grep -c "_build_mint_installer_tab" "${INSTALL_DIR}/gui_drives.py" 2>/dev/null || echo 0)
    if [[ "${COUNT}" -ge 2 ]]; then
        echo -e "  ${GREEN}${BOLD}✅ Reparatur erfolgreich! (${COPIED} Dateien kopiert)${RESET}"
        echo -e "  ${GREEN}Starten mit: peessi-multitool${RESET}"
    else
        echo -e "  ${RED}❌ Reparatur fehlgeschlagen – _build_mint_installer_tab immer noch nicht gefunden${RESET}"
        exit 1
    fi
    exit 0
fi

# ═══════════════════════════════════════════════════════════
HEAD "ZUSAMMENFASSUNG"
# ═══════════════════════════════════════════════════════════

echo ""
if [[ ${ERRORS} -eq 0 && ${WARNINGS} -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}✅ Alles in Ordnung – Starten mit: peessi-multitool${RESET}"
elif [[ ${ERRORS} -eq 0 ]]; then
    echo -e "  ${YELLOW}${BOLD}⚠️  ${WARNINGS} Warnungen, aber keine kritischen Fehler${RESET}"
    echo -e "  ${GREEN}Starten mit: peessi-multitool${RESET}"
else
    echo -e "  ${RED}${BOLD}❌ ${ERRORS} Fehler, ${WARNINGS} Warnungen${RESET}"
    echo ""
    echo -e "  ${YELLOW}Schnellreparatur (aus dem Ordner mit den .py-Dateien):${RESET}"
    echo -e "  ${CYAN}sudo bash diagnose.sh --repair${RESET}"
    echo ""
    echo -e "  ${YELLOW}Oder manuell:${RESET}"
    echo -e "  ${CYAN}sudo cp gui_drives.py gui_system.py main.py /usr/local/lib/peessi-multitool/${RESET}"
fi
echo ""
