#!/bin/bash
# =============================================================================
#  Peeßi's System Multitool v4.1 – Installationsskript
#  Autor:   Mario Peeß, Großenhain  |  mapegr@mailbox.org
#  Version: 4.1  |  2025-2026
# =============================================================================
#  Dieses Skript:
#    1.  Prüft alle System-Abhängigkeiten und installiert fehlende Pakete
#    2.  Legt ein Python-venv an (fuer zukuenftige Pakete)
#    3.  Prueft Python-Abhaengigkeiten
#    4.  Kopiert alle Programmdateien nach /usr/local/lib/peessi-multitool/
#    5.  Erstellt einen Wrapper in /usr/local/bin/ (nutzt venv-Python)
#    6.  Erstellt Startmenü-Eintrag (.desktop) + Icon
#    7.  Richtet PolicyKit-Regel ein (passwortloser GUI-Start)
#    8.  Erstellt ein Deinstallations-Script
#
#  Aufruf: sudo ./install-peessi-multitool.sh
#  Deinstall: sudo /usr/local/lib/peessi-multitool/uninstall.sh
# =============================================================================

set -euo pipefail

# ── Farben ───────────────────────────────────────────────────────────────────
RED='\033[1;31m';  GREEN='\033[1;32m';  YELLOW='\033[1;33m'
BLUE='\033[1;34m'; CYAN='\033[1;36m';   BOLD='\033[1m';  RESET='\033[0m'

# ── Konfiguration ─────────────────────────────────────────────────────────────
PROG_NAME="peessi-multitool"
DISPLAY_NAME="Peeßi's System Multitool"
MAIN_SCRIPT="main.py"
INSTALL_DIR="/usr/local/lib/${PROG_NAME}"
VENV_DIR="${INSTALL_DIR}/venv"
BIN_WRAPPER="/usr/local/bin/${PROG_NAME}"
BIN_ROOT_WRAPPER="/usr/local/bin/${PROG_NAME}-root"
DESKTOP_FILE="/usr/share/applications/${PROG_NAME}.desktop"
POLKIT_DIR="/usr/share/polkit-1/actions"
POLKIT_FILE="${POLKIT_DIR}/org.freedesktop.pkexec.${PROG_NAME}.policy"
ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python-Mindestversion
PY_MIN_MAJOR=3
PY_MIN_MINOR=8

# Python-Pakete die im venv installiert werden
VENV_PACKAGES=(
    "pillow"   # Foto-Anzeige im Über-Tab
)

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────
info()    { echo -e "${BLUE}[INFO]${RESET}    $*"; }
success() { echo -e "${GREEN}[OK]${RESET}      $*"; }
warning() { echo -e "${YELLOW}[WARNUNG]${RESET} $*"; }
error()   { echo -e "${RED}[FEHLER]${RESET}  $*" >&2; }
step()    { echo -e "\n${BOLD}${CYAN}══  $*  ══${RESET}"; }

# ── Root-Prüfung ──────────────────────────────────────────────────────────────
step "Prüfe Rechte"
if [[ $EUID -ne 0 ]]; then
    error "Bitte mit sudo ausführen:  sudo ./install-peessi-multitool.sh"
    exit 1
fi
success "Root-Rechte vorhanden."

# ── Ursprünglichen Benutzer ermitteln ─────────────────────────────────────────
ORIG_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "$USER")}"
ORIG_HOME=$(eval echo "~${ORIG_USER}")
info "Installiere für Benutzer: ${BOLD}${ORIG_USER}${RESET}"

# ── Quelldateien prüfen ───────────────────────────────────────────────────────
step "Prüfe Quelldateien"

# Pflicht: main.py muss vorhanden sein
if [[ ! -f "${SCRIPT_DIR}/${MAIN_SCRIPT}" ]]; then
    error "${MAIN_SCRIPT} nicht gefunden in '${SCRIPT_DIR}'."
    error "Bitte alle Dateien des Pakets im selben Ordner ablegen."
    exit 1
fi
success "${MAIN_SCRIPT} gefunden."

# Alle erwarteten Module prüfen
MODULES=(
    "config.py" "models.py" "database.py" "security.py"
    "smart_engine.py" "wipe_engine.py" "recovery_engine.py"
    "gui_base.py" "gui_drives.py" "gui_system.py"
)
MISSING_MODULES=()
for mod in "${MODULES[@]}"; do
    if [[ -f "${SCRIPT_DIR}/${mod}" ]]; then
        success "  ${mod} ✓"
    else
        warning "  ${mod} – nicht gefunden"
        MISSING_MODULES+=("$mod")
    fi
done
if [[ ${#MISSING_MODULES[@]} -gt 0 ]]; then
    warning "Fehlende Module: ${MISSING_MODULES[*]}"
    warning "Das Programm könnte unvollständig sein."
fi

# ── Python-Version prüfen ─────────────────────────────────────────────────────
step "Prüfe Python-Version"
PYTHON_BIN=""
for py in python3 python3.12 python3.11 python3.10 python3.9 python3.8; do
    if command -v "$py" &>/dev/null; then
        ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        major="${ver%%.*}"
        minor="${ver##*.}"
        if [[ "$major" -ge "$PY_MIN_MAJOR" && "$minor" -ge "$PY_MIN_MINOR" ]]; then
            PYTHON_BIN="$py"
            success "Python ${ver} gefunden: $(command -v $py)"
            break
        fi
    fi
done
if [[ -z "$PYTHON_BIN" ]]; then
    error "Python ${PY_MIN_MAJOR}.${PY_MIN_MINOR}+ nicht gefunden!"
    error "Bitte installieren: sudo apt install python3"
    exit 1
fi

# ── Paketlisten aktualisieren ─────────────────────────────────────────────────
step "Paketlisten aktualisieren"
if apt-get update -qq; then
    success "Paketlisten aktualisiert."
else
    warning "apt update schlug fehl – fahre trotzdem fort."
fi

# ── System-Abhängigkeiten ─────────────────────────────────────────────────────
#  Format: "apt-paket:befehl:beschreibung[:optional]"
step "Prüfe und installiere System-Abhängigkeiten"

DEPENDENCIES=(
    # Python
    "python3:python3:Python 3 Interpreter"
    "python3-tk:python3-tk:Tkinter GUI-Bibliothek"
    "python3-venv:python3-venv:Python venv"
    "python3-pip:pip3:pip (für venv-Pakete)"

    # Datenrettung
    "gddrescue:ddrescue:ddrescue – Sektor-für-Sektor Rettung"
    "testdisk:photorec:testdisk/photorec – Dateiwiederherstellung"

    # Laufwerk-Diagnose
    "smartmontools:smartctl:S.M.A.R.T. Diagnose"
    "hdparm:hdparm:HDD-Parameter & ATA Secure Erase"
    "nvme-cli:nvme:NVMe SSD Tools"
    "udisks2:udisksctl:Laufwerk-Verwaltung"

    # System-Info
    "util-linux:lsblk:lsblk (util-linux)"
    "util-linux:blkid:blkid (util-linux)"
    "util-linux:findmnt:findmnt (util-linux)"
    "usbutils:lsusb:USB-Geräte-Info"

    # PolicyKit
    "policykit-1:pkexec:PolicyKit – Root-Rechte für GUI-Apps"

    # Systemd
    "systemd:systemctl:systemd"
    "systemd:journalctl:journald"

    # Desktop-Integration
    "libnotify-bin:notify-send:Desktop-Benachrichtigungen"
    "xdg-utils:xdg-open:xdg-utils"

    # Optional
    "zenity:zenity:Zenity GTK-Dialoge:optional"
    "nala:nala:Nala APT-Frontend:optional"
    "fwupd:fwupdmgr:Firmware-Updates:optional"
    "wget:wget:wget:optional"
    "efibootmgr:efibootmgr:EFI Boot-Manager:optional"
)

MISSING_PKGS=()
OPTIONAL_MISSING=()

for dep in "${DEPENDENCIES[@]}"; do
    IFS=':' read -r pkg cmd desc flag <<< "${dep}:::"
    pkg="${dep%%:*}"
    rest="${dep#*:}"
    cmd="${rest%%:*}"
    rest2="${rest#*:}"
    desc="${rest2%%:*}"
    flag="${rest2##*:}"
    [[ "$flag" == "$desc" ]] && flag=""
    optional=false
    [[ "$flag" == "optional" ]] && optional=true

    # Befehl im PATH?
    if command -v "$cmd" &>/dev/null; then
        success "${cmd} ✓"
        continue
    fi
    # Paket installiert?
    if dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
        success "${pkg} (Paket) ✓"
        continue
    fi

    if $optional; then
        warning "${cmd} fehlt  [optional: ${desc}]"
        OPTIONAL_MISSING+=("$pkg")
    else
        error   "${cmd} fehlt  →  Paket: ${pkg}  [${desc}]"
        MISSING_PKGS+=("$pkg")
    fi
done

# Pflicht-Pakete
if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    echo ""
    info "Installiere ${#MISSING_PKGS[@]} fehlende Pflicht-Pakete..."
    if apt-get install -y "${MISSING_PKGS[@]}"; then
        success "Pflicht-Pakete installiert: ${MISSING_PKGS[*]}"
    else
        error "Installation fehlgeschlagen. Bitte manuell prüfen."
        exit 1
    fi
fi

# Optionale Pakete
if [[ ${#OPTIONAL_MISSING[@]} -gt 0 ]]; then
    echo ""
    info "Installiere ${#OPTIONAL_MISSING[@]} optionale Pakete..."
    if apt-get install -y "${OPTIONAL_MISSING[@]}" 2>/dev/null; then
        success "Optionale Pakete installiert: ${OPTIONAL_MISSING[*]}"
    else
        warning "Einige optionale Pakete nicht verfügbar – kein Problem."
    fi
fi

# ── Programm-Verzeichnis anlegen & Dateien kopieren ───────────────────────────
step "Installiere Programmdateien"
mkdir -p "${INSTALL_DIR}"

# Alle Python-Dateien kopieren
PY_FILES=(
    "main.py" "config.py" "models.py" "database.py" "security.py"
    "smart_engine.py" "wipe_engine.py" "recovery_engine.py"
    "gui_base.py" "gui_drives.py" "gui_system.py"
)
for f in "${PY_FILES[@]}"; do
    if [[ -f "${SCRIPT_DIR}/${f}" ]]; then
        cp "${SCRIPT_DIR}/${f}" "${INSTALL_DIR}/${f}"
        chmod 644 "${INSTALL_DIR}/${f}"
        success "  ${f} ✓"
    else
        warning "  ${f} – nicht gefunden, wird übersprungen"
    fi
done

# Begleit-Skripte kopieren falls vorhanden
COMPANION_SCRIPTS=(
    "scriptkonverter2.sh"
    "install-update_und_schutdown_mint.sh"
    "diagnose.sh"
    "systempflege.sh"
    "system_optimizer.sh"
    "boot-check-ein-oder_abschalten.sh"
    "programm-autostart_mit_root.sh"
    "Einmal-Starter.sh"
    "Festplatte_einbinden.sh"
    "Festplatten_anzeigen.sh"
)
echo ""
info "Kopiere Begleit-Skripte (falls vorhanden)..."
for s in "${COMPANION_SCRIPTS[@]}"; do
    if [[ -f "${SCRIPT_DIR}/${s}" ]]; then
        cp "${SCRIPT_DIR}/${s}" "${INSTALL_DIR}/${s}"
        chmod 755 "${INSTALL_DIR}/${s}"
        success "  ${s} ✓"
    fi
done

success "Programmdateien installiert: ${INSTALL_DIR}"

# ── Python venv anlegen ───────────────────────────────────────────────────────
# venv anlegen fuer eventuelle zukuenftige Pakete

step "Python venv anlegen"

VENV_PYTHON="${VENV_DIR}/bin/python3"
VENV_PIP="${VENV_DIR}/bin/pip"

# Altes venv entfernen falls vorhanden (sauber neu aufbauen)
if [[ -d "${VENV_DIR}" ]]; then
    info "Bestehendes venv wird neu aufgebaut..."
    rm -rf "${VENV_DIR}"
fi

info "Erstelle venv in ${VENV_DIR}..."
if "${PYTHON_BIN}" -m venv --system-site-packages "${VENV_DIR}"; then
    success "venv erstellt: ${VENV_DIR}"
else
    error "venv konnte nicht erstellt werden!"
    error "Bitte prüfen: sudo apt install python3-venv"
    exit 1
fi

# pip im venv aktualisieren
info "Aktualisiere pip im venv..."
"${VENV_PYTHON}" -m pip install --upgrade pip --quiet 2>/dev/null || true

# Python-Pakete im venv installieren
step "Installiere Python-Pakete im venv"
for pkg in "${VENV_PACKAGES[@]}"; do
    info "Installiere ${pkg} im venv..."
    if "${VENV_PIP}" install --upgrade --no-cache-dir --quiet "${pkg}"; then
        success "${pkg} ✓"
        # Sofort-Test (pillow: PIL.ImageTk prüfen, andere normal)
        if [[ "${pkg}" == "pillow" ]]; then
            TEST_CMD="from PIL import Image, ImageTk; print(Image.__version__)"
        else
            TEST_CMD="import ${pkg%%[>=]*}"
        fi
        if "${VENV_PYTHON}" -c "${TEST_CMD}" 2>/dev/null; then
            success "${pkg} Import-Test ✓"
        else
            warning "${pkg} installiert, aber Import schlug fehl – prüfen Sie die Ausgabe oben."
        fi
    else
        warning "${pkg} konnte nicht installiert werden."
        warning "Manuell nachinstallieren: sudo ${VENV_PIP} install ${pkg}"
    fi
done

# ── Import-Selbsttest ─────────────────────────────────────────────────────────
step "Import-Selbsttest"

IMPORT_ERRORS=0
check_import() {
    local mod="$1"
    local pkg_hint="${2:-$1}"
    if "${VENV_PYTHON}" -c "import ${mod}" 2>/dev/null; then
        success "import ${mod} ✓"
    else
        warning "import ${mod} fehlgeschlagen  (Paket: ${pkg_hint})"
        ((IMPORT_ERRORS++))
    fi
}

check_import "tkinter"     "python3-tk"
# matplotlib nicht mehr benoetigt
check_import "sqlite3"     "python3 built-in"
check_import "subprocess"  "python3 built-in"

if [[ $IMPORT_ERRORS -gt 0 ]]; then
    warning "${IMPORT_ERRORS} Import(s) fehlgeschlagen."
    warning "Das Programm könnte eingeschränkt laufen."
    warning "Alle Kernfunktionen (ohne Diagramme) bleiben verfügbar."
else
    success "Alle Imports erfolgreich ✓"
fi

# ── Wrapper-Scripts ───────────────────────────────────────────────────────────
step "Erstelle Starter-Scripts"

# Haupt-Wrapper: nutzt das venv-Python
cat > "${BIN_WRAPPER}" << WRAPPER
#!/bin/bash
# Starter-Wrapper für Peeßi's System Multitool v4.1
# Startet immer mit dem venv-Python → matplotlib und alle Pakete verfügbar

PROG="${INSTALL_DIR}/main.py"
VENV_PYTHON="${VENV_DIR}/bin/python3"
FALLBACK_PYTHON="python3"

# venv-Python bevorzugen
if [[ -x "\${VENV_PYTHON}" ]]; then
    PY="\${VENV_PYTHON}"
else
    PY="\${FALLBACK_PYTHON}"
fi

if [[ \$EUID -eq 0 ]]; then
    exec "\${PY}" "\${PROG}" "\$@"
elif command -v pkexec &>/dev/null; then
    exec pkexec "${BIN_ROOT_WRAPPER}" "\$@"
else
    exec sudo "\${PY}" "\${PROG}" "\$@"
fi
WRAPPER
chmod 755 "${BIN_WRAPPER}"
success "Starter: ${BIN_WRAPPER}"

# Root-Wrapper für pkexec (pkexec ruft nur direkte Executables auf)
cat > "${BIN_ROOT_WRAPPER}" << ROOTWRAPPER
#!/bin/bash
# Root-Wrapper für pkexec – nutzt venv-Python
VENV_PYTHON="${VENV_DIR}/bin/python3"
PROG="${INSTALL_DIR}/main.py"
if [[ -x "\${VENV_PYTHON}" ]]; then
    exec "\${VENV_PYTHON}" "\${PROG}" "\$@"
else
    exec python3 "\${PROG}" "\$@"
fi
ROOTWRAPPER
chmod 755 "${BIN_ROOT_WRAPPER}"
success "Root-Wrapper: ${BIN_ROOT_WRAPPER}"

# ── PolicyKit-Regel ───────────────────────────────────────────────────────────
step "Erstelle PolicyKit-Regel"
mkdir -p "${POLKIT_DIR}"
cat > "${POLKIT_FILE}" << POLKIT
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.freedesktop.pkexec.${PROG_NAME}.run">
    <description>${DISPLAY_NAME} ausführen</description>
    <message>Administratorrechte werden benötigt für den Zugriff auf Laufwerke und Systemfunktionen.</message>
    <defaults>
      <allow_any>auth_admin_keep</allow_any>
      <allow_inactive>auth_admin_keep</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">${BIN_ROOT_WRAPPER}</annotate>
    <annotate key="org.freedesktop.policykit.exec.allow_gui">true</annotate>
  </action>
</policyconfig>
POLKIT
success "PolicyKit: ${POLKIT_FILE}"

# ── Programm-Icon ─────────────────────────────────────────────────────────────
step "Installiere Programm-Icon"
mkdir -p "${ICON_DIR}"
cat > "${ICON_DIR}/${PROG_NAME}.svg" << 'SVGICON'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <rect width="64" height="64" rx="12" fill="#2c3e50"/>
  <g fill="none" stroke="#3498db" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="22" cy="18" r="8" fill="#3498db" fill-opacity="0.25"/>
    <line x1="27" y1="23" x2="50" y2="48"/>
    <line x1="46" y1="44" x2="52" y2="50"/>
  </g>
  <rect x="12" y="36" width="28" height="16" rx="4" fill="none" stroke="#2ecc71" stroke-width="2.5"/>
  <circle cx="34" cy="44" r="2.5" fill="#2ecc71"/>
  <line x1="14" y1="44" x2="26" y2="44" stroke="#2ecc71" stroke-width="2" stroke-linecap="round"/>
  <circle cx="50" cy="16" r="5" fill="#e74c3c"/>
  <text x="47.5" y="20" font-family="monospace" font-size="7" font-weight="bold" fill="white">P</text>
</svg>
SVGICON
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor/ &>/dev/null || true
fi
success "Icon: ${ICON_DIR}/${PROG_NAME}.svg"

# ── Startmenü-Eintrag ─────────────────────────────────────────────────────────
step "Erstelle Startmenü-Eintrag"
cat > "${DESKTOP_FILE}" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=${DISPLAY_NAME}
GenericName=System Multitool
Comment=Datenrettung, Laufwerksverwaltung, Systempflege und mehr
Exec=${BIN_WRAPPER}
Icon=${PROG_NAME}
Terminal=false
Categories=System;Utility;Security;
Keywords=rescue;recovery;wipe;secure;disk;usb;system;tools;
StartupNotify=true
StartupWMClass=peessi-multitool
DESKTOP
chmod 644 "${DESKTOP_FILE}"
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database /usr/share/applications/ &>/dev/null || true
fi
success "Startmenü: ${DESKTOP_FILE}"

# ── Desktop-Verknüpfung (optional) ───────────────────────────────────────────
step "Desktop-Verknüpfung"
USER_DESKTOP="${ORIG_HOME}/Desktop"
if [[ -d "${USER_DESKTOP}" ]]; then
    DESKTOP_LINK="${USER_DESKTOP}/${PROG_NAME}.desktop"
    cp "${DESKTOP_FILE}" "${DESKTOP_LINK}"
    chown "${ORIG_USER}:${ORIG_USER}" "${DESKTOP_LINK}"
    chmod 755 "${DESKTOP_LINK}"
    if command -v gio &>/dev/null; then
        sudo -u "${ORIG_USER}" gio set "${DESKTOP_LINK}" metadata::trusted true 2>/dev/null || true
    fi
    success "Desktop-Link: ${DESKTOP_LINK}"
else
    info "Kein Desktop-Ordner – wird übersprungen."
fi

# ── Deinstallations-Script ────────────────────────────────────────────────────
step "Erstelle Deinstallations-Script"
cat > "${INSTALL_DIR}/uninstall.sh" << UNINSTALL
#!/bin/bash
# Deinstallation von Peeßi's System Multitool v4.1
set -euo pipefail
RED='\033[1;31m'; GREEN='\033[1;32m'; RESET='\033[0m'
[[ \$EUID -ne 0 ]] && { echo "Bitte als root ausführen: sudo ${INSTALL_DIR}/uninstall.sh"; exit 1; }
echo -e "\n\${RED}Deinstalliere ${DISPLAY_NAME}...\${RESET}\n"
for f in "${BIN_WRAPPER}" "${BIN_ROOT_WRAPPER}"; do
    [[ -f "\$f" ]] && rm -f "\$f" && echo "Gelöscht: \$f"
done
for f in "${DESKTOP_FILE}" "${POLKIT_FILE}" "${ICON_DIR}/${PROG_NAME}.svg"; do
    [[ -f "\$f" ]] && rm -f "\$f" && echo "Gelöscht: \$f"
done
[[ -d "${INSTALL_DIR}" ]] && rm -rf "${INSTALL_DIR}" && echo "Gelöscht: ${INSTALL_DIR}"
command -v update-desktop-database &>/dev/null && update-desktop-database /usr/share/applications/ &>/dev/null || true
command -v gtk-update-icon-cache   &>/dev/null && gtk-update-icon-cache -f -t /usr/share/icons/hicolor/ &>/dev/null || true
echo -e "\n\${GREEN}Deinstallation abgeschlossen.\${RESET}"
echo "Konfiguration bleibt erhalten: ~/.config/peessi-multitool/"
echo "Zum vollständigen Entfernen: rm -rf ~/.config/peessi-multitool/"
UNINSTALL
chmod 755 "${INSTALL_DIR}/uninstall.sh"
success "Deinstall: ${INSTALL_DIR}/uninstall.sh"

# ── Laufzeit-Selbsttest ──────────────────────────────────────────────────────
# Testet den ECHTEN Startpfad: venv-Python → alle Module importierbar
step "Laufzeit-Selbsttest"

SELFTEST_RESULT=0

# Pillow separat testen – ImageTk braucht X11-Display, daher nur PIL.Image pruefen
if "${VENV_PYTHON}" -c "from PIL import Image; print('  ✅ pillow ' + Image.__version__)" 2>/dev/null; then
    PILLOW_OK=true
else
    echo "  ⚠️  pillow nicht im venv – Avatar-Foto wird als Platzhalter angezeigt"
    PILLOW_OK=true   # kein harter Fehler, Programm laeuft trotzdem
fi

"${VENV_PYTHON}" - << 'PYTEST'
import sys, os
sys.path.insert(0, "/usr/local/lib/peessi-multitool")
errors = []

# 1. tkinter
try:
    import tkinter
    print(f"  ✅ tkinter (Tk {tkinter.TkVersion})")
except ImportError as e:
    print(f"  ❌ tkinter: {e}")
    errors.append("tkinter")

# 3. sqlite3
try:
    import sqlite3
    print(f"  ✅ sqlite3")
except ImportError as e:
    print(f"  ❌ sqlite3: {e}")
    errors.append("sqlite3")

# 4. eigene Module
for mod in ["config","models","database","security",
            "smart_engine","wipe_engine","recovery_engine"]:
    try:
        __import__(mod)
        print(f"  ✅ {mod}")
    except Exception as e:
        print(f"  ❌ {mod}: {e}")
        errors.append(mod)

if errors:
    print(f"\nFEHLER in: {', '.join(errors)}")
    sys.exit(1)
else:
    print("\n  Alle Imports OK – Programm wird korrekt starten.")
    sys.exit(0)
PYTEST

SELFTEST_RESULT=$?
if [[ $SELFTEST_RESULT -eq 0 ]]; then
    success "Laufzeit-Selbsttest bestanden ✓"
else
    warning "Laufzeit-Selbsttest fehlgeschlagen!"
    warning "Das Programm könnte eingeschränkt laufen – bitte Ausgabe oben prüfen."
fi

# ── Zusammenfassung ───────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║     ✅  Installation erfolgreich abgeschlossen!              ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${BOLD}Version:${RESET}         4.1"
echo -e "  ${BOLD}Programm:${RESET}        ${INSTALL_DIR}/main.py"
echo -e "  ${BOLD}Python venv:${RESET}     ${VENV_DIR}"
echo -e "  ${BOLD}Starter:${RESET}         ${BIN_WRAPPER}"
echo -e "  ${BOLD}Startmenü:${RESET}       ${DESKTOP_FILE}"
echo -e "  ${BOLD}PolicyKit:${RESET}       ${POLKIT_FILE}"
echo ""
echo -e "  ${BOLD}Starten mit:${RESET}"
echo -e "    ${CYAN}${BIN_WRAPPER}${RESET}     ← Terminal"
echo -e "    ${CYAN}Startmenü → System → ${DISPLAY_NAME}${RESET}"
echo ""
echo -e "  ${BOLD}Deinstallieren:${RESET}"
echo -e "    ${YELLOW}sudo ${INSTALL_DIR}/uninstall.sh${RESET}"
echo ""

# matplotlib nicht mehr benoetigt – SMART-Verlauf wird als Texttabelle angezeigt
echo ""
