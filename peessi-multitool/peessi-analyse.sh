#!/bin/bash
# =============================================================================
# Peeßi's System Multitool v4.1 – VOLLSTÄNDIGE SYSTEM-ANALYSE
# 14 Prüfbereiche | Erstellt: ~/peessi-analyse-DATUM.log + peessi-analyse-kurz.txt
# Aufruf: sudo bash ~/peessi-analyse.sh
# =============================================================================

set -uo pipefail

INSTALL_DIR="/usr/local/lib/peessi-multitool"
BIN_WRAPPER="/usr/local/bin/peessi-multitool"
BIN_ROOT="/usr/local/bin/peessi-multitool-root"
VENV_PYTHON="${INSTALL_DIR}/venv/bin/python3"
LOG_USER="${SUDO_USER:-${USER:-$(logname 2>/dev/null || echo root)}}"
LOG_HOME=$(eval echo "~${LOG_USER}")
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="${LOG_HOME}/peessi-analyse-${TIMESTAMP}.log"
SHORT_FILE="${LOG_HOME}/peessi-analyse-kurz.txt"

RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'
BLUE='\033[1;34m'; CYAN='\033[1;36m'; BOLD='\033[1m'; RESET='\033[0m'

ERRORS=0; WARNINGS=0; PASSED=0
declare -a ERROR_LIST=()
declare -a WARN_LIST=()

_log_raw() { echo "$*" >> "${LOG_FILE}"; }
OK()   { echo -e "  ${GREEN}✅  $*${RESET}"; _log_raw "  [OK]   $*"; ((PASSED++)); }
FAIL() { echo -e "  ${RED}❌  $*${RESET}"; _log_raw "  [FAIL] $*"; ((ERRORS++)); ERROR_LIST+=("$*"); }
WARN() { echo -e "  ${YELLOW}⚠️   $*${RESET}"; _log_raw "  [WARN] $*"; ((WARNINGS++)); WARN_LIST+=("$*"); }
INFO() { echo -e "  ${CYAN}ℹ️   $*${RESET}"; _log_raw "  [INFO] $*"; }
HEAD() {
    echo -e "\n${BOLD}${BLUE}╔══  $*  ══╗${RESET}"
    _log_raw ""; _log_raw "══════════════════════════════════════════════════"
    _log_raw "  $*"; _log_raw "══════════════════════════════════════════════════"
}

clear
echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Peeßi's System Multitool v4.1 – SYSTEM-ANALYSE           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${RESET}"
_log_raw "=============================================================="
_log_raw "  PEEESSI'S SYSTEM MULTITOOL v4.1 – SYSTEM-ANALYSE"
_log_raw "  Datum: $(date '+%d.%m.%Y %H:%M:%S') | Host: $(hostname) | User: $(whoami)"
_log_raw "=============================================================="
echo "  Datum: $(date '+%d.%m.%Y %H:%M:%S')  |  Log: ${LOG_FILE}"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "1  INSTALLATIONS-VERZEICHNISSE & WRAPPER"
# ══════════════════════════════════════════════════════════════════════════════

if [[ -d "${INSTALL_DIR}" ]]; then
    OK "Installationsordner: ${INSTALL_DIR}"
    PY_COUNT=$(find "${INSTALL_DIR}" -maxdepth 1 -name "*.py" 2>/dev/null | wc -l)
    SH_COUNT=$(find "${INSTALL_DIR}" -maxdepth 1 -name "*.sh" 2>/dev/null | wc -l)
    INFO "  ${PY_COUNT} Python-Dateien, ${SH_COUNT} Shell-Scripts (ohne venv/Unterordner)"
else
    FAIL "Installationsordner fehlt: ${INSTALL_DIR}"
fi

[[ -f "${BIN_WRAPPER}" ]] && OK "Starter: ${BIN_WRAPPER}" || FAIL "Starter fehlt"
[[ -f "${BIN_ROOT}" ]]    && OK "Root-Wrapper: ${BIN_ROOT}" || FAIL "Root-Wrapper fehlt"

[[ -f "${BIN_WRAPPER}" ]] && grep -q "PEESSI_ENV_FILE" "${BIN_WRAPPER}" \
    && OK "Display-Fix im Wrapper vorhanden" || FAIL "Display-Fix fehlt im Wrapper"

[[ -x "${VENV_PYTHON}" ]] \
    && OK "Python venv: $("${VENV_PYTHON}" --version 2>&1)" \
    || WARN "venv nicht gefunden – nutzt System-Python"

[[ -f "/usr/share/applications/peessi-multitool.desktop" ]] \
    && OK "Startmenü-Eintrag vorhanden" || WARN "Startmenü-Eintrag fehlt"

PY="${VENV_PYTHON:-python3}"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "2  PYTHON-DATEIEN: ZEILEN, MD5, SYNTAX"
# ══════════════════════════════════════════════════════════════════════════════

declare -A REF_LINES=(
    ["main.py"]=293         ["config.py"]=99        ["models.py"]=217
    ["database.py"]=87      ["security.py"]=58       ["smart_engine.py"]=160
    ["wipe_engine.py"]=171  ["recovery_engine.py"]=202
    ["gui_base.py"]=270     ["gui_drives.py"]=1792   ["gui_system.py"]=2673
)
declare -A REF_MD5=(
    ["main.py"]="36e6f634eb4c"      ["config.py"]="d65bf2cb34ea"
    ["models.py"]="ddd148b977ff"    ["database.py"]="b2a09db49aa8"
    ["security.py"]="06c95a93c131"  ["smart_engine.py"]="a497e9f96f2d"
    ["wipe_engine.py"]="b91b8acb324b" ["recovery_engine.py"]="f07773856c2a"
    ["gui_base.py"]="ad07e3bfbdef"  ["gui_drives.py"]="2dae243f994d"
    ["gui_system.py"]="27133a6f32b4"
)

printf "  %-22s %7s %7s  %-14s  %s\n" "Datei" "Ref-Z" "Ist-Z" "MD5(12)" "Status"
printf "  %-22s %7s %7s  %-14s  %s\n" "──────────────────────" "───────" "───────" "──────────────" "──────"
_log_raw ""

for fn in "${!REF_LINES[@]}"; do
    fp="${INSTALL_DIR}/${fn}"
    ref_lines="${REF_LINES[$fn]}"; ref_md5="${REF_MD5[$fn]}"
    if [[ ! -f "${fp}" ]]; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "FEHLT" "–"
        echo -e "${RED}❌ FEHLT${RESET}"; _log_raw "  ${fn}: FEHLT"
        ((ERRORS++)); ERROR_LIST+=("${fn}: Datei fehlt"); continue
    fi
    ist_lines=$(wc -l < "${fp}"); ist_md5=$(md5sum "${fp}" | cut -c1-12)
    if ! ${PY} -m py_compile "${fp}" 2>/tmp/syn_$$.txt; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${RED}❌ SYNTAXFEHLER: $(cat /tmp/syn_$$.txt | head -1)${RESET}"
        _log_raw "  ${fn}: SYNTAXFEHLER"
        ((ERRORS++)); ERROR_LIST+=("${fn}: Syntaxfehler")
    elif [[ "${ist_md5}" == "${ref_md5}" ]]; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${GREEN}✅ Identisch${RESET}"; _log_raw "  ${fn}: Identisch"; ((PASSED++))
    elif [[ "${ist_lines}" -lt $((ref_lines - 50)) ]]; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${RED}❌ KÜRZER als erwartet${RESET}"; _log_raw "  ${fn}: KÜRZER"
        ((ERRORS++)); ERROR_LIST+=("${fn}: Nur ${ist_lines} statt ${ref_lines} Zeilen")
    else
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${YELLOW}⚠️  Geändert (${ist_lines} Zeilen)${RESET}"; _log_raw "  ${fn}: Geändert"
        ((WARNINGS++)); WARN_LIST+=("${fn}: Unterschiedlich (${ist_lines} vs ${ref_lines} Zeilen)")
    fi
    rm -f /tmp/syn_$$.txt
done

echo ""
INFO "Extra-Dateien:"
declare -A EXTRA_MIN=( ["gui_grub.py"]=5000 ["gui_drive_health.py"]=5000 ["gui_advanced.py"]=45389
    ["optimizer.sh"]=500 ["eggs-iso-tool.sh"]=1000 ["drive-health-tool.sh"]=1000 )
for fn in "${!EXTRA_MIN[@]}"; do
    fp="${INSTALL_DIR}/${fn}"
    min="${EXTRA_MIN[$fn]}"
    if [[ -f "${fp}" ]]; then
        sz=$(stat -c%s "${fp}" 2>/dev/null || echo 0)
        [[ $sz -gt $min ]] && OK "${fn}  (${sz} Bytes)" \
                           || WARN "${fn} verdächtig klein: ${sz} Bytes (erwartet >${min})"
    else
        WARN "${fn} fehlt – install-peessi-multitool.sh erneut ausführen"
    fi
done
[[ -d "${INSTALL_DIR}/grub-control-center" ]] \
    && OK "grub-control-center/ ($(find "${INSTALL_DIR}/grub-control-center" -name '*.sh' | wc -l) Scripts)" \
    || WARN "grub-control-center/ fehlt"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "3  KRITISCHE METHODEN"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYCHECK' 2>&1 | tee -a "${LOG_FILE}"
import sys, os, ast
INSTALL_DIR = "/usr/local/lib/peessi-multitool"
REQUIRED = {
    "gui_drives.py": {"DrivesTabs": [
        "_build","refresh_drives","_build_recovery_tab","_build_wipe_tab",
        "_build_iso_tab","_build_iso_clone_subtab","_start_iso_clone",
        "_build_usb_clone_tab","_build_partition_tab","_build_drive_health_tab",
        "_update_iso_targets","_start_iso_write","_start_clone","_update_wipe_list",
    ]},
    "gui_system.py": {
        "DashboardTab": ["_build","_update_system_cards","_update_drive_table"],
        "SystemTab":    ["_build","_build_cleanup","_build_optimizer","_build_boot",
                        "_build_bios","_build_update_shutdown","_build_einmal_starter",
                        "_build_eggs_iso","_build_grub_tab","_eggs_iso_start","_eggs_iso_dad"],
        "NetworkTab":   ["_build","_build_interfaces","_build_ping","_build_connections",
                        "_build_wlan_passwords","_refresh_connections","_conn_sort","_copy_connections"],
        "LogsTab":      ["_build","_build_log_viewer","_build_diagnose",
                        "_export_all_logs","_load_all_logs","_search_log"],
        "SettingsTab":  ["_build","_save","_reset"],
        "AboutTab":     ["_build"],
    },
    "gui_base.py": {"GuiBase": [
        "log_to","clear_log","copy_log","make_log_widget","run_shell_async",
        "make_scrollable_tab","make_shell_tab","apply_theme",
    ]},
    "main.py": {"App": ["__init__","_build_ui","_toggle_theme","refresh_drives","run"]},
}
OPTIONAL = {
    "gui_grub.py":         {"GrubTab":         ["_build","_check_status","_set_timeout","_update_grub","_run_check"]},
    "gui_drive_health.py": {"DriveHealthTab":  ["_build","_build_smart_sub","_build_badblocks_sub",
                                                "_smart_read","_bb_start","_bb_stop","_refresh_drives"]},
}
errors = 0; passed = 0
def check_file(fn, classes, required=True):
    global errors, passed
    fp = os.path.join(INSTALL_DIR, fn)
    if not os.path.isfile(fp):
        sym = "❌" if required else "⚠️ "
        print(f"  {sym}  {fn}: fehlt"); errors += (1 if required else 0); return
    try: tree = ast.parse(open(fp).read())
    except SyntaxError as e:
        print(f"  ❌  {fn}: Syntaxfehler: {e}"); errors += 1; return
    found = {n.name: {m.name for m in ast.walk(n) if isinstance(m, ast.FunctionDef)}
             for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    for cls, methods in classes.items():
        if cls not in found:
            print(f"  ❌  {fn}: Klasse '{cls}' fehlt"); errors += 1; continue
        for m in methods:
            if m in found[cls]: passed += 1
            else: print(f"  ❌  {fn}: {cls}.{m}() FEHLT"); errors += 1
for fn, cls in REQUIRED.items(): check_file(fn, cls, True)
for fn, cls in OPTIONAL.items(): check_file(fn, cls, False)
if errors == 0: print(f"  ✅  Alle kritischen Methoden vorhanden ({passed} geprüft)")
else: print(f"\n  Ergebnis: {passed} OK, {errors} FEHLER")
sys.exit(errors)
PYCHECK
[[ $? -eq 0 ]] && OK "Methoden-Check bestanden" || FAIL "Methoden-Check: Fehler"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "4  PYTHON IMPORTS"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYIMPORT' 2>&1 | tee -a "${LOG_FILE}"
import sys, os
sys.path.insert(0, "/usr/local/lib/peessi-multitool")
errors = 0
for mod in ["config","models","database","security","smart_engine",
            "wipe_engine","recovery_engine","gui_base","gui_drives","gui_system"]:
    try: __import__(mod); print(f"  ✅  {mod}.py")
    except Exception as e: print(f"  ❌  {mod}.py: {e}"); errors += 1
print()
for mod, fn in [("gui_grub","gui_grub.py"),("gui_drive_health","gui_drive_health.py")]:
    try: __import__(mod); print(f"  ✅  {fn}")
    except Exception as e: print(f"  ⚠️   {fn}: {e}")
print()
checks = [
    ("gui_drives","DrivesTabs","_build_drive_health_tab"),
    ("gui_drives","DrivesTabs","_update_iso_targets"),
    ("gui_system","SystemTab","_build_eggs_iso"),
    ("gui_system","SystemTab","_build_grub_tab"),
    ("gui_system","LogsTab","_export_all_logs"),
    ("gui_base","GuiBase","make_scrollable_tab"),
]
for mod_name, cls_name, method in checks:
    try:
        cls = getattr(__import__(mod_name), cls_name)
        sym = "✅" if hasattr(cls, method) else "❌"
        if not hasattr(cls, method): errors += 1
        print(f"  {sym}  {cls_name}.{method}()")
    except Exception as e: print(f"  ⚠️   {cls_name}.{method}(): {e}")
sys.exit(errors)
PYIMPORT

# ══════════════════════════════════════════════════════════════════════════════
HEAD "5  SYSTEM-ABHÄNGIGKEITEN"
# ══════════════════════════════════════════════════════════════════════════════

TOOLS=(
    "python3:python3:Python 3:pflicht"
    "python3-tk::Tkinter:pflicht"
    "pkexec:policykit-1:Root-Rechte:pflicht"
    "lsblk:util-linux:Laufwerke:pflicht"
    "smartctl:smartmontools:SMART:pflicht"
    "ddrescue:gddrescue:Datenrettung:pflicht"
    "photorec:testdisk:Dateirettung:pflicht"
    "badblocks:e2fsprogs:Oberflächenscan:pflicht"
    "nmcli:network-manager:WLAN-Passwörter:pflicht"
    "ss:iproute2:Verbindungen:pflicht"
    "ip:iproute2:Netzwerk:pflicht"
    "xhost:x11-xserver-utils:X11:pflicht"
    "git:git:Git:pflicht"
    "curl:curl:Download:pflicht"
    "efibootmgr:efibootmgr:EFI Boot:optional"
    "zenity:zenity:GRUB CC GUI:optional"
    "os-prober:os-prober:Dual-Boot:optional"
    "netstat:net-tools:Fallback Netz:optional"
    "flatpak:flatpak:Flatpak:optional"
    "nala:nala:APT Frontend:optional"
    "xdg-open:xdg-utils:URLs öffnen:optional"
    "eggs:penguins-eggs:Live-ISO:optional"
    "nwipe:nwipe:Sicheres Löschen:optional"
    "rsync:rsync:Datenmigration:optional"
    "mdadm:mdadm:RAID:optional"
    "lvm:lvm2:LVM:optional"
    "ms-sys:ms-sys:Windows-MBR:optional"
)
for entry in "${TOOLS[@]}"; do
    IFS=':' read -r cmd pkg desc prio <<< "${entry}"
    found=false
    [[ "${cmd}" == "python3-tk" ]] && ${PY} -c "import tkinter" 2>/dev/null && found=true
    [[ "${cmd}" != "python3-tk" ]] && command -v "${cmd}" &>/dev/null && found=true
    if $found; then
        VER=$(${cmd} --version 2>/dev/null | head -1 | cut -c1-40 2>/dev/null || echo "")
        OK "${cmd}  ${VER:+(${VER})}"
    else
        [[ "${prio}" == "pflicht" ]] && FAIL "${cmd} FEHLT → apt install ${pkg}" \
                                     || WARN "${cmd} fehlt (optional)"
    fi
done

# ══════════════════════════════════════════════════════════════════════════════
HEAD "6  PYTHON-MODULE"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYMOD' 2>&1 | tee -a "${LOG_FILE}"
import sys
for mod, pkg, req in [
    ("tkinter","python3-tk",True), ("sqlite3","eingebaut",True),
    ("subprocess","eingebaut",True), ("threading","eingebaut",True),
    ("hashlib","eingebaut",True), ("json","eingebaut",True),
    ("re","eingebaut",True), ("ast","eingebaut",True),
    ("PIL","python3-pil",False), ("importlib","eingebaut",True),
]:
    try:
        m = __import__(mod); v = getattr(m,'__version__','')
        print(f"  ✅  {mod}  {v and f'({v})' or ''}")
    except ImportError:
        msg = f"❌  {mod} FEHLT → apt install {pkg}" if req else f"⚠️   {mod} fehlt (optional)"
        print(f"  {msg}")
PYMOD

# ══════════════════════════════════════════════════════════════════════════════
HEAD "7  DISPLAY / X11"
# ══════════════════════════════════════════════════════════════════════════════

[[ -n "${DISPLAY:-}" ]] && OK "DISPLAY=${DISPLAY}" || WARN "DISPLAY nicht gesetzt"
[[ -n "${XAUTHORITY:-}" ]] && OK "XAUTHORITY=${XAUTHORITY}" || WARN "XAUTHORITY nicht gesetzt"
if command -v xhost &>/dev/null; then
    XHOST_OUT=$(xhost 2>/dev/null || echo "")
    echo "${XHOST_OUT}" | grep -q "localuser:root" \
        && OK "Root hat X11-Zugriff" \
        || INFO "xhost für Root nicht aktiv (Wrapper setzt automatisch)"
fi
[[ -f "${BIN_WRAPPER}" ]] && grep -q "PEESSI_ENV_FILE" "${BIN_WRAPPER}" \
    && OK "Wrapper enthält Display-Fix" || FAIL "Wrapper: Display-Fix fehlt"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "8  NETZWERK-VERBINDUNGEN"
# ══════════════════════════════════════════════════════════════════════════════

SS_LINES=$(ss -tunp 2>/dev/null | wc -l)
[[ ${SS_LINES} -gt 1 ]] && OK "ss -tunp: ${SS_LINES} Zeilen" || WARN "ss -tunp: keine Daten"

${PY} - << 'PYSS' 2>&1 | tee -a "${LOG_FILE}"
import subprocess, re
def parse(line):
    p = line.split()
    if len(p) < 5: return None
    pm = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
    return (p[0], p[4] if len(p)>4 else "", p[5] if len(p)>5 else "",
            p[1], f"{pm.group(2)}/{pm.group(1)}" if pm else "")
r = subprocess.run(["ss","-tunp"], capture_output=True, text=True, timeout=10)
rows = [x for l in r.stdout.splitlines()
        if l and not l.startswith(("Netid","State")) for x in [parse(l)] if x]
if rows:
    print(f"  ✅  Parser: {len(rows)} Verbindungen erkannt")
    for row in rows[:4]:
        print(f"         {row[0]:5} {row[3]:12} {row[1]:25} → {row[2]}")
else:
    print("  ⚠️   Keine Verbindungen (normal)")
PYSS

# ══════════════════════════════════════════════════════════════════════════════
HEAD "9  LAUFWERKE, SMART & BADBLOCKS"
# ══════════════════════════════════════════════════════════════════════════════

if command -v lsblk &>/dev/null; then
    DISK_COUNT=$(lsblk -d -o NAME,TYPE -n 2>/dev/null | awk '$2=="disk"' | wc -l)
    OK "lsblk: ${DISK_COUNT} Laufwerk(e)"
    lsblk -d -o NAME,SIZE,MODEL,ROTA,TYPE -n 2>/dev/null | while read -r name size model rota type; do
        [[ "$type" == "disk" ]] || continue
        typ=$([[ "$rota" == "1" ]] && echo "HDD" || echo "SSD/Flash")
        INFO "  /dev/${name}  ${size:-?}  ${typ}  ${model:-unbekannt}"
    done
else
    FAIL "lsblk fehlt"
fi

command -v smartctl &>/dev/null \
    && OK "smartctl: $(smartctl --version 2>/dev/null | head -1 | cut -c1-60)" \
    || FAIL "smartctl fehlt"

command -v badblocks &>/dev/null \
    && OK "badblocks verfügbar" || FAIL "badblocks fehlt → apt install e2fsprogs"

SMART_DB="${LOG_HOME}/.local/share/peessi-multitool/smart_history.db"
[[ -f "${SMART_DB}" ]] \
    && OK "SMART-DB: $(stat -c%s "${SMART_DB}") Bytes" \
    || INFO "SMART-DB noch nicht vorhanden"

[[ -d "${LOG_HOME}/DriveTests" ]] \
    && OK "DriveTests/: $(ls "${LOG_HOME}/DriveTests/" 2>/dev/null | wc -l) Log(s)" \
    || INFO "DriveTests/ noch nicht vorhanden"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "10  WLAN / NETZWERK-MANAGER"
# ══════════════════════════════════════════════════════════════════════════════

if command -v nmcli &>/dev/null; then
    NM_STATUS=$(nmcli -t -f STATE general 2>/dev/null || echo "unbekannt")
    OK "NetworkManager: ${NM_STATUS}"
    WLAN_COUNT=$(nmcli -t -f NAME,TYPE connection show 2>/dev/null | grep -c "wireless" || echo 0)
    [[ "${WLAN_COUNT}" -gt 0 ]] && OK "${WLAN_COUNT} WLAN-Verbindung(en)" || INFO "Keine WLAN-Verbindungen"
    [[ $EUID -eq 0 ]] && OK "Root für nmcli --show-secrets OK"
else
    FAIL "nmcli fehlt"
fi

# ══════════════════════════════════════════════════════════════════════════════
HEAD "11  KONFIGURATION & LOGS"
# ══════════════════════════════════════════════════════════════════════════════

ORIG_USER="${SUDO_USER:-${USER}}"
ORIG_HOME=$(eval echo "~${ORIG_USER}")
CONFIG_FILE="${ORIG_HOME}/.config/peessi-multitool/settings.json"
ERROR_LOG="${ORIG_HOME}/peessi_multitool_fehler.log"

if [[ -f "${CONFIG_FILE}" ]]; then
    ${PY} -c "
import json, sys
s = json.load(open('${CONFIG_FILE}'))
print(f'  ✅  settings.json OK | Theme: {s.get(\"theme\",\"?\")} | Fenster: {s.get(\"window_size\",\"?\")}')
" 2>/dev/null || FAIL "settings.json ungültiges JSON"
else
    INFO "settings.json nicht vorhanden (normal beim ersten Start)"
fi

if [[ -f "${ERROR_LOG}" ]]; then
    ERR_LINES=$(wc -l < "${ERROR_LOG}")
    [[ ${ERR_LINES} -gt 0 ]] \
        && WARN "Fehler-Log: ${ERR_LINES} Zeilen in ${ERROR_LOG}" \
        || OK "Fehler-Log leer"
    [[ ${ERR_LINES} -gt 0 ]] && {
        INFO "  Letzter Eintrag (letzte 4 Zeilen):"
        tail -4 "${ERROR_LOG}" | while IFS= read -r line; do INFO "    ${line}"; done
    }
else
    OK "Kein Fehler-Log vorhanden"
fi

# ══════════════════════════════════════════════════════════════════════════════
HEAD "12  LAUFZEIT-TEST"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYRUN' 2>&1 | tee -a "${LOG_FILE}"
import sys, os
sys.path.insert(0, "/usr/local/lib/peessi-multitool")
errors = 0

try:
    import config
    print(f"  ✅  VERSION='{config.VERSION}'  USER='{config.ORIGINAL_USER}'")
    s = config.load_settings()
    print(f"  ✅  load_settings() OK (Theme: {s.get('theme','?')}, Fenster: {s.get('window_size','?')})")
except Exception as e:
    print(f"  ❌  config: {e}"); errors += 1

for cls_name, module, *args in [
    ("SecurityManager", "security"),
    ("SmartDatabase",   "database"),
]:
    try:
        cls = getattr(__import__(module), cls_name)
        cls()
        print(f"  ✅  {cls_name}() OK")
    except Exception as e:
        print(f"  ❌  {cls_name}: {e}"); errors += 1

try:
    from models import DriveInfo
    di = DriveInfo("/dev/sda","Test",256060514304,"ext4","/",False,False)
    print(f"  ✅  DriveInfo OK | size='{di.get_size_human()}' | type='{di.get_type_label()}'")
    di2 = DriveInfo("/dev/sdb","Test","238.5G","","",True,True)
    print(f"  ✅  DriveInfo(str-size) → '{di2.get_size_human()}'")
except Exception as e:
    print(f"  ❌  DriveInfo: {e}"); errors += 1

try:
    from wipe_engine import WipeEngine
    print(f"  ✅  WipeEngine.METHODS: {list(WipeEngine.METHODS.keys())}")
except Exception as e:
    print(f"  ❌  WipeEngine: {e}"); errors += 1

try:
    from smart_engine import query_smart_attributes
    print(f"  ✅  smart_engine.query_smart_attributes importierbar")
except Exception as e:
    print(f"  ❌  smart_engine: {e}"); errors += 1

import ast
try:
    tree = ast.parse(open("/usr/local/lib/peessi-multitool/gui_base.py").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == "GuiBase":
            methods = {m.name for m in ast.walk(n) if isinstance(m, ast.FunctionDef)}
            for m in ["make_scrollable_tab","run_shell_async","make_shell_tab"]:
                sym = "✅" if m in methods else "❌"
                if m not in methods: errors += 1
                print(f"  {sym}  GuiBase.{m}()")
except Exception as e:
    print(f"  ❌  gui_base AST: {e}"); errors += 1

sys.exit(errors)
PYRUN

# ══════════════════════════════════════════════════════════════════════════════
HEAD "13  SHELL-SCRIPTS PRÜFUNG"
# ══════════════════════════════════════════════════════════════════════════════

for script in optimizer.sh eggs-iso-tool.sh drive-health-tool.sh; do
    fp="${INSTALL_DIR}/${script}"
    if [[ -f "${fp}" ]]; then
        bash -n "${fp}" 2>/dev/null && OK "${script}: Syntax OK" || FAIL "${script}: Syntaxfehler"
        [[ -x "${fp}" ]] && OK "${script}: ausführbar" || WARN "${script}: nicht ausführbar"
    else
        WARN "${script}: fehlt"
    fi
done

if [[ -d "${INSTALL_DIR}/grub-control-center" ]]; then
    GCC_OK=0; GCC_ERR=0
    while IFS= read -r sh; do
        bash -n "${sh}" 2>/dev/null && ((GCC_OK++)) \
            || { ((GCC_ERR++)); FAIL "grub-cc Syntaxfehler: $(basename "${sh}")"; }
    done < <(find "${INSTALL_DIR}/grub-control-center" -name "*.sh")
    [[ ${GCC_ERR} -eq 0 ]] && OK "grub-control-center: ${GCC_OK} Scripts Syntax OK"
fi

if [[ -f "${INSTALL_DIR}/optimizer.sh" ]]; then
    grep -q "sysctl\|swappiness" "${INSTALL_DIR}/optimizer.sh" \
        && OK "optimizer.sh: Kernel-Tuning-Abschnitt vorhanden" \
        || WARN "optimizer.sh: Kernel-Tuning fehlt"
    grep -q "swapfile" "${INSTALL_DIR}/optimizer.sh" \
        && OK "optimizer.sh: Swap-Abschnitt vorhanden" || WARN "optimizer.sh: Swap fehlt"
    grep -q "firefox\|Firefox" "${INSTALL_DIR}/optimizer.sh" \
        && OK "optimizer.sh: Firefox-Abschnitt vorhanden" || WARN "optimizer.sh: Firefox fehlt"
fi

# ══════════════════════════════════════════════════════════════════════════════
HEAD "14  X11-SICHERHEIT & SCROLL-BINDING"
# ══════════════════════════════════════════════════════════════════════════════

for fn in gui_drives.py gui_system.py gui_base.py; do
    fp="${INSTALL_DIR}/${fn}"
    [[ -f "${fp}" ]] || continue
    CNT=$(grep -c "\.bind_all\|\.unbind_all" "${fp}" 2>/dev/null || echo 0)
    [[ $CNT -gt 0 ]] \
        && WARN "${fn}: ${CNT}× bind_all (kann X11 destabilisieren)" \
        || OK "${fn}: kein bind_all (sicher)"
done

${PY} - << 'PYSCROLL' 2>&1 | tee -a "${LOG_FILE}"
import os
INSTALL_DIR = "/usr/local/lib/peessi-multitool"
counts = {"make_scrollable_tab":0, "_bind_rec":0, "_bind_all":0, "MouseWheel":0}
for fn in ["gui_drives.py","gui_system.py","gui_base.py","gui_grub.py","gui_drive_health.py"]:
    fp = os.path.join(INSTALL_DIR, fn)
    if not os.path.isfile(fp): continue
    src = open(fp).read()
    for k in counts: counts[k] += src.count(k)
print(f"  ✅  make_scrollable_tab: {counts['make_scrollable_tab']}× aufgerufen")
bind = counts['_bind_rec'] + counts['_bind_all']
print(f"  {'✅' if bind>0 else '⚠️ '}  Rekursives Scroll-Binding: {bind}× vorhanden")
print(f"  ✅  MouseWheel-Bindings gesamt: {counts['MouseWheel']}×")
PYSCROLL

# ══════════════════════════════════════════════════════════════════════════════
HEAD "ZUSAMMENFASSUNG"
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "  ${BOLD}Ergebnis:  ${GREEN}${PASSED} OK${RESET}  ${RED}${ERRORS} Fehler${RESET}  ${YELLOW}${WARNINGS} Warnungen${RESET}"
_log_raw ""; _log_raw "ZUSAMMENFASSUNG: ${PASSED} OK / ${ERRORS} Fehler / ${WARNINGS} Warnungen"

[[ ${ERRORS} -eq 0 ]] \
    && echo -e "\n  ${GREEN}${BOLD}✅ Keine kritischen Fehler.${RESET}" \
    || { echo -e "\n  ${RED}${BOLD}❌ ${ERRORS} kritische Fehler:${RESET}"
         for e in "${ERROR_LIST[@]}"; do echo -e "    ${RED}•  ${e}${RESET}"; done; }

[[ ${WARNINGS} -gt 0 ]] && {
    echo -e "\n  ${YELLOW}${BOLD}⚠️  ${WARNINGS} Warnungen:${RESET}"
    for w in "${WARN_LIST[@]}"; do echo -e "    ${YELLOW}•  ${w}${RESET}"; done; }

echo -e "\n  ${BOLD}Reparatur:${RESET} sudo bash install-peessi-multitool.sh"

{
echo "Peeßi's System Multitool v4.1 – Analyse-Kurzfassung"
echo "$(date '+%d.%m.%Y %H:%M:%S')  |  $(hostname)  |  $(whoami)"
echo "================================================================"
echo "ERGEBNIS: ${PASSED} OK / ${ERRORS} Fehler / ${WARNINGS} Warnungen"
echo ""
[[ ${ERRORS} -gt 0 ]]   && { echo "KRITISCHE FEHLER:"; for e in "${ERROR_LIST[@]}"; do echo "  • $e"; done; echo ""; }
[[ ${WARNINGS} -gt 0 ]] && { echo "WARNUNGEN:";        for w in "${WARN_LIST[@]}"; do echo "  • $w"; done; echo ""; }
echo "INSTALLIERTE DATEIEN:"
for fn in main.py gui_drives.py gui_system.py gui_grub.py gui_drive_health.py config.py; do
    fp="${INSTALL_DIR}/${fn}"
    [[ -f "$fp" ]] && echo "  ${fn}: $(wc -l<"$fp") Zeilen, MD5=$(md5sum "$fp"|cut -c1-12)" \
                   || echo "  ${fn}: FEHLT"
done
echo ""
echo "SHELL-SCRIPTS:"
for fn in optimizer.sh eggs-iso-tool.sh drive-health-tool.sh; do
    fp="${INSTALL_DIR}/${fn}"
    [[ -f "$fp" ]] && echo "  ${fn}: $(stat -c%s "$fp") Bytes" || echo "  ${fn}: FEHLT"
done
echo ""
echo "SYSTEM: Python=$(python3 --version 2>&1) | OS=$(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME}" || uname -r)"
echo ""
echo "LOGS:"
echo "  ${LOG_FILE}"
echo "  ${SHORT_FILE}"
} > "${SHORT_FILE}"

chown "${LOG_USER}:${LOG_USER}" "${LOG_FILE}" "${SHORT_FILE}" 2>/dev/null || true
echo -e "\n  📄 ${LOG_FILE}\n  📄 ${SHORT_FILE}\n"
