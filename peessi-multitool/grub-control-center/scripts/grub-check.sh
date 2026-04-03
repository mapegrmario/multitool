#!/bin/bash
# ============================================
# GRUB Control Center - System Analyse v2.1
# ============================================

set -uo pipefail

# Ermittle Skript-Verzeichnis (folge Symlinks)
SCRIPT_PATH="${BASH_SOURCE[0]}"
# Folge Symlink falls vorhanden
if [ -L "$SCRIPT_PATH" ]; then
    SCRIPT_PATH="$(readlink -f "$SCRIPT_PATH")"
fi
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
LIB_DIR="${SCRIPT_DIR}/../lib"

# Lade Bibliotheken
for lib in config logging validation; do
    lib_file="$LIB_DIR/${lib}.sh"
    if [ -f "$lib_file" ]; then
        # shellcheck source=/dev/null
        source "$lib_file"
    else
        echo "FEHLER: Bibliothek nicht gefunden: $lib_file" >&2
        exit 1
    fi
done

# Root-Rechte prüfen
check_root

# Initialisiere Logging
init_logging

print_header "$PROGRAM_NAME - System-Analyse v$VERSION"

# ============================================
# Prüffunktionen
# ============================================

check_file() {
    local file="$1"
    local description="${2:-Datei}"
    
    if [ -f "$file" ]; then
        log "OK: $description -> $file"
        print_ok "$description vorhanden: $file"
        return 0
    else
        error "FEHLT: $description -> $file"
        print_error "$description fehlt: $file"
        return 1
    fi
}

check_dir() {
    local dir="$1"
    local description="${2:-Verzeichnis}"
    
    if [ -d "$dir" ]; then
        log "OK: $description -> $dir"
        print_ok "$description vorhanden: $dir"
        return 0
    else
        error "FEHLT: $description -> $dir"
        print_error "$description fehlt: $dir"
        return 1
    fi
}

check_cmd() {
    local cmd="$1"
    
    if command -v "$cmd" &>/dev/null; then
        local version=""
        case "$cmd" in
            grub-install)
                version=$(grub-install --version 2>/dev/null | head -1)
                ;;
            git)
                version=$(git --version 2>/dev/null)
                ;;
        esac
        
        log "OK: Tool installiert -> $cmd ${version:+($version)}"
        print_ok "Tool installiert: $cmd ${version:+($version)}"
        return 0
    else
        error "FEHLT: Tool -> $cmd"
        print_error "Tool fehlt: $cmd"
        return 1
    fi
}

check_permissions() {
    local file="$1"
    local expected_owner="${2:-root:root}"
    local expected_perms="${3:-644}"
    
    if [ ! -f "$file" ]; then
        return 1
    fi
    
    local owner
    owner=$(stat -c "%U:%G" "$file" 2>/dev/null)
    local perms
    perms=$(stat -c "%a" "$file" 2>/dev/null)
    
    if [ "$owner" = "$expected_owner" ]; then
        log "OK: Korrekter Besitzer -> $file ($owner)"
        print_ok "Korrekter Besitzer: $file ($owner)"
    else
        warn "Abweichender Besitzer -> $file ($owner, erwartet: $expected_owner)"
        print_warning "Abweichender Besitzer: $file"
    fi
    
    if [ "$perms" = "$expected_perms" ]; then
        log "OK: Korrekte Berechtigungen -> $file ($perms)"
        print_ok "Korrekte Berechtigungen: $file ($perms)"
    else
        warn "Abweichende Berechtigungen -> $file ($perms, erwartet: $expected_perms)"
        print_warning "Abweichende Berechtigungen: $file ($perms)"
    fi
}

# ============================================
# System-Informationen
# ============================================

print_header "SYSTEM-INFORMATIONEN"

print_info "Benutzer: $CURRENT_USER"
print_info "Kernel: $(uname -r)"
print_info "Architektur: $(uname -m)"
print_info "Hostname: $(hostname)"

log "User: $CURRENT_USER (sudo: ${SUDO_USER:-none})"
log "EUID: $EUID"
log "Kernel: $(uname -r)"
log "System: $(uname -a)"
log "Hostname: $(hostname)"
log "Architektur: $(uname -m)"

# Boot-Modus
if [ -d "/sys/firmware/efi" ]; then
    print_info "Boot-Modus: UEFI"
    log "Boot-Modus: UEFI"
    
    if [ -d "/boot/efi" ]; then
        efi_size=$(df -h /boot/efi 2>/dev/null | tail -1 | awk '{print $2}')
        print_info "EFI-Partition: $efi_size"
        log "EFI-Partition Größe: $efi_size"
    fi
else
    print_info "Boot-Modus: BIOS/Legacy"
    log "Boot-Modus: BIOS/Legacy"
fi

# ============================================
# GRUB-Dateien
# ============================================

print_header "GRUB-DATEIEN"

check_file "$GRUB_FILE" "GRUB-Konfiguration"
if [ -f /boot/grub/grub.cfg ]; then
    check_file /boot/grub/grub.cfg "GRUB-Menü"
elif [ -f /boot/grub2/grub.cfg ]; then
    check_file /boot/grub2/grub.cfg "GRUB-Menü"
fi

check_permissions "$GRUB_FILE" "root:root" "644"

# Zeige GRUB-Konfiguration
if [ -f "$GRUB_FILE" ]; then
    timeout=$(grep "^GRUB_TIMEOUT=" "$GRUB_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"')
    default=$(grep "^GRUB_DEFAULT=" "$GRUB_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"')
    
    print_info "GRUB_TIMEOUT: ${timeout:-nicht gesetzt}"
    print_info "GRUB_DEFAULT: ${default:-nicht gesetzt}"
    
    log "GRUB_TIMEOUT: ${timeout:-nicht gesetzt}"
    log "GRUB_DEFAULT: ${default:-nicht gesetzt}"
fi

# ============================================
# GRUB-Tools
# ============================================

print_header "GRUB-TOOLS"

check_cmd update-grub || check_cmd grub-mkconfig || check_cmd grub2-mkconfig
check_cmd grub-install
check_cmd grub-probe

# ============================================
# Themes & Grafik
# ============================================

print_header "THEMES & GRAFIK"

check_dir "$THEME_DIR" "Theme-Verzeichnis"

if grep -q "^GRUB_BACKGROUND" "$GRUB_FILE" 2>/dev/null; then
    bg=$(grep "^GRUB_BACKGROUND" "$GRUB_FILE" | cut -d'"' -f2)
    print_info "Hintergrund konfiguriert: $bg"
    
    if [ -f "$bg" ]; then
        bg_size=$(du -h "$bg" 2>/dev/null | cut -f1)
        print_ok "Hintergrund-Datei vorhanden ($bg_size)"
    else
        print_error "Hintergrund-Datei nicht gefunden"
    fi
else
    print_info "Kein Hintergrund konfiguriert"
fi

if grep -q "^GRUB_THEME" "$GRUB_FILE" 2>/dev/null; then
    theme=$(grep "^GRUB_THEME" "$GRUB_FILE" | cut -d'"' -f2)
    print_info "Theme konfiguriert: $theme"
    
    if [ -f "$theme" ]; then
        print_ok "Theme-Datei vorhanden"
    else
        print_error "Theme-Datei nicht gefunden"
    fi
else
    print_info "Kein Theme konfiguriert"
fi

# Verfügbare Themes
if [ -d "$THEME_DIR" ] && [ -n "$(ls -A "$THEME_DIR" 2>/dev/null)" ]; then
    print_info "Verfügbare Themes:"
    for theme_dir in "$THEME_DIR"/*/; do
        if [ -f "$theme_dir/theme.txt" ]; then
            theme_name=$(basename "$theme_dir")
            print_info "  • $theme_name"
            log "  - $theme_name"
        fi
    done
fi

# ============================================
# Tools & Abhängigkeiten
# ============================================

print_header "TOOLS & ABHÄNGIGKEITEN"

check_cmd zenity
check_cmd git
check_cmd os-prober
check_cmd timeshift || print_warning "Timeshift nicht installiert (optional)"
check_cmd lsblk
check_cmd blkid

# ============================================
# Recovery-Komponenten
# ============================================

print_header "RECOVERY-KOMPONENTEN"

check_file "$CUSTOM_DIR/recovery.sh" "Recovery-Script"
if [ -f "$CUSTOM_DIR/recovery.sh" ]; then
    if [ -x "$CUSTOM_DIR/recovery.sh" ]; then
        print_ok "Recovery-Script ist ausführbar"
    else
        print_error "Recovery-Script nicht ausführbar"
    fi
fi

check_file /etc/grub.d/41_recovery "GRUB-Recovery-Menü"
if [ -f /etc/grub.d/41_recovery ]; then
    if [ -x /etc/grub.d/41_recovery ]; then
        print_ok "GRUB-Recovery-Menü ist aktiv"
        
        # Prüfe UUID
        if grep -q "ROOT_UUID_PLACEHOLDER" /etc/grub.d/41_recovery 2>/dev/null; then
            print_error "UUID nicht ersetzt! Recovery wird nicht funktionieren!"
            error "KRITISCH: UUID-Platzhalter nicht ersetzt"
        fi
    else
        print_error "GRUB-Recovery-Menü nicht ausführbar"
    fi
fi

# ============================================
# GRUB-Menüeinträge
# ============================================

print_header "GRUB-MENÜEINTRÄGE"

grub_cfg=""
if [ -f /boot/grub/grub.cfg ]; then
    grub_cfg="/boot/grub/grub.cfg"
elif [ -f /boot/grub2/grub.cfg ]; then
    grub_cfg="/boot/grub2/grub.cfg"
fi

if [ -n "$grub_cfg" ] && [ -f "$grub_cfg" ]; then
    count=$(grep -c "^menuentry" "$grub_cfg" 2>/dev/null || echo "0")
    print_info "Boot-Einträge insgesamt: $count"
    
    if [ "$count" -gt 0 ]; then
        print_info "Menüeinträge (erste 10):"
        grep "^menuentry" "$grub_cfg" | head -10 | sed 's/^menuentry "//;s/".*$//' | while read -r entry; do
            print_info "  • $entry"
            log "  - $entry"
        done
    fi
fi

# ============================================
# Festplatten & Partitionen
# ============================================

print_header "FESTPLATTEN & PARTITIONEN"

print_info "Festplatten:"
lsblk -d -o NAME,SIZE,MODEL 2>/dev/null | tail -n +2 | while read -r line; do
    print_info "  $line"
    log "  Disk: $line"
done

echo ""
print_info "Root-Partition:"
root_dev=$(findmnt -n -o SOURCE / 2>/dev/null)
root_uuid=$(blkid -s UUID -o value "$root_dev" 2>/dev/null)
print_info "  Device: $root_dev"
print_info "  UUID: $root_uuid"
log "Root-Partition: $root_dev (UUID: $root_uuid)"

# ============================================
# Speicherplatz
# ============================================

print_header "SPEICHERPLATZ"

print_info "/boot:"
df -h /boot 2>/dev/null | tail -1 | while read -r line; do
    print_info "  $line"
    log "  /boot: $line"
done

print_info "Root (/):"
df -h / 2>/dev/null | tail -1 | while read -r line; do
    print_info "  $line"
    log "  /: $line"
done

# ============================================
# Backups
# ============================================

print_header "GRUB-BACKUPS"

backup_count=$(find "$(dirname "$GRUB_FILE")" -name "$(basename "$GRUB_FILE").bak.*" 2>/dev/null | wc -l)

if [ "$backup_count" -gt 0 ]; then
    print_info "Gefundene Backups: $backup_count"
    log "Backup-Anzahl: $backup_count"
else
    print_warning "Keine Backups gefunden"
fi

# ============================================
# Fehlerzusammenfassung
# ============================================

print_header "ZUSAMMENFASSUNG"

error_count=0
if [ -f "$USER_ERR" ]; then
    error_count=$(grep -c "^\[ERROR\]" "$USER_ERR" 2>/dev/null || echo "0")
fi

if [ "$error_count" -gt 0 ]; then
    print_error "Es wurden $error_count Fehler gefunden!"
    echo ""
    print_warning "Fehlerdetails:"
    grep "^\[ERROR\]" "$USER_ERR" 2>/dev/null | while read -r line; do
        echo "  $line"
    done
    echo ""
    print_warning "Führe 'sudo grub-control-center' aus, um Probleme zu beheben."
else
    print_ok "Keine Fehler gefunden - System ist in Ordnung!"
fi

echo ""
print_header "ANALYSE ABGESCHLOSSEN"
echo ""
echo "Log-Dateien:"
echo "  • Benutzer-Log: $USER_LOG"
echo "  • Fehler-Log:   $USER_ERR"
echo "  • System-Log:   $SYSTEM_LOG"
echo ""

log "Analyse abgeschlossen: $(date)"
