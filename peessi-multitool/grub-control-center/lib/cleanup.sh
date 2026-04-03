#!/bin/bash
# ============================================
# GRUB Control Center - Cleanup
# ============================================

# Cleanup-Handler einrichten
setup_cleanup_handler() {
    cleanup_handler() {
        local exit_code=$?
        
        debug "Führe Cleanup durch..."
        
        # Räume temporäre Verzeichnisse auf
        for dir in "${TEMP_DIRS[@]}"; do
            if [ -d "$dir" ]; then
                debug "Lösche temporäres Verzeichnis: $dir"
                rm -rf "$dir" 2>/dev/null || warn "Konnte $dir nicht löschen"
            fi
        done
        
        # Räume temporäre Dateien auf
        for file in "${TEMP_FILES[@]}"; do
            if [ -f "$file" ]; then
                debug "Lösche temporäre Datei: $file"
                rm -f "$file" 2>/dev/null || warn "Konnte $file nicht löschen"
            fi
        done
        
        debug "Cleanup abgeschlossen"
        exit $exit_code
    }
    
    trap cleanup_handler EXIT INT TERM
}

# Registriere temporäres Verzeichnis
register_temp_dir() {
    local dir="$1"
    TEMP_DIRS+=("$dir")
    debug "Temporäres Verzeichnis registriert: $dir"
}

# Registriere temporäre Datei
register_temp_file() {
    local file="$1"
    TEMP_FILES+=("$file")
    debug "Temporäre Datei registriert: $file"
}

# Erstelle sicheres temporäres Verzeichnis
create_temp_dir() {
    local prefix="${1:-grub-tmp}"
    local temp_dir
    
    temp_dir=$(mktemp -d "/tmp/${prefix}.XXXXXXXXXX") || {
        error "Konnte temporäres Verzeichnis nicht erstellen"
        return 1
    }
    
    register_temp_dir "$temp_dir"
    echo "$temp_dir"
    return 0
}

# Erstelle sichere temporäre Datei
create_temp_file() {
    local prefix="${1:-grub-tmp}"
    local temp_file
    
    temp_file=$(mktemp "/tmp/${prefix}.XXXXXXXXXX") || {
        error "Konnte temporäre Datei nicht erstellen"
        return 1
    }
    
    register_temp_file "$temp_file"
    echo "$temp_file"
    return 0
}

# Exportiere Funktionen
export -f setup_cleanup_handler register_temp_dir register_temp_file
export -f create_temp_dir create_temp_file
