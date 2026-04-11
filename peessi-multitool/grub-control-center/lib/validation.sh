#!/bin/bash
# ============================================
# GRUB Control Center - Validation
# ============================================

# Root-Rechte prüfen
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Dieses Programm benötigt Root-Rechte!"
        echo "Bitte mit sudo ausführen: sudo $0"
        exit 1
    fi
}

# Prüfe ob zenity verfügbar ist
check_zenity() {
    if ! command -v zenity &>/dev/null; then
        error "zenity ist nicht installiert"
        return 1
    fi
    return 0
}

# GitHub URL validieren (KORRIGIERT)
validate_github_url() {
    local url="$1"
    
    if [ -z "$url" ]; then
        return 1
    fi
    
    # Erlaubt: https://github.com/user/repo oder https://github.com/user/repo.git
    if [[ "$url" =~ ^https://github\.com/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+(\.git)?/?$ ]]; then
        return 0
    fi
    
    return 1
}

# Bild validieren
validate_image() {
    local file="$1"
    
    # Prüfe Existenz
    if [ ! -f "$file" ]; then
        error "Datei nicht gefunden: $file"
        return 1
    fi
    
    # Prüfe Dateigröße
    local size
    size=$(stat -c%s "$file" 2>/dev/null) || {
        error "Konnte Dateigröße nicht ermitteln"
        return 1
    }
    
    if [ "$size" -gt "$MAX_IMAGE_SIZE" ]; then
        error "Bild zu groß (max 5MB): $((size / 1024 / 1024)) MB"
        return 1
    fi
    
    # Prüfe Bildformat
    local mime
    mime=$(file -b --mime-type "$file" 2>/dev/null) || {
        error "Konnte Dateityp nicht ermitteln"
        return 1
    }
    
    case "$mime" in
        image/png|image/jpeg|image/jpg)
            debug "Gültiges Bildformat: $mime"
            return 0
            ;;
        *)
            error "Ungültiges Bildformat: $mime (nur PNG/JPEG)"
            return 1
            ;;
    esac
}

# Timeout-Wert validieren
validate_timeout() {
    local timeout="$1"
    
    if [[ ! "$timeout" =~ ^[0-9]+$ ]]; then
        error "Ungültiger Timeout-Wert: $timeout (nur Zahlen)"
        return 1
    fi
    
    if [ "$timeout" -lt 0 ] || [ "$timeout" -gt 120 ]; then
        error "Timeout außerhalb des gültigen Bereichs (0-120): $timeout"
        return 1
    fi
    
    return 0
}

# Prüfe ob Block-Device existiert
validate_block_device() {
    local device="$1"
    
    if [ ! -b "$device" ]; then
        error "$device ist kein gültiges Block-Device"
        return 1
    fi
    
    return 0
}

# Sanitize Disk/Partition-Name
sanitize_disk_name() {
    local name="$1"
    # Entferne alles außer alphanumerischen Zeichen
    echo "$name" | tr -cd '[:alnum:]'
}

# Prüfe Schreibrechte
check_write_permission() {
    local path="$1"
    
    if [ ! -w "$path" ]; then
        error "Keine Schreibrechte für: $path"
        return 1
    fi
    
    return 0
}

# Prüfe Datei-Existenz
check_file_exists() {
    local file="$1"
    local description="${2:-Datei}"
    
    if [ ! -f "$file" ]; then
        error "$description nicht gefunden: $file"
        return 1
    fi
    
    return 0
}

# Prüfe Verzeichnis-Existenz
check_dir_exists() {
    local dir="$1"
    local description="${2:-Verzeichnis}"
    
    if [ ! -d "$dir" ]; then
        error "$description nicht gefunden: $dir"
        return 1
    fi
    
    return 0
}

# Tool-Verfügbarkeit prüfen
check_tool() {
    local tool="$1"
    
    if ! command -v "$tool" &>/dev/null; then
        return 1
    fi
    
    return 0
}

# Alle benötigten Tools prüfen
check_required_tools() {
    local missing_tools=()
    local required_tools="update-grub grub-install grub-mkconfig"
    
    for tool in $required_tools; do
        if ! check_tool "$tool"; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        error "Fehlende Tools: ${missing_tools[*]}"
        return 1
    fi
    
    return 0
}

# Exportiere Funktionen
export -f check_root check_zenity validate_github_url validate_image
export -f validate_timeout validate_block_device sanitize_disk_name
export -f check_write_permission check_file_exists check_dir_exists
export -f check_tool check_required_tools
