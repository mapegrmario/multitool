#!/bin/bash
# ============================================
# GRUB Control Center - Theme Management
# ============================================

# Theme-Verzeichnis erstellen
create_theme_dir() {
    if [ ! -d "$THEME_DIR" ]; then
        if mkdir -p "$THEME_DIR"; then
            log "Theme-Verzeichnis erstellt: $THEME_DIR"
            return 0
        else
            error "Konnte Theme-Verzeichnis nicht erstellen"
            return 1
        fi
    else
        debug "Theme-Verzeichnis existiert bereits"
        return 0
    fi
}

# Verfügbare Themes auflisten
list_themes() {
    if [ ! -d "$THEME_DIR" ]; then
        return 1
    fi
    
    local themes
    themes=$(find "$THEME_DIR" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort)
    
    if [ -z "$themes" ]; then
        return 1
    fi
    
    echo "$themes"
    return 0
}

# Prüfe ob Theme gültig ist
validate_theme() {
    local theme_dir="$1"
    
    if [ ! -d "$theme_dir" ]; then
        error "Theme-Verzeichnis nicht gefunden: $theme_dir"
        return 1
    fi
    
    if [ ! -f "$theme_dir/theme.txt" ]; then
        error "theme.txt nicht gefunden in: $theme_dir"
        return 1
    fi
    
    return 0
}

# Theme aktivieren
activate_theme() {
    local theme_name="$1"
    local theme_path="$THEME_DIR/$theme_name/theme.txt"
    
    if ! validate_theme "$THEME_DIR/$theme_name"; then
        return 1
    fi
    
    log "Aktiviere Theme: $theme_name"
    
    if set_grub_theme "$theme_path"; then
        log "Theme erfolgreich aktiviert: $theme_name"
        return 0
    fi
    
    return 1
}

# Theme herunterladen (KORRIGIERT - mit verbesserter URL-Validierung)
download_theme() {
    local url="$1"
    
    # Validiere URL
    if ! validate_github_url "$url"; then
        error "Ungültige GitHub URL: $url"
        return 1
    fi
    
    log "Lade Theme herunter: $url"
    
    # Erstelle sicheres temporäres Verzeichnis
    local tmp_dir
    tmp_dir=$(create_temp_dir "grubtheme") || return 1
    
    # Git-Clone mit Timeout und ohne Passwort-Prompts
    GIT_TERMINAL_PROMPT=0 timeout "$GIT_TIMEOUT" git clone --depth 1 --single-branch "$url" "$tmp_dir" 2>&1 | tee -a "$USER_LOG"
    local clone_result=${PIPESTATUS[0]}
    
    if [ $clone_result -ne 0 ]; then
        error "Download fehlgeschlagen (Exit-Code: $clone_result)"
        return 1
    fi
    
    # Extrahiere Theme-Namen aus URL
    local theme_name
    theme_name=$(basename "$url" .git)
    
    # Suche theme.txt rekursiv (max 3 Ebenen tief)
    local found_theme
    found_theme=$(find "$tmp_dir" -maxdepth 3 -name "theme.txt" -type f | head -1)
    
    if [ -z "$found_theme" ]; then
        error "Kein gültiges GRUB Theme gefunden (theme.txt fehlt)"
        return 1
    fi
    
    local theme_dir_found
    theme_dir_found=$(dirname "$found_theme")
    
    # Prüfe ob Theme bereits existiert
    local target_dir="$THEME_DIR/$theme_name"
    if [ -d "$target_dir" ]; then
        warn "Theme '$theme_name' existiert bereits, überschreibe..."
        rm -rf "$target_dir"
    fi
    
    # Kopiere Theme
    if ! cp -r "$theme_dir_found" "$target_dir"; then
        error "Fehler beim Installieren des Themes"
        return 1
    fi
    
    log "Theme erfolgreich installiert: $theme_name"
    echo "$theme_name"
    return 0
}

# Setze Standard-Hintergrund
set_default_background() {
    local bg_path="/boot/grub/bg.png"
    
    if [ -f "$bg_path" ]; then
        debug "Standard-Hintergrund existiert bereits"
        return 0
    fi
    
    log "Erstelle Standard-Hintergrund..."
    
    # Versuche verschiedene Quellen
    local sources=(
        "/usr/share/pixmaps/debian-logo.png"
        "/usr/share/backgrounds/default.png"
        "/usr/share/pixmaps/fedora-logo.png"
        "/usr/share/backgrounds/images/default.png"
    )
    
    for source in "${sources[@]}"; do
        if [ -f "$source" ]; then
            log "Verwende Hintergrund: $source"
            if cp "$source" "$bg_path"; then
                if set_grub_config "GRUB_BACKGROUND" "$bg_path"; then
                    log "Standard-Hintergrund gesetzt"
                    return 0
                fi
            fi
        fi
    done
    
    # Erstelle minimales schwarzes PNG wenn ImageMagick verfügbar
    if command -v convert &>/dev/null; then
        log "Erstelle schwarzen Hintergrund mit ImageMagick"
        if convert -size 1024x768 xc:black "$bg_path"; then
            if set_grub_config "GRUB_BACKGROUND" "$bg_path"; then
                log "Standard-Hintergrund erstellt"
                return 0
            fi
        fi
    fi
    
    warn "Konnte keinen Standard-Hintergrund setzen"
    return 1
}

# Exportiere Funktionen
export -f create_theme_dir list_themes validate_theme
export -f activate_theme download_theme set_default_background
