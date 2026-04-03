#!/bin/bash
# ============================================
# GRUB Control Center - Backup & Rollback
# ============================================

# Sichere Backup-Funktion (KORRIGIERT - mit PID und Nanosekunden)
backup_grub() {
    if [ ! -f "$GRUB_FILE" ]; then
        error "GRUB-Konfiguration nicht gefunden: $GRUB_FILE"
        return 1
    fi
    
    # Sichere Backup-Datei: Timestamp + PID + Random
    local timestamp
    timestamp=$(date +%s%N 2>/dev/null) || timestamp=$(date +%s)
    local pid=$$
    local random
    random=$(cat /dev/urandom 2>/dev/null | tr -dc 'a-f0-9' | head -c 8)
    
    LAST_BACKUP="${GRUB_FILE}.bak.${timestamp}.${pid}.${random}"
    
    if ! cp -p "$GRUB_FILE" "$LAST_BACKUP"; then
        error "Konnte Backup nicht erstellen"
        LAST_BACKUP=""
        return 1
    fi
    
    log "Backup erstellt: $LAST_BACKUP"
    
    # Bereinige alte Backups (behalte nur letzte MAX_BACKUPS)
    cleanup_old_backups
    
    return 0
}

# Bereinige alte Backups
cleanup_old_backups() {
    local backup_count
    backup_count=$(find "$(dirname "$GRUB_FILE")" -name "$(basename "$GRUB_FILE").bak.*" 2>/dev/null | wc -l)
    
    if [ "$backup_count" -gt "$MAX_BACKUPS" ]; then
        debug "Bereinige alte Backups (behalte letzte $MAX_BACKUPS)"
        
        # Lösche die ältesten Backups
        find "$(dirname "$GRUB_FILE")" -name "$(basename "$GRUB_FILE").bak.*" -type f -printf '%T@ %p\n' 2>/dev/null | \
            sort -n | \
            head -n -"$MAX_BACKUPS" | \
            cut -d' ' -f2- | \
            xargs -r rm -f
            
        log "Alte Backups bereinigt"
    fi
}

# Stelle letztes Backup wieder her
restore_last_backup() {
    if [ -z "$LAST_BACKUP" ] || [ ! -f "$LAST_BACKUP" ]; then
        error "Kein Backup verfügbar zum Wiederherstellen"
        return 1
    fi
    
    log "Stelle Backup wieder her: $LAST_BACKUP"
    
    if ! cp "$LAST_BACKUP" "$GRUB_FILE"; then
        error "KRITISCH: Konnte Backup nicht wiederherstellen!"
        return 1
    fi
    
    log "Backup erfolgreich wiederhergestellt"
    return 0
}

# Liste verfügbare Backups
list_backups() {
    local backups
    backups=$(find "$(dirname "$GRUB_FILE")" -name "$(basename "$GRUB_FILE").bak.*" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2-)
    
    if [ -z "$backups" ]; then
        print_info "Keine Backups gefunden"
        return 1
    fi
    
    print_info "Verfügbare Backups:"
    echo "$backups" | while read -r backup; do
        local timestamp
        timestamp=$(stat -c %y "$backup" 2>/dev/null | cut -d'.' -f1)
        local size
        size=$(du -h "$backup" 2>/dev/null | cut -f1)
        echo "  - $(basename "$backup") [$timestamp, $size]"
    done
    
    return 0
}

# Stelle spezifisches Backup wieder her
restore_specific_backup() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        error "Backup-Datei nicht gefunden: $backup_file"
        return 1
    fi
    
    log "Stelle Backup wieder her: $backup_file"
    
    # Erstelle Backup der aktuellen Konfiguration vor dem Restore
    if ! backup_grub; then
        warn "Konnte kein Backup der aktuellen Konfiguration erstellen"
    fi
    
    if ! cp "$backup_file" "$GRUB_FILE"; then
        error "Konnte Backup nicht wiederherstellen"
        return 1
    fi
    
    log "Backup erfolgreich wiederhergestellt: $backup_file"
    return 0
}

# Exportiere Funktionen
export -f backup_grub cleanup_old_backups restore_last_backup
export -f list_backups restore_specific_backup
