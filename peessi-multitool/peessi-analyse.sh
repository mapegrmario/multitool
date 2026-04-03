#!/bin/bash
# =============================================================================
# Peeßi's System Multitool v4.1 – VOLLSTÄNDIGE SYSTEM-ANALYSE
# Prüft Installation, Dateien, Methoden, Abhängigkeiten und Systemumgebung
# Erstellt: /home/<user>/peessi-analyse-DATUM.log + peessi-analyse-kurz.txt
#
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
BLUE='\033[1;34m'; CYAN='\033[1;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

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

if [[ -d "${INSTALL_DIR}" ]] || [[ -f "${INSTALL_DIR}/main.py" ]]; then
    OK "Installationsordner: ${INSTALL_DIR}"
    PY_COUNT=$(find "${INSTALL_DIR}" -maxdepth 1 -name "*.py" 2>/dev/null | wc -l)
    INFO "  ${PY_COUNT} Python-Programmdateien (ohne venv)"
else
    FAIL "Installationsordner fehlt: ${INSTALL_DIR}"
fi

[[ -f "${BIN_WRAPPER}" ]] && OK "Starter: ${BIN_WRAPPER}" || FAIL "Starter fehlt: ${BIN_WRAPPER}"
[[ -f "${BIN_ROOT}" ]]    && OK "Root-Wrapper: ${BIN_ROOT}" || FAIL "Root-Wrapper fehlt"

if [[ -f "${BIN_WRAPPER}" ]]; then
    grep -q "PEESSI_ENV_FILE\|xhost\|DISPLAY" "${BIN_WRAPPER}" \
        && OK "Display-Fix im Wrapper vorhanden" \
        || FAIL "Display-Fix fehlt im Wrapper"
fi

if [[ -x "${VENV_PYTHON}" ]]; then
    OK "Python venv: $("${VENV_PYTHON}" --version 2>&1)"
else
    WARN "venv nicht gefunden – nutzt System-Python"
fi

[[ -f "/usr/share/applications/peessi-multitool.desktop" ]] \
    && OK "Startmenü-Eintrag vorhanden" \
    || WARN "Startmenü-Eintrag fehlt"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "2  PYTHON-DATEIEN: ZEILEN, MD5, SYNTAX"
# ══════════════════════════════════════════════════════════════════════════════

declare -A REF_LINES=(
    ["main.py"]=286
    ["config.py"]=99
    ["models.py"]=217
    ["database.py"]=82
    ["security.py"]=58
    ["smart_engine.py"]=160
    ["wipe_engine.py"]=171
    ["recovery_engine.py"]=202
    ["gui_base.py"]=193
    ["gui_drives.py"]=1725
    ["gui_system.py"]=2658
)

declare -A REF_MD5=(
    ["main.py"]="5372ca17fce8"
    ["config.py"]="d65bf2cb34ea"
    ["models.py"]="ddd148b977ff"
    ["database.py"]="244f2dd750f1"
    ["security.py"]="06c95a93c131"
    ["smart_engine.py"]="a497e9f96f2d"
    ["wipe_engine.py"]="b91b8acb324b"
    ["recovery_engine.py"]="f07773856c2a"
    ["gui_base.py"]="b1d676d182b3"
    ["gui_drives.py"]="b3a2a6c12b99"
    ["gui_system.py"]="da754053c3ae"
)

PY="${VENV_PYTHON:-python3}"

printf "  %-22s %7s %7s  %-14s  %s\n" "Datei" "Ref-Z" "Ist-Z" "MD5 (12)" "Status"
printf "  %-22s %7s %7s  %-14s  %s\n" "──────────────────────" "───────" "───────" "──────────────" "──────"
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
        _log_raw "  $(printf '%-22s' ${fn}) FEHLT"
        ((ERRORS++)); ERROR_LIST+=("${fn}: Datei fehlt"); continue
    fi

    ist_lines=$(wc -l < "${fp}")
    ist_md5=$(md5sum "${fp}" | cut -c1-12)

    if ! ${PY} -m py_compile "${fp}" 2>/tmp/syn_$$.txt; then
        syn_err=$(cat /tmp/syn_$$.txt | head -1)
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${RED}❌ SYNTAXFEHLER${RESET}"
        _log_raw "  $(printf '%-22s' ${fn}) SYNTAXFEHLER: ${syn_err}"
        ((ERRORS++)); ERROR_LIST+=("${fn}: Syntaxfehler")
    elif [[ "${ist_md5}" == "${ref_md5}" ]]; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${GREEN}✅ Identisch${RESET}"
        _log_raw "  $(printf '%-22s' ${fn}) Identisch"
        ((PASSED++))
    elif [[ "${ist_lines}" -lt $((ref_lines - 50)) ]]; then
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${RED}❌ KÜRZER als erwartet${RESET}"
        _log_raw "  $(printf '%-22s' ${fn}) KÜRZER (${ist_lines} < ${ref_lines})"
        ((ERRORS++)); ERROR_LIST+=("${fn}: Datei hat ${ist_lines} statt ${ref_lines} Zeilen")
    else
        printf "  %-22s %7s %7s  %-14s  " "${fn}" "${ref_lines}" "${ist_lines}" "${ist_md5}"
        echo -e "${YELLOW}⚠️  Geändert (${ist_lines} Zeilen)${RESET}"
        _log_raw "  $(printf '%-22s' ${fn}) Geändert (${ist_lines} Zeilen)"
        ((WARNINGS++)); WARN_LIST+=("${fn}: Unterschiedlich (${ist_lines} vs ${ref_lines} Zeilen)")
    fi
    rm -f /tmp/syn_$$.txt
done

# ══════════════════════════════════════════════════════════════════════════════
HEAD "3  KRITISCHE METHODEN"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYCHECK' 2>&1 | tee -a "${LOG_FILE}"
import sys, os, ast

INSTALL_DIR = "/usr/local/lib/peessi-multitool"

REQUIRED = {
    "main.py": {"App": ["__init__","_build_ui","_toggle_theme","refresh_drives","run"]},
    "gui_drives.py": {
        "DrivesTabs": [
            "_build","refresh_drives",
            "_build_recovery_tab","_build_wipe_tab","_build_smart_tab",
            "_build_iso_tab","_build_iso_clone_subtab","_start_iso_clone",
            "_build_usb_clone_tab","_build_partition_tab",
            "_update_iso_targets","_update_clone_combos","_update_wipe_list",
            "_start_iso_write","_start_clone",
            "_read_smart","_save_smart_to_db","_show_smart_history",
            "_confirm_wipe","_start_recovery",
        ],
    },
    "gui_system.py": {
        "DashboardTab":  ["_build","_update_system_cards","_update_drive_table"],
        "SystemTab":     ["_build","_build_cleanup","_build_optimizer","_build_boot",
                         "_build_bios","_build_update_shutdown","_build_einmal_starter"],
        "NetworkTab":    ["_build","_build_interfaces","_build_ping","_build_connections",
                         "_build_wlan_passwords","_refresh_interfaces","_run_ping",
                         "_refresh_connections","_read_wlan_passwords",
                         "_conn_sort","_copy_connections"],
        "LogsTab":       ["_build","_build_log_viewer","_build_diagnose","_run_diagnose"],
        "SettingsTab":   ["_build","_save","_reset"],
        "AboutTab":      ["_build"],
    },
    "models.py": {
        "DriveInfo":    ["get_size_human","get_type_label","_is_system_drive"],
        "DriveScanner": ["scan","_make","_is_usb"],
    },
    "gui_base.py": {
        "GuiBase": ["log_to","clear_log","copy_log","make_log_widget","run_shell_async"],
    },
}

errors = 0; passed = 0

for fn, classes in REQUIRED.items():
    fp = os.path.join(INSTALL_DIR, fn)
    if not os.path.isfile(fp):
        print(f"  ❌  {fn}: Datei fehlt"); errors += 1; continue
    try:
        tree = ast.parse(open(fp).read())
    except SyntaxError as e:
        print(f"  ❌  {fn}: Syntaxfehler: {e}"); errors += 1; continue

    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            found[node.name] = {n.name for n in ast.walk(node) if isinstance(n, ast.FunctionDef)}

    for cls, methods in classes.items():
        if cls not in found:
            print(f"  ❌  {fn}: Klasse '{cls}' fehlt"); errors += 1; continue
        for m in methods:
            if m in found[cls]: passed += 1
            else:
                print(f"  ❌  {fn}: {cls}.{m}() FEHLT"); errors += 1

# GuiBase Vererbungs-Check
guibase_fp = os.path.join(INSTALL_DIR, "gui_base.py")
if os.path.isfile(guibase_fp):
    tree = ast.parse(open(guibase_fp).read())
    gb_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "GuiBase":
            gb_methods = {n.name for n in ast.walk(node) if isinstance(n, ast.FunctionDef)}
    for m in ["apply_theme","rebuild_log_colors","make_shell_tab"]:
        if m in gb_methods: passed += 1
        else: print(f"  ❌  gui_base.py: GuiBase.{m}() fehlt"); errors += 1

if errors == 0:
    print(f"  ✅  Alle kritischen Methoden vorhanden ({passed} geprüft)")
else:
    print(f"\n  Ergebnis: {passed} OK, {errors} FEHLER")

sys.exit(errors)
PYCHECK
[[ $? -eq 0 ]] && OK "Methoden-Check bestanden" || FAIL "Methoden-Check: Fehler gefunden"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "4  PYTHON IMPORTS"
# ══════════════════════════════════════════════════════════════════════════════

${PY} - << 'PYIMPORT' 2>&1 | tee -a "${LOG_FILE}"
import sys, os
sys.path.insert(0, "/usr/local/lib/peessi-multitool")

modules = ["config","models","database","security","smart_engine",
           "wipe_engine","recovery_engine","gui_base","gui_drives","gui_system"]
errors = 0
for mod in modules:
    try:
        __import__(mod)
        print(f"  ✅  {mod}.py")
    except Exception as e:
        print(f"  ❌  {mod}.py: {e}"); errors += 1

print()
# Kritische Klassen testen
checks = [
    ("gui_drives","DrivesTabs","_build_iso_clone_subtab"),
    ("gui_drives","DrivesTabs","_start_iso_clone"),
    ("gui_drives","DrivesTabs","_update_iso_targets"),
    ("gui_system","NetworkTab","_refresh_connections"),
    ("gui_system","NetworkTab","_conn_sort"),
    ("gui_system","AboutTab","_build"),
]
for mod_name, cls_name, method in checks:
    try:
        mod = __import__(mod_name)
        cls = getattr(mod, cls_name)
        if hasattr(cls, method):
            print(f"  ✅  {cls_name}.{method}()")
        else:
            print(f"  ❌  {cls_name}.{method}() FEHLT"); errors += 1
    except Exception as e:
        print(f"  ❌  {cls_name}.{method}(): {e}"); errors += 1

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
    "nmcli:network-manager:WLAN-Passwörter:pflicht"
    "ss:iproute2:Verbindungen:pflicht"
    "ip:iproute2:Netzwerk:pflicht"
    "xhost:x11-xserver-utils:X11:pflicht"
    "efibootmgr:efibootmgr:EFI Boot:optional"
    "netstat:net-tools:Netzwerk Fallback:optional"
    "git:git:Git:optional"
    "wget:wget:Download:optional"
    "flatpak:flatpak:Flatpak:optional"
    "nala:nala:APT Frontend:optional"
    "xdg-open:xdg-utils:URLs öffnen:optional"
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
        [[ "${prio}" == "pflicht" ]] && FAIL "${cmd} FEHLT [${desc}] → apt install ${pkg}" \
                                     || WARN "${cmd} fehlt [${desc}] (optional)"
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
    ("re","eingebaut",True), ("PIL","python3-pil",False),
    ("importlib","eingebaut",True),
]:
    try:
        m = __import__(mod)
        v = getattr(m,'__version__','')
        print(f"  ✅  {mod}  {v and f'({v})' or ''}")
    except ImportError:
        if req: print(f"  ❌  {mod} FEHLT → apt install {pkg}")
        else:   print(f"  ⚠️   {mod} fehlt [{pkg}] (optional)")
PYMOD

# ══════════════════════════════════════════════════════════════════════════════
HEAD "7  DISPLAY / X11"
# ══════════════════════════════════════════════════════════════════════════════

[[ -n "${DISPLAY:-}" ]] && OK "DISPLAY=${DISPLAY}" || WARN "DISPLAY nicht gesetzt"
[[ -n "${XAUTHORITY:-}" ]] && OK "XAUTHORITY=${XAUTHORITY}" || WARN "XAUTHORITY nicht gesetzt"

if command -v xhost &>/dev/null; then
    XHOST_OUT=$(xhost 2>/dev/null || echo "")
    if echo "${XHOST_OUT}" | grep -q "localuser:root"; then
        OK "Root hat X11-Zugriff"
    else
        if [[ $EUID -eq 0 ]]; then
            INFO "xhost für Root nicht aktiv (normal bei sudo – Wrapper setzt es automatisch)"
        else
            WARN "Root hat keinen X11-Zugriff → peessi-multitool starten statt sudo python3"
        fi
    fi
fi
[[ -f "${BIN_WRAPPER}" ]] && grep -q "PEESSI_ENV_FILE" "${BIN_WRAPPER}" \
    && OK "Wrapper enthält Display-Fix" || FAIL "Wrapper enthält KEINEN Display-Fix"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "8  NETZWERK-VERBINDUNGEN"
# ══════════════════════════════════════════════════════════════════════════════

SS_LINES=$(ss -tunp 2>/dev/null | wc -l)
[[ ${SS_LINES} -gt 1 ]] && OK "ss -tunp: ${SS_LINES} Zeilen" || WARN "ss -tunp: keine Daten"

${PY} - << 'PYSS' 2>&1 | tee -a "${LOG_FILE}"
import subprocess, re, sys
def parse(line):
    parts = line.split()
    if len(parts) < 5: return None
    pm = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
    proc = f"{pm.group(2)}/{pm.group(1)}" if pm else ""
    return (parts[0], parts[4] if len(parts)>4 else "", parts[5] if len(parts)>5 else "", parts[1], proc)

r = subprocess.run(["ss","-tunp"], capture_output=True, text=True, timeout=10)
rows = [parse(l.rstrip()) for l in r.stdout.splitlines()
        if l and not l.startswith(("Netid","State")) and parse(l.rstrip())]
rows = [r for r in rows if r]
if rows:
    print(f"  ✅  Parser: {len(rows)} Verbindungen erkannt")
    for row in rows[:3]:
        print(f"         {row[0]:5} {row[3]:12} {row[1]:25} → {row[2]}")
else:
    print("  ⚠️   Keine Verbindungen (normal wenn nichts aktiv)")
PYSS

# ══════════════════════════════════════════════════════════════════════════════
HEAD "9  LAUFWERKE & ISO-BRENNER"
# ══════════════════════════════════════════════════════════════════════════════

if command -v lsblk &>/dev/null; then
    DISK_COUNT=$(lsblk -J -b -o NAME,TYPE 2>/dev/null | ${PY} -c "
import json,sys
d=json.load(sys.stdin)
print(len([x for x in d.get('blockdevices',[]) if x.get('type')=='disk']))" 2>/dev/null || echo "?")
    OK "lsblk: ${DISK_COUNT} Laufwerk(e)"

    # Größen-Test (238.5G Problem)
    NONNUM=$(lsblk -d -o SIZE 2>/dev/null | tail -n+2 | grep -cvE '^[0-9]+$' || echo 0)
    if [[ ${NONNUM} -gt 0 ]]; then
        INFO "lsblk ohne -b: ${NONNUM}× String-Größen (normal) – Programm nutzt -b (Bytes)"
    else
        OK "lsblk Größen numerisch"
    fi
else
    FAIL "lsblk fehlt"
fi

command -v smartctl &>/dev/null \
    && OK "smartctl: $(smartctl --version 2>/dev/null | head -1)" \
    || FAIL "smartctl fehlt → SMART-Monitor inaktiv"

# ══════════════════════════════════════════════════════════════════════════════
HEAD "10  WLAN / NETZWERK-MANAGER"
# ══════════════════════════════════════════════════════════════════════════════

if command -v nmcli &>/dev/null; then
    NM_STATUS=$(nmcli -t -f STATE general 2>/dev/null || echo "unbekannt")
    OK "NetworkManager: ${NM_STATUS}"
    WLAN_COUNT=$(nmcli -t -f NAME,TYPE connection show 2>/dev/null | grep -c "wireless" || echo 0)
    [[ "${WLAN_COUNT}" -gt 0 ]] && OK "${WLAN_COUNT} WLAN-Verbindung(en)" || INFO "Keine WLAN-Verbindungen"
    [[ $EUID -eq 0 ]] && OK "nmcli --show-secrets: Root-Rechte OK" || INFO "Root-Rechte für WLAN-Passwörter nötig"
else
    FAIL "nmcli fehlt – WLAN-Passwörter-Tab inaktiv"
fi

# ══════════════════════════════════════════════════════════════════════════════
HEAD "11  KONFIGURATION & LOGS"
# ══════════════════════════════════════════════════════════════════════════════

ORIG_USER="${SUDO_USER:-${USER}}"
ORIG_HOME=$(eval echo "~${ORIG_USER}")
CONFIG_DIR="${ORIG_HOME}/.config/peessi-multitool"
CONFIG_FILE="${CONFIG_DIR}/settings.json"
ERROR_LOG="${ORIG_HOME}/peessi_multitool_fehler.log"

[[ -d "${CONFIG_DIR}" ]] && OK "Konfig-Ordner: ${CONFIG_DIR}" \
    || INFO "Konfig-Ordner noch nicht vorhanden (beim ersten Start erstellt)"

if [[ -f "${CONFIG_FILE}" ]]; then
    ${PY} -c "import json; json.load(open('${CONFIG_FILE}'))" 2>/dev/null \
        && OK "settings.json gültig" || FAIL "settings.json ungültiges JSON"
else
    INFO "settings.json nicht vorhanden (normal beim ersten Start)"
fi

if [[ -f "${ERROR_LOG}" ]]; then
    ERR_LINES=$(wc -l < "${ERROR_LOG}")
    [[ ${ERR_LINES} -gt 0 ]] \
        && WARN "Fehler-Log: ${ERROR_LOG} (${ERR_LINES} Zeilen)" \
        || OK "Fehler-Log leer"
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
    print(f"  ✅  VERSION = '{config.VERSION}'")
    print(f"  ✅  ORIGINAL_USER = '{config.ORIGINAL_USER}'")
    s = config.load_settings()
    print(f"  ✅  load_settings() OK (Theme: {s.get('theme','?')})")
except Exception as e:
    print(f"  ❌  config: {e}"); errors += 1

try:
    from security import SecurityManager
    SecurityManager()
    print(f"  ✅  SecurityManager() OK")
except Exception as e:
    print(f"  ❌  SecurityManager: {e}"); errors += 1

try:
    from models import DriveInfo
    di = DriveInfo("/dev/sda","Test",256060514304,"ext4","/",False,False)
    assert di.get_size_human() != ""
    di2 = DriveInfo("/dev/sdb","Test","238.5G","","",True,True)
    s = di2.get_size_human()
    print(f"  ✅  DriveInfo OK  (238.5G → '{s}')")
except Exception as e:
    print(f"  ❌  DriveInfo: {e}"); errors += 1

try:
    from database import SmartDatabase
    SmartDatabase()
    print(f"  ✅  SmartDatabase() OK")
except Exception as e:
    print(f"  ❌  SmartDatabase: {e}"); errors += 1

try:
    from wipe_engine import WipeEngine
    print(f"  ✅  WipeEngine.METHODS: {list(WipeEngine.METHODS.keys())}")
except Exception as e:
    print(f"  ❌  WipeEngine: {e}"); errors += 1

sys.exit(errors)
PYRUN

# ══════════════════════════════════════════════════════════════════════════════
HEAD "13  X11-SICHERHEIT (bind_all-Check)"
# ══════════════════════════════════════════════════════════════════════════════

for fn in gui_drives.py gui_system.py gui_base.py; do
    fp="${INSTALL_DIR}/${fn}"
    [[ ! -f "${fp}" ]] && continue
    BINDALL=$(grep -c "bind_all\|unbind_all" "${fp}" 2>/dev/null || echo 0)
    if [[ ${BINDALL} -gt 0 ]]; then
        WARN "${fn}: ${BINDALL}× bind_all/unbind_all – kann X11 destabilisieren!"
    else
        OK "${fn}: kein bind_all (sicher)"
    fi
done

# ══════════════════════════════════════════════════════════════════════════════
HEAD "ZUSAMMENFASSUNG"
# ══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "  ${BOLD}Ergebnis:  ${GREEN}${PASSED} OK${RESET}  ${RED}${ERRORS} Fehler${RESET}  ${YELLOW}${WARNINGS} Warnungen${RESET}"
echo ""

_log_raw ""; _log_raw "=============================================================="
_log_raw "  ZUSAMMENFASSUNG: ${PASSED} OK / ${ERRORS} Fehler / ${WARNINGS} Warnungen"
_log_raw "=============================================================="

if [[ ${ERRORS} -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}✅ Keine kritischen Fehler.${RESET}"
    _log_raw "  STATUS: OK"
else
    echo -e "  ${RED}${BOLD}❌ ${ERRORS} kritische Fehler:${RESET}"
    _log_raw "  STATUS: FEHLER"
    for err in "${ERROR_LIST[@]}"; do
        echo -e "    ${RED}•  ${err}${RESET}"; _log_raw "  • ${err}"
    done
fi

if [[ ${WARNINGS} -gt 0 ]]; then
    echo ""; echo -e "  ${YELLOW}${BOLD}⚠️  ${WARNINGS} Warnungen:${RESET}"
    _log_raw ""; _log_raw "  Warnungen:"
    for warn in "${WARN_LIST[@]}"; do
        echo -e "    ${YELLOW}•  ${warn}${RESET}"; _log_raw "  • ${warn}"
    done
fi

echo ""
echo -e "  ${BOLD}Reparatur:${RESET} sudo bash update.sh (aus dem Projektordner)"

# Kurzfassung
{
echo "Peeßi's System Multitool v4.1 – Analyse-Kurzfassung"
echo "$(date '+%d.%m.%Y %H:%M:%S')  |  $(hostname)  |  $(whoami)"
echo "================================================================"
echo ""
echo "ERGEBNIS: ${PASSED} OK / ${ERRORS} Fehler / ${WARNINGS} Warnungen"
echo ""
[[ ${ERRORS} -gt 0 ]] && { echo "KRITISCHE FEHLER:"; for e in "${ERROR_LIST[@]}"; do echo "  • $e"; done; echo ""; }
[[ ${WARNINGS} -gt 0 ]] && { echo "WARNUNGEN:"; for w in "${WARN_LIST[@]}"; do echo "  • $w"; done; echo ""; }
echo "INSTALLIERTE DATEIEN:"
for fn in main.py gui_drives.py gui_system.py config.py; do
    fp="${INSTALL_DIR}/${fn}"
    [[ -f "$fp" ]] && echo "  ${fn}: $(wc -l < "$fp") Zeilen, MD5=$(md5sum "$fp" | cut -c1-12)" \
                   || echo "  ${fn}: FEHLT"
done
echo ""
echo "SYSTEM:"
echo "  Python: $(python3 --version 2>&1)"
echo "  OS:     $(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME}" || uname -r)"
echo ""
echo "LOGS:"
echo "  Vollständig : ${LOG_FILE}"
echo "  Kurzfassung : ${SHORT_FILE}"
} > "${SHORT_FILE}"

chown "${LOG_USER}:${LOG_USER}" "${LOG_FILE}" "${SHORT_FILE}" 2>/dev/null || true

echo ""
echo -e "  ${BOLD}📄 Logs:${RESET}"
echo -e "  ${LOG_FILE}"
echo -e "  ${SHORT_FILE}"
echo ""
