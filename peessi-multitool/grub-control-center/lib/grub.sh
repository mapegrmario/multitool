#!/bin/bash
# ============================================
# GRUB Control Center - GRUB Operations
# ============================================

# Distributionsunabhängiges GRUB-Update (KORRIGIERT)
update_grub_system() {
    log "Führe GRUB-Update durch..."
    
    local grub_cfg
    local update_cmd
    
    # Erkenne GRUB-Konfigurationsdatei
    if [ -f /boot/grub/grub.cfg ]; then
        grub_cfg="/boot/grub/grub.cfg"
    elif [ -f /boot/grub2/grub.cfg ]; then
        grub_cfg="/boot/grub2/grub.cfg"
    else
        error "GRUB-Konfigurationsdatei nicht gefunden"
        return 1
    fi
    
    # Erkenne Update-Befehl
    if command -v update-grub &>/dev/null; then
        update_cmd="update-grub"
    elif command -v grub-mkconfig &>/dev/null; then
        update_cmd="grub-mkconfig -o $grub_cfg"
    elif command -v grub2-mkconfig &>/dev/null; then
        update_cmd="grub2-mkconfig -o $grub_cfg"
    else
        error "Kein GRUB-Update-Kommando gefunden"
        return 1
    fi
    
    log "Verwende: $update_cmd"
    
    # Führe Update durch
    if eval "$update_cmd" 2>&1 | tee -a "$USER_LOG"; then
        log "GRUB erfolgreich aktualisiert"
        return 0
    else
        error "GRUB-Update fehlgeschlagen"
        return 1
    fi
}

# GRUB-Update mit Rollback (NEU)
update_grub_with_rollback() {
    # Erstelle Backup vor der Änderung
    if ! backup_grub; then
        error "Konnte kein Backup erstellen, Abbruch!"
        return 1
    fi
    
    # Versuche GRUB zu aktualisieren
    if update_grub_system; then
        log "GRUB-Update mit Rollback erfolgreich"
        return 0
    else
        # Rollback bei Fehler
        error "GRUB-Update fehlgeschlagen, stelle Backup wieder her..."
        if restore_last_backup; then
            warn "Backup wiederhergestellt, ursprüngliche Konfiguration aktiv"
        else
            error "KRITISCH: Konnte Backup nicht wiederherstellen!"
        fi
        return 1
    fi
}

# Sichere GRUB-Konfigurations-Änderung (NEU)
set_grub_config() {
    local key="$1"
    local value="$2"
    
    # Validiere Eingabe
    if [ -z "$key" ]; then
        error "Kein Konfigurations-Key angegeben"
        return 1
    fi
    
    log "Setze GRUB-Konfiguration: ${key}=\"${value}\""
    
    # Erstelle Backup
    if ! backup_grub; then
        return 1
    fi
    
    # Entferne alle existierenden Einträge
    if ! sed -i "/^${key}=/d" "$GRUB_FILE"; then
        error "Fehler beim Bearbeiten von $GRUB_FILE"
        restore_last_backup
        return 1
    fi
    
    # Füge neuen Eintrag hinzu
    if ! echo "${key}=\"${value}\"" >> "$GRUB_FILE"; then
        error "Fehler beim Schreiben in $GRUB_FILE"
        restore_last_backup
        return 1
    fi
    
    log "GRUB-Konfiguration aktualisiert: ${key}=\"${value}\""
    return 0
}

# Hole aktuelle GRUB-Konfiguration
get_grub_config() {
    local key="$1"
    
    if [ ! -f "$GRUB_FILE" ]; then
        return 1
    fi
    
    grep "^${key}=" "$GRUB_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"'
}

# Setze GRUB-Timeout
set_grub_timeout() {
    local timeout="$1"
    
    if ! validate_timeout "$timeout"; then
        return 1
    fi
    
    if set_grub_config "GRUB_TIMEOUT" "$timeout"; then
        log "GRUB-Timeout gesetzt: $timeout Sekunden"
        return 0
    fi
    
    return 1
}

# Setze GRUB-Default
set_grub_default() {
    local default="$1"
    
    if [ -z "$default" ]; then
        error "Kein Default-Wert angegeben"
        return 1
    fi
    
    if set_grub_config "GRUB_DEFAULT" "$default"; then
        log "GRUB-Default gesetzt: $default"
        return 0
    fi
    
    return 1
}

# Setze GRUB-Hintergrund
set_grub_background() {
    local image_file="$1"
    local bg_path="/boot/grub/bg.png"
    
    if ! validate_image "$image_file"; then
        return 1
    fi
    
    log "Setze GRUB-Hintergrund: $image_file"
    
    # Konvertiere Bild wenn nötig
    local mime
    mime=$(file -b --mime-type "$image_file")
    
    case "$mime" in
        image/png)
            if ! cp "$image_file" "$bg_path"; then
                error "Konnte Bild nicht kopieren"
                return 1
            fi
            ;;
        image/jpeg|image/jpg)
            if ! command -v convert &>/dev/null; then
                error "ImageMagick nicht installiert, kann JPEG nicht konvertieren"
                return 1
            fi
            if ! convert "$image_file" "$bg_path"; then
                error "Konnte Bild nicht konvertieren"
                return 1
            fi
            ;;
    esac
    
    # Setze in GRUB-Konfiguration
    if set_grub_config "GRUB_BACKGROUND" "$bg_path"; then
        log "GRUB-Hintergrund erfolgreich gesetzt"
        return 0
    fi
    
    return 1
}

# Setze GRUB-Theme
set_grub_theme() {
    local theme_path="$1"
    
    if [ ! -f "$theme_path" ]; then
        error "Theme-Datei nicht gefunden: $theme_path"
        return 1
    fi
    
    if set_grub_config "GRUB_THEME" "$theme_path"; then
        log "GRUB-Theme gesetzt: $theme_path"
        return 0
    fi
    
    return 1
}

# Hole verfügbare Boot-Einträge
get_boot_entries() {
    local grub_cfg
    
    if [ -f /boot/grub/grub.cfg ]; then
        grub_cfg="/boot/grub/grub.cfg"
    elif [ -f /boot/grub2/grub.cfg ]; then
        grub_cfg="/boot/grub2/grub.cfg"
    else
        return 1
    fi
    
    grep "^menuentry" "$grub_cfg" 2>/dev/null | sed 's/^menuentry "//;s/".*$//'
}

# Zähle Boot-Einträge
count_boot_entries() {
    get_boot_entries | wc -l
}

# Exportiere Funktionen
export -f update_grub_system update_grub_with_rollback
export -f set_grub_config get_grub_config
export -f set_grub_timeout set_grub_default
export -f set_grub_background set_grub_theme
export -f get_boot_entries count_boot_entries
