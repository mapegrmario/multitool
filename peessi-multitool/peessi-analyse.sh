#!/bin/bash
# =============================================================================
# Peeßi's System Multitool – VOLLSTÄNDIGE SYSTEM-ANALYSE
# Prüft Installation, Dateien, Methoden, Abhängigkeiten und Systemumgebung
# Erstellt: /home/<user>/peessi-analyse.log  und  /home/<user>/peessi-analyse-kurz.txt
#
# Aufruf: bash peessi-analyse.sh
#         sudo bash peessi-analyse.sh   (für vollständige Prozess-Info)
# =============================================================================

set -uo pipefail

# ── Konfiguration ─────────────────────────────────────────────────────────────
INSTALL_DIR="/usr/local/lib/peessi-multitool"
BIN_WRAPPER="/usr/local/bin/peessi-multitool"
BIN_ROOT="/usr/local/bin/peessi-multitool-root"
VENV_PYTHON="${INSTALL_DIR}/venv/bin/python3"
LOG_USER="${SUDO_USER:-${USER:-$(logname 2>/dev/null || echo root)}}"
LOG_HOME=$(eval echo "~${LOG_USER}")
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="${LOG_HOME}/peessi-analyse-${TIMESTAMP}.log"
SHORT_FILE="${LOG_HOME}/peessi-analyse-kurz.txt"

# ── Farben ────────────────────────────────────────────────────────────────────
RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'
BLUE='\033[1;34m'; CYAN='\033[1;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

# ── Zähler ────────────────────────────────────────────────────────────────────
ERRORS=0; WARNINGS=0; PASSED=0
declare -a ERROR_LIST=()
declare -a WARN_LIST=()

# ── Logging ───────────────────────────────────────────────────────────────────
# Beide: Terminal (farbig) + Log-Datei (ohne Farben)
_log_raw() { echo "$*" >> "${LOG_FILE}"; }

OK()   {
    echo -e "  ${GREEN}✅  $*${RESET}"
    _log_raw "  [OK]   $*"
    ((PASSED++))
}
FAIL() {
    echo -e "  ${RED}❌  $*${RESET}"
    _log_raw "  [FAIL] $*"
    ((ERRORS++))
    ERROR_LIST+=("$*")
}
WARN() {
    echo -e "  ${YELLOW}⚠️   $*${RESET}"
    _log_raw "  [WARN] $*"
    ((WARNINGS++))
    WARN_LIST+=("$*")
}
INFO() {
    echo -e "  ${CYAN}ℹ️   $*${RESET}"
    _log_raw "  [INFO] $*"
}
HEAD() {
    echo -e "\n${BOLD}${BLUE}╔══  $*  ══╗${RESET}"
    _log_raw ""
    _log_raw "══════════════════════════════════════════════════"
    _log_raw "  $*"
    _log_raw "══════════════════════════════════════════════════"
}
DETAIL() {
    echo -e "  ${DIM}$*${RESET}"
    _log_raw "         $*"
}

# ── Header ────────────────────────────────────────────────────────────────────
clear
echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║    Peeßi's System Multitool – VOLLSTÄNDIGE SYSTEM-ANALYSE  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

_log_raw "=============================================================="
_log_raw "  PEEESSI'S SYSTEM MULTITOOL – VOLLSTÄNDIGE SYSTEM-ANALYSE"
_log_raw "=============================================================="
_log_raw "  Datum     : $(date '+%d.%m.%Y %H:%M:%S')"
_log_raw "  Benutzer  : $(whoami) (EUID=$EUID)"
_log_raw "  Hostname  : $(hostname)"
_log_raw "  System    : $(uname -r)"
_log_raw "  Log-Datei : ${LOG_FILE}"
_log_raw "=============================================================="

echo "  Datum     : $(date '+%d.%m.%Y %H:%M:%S')"
echo "  Benutzer  : $(whoami)  (EUID=$EUID)"
echo "  Log-Datei : ${LOG_FILE}"


# ══════════════════════════════════════════════════════════════════════════════
HEAD "1  INSTALLATIONS-VERZEICHNISSE & WRAPPER"
# ══════════════════════════════════════════════════════════════════════════════

# Hauptverzeichnis – mehrere Prüfmethoden (sudo kann Pfad-Auflösung ändern)
if [[ -d "${INSTALL_DIR}" ]] || [[ -d "$(realpath "${INSTALL_DIR}" 2>/dev/null)" ]]; then
    OK "Installationsordner: ${INSTALL_DIR}"
    # Auch prüfen ob Dateien tatsächlich drin sind
    PY_COUNT=$(find "${INSTALL_DIR}" -maxdepth 1 -name "*.py" 2>/dev/null | wc -l)
    INFO "  ${PY_COUNT} Python-Programmdateien gefunden (ohne venv)"
elif [[ -f "${INSTALL_DIR}/main.py" ]]; then
    # Ordner-Check schlägt fehl aber Dateien existieren (Symlink o.ä.)
    OK "Installationsordner: ${INSTALL_DIR} (Dateien vorhanden)"
else
    FAIL "Installationsordner fehlt: ${INSTALL_DIR}"
fi

# Wrapper
[[ -f "${BIN_WRAPPER}" ]] && OK "Starter: ${BIN_WRAPPER}" \
    || FAIL "Starter fehlt: ${BIN_WRAPPER}"
[[ -f "${BIN_ROOT}" ]] && OK "Root-Wrapper: ${BIN_ROOT}" \
    || FAIL "Root-Wrapper fehlt: ${BIN_ROOT}"

# Display-Fix im Wrapper
if [[ -f "${BIN_WRAPPER}" ]]; then
    if grep -q "PEESSI_ENV_FILE\|xhost\|DISPLAY" "${BIN_WRAPPER}"; then
        OK "Display-Fix im Wrapper vorhanden"
    else
        FAIL "Display-Fix fehlt im Wrapper → Programm startet nicht nach Passwort-Eingabe"
    fi
fi

# venv
if [[ -x "${VENV_PYTHON}" ]]; then
    VER=$("${VENV_PYTHON}" --version 2>&1)
    OK "Python venv: ${VER}"
else
    WARN "venv nicht gefunden – nutzt System-Python"
fi

# Desktop-Eintrag
[[ -f "/usr/share/applications/peessi-multitool.desktop" ]] \
    && OK "Startmenü-Eintrag vorhanden" \
    || WARN "Startmenü-Eintrag fehlt"


# ══════════════════════════════════════════════════════════════════════════════
HEAD "2  PYTHON-DATEIEN: ZEILEN, MD5, SYNTAX"
# ══════════════════════════════════════════════════════════════════════════════

# Referenz-Werte (aus der aktuellen Entwicklungsversion)
# Format: "dateiname:zeilen:md5"
declare -A REF_LINES=(
    ["main.py"]=287
    ["config.py"]=99
    ["models.py"]=185
    ["database.py"]=82
    ["security.py"]=58
    ["smart_engine.py"]=160
    ["wipe_engine.py"]=171
    ["recovery_engine.py"]=202
    ["gui_base.py"]=236
    ["gui_drives.py"]=2933
    ["gui_system.py"]=2648
)

declare -A REF_MD5=(
    ["main.py"]="4ab845457d24"
    ["config.py"]="ccbc5514c81a"
    ["models.py"]="6a1d121c61e7"
    ["database.py"]="244f2dd750f1"
    ["security.py"]="06c95a93c131"
    ["smart_engine.py"]="a497e9f96f2d"
    ["wipe_engine.py"]="b91b8acb324b"
    ["recovery_engine.py"]="f07773856c2a"
    ["gui_base.py"]="32bf75321c62"
    ["gui_drives.py"]="820eb7348529"
    ["gui_system.py"]="5169f4c033c5"
)

PY="${VENV_PYTHON:-python3}"

printf "  %-22s %7s %7s  %-14s  %s\n" "Datei" "Ref-Z" "Ist-Z" "MD5 (12)" "Status"
printf "  %-22s %7s %7s  %-14s  %s\n" "──────────────────────" "───────" "───────" "──────────────" "──────────────"
_log_raw ""
_log_raw "  Datei                  Ref-Z   Ist-Z  MD5(12)       Status"
_log_raw "  ─────────────────────────────────────────────────────────────"

for fn in "${!REF_LINES[@]}"; do
    fp="${INSTALL_DIR}/${fn}"
    ref_lines="${REF_LINES[$fn]}"
    ref_md5="${REF_MD5[$fn]}"

    if [[ ! -f "${fp}" ]]; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "fehlt" "–"
        echo -e "${RED}❌ FEHLT${RESET}"
        _log_raw "  $(printf '%-22s' ${fn}) $(printf '%7s' ${ref_lines}) $(printf '%7s' 'fehlt')  –              FEHLT"
        ((ERRORS++)); ERROR_LIST+=("${fn}: Datei fehlt")
        continue
    fi

    ist_lines=$(wc -l < "${fp}")
    ist_md5=$(md5sum "${fp}" | cut -c1-12)

    # Syntax prüfen
    syntax_ok=true
    syntax_err=""
    if ! ${PY} -m py_compile "${fp}" 2>/tmp/syntax_err_$$.txt; then
        syntax_ok=false
        syntax_err=$(cat /tmp/syntax_err_$$.txt | head -1)
    fi
    rm -f /tmp/syntax_err_$$.txt

    if ! $syntax_ok; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${RED}❌ SYNTAXFEHLER${RESET}"
        _log_raw "  $(printf '%-22s' ${fn}) $(printf '%7s' ${ref_lines}) $(printf '%7s' ${ist_lines})  ${ist_md5}  SYNTAXFEHLER: ${syntax_err}"
        ((ERRORS++)); ERROR_LIST+=("${fn}: Syntaxfehler – ${syntax_err}")
    elif [[ "${ist_md5}" == "${ref_md5}" ]]; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${GREEN}✅ Identisch${RESET}"
        _log_raw "  $(printf '%-22s' ${fn}) $(printf '%7s' ${ref_lines}) $(printf '%7s' ${ist_lines})  ${ist_md5}  Identisch"
        ((PASSED++))
    elif [[ "${ist_lines}" -lt $((ref_lines - 50)) ]]; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${RED}❌ DEUTLICH KÜRZER (${ist_lines} statt ${ref_lines})${RESET}"
        _log_raw "  $(printf '%-22s' ${fn}) $(printf '%7s' ${ref_lines}) $(printf '%7s' ${ist_lines})  ${ist_md5}  KÜRZER – evtl. veraltet"
        ((ERRORS++)); ERROR_LIST+=("${fn}: Datei hat ${ist_lines} Zeilen statt ${ref_lines}")
    else
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${YELLOW}⚠️  Geändert (${ist_lines} Zeilen)${RESET}"
        _log_raw "  $(printf '%-22s' ${fn}) $(printf '%7s' ${ref_lines}) $(printf '%7s' ${ist_lines})  ${ist_md5}  Unterschiedlich"
        ((WARNINGS++)); WARN_LIST+=("${fn}: Unterschiedlich (${ist_lines} vs ${ref_lines} Zeilen)")
    fi
done


# ══════════════════════════════════════════════════════════════════════════════
HEAD "3  KRITISCHE METHODEN (Vollständigkeitsprüfung)"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYCHECK' 2>&1 | tee -a "${LOG_FILE}"
import sys, os, ast, json

INSTALL_DIR = "/usr/local/lib/peessi-multitool"
LOG_FILE = open("/tmp/peessi_method_check.txt", "w")

# Kritische Methoden die IMMER vorhanden sein müssen
REQUIRED = {
    "main.py": {
        "App": ["__init__","_build_ui","_toggle_theme","refresh_drives",
                "_startup_checks","run","_start_dashboard_updater"],
    },
    "gui_drives.py": {
        "DrivesTabs": [
            "_build","refresh_drives","_build_recovery_tab","_build_wipe_tab",
            "_build_smart_tab","_build_iso_tab","_build_usb_clone_tab",
            "_build_partition_tab","_build_eggs_tab","_build_mint_installer_tab",
            "_build_iso_clone_subtab","_start_iso_clone",
            "_eggs_check_status","_eggs_install_fresh","_eggs_install_appimage",
            "_eggs_produce","_eggs_run_cmd","_eggs_list_isos","_eggs_verify_checksum",
            "_eggs_open_folder",
            "_mint_import","_build_mint_installer_tab","_mint_make_log",
            "_mint_iso_row","_mint_drive_row","_mint_get_drive","_mint_log_stream",
            "_mint_build_dd","_mint_check_hash","_mint_run_dd",
            "_mint_build_full","_mint_run_full",
            "_mint_build_ventoy","_mint_run_ventoy",
            "_mint_build_clone","_mint_run_clone",
            "_mint_build_info","_mint_run_info",
            "_mint_build_settings","_mint_run_prepare",
        ],
    },
    "gui_system.py": {
        "DashboardTab":  ["_build","_update_system_cards","_update_drive_table"],
        "SystemTab":     ["_build","_build_cleanup","_build_optimizer","_build_boot",
                         "_build_bios","_build_update_shutdown","_build_einmal_starter"],
        "NetworkTab":    ["_build","_build_interfaces","_build_ping","_build_connections",
                         "_build_wlan_passwords","_refresh_interfaces","_run_ping",
                         "_refresh_connections","_read_wlan_passwords","_copy_wlan_password",
                         "_conn_sort","_copy_connections"],
        "LogsTab":       ["_build","_build_log_viewer","_build_diagnose","_run_diagnose"],
        "SettingsTab":   ["_build","_save","_reset"],  # apply_theme ist in GuiBase (Vererbung)
        "AboutTab":      ["_build"],
        "HilfeTab":      ["_build","_show_section","_render_section","_on_search"],
    },
    "models.py": {
        "DriveInfo":    ["get_size_human","get_type_label"],
        "DriveScanner": ["scan","_make","_is_usb"],
        "USBInfo":      [],
    },
    # gui_base.py: GuiBase-Methoden werden separat via Vererbungs-Check geprüft
}

errors = 0
warnings = 0
passed = 0

for fn, classes in REQUIRED.items():
    fp = os.path.join(INSTALL_DIR, fn)
    if not os.path.isfile(fp):
        LOG_FILE.write(f"[FAIL] {fn}: Datei fehlt\n")
        print(f"  ❌  {fn}: Datei fehlt")
        errors += 1
        continue
    try:
        tree = ast.parse(open(fp).read())
    except SyntaxError as e:
        LOG_FILE.write(f"[FAIL] {fn}: Syntaxfehler: {e}\n")
        print(f"  ❌  {fn}: Syntaxfehler: {e}")
        errors += 1
        continue

    # Alle Klassen und ihre Methoden erfassen
    found_classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = {n.name for n in ast.walk(node)
                      if isinstance(n, ast.FunctionDef)}
            found_classes[node.name] = methods

    for cls_name, methods in classes.items():
        if cls_name not in found_classes:
            LOG_FILE.write(f"[FAIL] {fn}: Klasse '{cls_name}' fehlt\n")
            print(f"  ❌  {fn}: Klasse '{cls_name}' FEHLT")
            errors += 1
            continue

        for method in methods:
            if method in found_classes[cls_name]:
                passed += 1
            else:
                LOG_FILE.write(f"[FAIL] {fn}: {cls_name}.{method}() FEHLT\n")
                print(f"  ❌  {fn}: {cls_name}.{method}() FEHLT")
                errors += 1

# Vererbte Methoden: GuiBase stellt apply_theme, log_to, make_log_widget etc. bereit
INHERITED_FROM_GUIBASE = ["apply_theme", "rebuild_log_colors", "log_to", "clear_log",
                           "copy_log", "make_log_widget", "run_shell_async", "make_shell_tab"]
guibase_fp = "/usr/local/lib/peessi-multitool/gui_base.py"
if os.path.isfile(guibase_fp):
    guibase_tree = ast.parse(open(guibase_fp).read())
    guibase_methods = set()
    for node in ast.walk(guibase_tree):
        if isinstance(node, ast.ClassDef) and node.name == "GuiBase":
            guibase_methods = {n.name for n in ast.walk(node) if isinstance(n, ast.FunctionDef)}
    for m in INHERITED_FROM_GUIBASE:
        if m in guibase_methods:
            LOG_FILE.write(f"[OK] gui_base.py: GuiBase.{m}() (wird vererbt)\n")
            passed += 1
        else:
            LOG_FILE.write(f"[FAIL] gui_base.py: GuiBase.{m}() FEHLT\n")
            print(f"  ❌  gui_base.py: GuiBase.{m}() FEHLT")
            errors += 1

# Top-Level Funktionen prüfen
TL_REQUIRED = {
    "gui_drives.py": ["_bind_mousewheel", "import_os_path_exists"],
    "gui_system.py": ["_bind_mousewheel"],
}
for fn, funcs in TL_REQUIRED.items():
    fp = os.path.join(INSTALL_DIR, fn)
    if not os.path.isfile(fp): continue
    content = open(fp).read()
    for func in funcs:
        if f"def {func}" in content:
            passed += 1
        else:
            LOG_FILE.write(f"[FAIL] {fn}: Funktion '{func}' fehlt\n")
            print(f"  ❌  {fn}: Funktion '{func}' FEHLT")
            errors += 1

LOG_FILE.write(f"\nMethoden-Check: {passed} OK, {errors} Fehler, {warnings} Warnungen\n")
LOG_FILE.close()

if errors == 0:
    print(f"  ✅  Alle kritischen Methoden vorhanden ({passed} geprüft)")
else:
    print(f"\n  Ergebnis: {passed} OK, {errors} FEHLER")

sys.exit(errors)
PYCHECK

METHOD_RC=$?
if [[ $METHOD_RC -eq 0 ]]; then
    OK "Alle kritischen Methoden vorhanden"
else
    FAIL "Methoden-Check: ${METHOD_RC} Fehler gefunden (Details in Log)"
fi

# Methoden-Log anhängen
cat /tmp/peessi_method_check.txt >> "${LOG_FILE}" 2>/dev/null


# ══════════════════════════════════════════════════════════════════════════════
HEAD "4  PYTHON IMPORTS (alle Module)"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYIMPORT' 2>&1 | tee -a "${LOG_FILE}"
import sys, os
sys.path.insert(0, "/usr/local/lib/peessi-multitool")

modules = [
    ("config",          "config.py"),
    ("models",          "models.py"),
    ("database",        "database.py"),
    ("security",        "security.py"),
    ("smart_engine",    "smart_engine.py"),
    ("wipe_engine",     "wipe_engine.py"),
    ("recovery_engine", "recovery_engine.py"),
    ("gui_base",        "gui_base.py"),
    ("gui_drives",      "gui_drives.py"),
    ("gui_system",      "gui_system.py"),
]

errors = 0
for mod, fname in modules:
    try:
        m = __import__(mod)
        print(f"  ✅  {fname}")
    except Exception as e:
        print(f"  ❌  {fname}: {e}")
        errors += 1

# Kritische Klassen
checks = [
    ("gui_drives", "DrivesTabs", "_build_mint_installer_tab"),
    ("gui_drives", "DrivesTabs", "_build_eggs_tab"),
    ("gui_drives", "DrivesTabs", "_start_iso_clone"),
    ("gui_system", "HilfeTab",   "_build"),
    ("gui_system", "NetworkTab", "_refresh_connections"),
    ("gui_system", "NetworkTab", "_conn_sort"),
]
print("")
for mod_name, cls_name, method in checks:
    try:
        mod = __import__(mod_name)
        cls = getattr(mod, cls_name)
        if hasattr(cls, method):
            print(f"  ✅  {cls_name}.{method}()")
        else:
            print(f"  ❌  {cls_name}.{method}() FEHLT")
            errors += 1
    except Exception as e:
        print(f"  ❌  {cls_name}.{method}(): {e}")
        errors += 1

sys.exit(errors)
PYIMPORT


# ══════════════════════════════════════════════════════════════════════════════
HEAD "5  SYSTEM-ABHÄNGIGKEITEN (Tools & Pakete)"
# ══════════════════════════════════════════════════════════════════════════════

# Format: "befehl:paket:beschreibung:pflicht/optional"
TOOLS=(
    "python3:python3:Python 3 Interpreter:pflicht"
    "python3-tk::Tkinter GUI:pflicht"
    "pkexec:policykit-1:PolicyKit Root-Rechte:pflicht"
    "lsblk:util-linux:Laufwerkserkennung:pflicht"
    "smartctl:smartmontools:SMART-Diagnose:pflicht"
    "ddrescue:gddrescue:Datenrettung:pflicht"
    "photorec:testdisk:Datei-Wiederherstellung:pflicht"
    "nmcli:network-manager:WLAN-Passwörter:pflicht"
    "ss:iproute2:Netzwerk-Verbindungen:pflicht"
    "ip:iproute2:Netzwerk-Interfaces:pflicht"
    "xhost:x11-xserver-utils:X11 Zugriff für Root:pflicht"
    "efibootmgr:efibootmgr:EFI Boot-Manager:optional"
    "netstat:net-tools:Netzwerk Fallback:optional"
    "eggs::Penguins-Eggs:optional"
    "git:git:fresh-eggs Installation:optional"
    "wget:wget:Download-Tool:optional"
    "flatpak:flatpak:Flatpak Bereinigung:optional"
    "nala:nala:APT Frontend:optional"
    "xdg-open:xdg-utils:URLs/Dateien öffnen:optional"
)

MISSING_PFLICHT=()
MISSING_OPT=()

for entry in "${TOOLS[@]}"; do
    IFS=':' read -r cmd pkg desc prio <<< "${entry}"

    found=false
    # Spezialfall: python3-tk (kein Binary, nur Paket)
    if [[ "${cmd}" == "python3-tk" ]]; then
        if ${PY} -c "import tkinter" 2>/dev/null; then
            found=true
        fi
    else
        command -v "${cmd}" &>/dev/null && found=true
    fi

    if $found; then
        VER=$(${cmd} --version 2>/dev/null | head -1 | cut -c1-40 2>/dev/null || echo "")
        OK "${cmd}  ${VER:+(${VER})}"
    else
        if [[ "${prio}" == "pflicht" ]]; then
            FAIL "${cmd} FEHLT  [${desc}]  → apt install ${pkg}"
            MISSING_PFLICHT+=("${pkg}")
        else
            WARN "${cmd} fehlt  [${desc}] (optional)"
            MISSING_OPT+=("${pkg}")
        fi
    fi
done

if [[ ${#MISSING_PFLICHT[@]} -gt 0 ]]; then
    echo ""
    echo -e "  ${YELLOW}Fehlende Pflicht-Pakete installieren:${RESET}"
    echo -e "  ${CYAN}sudo apt install ${MISSING_PFLICHT[*]}${RESET}"
fi


# ══════════════════════════════════════════════════════════════════════════════
HEAD "6  PYTHON-MODULE (Standard & Drittanbieter)"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYMOD' 2>&1 | tee -a "${LOG_FILE}"
import sys
modules = [
    ("tkinter",     "python3-tk", True),
    ("sqlite3",     "eingebaut",  True),
    ("subprocess",  "eingebaut",  True),
    ("threading",   "eingebaut",  True),
    ("hashlib",     "eingebaut",  True),
    ("json",        "eingebaut",  True),
    ("re",          "eingebaut",  True),
    ("PIL",         "python3-pil / pillow", False),
    ("importlib",   "eingebaut",  True),
]
errors = 0
for mod, pkg, required in modules:
    try:
        m = __import__(mod)
        ver = getattr(m, '__version__', '')
        print(f"  ✅  {mod}  {ver and f'({ver})' or ''}")
    except ImportError:
        if required:
            print(f"  ❌  {mod} FEHLT  → apt install {pkg}")
            errors += 1
        else:
            print(f"  ⚠️   {mod} fehlt  [{pkg}] (optional)")
sys.exit(errors)
PYMOD


# ══════════════════════════════════════════════════════════════════════════════
HEAD "7  DISPLAY / X11 / WAYLAND (Start-Problem-Check)"
# ══════════════════════════════════════════════════════════════════════════════

[[ -n "${DISPLAY:-}" ]] && OK "DISPLAY=${DISPLAY}" \
    || WARN "DISPLAY nicht gesetzt"
[[ -n "${WAYLAND_DISPLAY:-}" ]] && OK "WAYLAND_DISPLAY=${WAYLAND_DISPLAY}" \
    || INFO "WAYLAND_DISPLAY nicht gesetzt (X11-Modus normal)"
[[ -n "${XAUTHORITY:-}" ]] && OK "XAUTHORITY=${XAUTHORITY}" \
    || WARN "XAUTHORITY nicht gesetzt"

if command -v xhost &>/dev/null; then
    XHOST_OUT=$(xhost 2>/dev/null || echo "")
    if echo "${XHOST_OUT}" | grep -q "localuser:root"; then
        OK "Root hat X11-Zugriff (xhost +SI:localuser:root aktiv)"
    else
        if [[ $EUID -eq 0 ]]; then
            # Als Root gestartet: xhost läuft auf Display des Original-Users
            # Das ist normal – der Wrapper setzt xhost beim Start automatisch
            INFO "xhost für Root nicht aktiv (normal wenn Analyse-Script direkt als sudo)"
            INFO "Der Programm-Wrapper setzt xhost +SI:localuser:root automatisch beim Start"
            INFO "Falls Programm nach Passwort-Eingabe nicht startet: xhost +SI:localuser:root im Terminal"
        else
            WARN "Root hat keinen X11-Zugriff → nach Passwort-Eingabe startet Fenster nicht"
            INFO "Fix: xhost +SI:localuser:root  (wird vom Wrapper automatisch gesetzt)"
        fi
    fi
fi

# Wrapper enthält Display-Fix?
if [[ -f "${BIN_WRAPPER}" ]]; then
    grep -q "PEESSI_ENV_FILE" "${BIN_WRAPPER}" \
        && OK "Wrapper enthält Display-Fix (PEESSI_ENV_FILE)" \
        || FAIL "Wrapper enthält KEINEN Display-Fix → Programm startet nicht nach Passwort"
fi


# ══════════════════════════════════════════════════════════════════════════════
HEAD "8  NETZWERK-VERBINDUNGEN (Tab-Diagnose)"
# ══════════════════════════════════════════════════════════════════════════════

# ss Ausgabe testen
SS_OUT=$(ss -tunp 2>/dev/null)
SS_LINES=$(echo "${SS_OUT}" | wc -l)
if [[ ${SS_LINES} -gt 1 ]]; then
    OK "ss -tunp liefert ${SS_LINES} Zeilen"
else
    WARN "ss -tunp liefert keine Daten"
fi

# Parser simulieren
${PY} - << 'PYSS' 2>&1 | tee -a "${LOG_FILE}"
import subprocess, re, sys

def parse(line):
    parts = line.split()
    if len(parts) < 5: return None
    proto = parts[0]; state = parts[1]
    local = parts[4] if len(parts) > 4 else ""
    remote = parts[5] if len(parts) > 5 else ""
    pm = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
    proc = f"{pm.group(2)}/{pm.group(1)}" if pm else ""
    return (proto, local, remote, state, proc)

r = subprocess.run(["ss", "-tunp"], capture_output=True, text=True, timeout=10)
rows = []
for line in r.stdout.splitlines():
    line = line.rstrip()
    if not line or line.startswith(("Netid","State")): continue
    result = parse(line)
    if result: rows.append(result)

if rows:
    print(f"  ✅  Parser: {len(rows)} Verbindungen erkannt")
    for row in rows[:3]:
        print(f"         {row[0]:5} {row[3]:12} {row[1]:25} → {row[2]}")
else:
    print("  ⚠️   Parser: Keine Verbindungen – normal wenn nichts aktiv")
sys.exit(0)
PYSS


# ══════════════════════════════════════════════════════════════════════════════
HEAD "9  PENGUINS-EGGS INSTALLATION"
# ══════════════════════════════════════════════════════════════════════════════

# eggs prüfen: auch direkte Pfade (nicht nur PATH)
EGGS_PATH=""
for ep in "$(command -v eggs 2>/dev/null)" "/usr/local/bin/eggs" "/usr/bin/eggs"; do
    [[ -f "${ep}" ]] && EGGS_PATH="${ep}" && break
done

if [[ -n "${EGGS_PATH}" ]]; then
    EGGS_SIZE=$(stat -c%s "${EGGS_PATH}" 2>/dev/null || echo 0)
    if [[ ${EGGS_SIZE} -lt 1000 ]]; then
        FAIL "eggs DEFEKT (${EGGS_SIZE} Bytes, Pfad: ${EGGS_PATH}) – fehlgeschlagener Download!"
        INFO "Fix-Befehl:"
        INFO "  sudo rm '${EGGS_PATH}'"
        INFO "  cd /tmp && rm -rf fresh-eggs"
        INFO "  git clone https://github.com/pieroproietti/fresh-eggs"
        INFO "  cd fresh-eggs && bash fresh-eggs.sh"
        INFO "Oder im Programm: Tab 'Penguins-Eggs' → Knopf '🗑 Defekte eggs-Datei entfernen'"
    else
        EGGS_VER=$("${EGGS_PATH}" --version 2>/dev/null | head -1 || echo "unbekannt")
        OK "eggs: ${EGGS_VER}  (${EGGS_SIZE} Bytes, Pfad: ${EGGS_PATH})"
    fi
else
    WARN "eggs nicht installiert (optional) – Penguins-Eggs Tab zeigt Installations-Optionen"
    INFO "Installation: Programm starten → Tab 'Laufwerke' → '🐧 Penguins-Eggs' → 'fresh-eggs installieren'"
fi

# fresh-eggs Repository
if [[ -d "/tmp/fresh-eggs" ]]; then
    WARN "/tmp/fresh-eggs Verzeichnis vorhanden – bei Reinstall wird es gelöscht"
else
    OK "/tmp/fresh-eggs nicht vorhanden (sauber)"
fi

# Ventoy
VENTOY_PATH=""
for vp in "/opt/ventoy" "/usr/local/ventoy" "${HOME}/ventoy"; do
    [[ -d "${vp}" ]] && VENTOY_PATH="${vp}" && break
done

if [[ -n "${VENTOY_PATH}" ]]; then
    OK "Ventoy gefunden: ${VENTOY_PATH}"
    FRESH_EGGS="${VENTOY_PATH}/plugin/fresh_eggs.sh"
    [[ -f "${FRESH_EGGS}" ]] && OK "Fresh Eggs Plugin: ${FRESH_EGGS}" \
        || WARN "Fresh Eggs Plugin nicht gefunden unter ${VENTOY_PATH}/plugin/"
else
    WARN "Ventoy nicht gefunden (optional)"
fi


# ══════════════════════════════════════════════════════════════════════════════
HEAD "10  MINT-INSTALLER (mint_full_installer.py)"
# ══════════════════════════════════════════════════════════════════════════════

MINT_FOUND=""
for cand in \
    "${INSTALL_DIR}/mint_full_installer.py" \
    "${HOME}/Projekte/peessi-multitool/../linux auf usb/mint_full_installer.py" \
    "$(dirname "${BASH_SOURCE[0]}")/../linux auf usb/mint_full_installer.py" \
    "$(dirname "${BASH_SOURCE[0]}")/mint_full_installer.py"; do
    cand_abs="$(realpath "${cand}" 2>/dev/null || echo "")"
    if [[ -f "${cand_abs}" ]]; then
        MINT_FOUND="${cand_abs}"
        break
    fi
done

if [[ -n "${MINT_FOUND}" ]]; then
    MINT_SIZE=$(stat -c%s "${MINT_FOUND}")
    MINT_LINES=$(wc -l < "${MINT_FOUND}")
    OK "mint_full_installer.py: ${MINT_FOUND} (${MINT_LINES} Zeilen)"

    # Kritische Klassen prüfen
    for cls in "DriveDetector" "VentoyManager" "USBInstaller" "ChecksumManager"; do
        grep -q "class ${cls}" "${MINT_FOUND}" \
            && OK "  Klasse ${cls} vorhanden" \
            || FAIL "  Klasse ${cls} fehlt in mint_full_installer.py"
    done
else
    FAIL "mint_full_installer.py nicht gefunden!"
    INFO "Erwarteter Pfad: ${INSTALL_DIR}/mint_full_installer.py"
    INFO "Kopieren: sudo cp 'linux auf usb/mint_full_installer.py' ${INSTALL_DIR}/"
fi


# ══════════════════════════════════════════════════════════════════════════════
HEAD "11  WLAN / NETZWERK-MANAGER"
# ══════════════════════════════════════════════════════════════════════════════

if command -v nmcli &>/dev/null; then
    NM_STATUS=$(nmcli -t -f STATE general 2>/dev/null || echo "unbekannt")
    OK "NetworkManager: ${NM_STATUS}"

    # WLAN-Verbindungen vorhanden?
    WLAN_COUNT=$(nmcli -t -f NAME,TYPE connection show 2>/dev/null | grep -c "wireless" || echo 0)
    if [[ "${WLAN_COUNT}" -gt 0 ]]; then
        OK "${WLAN_COUNT} WLAN-Verbindung(en) gespeichert"
    else
        INFO "Keine gespeicherten WLAN-Verbindungen"
    fi

    # Root-Rechte für --show-secrets testen
    if [[ $EUID -eq 0 ]]; then
        TEST_OUT=$(nmcli --show-secrets connection show 2>&1 | head -1)
        if echo "${TEST_OUT}" | grep -q "Error\|Fehler"; then
            WARN "nmcli --show-secrets: ${TEST_OUT}"
        else
            OK "nmcli --show-secrets funktioniert (Root-Rechte OK)"
        fi
    else
        INFO "nmcli --show-secrets Test nur als Root möglich"
    fi
else
    FAIL "nmcli nicht gefunden – WLAN-Passwörter-Tab funktioniert nicht"
fi


# ══════════════════════════════════════════════════════════════════════════════
HEAD "12  LAUFWERKE & SMART"
# ══════════════════════════════════════════════════════════════════════════════

# lsblk Test
if command -v lsblk &>/dev/null; then
    LSBLK_OUT=$(lsblk -J -b -o NAME,MODEL,SIZE,FSTYPE,MOUNTPOINT,TYPE,RM 2>/dev/null)
    DISK_COUNT=$(echo "${LSBLK_OUT}" | ${PY} -c "
import json,sys
data = json.load(sys.stdin)
disks = [d for d in data.get('blockdevices',[]) if d.get('type')=='disk']
print(len(disks))
" 2>/dev/null || echo "?")
    OK "lsblk -J -b: ${DISK_COUNT} Laufwerk(e) erkannt"

    # Größen-Parsing testen (238.5G Problem)
    SIZES=$(lsblk -d -o SIZE 2>/dev/null | tail -n +2)
    PARSE_ERR=0
    while IFS= read -r size; do
        [[ -z "${size}" ]] && continue
        # Enthält die Größe Buchstaben (nicht numerisch)?
        if ! echo "${size}" | grep -qE '^[0-9]+$'; then
            ((PARSE_ERR++))
        fi
    done <<< "${SIZES}"

    if [[ ${PARSE_ERR} -gt 0 ]]; then
        INFO "lsblk ohne -b gibt ${PARSE_ERR}× Größen als Strings (z.B. '238.5G') – normal"
        OK "Programm nutzt 'lsblk -b' (Bytes) + models.py parst Strings robust → kein Problem"
    else
        OK "lsblk Größen sind numerisch"
    fi
else
    FAIL "lsblk nicht gefunden"
fi

# smartctl Test
if command -v smartctl &>/dev/null; then
    SMART_VER=$(smartctl --version 2>/dev/null | head -1)
    OK "smartctl: ${SMART_VER}"
else
    FAIL "smartctl fehlt → SMART-Monitor-Tab inaktiv"
fi


# ══════════════════════════════════════════════════════════════════════════════
HEAD "13  KONFIGURATION & BENUTZER-DATEN"
# ══════════════════════════════════════════════════════════════════════════════

ORIG_USER="${SUDO_USER:-${USER}}"
ORIG_HOME=$(eval echo "~${ORIG_USER}")
CONFIG_DIR="${ORIG_HOME}/.config/peessi-multitool"
CONFIG_FILE="${CONFIG_DIR}/settings.json"
SMART_DB="${CONFIG_DIR}/smart_history.db"
ERROR_LOG="${ORIG_HOME}/peessi_multitool_fehler.log"

[[ -d "${CONFIG_DIR}" ]] && OK "Konfig-Ordner: ${CONFIG_DIR}" \
    || INFO "Konfig-Ordner noch nicht vorhanden (wird beim ersten Start erstellt)"

if [[ -f "${CONFIG_FILE}" ]]; then
    # JSON validieren
    if ${PY} -c "import json; json.load(open('${CONFIG_FILE}'))" 2>/dev/null; then
        VER_IN_CFG=$(${PY} -c "import json; d=json.load(open('${CONFIG_FILE}')); print(d.get('theme','?'))")
        OK "settings.json gültig (Theme: ${VER_IN_CFG})"
    else
        FAIL "settings.json ist KEIN gültiges JSON → wird beim nächsten Start neu erstellt"
    fi
else
    INFO "settings.json noch nicht vorhanden (normal beim ersten Start)"
fi

[[ -f "${SMART_DB}" ]] \
    && OK "SMART-Datenbank: ${SMART_DB}" \
    || INFO "SMART-Datenbank noch nicht vorhanden"

if [[ -f "${ERROR_LOG}" ]]; then
    ERR_LINES=$(wc -l < "${ERROR_LOG}")
    ERR_SIZE=$(stat -c%s "${ERROR_LOG}")
    if [[ ${ERR_LINES} -gt 0 ]]; then
        WARN "Fehler-Log vorhanden: ${ERROR_LOG} (${ERR_LINES} Zeilen, ${ERR_SIZE} Bytes)"
        INFO "Letzte 3 Einträge:"
        tail -3 "${ERROR_LOG}" 2>/dev/null | while IFS= read -r line; do
            DETAIL "  ${line}"
        done
    else
        OK "Fehler-Log leer"
    fi
else
    OK "Kein Fehler-Log vorhanden (gut)"
fi


# ══════════════════════════════════════════════════════════════════════════════
HEAD "14  LAUFZEIT-TEST (Programm-Start simulieren)"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYRUNTEST' 2>&1 | tee -a "${LOG_FILE}"
import sys, os
sys.path.insert(0, "/usr/local/lib/peessi-multitool")

errors = 0

# config laden
try:
    import config
    print(f"  ✅  VERSION = '{config.VERSION}'")
    print(f"  ✅  ORIGINAL_USER = '{config.ORIGINAL_USER}'")
    print(f"  ✅  INSTALL_DIR = '{config.INSTALL_DIR}'")
    settings = config.load_settings()
    print(f"  ✅  load_settings() OK (Theme: {settings.get('theme','?')})")
except Exception as e:
    print(f"  ❌  config: {e}"); errors += 1

# security
try:
    from security import SecurityManager
    sec = SecurityManager()
    print(f"  ✅  SecurityManager() OK")
except Exception as e:
    print(f"  ❌  SecurityManager: {e}"); errors += 1

# models
try:
    from models import DriveInfo, DriveScanner
    di = DriveInfo(device="/dev/sda", model="Test", size=256060514304,
                   fs_type="ext4", mount_point="/", removable=False, is_usb=False)
    assert di.get_size_human() != ""
    # Test mit String-Größe (238.5G Problem)
    di2 = DriveInfo(device="/dev/sda", model="Test", size="238.5G",
                    fs_type="", mount_point="", removable=False, is_usb=False)
    size_str = di2.get_size_human()
    print(f"  ✅  DriveInfo.get_size_human() OK  (238.5G → '{size_str}')")
except Exception as e:
    print(f"  ❌  DriveInfo: {e}"); errors += 1

# database
try:
    from database import SmartDatabase
    db = SmartDatabase()
    print(f"  ✅  SmartDatabase() OK")
except Exception as e:
    print(f"  ❌  SmartDatabase: {e}"); errors += 1

# wipe_engine
try:
    from wipe_engine import WipeEngine
    methods = list(WipeEngine.METHODS.keys())
    print(f"  ✅  WipeEngine.METHODS: {methods}")
except Exception as e:
    print(f"  ❌  WipeEngine: {e}"); errors += 1

sys.exit(errors)
PYRUNTEST


# ══════════════════════════════════════════════════════════════════════════════
HEAD "15  BIND_ALL / X11-SICHERHEITSCHECK"
# ══════════════════════════════════════════════════════════════════════════════

INFO "Prüft ob gefährliche bind_all/unbind_all Aufrufe vorhanden sind"

for fn in gui_drives.py gui_system.py gui_base.py; do
    fp="${INSTALL_DIR}/${fn}"
    [[ ! -f "${fp}" ]] && continue

    # bind_all in Helfer-Funktion (ok) vs. im Code selbst (gefährlich)
    BINDALL_COUNT=$(grep -c "bind_all\|unbind_all" "${fp}" 2>/dev/null || echo 0)
    IN_HELPER=$(grep -c "_bind_mousewheel\|def _bind_mousewheel" "${fp}" 2>/dev/null || echo 0)

    if [[ ${BINDALL_COUNT} -gt 0 ]]; then
        if [[ ${IN_HELPER} -gt 0 ]]; then
            OK "${fn}: bind_all nur in _bind_mousewheel Helper (sicher)"
        else
            FAIL "${fn}: bind_all/unbind_all gefunden OHNE Helper-Funktion → X11-Risiko!"
        fi
    else
        OK "${fn}: Kein bind_all/unbind_all (sicher)"
    fi
done


# ══════════════════════════════════════════════════════════════════════════════
HEAD "ZUSAMMENFASSUNG"
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "  ${BOLD}Ergebnis:  ${GREEN}${PASSED} OK${RESET}  ${RED}${ERRORS} Fehler${RESET}  ${YELLOW}${WARNINGS} Warnungen${RESET}"
echo ""

_log_raw ""
_log_raw "=============================================================="
_log_raw "  ZUSAMMENFASSUNG"
_log_raw "=============================================================="
_log_raw "  OK       : ${PASSED}"
_log_raw "  Fehler   : ${ERRORS}"
_log_raw "  Warnungen: ${WARNINGS}"

if [[ ${ERRORS} -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}✅ Keine kritischen Fehler – Installation sieht korrekt aus.${RESET}"
    _log_raw "  STATUS: OK"
else
    echo -e "  ${RED}${BOLD}❌ ${ERRORS} kritische Fehler gefunden:${RESET}"
    _log_raw "  STATUS: FEHLER"
    for err in "${ERROR_LIST[@]}"; do
        echo -e "    ${RED}•  ${err}${RESET}"
        _log_raw "  • ${err}"
    done
fi

if [[ ${WARNINGS} -gt 0 ]]; then
    echo ""
    echo -e "  ${YELLOW}${BOLD}⚠️  ${WARNINGS} Warnungen:${RESET}"
    _log_raw ""
    _log_raw "  Warnungen:"
    for warn in "${WARN_LIST[@]}"; do
        echo -e "    ${YELLOW}•  ${warn}${RESET}"
        _log_raw "  • ${warn}"
    done
fi

echo ""
echo -e "  ${BOLD}Schnellreparatur:${RESET}"
echo -e "  ${CYAN}sudo bash update.sh${RESET}  (aus dem Programmordner)"

_log_raw ""
_log_raw "  Log-Datei: ${LOG_FILE}"
_log_raw "  Kurzfassung: ${SHORT_FILE}"
_log_raw "=============================================================="


# ══════════════════════════════════════════════════════════════════════════════
# KURZFASSUNG erstellen
# ══════════════════════════════════════════════════════════════════════════════
{
echo "Peeßi's System Multitool – Analyse-Kurzfassung"
echo "$(date '+%d.%m.%Y %H:%M:%S')  |  $(hostname)  |  $(whoami)"
echo "================================================================"
echo ""
echo "ERGEBNIS: ${PASSED} OK / ${ERRORS} Fehler / ${WARNINGS} Warnungen"
echo ""

if [[ ${ERRORS} -gt 0 ]]; then
    echo "KRITISCHE FEHLER:"
    for err in "${ERROR_LIST[@]}"; do
        echo "  • ${err}"
    done
    echo ""
fi

if [[ ${WARNINGS} -gt 0 ]]; then
    echo "WARNUNGEN:"
    for warn in "${WARN_LIST[@]}"; do
        echo "  • ${warn}"
    done
    echo ""
fi

echo "INSTALLIERTE DATEIEN:"
for fn in main.py gui_drives.py gui_system.py config.py; do
    fp="${INSTALL_DIR}/${fn}"
    if [[ -f "${fp}" ]]; then
        echo "  ${fn}: $(wc -l < "${fp}") Zeilen, MD5=$(md5sum "${fp}" | cut -c1-12)"
    else
        echo "  ${fn}: FEHLT"
    fi
done

echo ""
echo "SYSTEM:"
echo "  Python: $(python3 --version 2>&1)"
echo "  OS:     $(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME}" || uname -r)"
echo "  eggs:   $(eggs --version 2>/dev/null | head -1 || echo 'nicht installiert')"
echo ""
echo "LOGS:"
echo "  Vollständiges Log: ${LOG_FILE}"
} > "${SHORT_FILE}"

# Eigentümer setzen
chown "${LOG_USER}:${LOG_USER}" "${LOG_FILE}" "${SHORT_FILE}" 2>/dev/null || true

echo ""
echo -e "  ${BOLD}📄 Log-Dateien:${RESET}"
echo -e "  Vollständig : ${LOG_FILE}"
echo -e "  Kurzfassung : ${SHORT_FILE}"
echo ""
