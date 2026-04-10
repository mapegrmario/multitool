#!/bin/bash
# ============================================
# GRUB CONTROL CENTER v2.1
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

# Lade alle Bibliotheken
for lib in config logging validation backup grub cleanup recovery theme; do
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

# Setup Cleanup-Handler
setup_cleanup_handler

log "=========================================="
log "$PROGRAM_NAME v$VERSION gestartet"
log "=========================================="

# ============================================
# GUI-Funktionen
# ============================================

# Timeout setzen (GUI)
set_timeout_gui() {
    check_zenity || return 1
    
    local current_timeout
    current_timeout=$(get_grub_config "GRUB_TIMEOUT")
    [ -z "$current_timeout" ] && current_timeout="5"
    
    local timeout
    timeout=$(zenity --entry \
        --title="GRUB Timeout ändern" \
        --text="Timeout in Sekunden eingeben (0-120):\n\nAktuell: $current_timeout Sekunden" \
        --entry-text="$current_timeout")
    
    [ -z "$timeout" ] && return
    
    if validate_timeout "$timeout"; then
        if set_grub_timeout "$timeout"; then
            if update_grub_with_rollback; then
                zenity --info --text="Timeout erfolgreich geändert: $timeout Sekunden"
            else
                zenity --error --text="Fehler beim Aktualisieren von GRUB!"
            fi
        else
            zenity --error --text="Fehler beim Setzen des Timeouts!"
        fi
    else
        zenity --error --text="Ungültiger Timeout-Wert!\nErlaubt: 0-120 Sekunden"
    fi
}

# Standard-Boot-Eintrag setzen (GUI)
set_default_gui() {
    check_zenity || return 1
    
    # Hole Boot-Einträge
    local entries
    entries=$(get_boot_entries)
    
    if [ -z "$entries" ]; then
        zenity --error --text="Keine Boot-Einträge gefunden!"
        return 1
    fi
    
    # Konvertiere zu Array für zenity
    local entry_array=()
    local index=0
    while IFS= read -r entry; do
        entry_array+=("$index" "$entry")
        ((index++))
    done <<< "$entries"
    
    # Zeige Auswahlmenü
    local choice
    choice=$(zenity --list \
        --title="Standard-Boot-Eintrag wählen" \
        --text="Wähle den Standard-Boot-Eintrag:" \
        --column="Index" --column="Boot-Eintrag" \
        "${entry_array[@]}" \
        --height=400 --width=600)
    
    [ -z "$choice" ] && return
    
    if set_grub_default "$choice"; then
        if update_grub_with_rollback; then
            zenity --info --text="Standard-Boot-Eintrag erfolgreich gesetzt: #$choice"
        else
            zenity --error --text="Fehler beim Aktualisieren von GRUB!"
        fi
    else
        zenity --error --text="Fehler beim Setzen des Standard-Eintrags!"
    fi
}

# Hintergrund setzen (GUI)
set_background_gui() {
    check_zenity || return 1
    
    local file
    file=$(zenity --file-selection \
        --title="Hintergrundbild wählen (PNG/JPEG)" \
        --file-filter="Bilder (PNG/JPEG) | *.png *.jpg *.jpeg" \
        --file-filter="Alle Dateien | *")
    
    [ -z "$file" ] && return
    
    if set_grub_background "$file"; then
        if update_grub_with_rollback; then
            zenity --info --text="Hintergrund erfolgreich gesetzt!"
        else
            zenity --error --text="Fehler beim Aktualisieren von GRUB!"
        fi
    else
        zenity --error --text="Fehler beim Setzen des Hintergrunds!"
    fi
}

# Theme aktivieren (GUI)
activate_theme_gui() {
    check_zenity || return 1
    
    # Erstelle Theme-Verzeichnis falls nötig
    create_theme_dir
    
    # Hole verfügbare Themes
    local themes
    themes=$(list_themes)
    
    if [ -z "$themes" ]; then
        zenity --error --text="Keine Themes gefunden!\nBitte zuerst ein Theme herunterladen."
        return 1
    fi
    
    # Konvertiere zu Array
    local theme_array=()
    while IFS= read -r theme; do
        theme_array+=("$theme")
    done <<< "$themes"
    
    # Zeige Auswahlmenü
    local choice
    choice=$(zenity --list \
        --title="Theme wählen" \
        --text="Verfügbare Themes:" \
        --column="Theme" \
        "${theme_array[@]}" \
        --height=300 --width=400)
    
    [ -z "$choice" ] && return
    
    if activate_theme "$choice"; then
        if update_grub_with_rollback; then
            zenity --info --text="Theme erfolgreich aktiviert: $choice"
        else
            zenity --error --text="Fehler beim Aktualisieren von GRUB!"
        fi
    else
        zenity --error --text="Fehler beim Aktivieren des Themes!"
    fi
}

# Theme herunterladen (GUI)
download_theme_gui() {
    check_zenity || return 1
    
    local url
    url=$(zenity --entry \
        --title="Theme Download" \
        --text="GitHub URL eingeben:\nBeispiel: https://github.com/username/theme-name" \
        --width=500)
    
    [ -z "$url" ] && return
    
    # Zeige Fortschritt
    (
        echo "10" ; echo "# Validiere URL..."
        sleep 0.5
        
        if ! validate_github_url "$url"; then
            zenity --error --text="Ungültige GitHub URL!\nFormat: https://github.com/username/repo"
            exit 1
        fi
        
        echo "20" ; echo "# Erstelle Theme-Verzeichnis..."
        create_theme_dir
        
        echo "30" ; echo "# Lade Theme herunter..."
        sleep 0.5
        
        echo "50" ; echo "# Clone Git-Repository..."
        theme_name=$(download_theme "$url")
        download_result=$?
        
        echo "90" ; echo "# Finalisiere..."
        sleep 0.5
        
        echo "100" ; echo "# Fertig!"
        
        if [ $download_result -eq 0 ]; then
            zenity --info --text="Theme erfolgreich installiert: $theme_name\n\nZum Aktivieren bitte 'Theme aktivieren' wählen."
        else
            zenity --error --text="Download fehlgeschlagen!\nPrüfe URL und Internetverbindung."
        fi
        
    ) | zenity --progress \
        --title="Theme Download" \
        --text="Initialisiere..." \
        --percentage=0 \
        --auto-close \
        --width=400
}

# ============================================
# Hauptmenü
# ============================================

main_menu() {
    while true; do
        if command -v zenity &>/dev/null; then
            # GUI-Modus
            local choice
            choice=$(zenity --list \
                --title="$PROGRAM_NAME v$VERSION" \
                --text="Wähle eine Option:" \
                --column="Option" \
                --height=400 --width=450 \
                "Boot Einstellungen" \
                "Design / Themes" \
                "Theme herunterladen" \
                "Recovery starten" \
                "Analyse System" \
                "Backups verwalten" \
                "Beenden")
            
            case "$choice" in
                "Boot Einstellungen")
                    local sub
                    sub=$(zenity --list \
                        --title="Boot Optionen" \
                        --column="Option" \
                        "Standard setzen" \
                        "Timeout ändern")
                    case "$sub" in
                        "Standard setzen") set_default_gui ;;
                        "Timeout ändern") set_timeout_gui ;;
                    esac
                    ;;
                "Design / Themes")
                    local sub
                    sub=$(zenity --list \
                        --title="Design Optionen" \
                        --column="Option" \
                        "Hintergrund setzen" \
                        "Theme aktivieren")
                    case "$sub" in
                        "Hintergrund setzen") set_background_gui ;;
                        "Theme aktivieren") activate_theme_gui ;;
                    esac
                    ;;
                "Theme herunterladen") 
                    download_theme_gui 
                    ;;
                "Recovery starten") 
                    if [ -f "$CUSTOM_DIR/recovery.sh" ]; then
                        "$CUSTOM_DIR/recovery.sh"
                    else
                        zenity --error --text="Recovery-Script nicht gefunden!\nBitte neu installieren."
                    fi
                    ;;
                "Analyse System")
                    if [ -f "$INSTALL_DIR/grub-check.sh" ]; then
                        ("$INSTALL_DIR/grub-check.sh" 2>&1) | \
                        zenity --text-info \
                            --title="System-Analyse" \
                            --width=800 --height=600
                    else
                        zenity --error --text="Analyse-Skript nicht gefunden!"
                    fi
                    ;;
                "Backups verwalten")
                    list_backups | zenity --text-info \
                        --title="GRUB-Backups" \
                        --width=600 --height=400
                    ;;
                "Beenden"|"") 
                    exit 0 
                    ;;
            esac
        else
            # Text-Modus Fallback
            echo ""
            echo "========================================="
            echo "   $PROGRAM_NAME v$VERSION (Text)"
            echo "========================================="
            echo "1) Boot Einstellungen"
            echo "2) Design / Themes"
            echo "3) Theme herunterladen"
            echo "4) Recovery starten"
            echo "5) Analyse System"
            echo "6) Backups verwalten"
            echo "7) Beenden"
            echo "========================================="
            read -p "Auswahl: " choice
            
            case "$choice" in
                1)
                    echo "1) Timeout ändern"
                    read -p "Auswahl: " sub
                    if [ "$sub" = "1" ]; then
                        read -p "Timeout in Sekunden (0-120): " timeout
                        if validate_timeout "$timeout"; then
                            set_grub_timeout "$timeout"
                            update_grub_with_rollback
                        fi
                    fi
                    ;;
                3)
                    read -p "GitHub URL: " url
                    if validate_github_url "$url"; then
                        create_theme_dir
                        theme_name=$(download_theme "$url")
                        echo "Theme installiert: $theme_name"
                    else
                        echo "Ungültige URL!"
                    fi
                    ;;
                4)
                    if [ -f "$CUSTOM_DIR/recovery.sh" ]; then
                        "$CUSTOM_DIR/recovery.sh"
                    fi
                    ;;
                5)
                    if [ -f "$INSTALL_DIR/grub-check.sh" ]; then
                        "$INSTALL_DIR/grub-check.sh"
                    fi
                    ;;
                6)
                    list_backups
                    ;;
                7) 
                    exit 0 
                    ;;
                *)
                    echo "Ungültige Auswahl!"
                    ;;
            esac
            read -p "Enter drücken zum Fortfahren..."
        fi
    done
}

# ============================================
# Initiales Setup
# ============================================

initial_setup() {
    log "Führe initiales Setup durch..."
    
    # Erstelle Verzeichnisse
    mkdir -p "$THEME_DIR" "$CUSTOM_DIR" "$LOG_DIR" 2>/dev/null
    
    # Prüfe ob Recovery-Komponenten fehlen
    if [ ! -f "$CUSTOM_DIR/recovery.sh" ] || [ ! -f "/etc/grub.d/41_recovery" ]; then
        log "Recovery-Komponenten fehlen, richte ein..."
        setup_recovery_system
    fi
    
    # Setze Standard-Hintergrund falls nötig
    if ! grep -q "^GRUB_BACKGROUND" "$GRUB_FILE" 2>/dev/null; then
        set_default_background
    fi
    
    log "Initiales Setup abgeschlossen"
}

# Führe initiales Setup durch
initial_setup

# Starte Hauptmenü
main_menu
