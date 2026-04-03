#!/bin/bash
# ============================================
# GRUB Control Center - Logging
# ============================================

# Stelle sicher, dass Konfiguration geladen ist
if [ -z "$USER_LOG" ]; then
    echo "FEHLER: config.sh muss zuerst geladen werden!" >&2
    exit 1
fi

# Initialisiere Log-Dateien
init_logging() {
    # Erstelle Log-Verzeichnis
    mkdir -p "$LOG_DIR" 2>/dev/null
    
    # Initialisiere Log-Dateien mit Header
    {
        echo "===================================================="
        echo "  $PROGRAM_NAME v$VERSION - Log"
        echo "===================================================="
        echo "Gestartet: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Benutzer: $CURRENT_USER (EUID: $EUID)"
        echo "Hostname: $(hostname)"
        echo "Kernel: $(uname -r)"
        echo "===================================================="
        echo ""
    } > "$USER_LOG"
    
    echo "=== ERROR LOG ===" > "$USER_ERR"
    
    {
        echo "=== SYSTEM LOG ==="
        echo "Gestartet: $(date)"
        echo ""
    } > "$SYSTEM_LOG" 2>/dev/null || true
}

# Logging-Funktionen mit korrekter Ausgabe
log() {
    local msg="[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"
    
    # Schreibe in Logs
    echo "$msg" >> "$USER_LOG"
    echo "$msg" >> "$SYSTEM_LOG" 2>/dev/null || true
    
    # Ausgabe auf stdout (nur wenn nicht silent mode)
    if [ "${SILENT_MODE:-0}" != "1" ]; then
        echo "$msg"
    fi
}

error() {
    local msg="[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1"
    
    # Schreibe in alle Logs
    echo "$msg" >> "$USER_LOG"
    echo "$msg" >> "$USER_ERR"
    echo "$msg" >> "$SYSTEM_LOG" 2>/dev/null || true
    
    # Ausgabe auf stderr in Rot
    echo -e "${RED}$msg${NC}" >&2
}

warn() {
    local msg="[WARN] $(date '+%Y-%m-%d %H:%M:%S') - $1"
    
    # Schreibe in Logs
    echo "$msg" >> "$USER_LOG"
    echo "$msg" >> "$SYSTEM_LOG" 2>/dev/null || true
    
    # Ausgabe in Gelb
    if [ "${SILENT_MODE:-0}" != "1" ]; then
        echo -e "${YELLOW}$msg${NC}"
    fi
}

debug() {
    if [ "${DEBUG_MODE:-0}" = "1" ]; then
        local msg="[DEBUG] $(date '+%Y-%m-%d %H:%M:%S') - $1"
        echo "$msg" >> "$USER_LOG"
        echo -e "${CYAN}$msg${NC}"
    fi
}

# Formatierte Ausgabe-Funktionen
print_header() {
    local text="$1"
    echo ""
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}$text${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
}

print_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Fortschrittsbalken
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((width * current / total))
    local empty=$((width - filled))
    
    printf "\r["
    printf "%${filled}s" | tr ' ' '='
    printf "%${empty}s" | tr ' ' ' '
    printf "] %3d%%" "$percentage"
    
    if [ "$current" -eq "$total" ]; then
        echo ""
    fi
}

# Exportiere Funktionen
export -f log error warn debug
export -f print_header print_ok print_error print_warning print_info
export -f show_progress
