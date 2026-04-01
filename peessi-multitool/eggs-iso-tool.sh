#!/bin/bash
# =============================================================================
# eggs-iso-tool.sh – Penguins-Eggs ISO-Erstellungs-Tool
# Teil von Peeßi's System Multitool
# Autor: Mario Peeß | Lizenz: GPLv3
# Ursprungsscript: mein-iso-tool.sh
# =============================================================================

LOG_DATEI="/home/eggs-erstellung.log"
STANDARD_ZIEL="/home/eggs"
RECHNER_AUS=false
ISO_AUSGABE="$STANDARD_ZIEL"

# Root-Prüfung
if [ "$EUID" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo $0 $*"
    exit 1
fi

# eggs-Prüfung
if ! command -v eggs &>/dev/null; then
    echo "FEHLER: 'eggs' ist nicht installiert."
    echo "Bitte über das Multitool installieren: Laufwerke → ISO-Brenner."
    exit 2
fi

# Echter Nutzer (für mom-Befehl)
ECHTER_NUTZER="${SUDO_USER:-$USER}"

# =============================================================================
# Hilfsfunktionen
# =============================================================================

logge() { echo -e "$1" | tee -a "$LOG_DATEI"; }

# Trap: laufenden eggs-Prozess sauber beenden
EGGS_PID=""
trap '
    [[ -n "$EGGS_PID" ]] && kill "$EGGS_PID" 2>/dev/null
    logge "Abbruch durch Benutzer."
    exit 1
' INT TERM

# =============================================================================
# Zielverzeichnis wählen
# =============================================================================
laufwerk_waehlen() {
    local PFADE=()
    while IFS= read -r line; do
        PFADE+=("$line")
    done < <(df -h --output=target 2>/dev/null | grep -E '/media/|/mnt/')

    echo "==========================================="
    echo "       ZIEL-LAUFWERK AUSWÄHLEN"
    echo "==========================================="
    echo "0) Standard-Ordner ($STANDARD_ZIEL)"
    for i in "${!PFADE[@]}"; do
        echo "$((i+1))) ${PFADE[$i]}"
    done
    echo "-------------------------------------------"
    echo -n "Auswahl [0-${#PFADE[@]}]: "
    read -r wahl

    ISO_AUSGABE="$STANDARD_ZIEL"
    if [[ "$wahl" =~ ^[0-9]+$ ]] && \
       [ "$wahl" -ge 1 ] && [ "$wahl" -le "${#PFADE[@]}" ]; then
        ISO_AUSGABE="${PFADE[$((wahl-1))]}"
    fi

    if [ ! -w "$ISO_AUSGABE" ]; then
        logge "Erstelle Zielverzeichnis: $ISO_AUSGABE"
        mkdir -p "$ISO_AUSGABE" || { logge "FEHLER: Ziel nicht erstellbar."; exit 1; }
    fi
    logge "Zielverzeichnis: $ISO_AUSGABE"
}

# =============================================================================
# ISO-Name für Boot-Manager setzen
# =============================================================================
iso_name_setzen() {
    echo "==========================================="
    echo "       ISO-NAME FÜR BOOT-MANAGER"
    echo "==========================================="
    echo "Der Name erscheint im GRUB/rEFInd Boot-Menü."
    echo -n "ISO-Name [Standard: PeessiLive]: "
    read -r iso_name
    iso_name="${iso_name:-PeessiLive}"
    # Nur erlaubte Zeichen
    iso_name=$(echo "$iso_name" | tr -cd 'a-zA-Z0-9_-')
    [ -z "$iso_name" ] && iso_name="PeessiLive"
    echo "ISO-Name gesetzt: $iso_name"
    echo "$iso_name"
}

# =============================================================================
# Calamares-Integration
# =============================================================================
installiere_calamares() {
    if command -v calamares &>/dev/null; then
        logge "Calamares bereits installiert – überspringe."
        return 0
    fi
    echo -n "Calamares-Installer in ISO integrieren? (j/n): "
    read -r cal_choice
    if [[ "$cal_choice" == "j" || "$cal_choice" == "J" ]]; then
        logge ">>> eggs calamares --install ..."
        eggs calamares --install >> "$LOG_DATEI" 2>&1
        [ $? -eq 0 ] && logge "Calamares erfolgreich integriert." \
                     || logge "WARNUNG: Calamares-Integration fehlgeschlagen."
    else
        logge "Calamares nicht integriert."
    fi
}

# =============================================================================
# Haupt-Erstellungsprozess
# =============================================================================
prozess_starten() {
    local modus=$1
    laufwerk_waehlen

    # ISO-Name für Boot-Manager
    local iso_name
    iso_name=$(iso_name_setzen)

    # Shutdown-Option
    echo -n "Nach Abschluss automatisch ausschalten? (j/n): "
    read -r choice
    [[ "$choice" == "j" || "$choice" == "J" ]] && RECHNER_AUS=true || RECHNER_AUS=false

    # System bereinigen
    echo -n "Vor Erstellung apt-get clean && autoremove ausführen? (j/n): "
    read -r bereinigen
    if [[ "$bereinigen" == "j" || "$bereinigen" == "J" ]]; then
        logge ">>> System bereinigen..."
        apt-get clean && apt-get autoremove -y >> "$LOG_DATEI" 2>&1
    fi

    # Calamares anbieten
    installiere_calamares

    mkdir -p "$ISO_AUSGABE"
    logge ">>> ISO-ERSTELLUNG STARTET ..."
    START_ZEIT=$(date +%s)

    # Design speichern (für modus=design)
    if [ "$modus" == "design" ]; then
        logge ">>> Speichere Design (als $ECHTER_NUTZER)..."
        sudo -E -u "$ECHTER_NUTZER" eggs mom --skilling >> "$LOG_DATEI" 2>&1 || \
            logge "WARNUNG: Design konnte nicht gespeichert werden."
    fi

    # eggs-Befehl je nach Modus
    case $modus in
        "standard")
            eggs produce --standard --prefix custom \
                --basename "${iso_name}-programmes" --nointeractive >> "$LOG_DATEI" 2>&1 &
            ;;
        "design")
            eggs produce --standard --prefix custom \
                --basename "${iso_name}-design" --nointeractive >> "$LOG_DATEI" 2>&1 &
            ;;
        "klon")
            eggs produce --clone --standard --prefix backup \
                --basename "${iso_name}-vollbackup" --nointeractive >> "$LOG_DATEI" 2>&1 &
            ;;
    esac

    EGGS_PID=$!
    tail -f "$LOG_DATEI" --pid=$EGGS_PID 2>/dev/null
    wait $EGGS_PID
    STATUS=$?
    EGGS_PID=""

    local erfolg=false
    local ENDE_ZEIT=$(date +%s)
    local DAUER=$(( (ENDE_ZEIT - START_ZEIT) / 60 ))

    if [ $STATUS -eq 0 ]; then
        logge ">>> ISO-Erstellung erfolgreich (${DAUER} min)."
        local ISO_DATEI
        ISO_DATEI=$(ls -t /home/eggs/*.iso 2>/dev/null | head -n1)
        if [ -n "$ISO_DATEI" ] && [ -f "$ISO_DATEI" ]; then
            logge ">>> Kopiere ISO nach $ISO_AUSGABE ..."
            if cp "$ISO_DATEI" "$ISO_AUSGABE/"; then
                rm "$ISO_DATEI"
                logge "ERFOLG: ISO → $ISO_AUSGABE"
                erfolg=true
            else
                logge "FEHLER: Kopieren fehlgeschlagen."
            fi
        else
            logge "FEHLER: Keine ISO in /home/eggs gefunden."
        fi
    else
        logge "!!! FEHLER BEI ISO-ERSTELLUNG (Exit: $STATUS) !!!"
    fi

    if [ "$erfolg" = true ] && [ "$RECHNER_AUS" = true ]; then
        logge "Shutdown in 60 Sekunden..."
        sleep 60
        shutdown -h now
    else
        echo ""
        echo "Drücke Enter, um zum Menü zurückzukehren."
        read -r
    fi
}

# =============================================================================
# Menü
# =============================================================================

# Falls mit Argument aufgerufen (z.B. vom Multitool: --modus standard)
if [ -n "${1:-}" ]; then
    case "$1" in
        --dad)      eggs dad -d ;;
        --standard) prozess_starten "standard" ;;
        --design)   prozess_starten "design" ;;
        --klon)     prozess_starten "klon" ;;
        *)          echo "Unbekannte Option: $1" ; exit 1 ;;
    esac
    exit 0
fi

# Interaktives Menü
while true; do
    clear
    echo "==========================================="
    echo "    PENGUIN'S EGGS – REPARATUR MODUS"
    echo "==========================================="
    echo "1) System vorbereiten (eggs dad -d)"
    echo "2) ISO erstellen (Nur Programme)"
    echo "3) ISO erstellen (Programme & Design)"
    echo "4) VOLLSTÄNDIGER KLON (Alles)"
    echo "5) Beenden"
    echo "==========================================="
    read -r opt
    case $opt in
        1) eggs dad -d; echo "Fertig. Enter."; read -r ;;
        2) prozess_starten "standard" ;;
        3) prozess_starten "design" ;;
        4) prozess_starten "klon" ;;
        5) exit 0 ;;
        *) echo "Ungültige Auswahl."; sleep 1 ;;
    esac
done
