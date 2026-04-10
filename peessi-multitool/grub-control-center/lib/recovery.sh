#!/bin/bash
# ============================================
# GRUB Control Center - Recovery Setup
# ============================================

# Erstelle GRUB-Menüeintrag (KORRIGIERT - mit UUID-Erkennung)
create_grub_menu() {
    log "Erstelle GRUB Recovery Menü..."
    
    # Automatische Erkennung der Root-Partition
    local root_device
    root_device=$(findmnt -n -o SOURCE / 2>/dev/null) || {
        error "Konnte Root-Partition nicht ermitteln"
        return 1
    }
    
    local root_uuid
    root_uuid=$(blkid -s UUID -o value "$root_device" 2>/dev/null) || {
        error "Konnte UUID der Root-Partition nicht ermitteln"
        return 1
    }
    
    log "Root-Partition: $root_device (UUID: $root_uuid)"
    
    # Backup des alten Menüs
    if [ -f /etc/grub.d/41_recovery ]; then
        local backup_menu="/etc/grub.d/41_recovery.bak.$(date +%s)"
        mv /etc/grub.d/41_recovery "$backup_menu"
        log "Altes Recovery-Menü gesichert: $backup_menu"
    fi
    
    # Erstelle neues Recovery-Menü
    cat > /etc/grub.d/41_recovery << 'MENU_EOF'
#!/bin/sh
exec tail -n +3 $0
# Dieses Menü wurde vom GRUB Control Center v2.1 erstellt

menuentry "🛠 GRUB Recovery System (Notfall)" --class recovery {
    search --set=root --fs-uuid ROOT_UUID_PLACEHOLDER
    echo "Starte Recovery-Modus..."
    linux /boot/vmlinuz root=UUID=ROOT_UUID_PLACEHOLDER ro recovery nomodeset
    initrd /boot/initrd.img
}

menuentry "🛠 GRUB Notfall-Shell (Fortgeschritten)" --class recovery {
    search --set=root --fs-uuid ROOT_UUID_PLACEHOLDER
    echo "Starte Notfall-Shell..."
    linux /boot/vmlinuz root=UUID=ROOT_UUID_PLACEHOLDER rw init=/bin/bash
    initrd /boot/initrd.img
}

menuentry "🛠 GRUB Single User Mode" --class recovery {
    search --set=root --fs-uuid ROOT_UUID_PLACEHOLDER
    echo "Starte Single User Mode..."
    linux /boot/vmlinuz root=UUID=ROOT_UUID_PLACEHOLDER ro single
    initrd /boot/initrd.img
}
MENU_EOF
    
    # Ersetze Platzhalter mit echter UUID
    if ! sed -i "s/ROOT_UUID_PLACEHOLDER/$root_uuid/g" /etc/grub.d/41_recovery; then
        error "Fehler beim Ersetzen der UUID"
        return 1
    fi
    
    # Setze Ausführungsrechte
    if ! chmod +x /etc/grub.d/41_recovery; then
        error "Konnte Ausführungsrechte nicht setzen"
        return 1
    fi
    
    log "GRUB Recovery Menü erstellt mit UUID: $root_uuid"
    return 0
}

# Installiere Recovery-Script
install_recovery_script() {
    log "Installiere Recovery-Script..."
    
    # Erstelle Custom-Verzeichnis
    mkdir -p "$CUSTOM_DIR" || {
        error "Konnte Custom-Verzeichnis nicht erstellen"
        return 1
    }
    
    # Kopiere Recovery-Script
    local recovery_source="$INSTALL_DIR/scripts/recovery.sh"
    local recovery_target="$CUSTOM_DIR/recovery.sh"
    
    if [ ! -f "$recovery_source" ]; then
        error "Recovery-Script-Quelle nicht gefunden: $recovery_source"
        return 1
    fi
    
    if ! cp "$recovery_source" "$recovery_target"; then
        error "Konnte Recovery-Script nicht kopieren"
        return 1
    fi
    
    if ! chmod +x "$recovery_target"; then
        error "Konnte Ausführungsrechte nicht setzen"
        return 1
    fi
    
    log "Recovery-Script installiert: $recovery_target"
    return 0
}

# Setup komplettes Recovery-System
setup_recovery_system() {
    print_header "Installiere Recovery-System"
    
    # Installiere Recovery-Script
    if ! install_recovery_script; then
        return 1
    fi
    print_ok "Recovery-Script installiert"
    
    # Erstelle GRUB-Menüeintrag
    if ! create_grub_menu; then
        return 1
    fi
    print_ok "GRUB-Menü erstellt"
    
    log "Recovery-System erfolgreich eingerichtet"
    return 0
}

# Exportiere Funktionen
export -f create_grub_menu install_recovery_script setup_recovery_system
