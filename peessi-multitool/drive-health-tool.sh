#!/bin/bash

# Farben für die Ausgabe
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. ROOT-CHECK (Muss ganz am Anfang stehen)
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}FEHLER: Dieses Script muss mit root-Rechten ausgeführt werden!${NC}"
  echo -e "Bitte starte es so: ${YELLOW}sudo $0${NC}"
  exit 1
fi

# Verzeichnis für Logs im Home-Ordner des echten Users erstellen
REAL_USER=${SUDO_USER:-$USER}
LOGDIR="/home/$REAL_USER/DriveTests"
mkdir -p "$LOGDIR"
chown $REAL_USER:$REAL_USER "$LOGDIR"
LOGFILE="$LOGDIR/test_$(date +%Y%m%d_%H%M%S).log"

# Funktion für sauberes Abbrechen (Strg+C)
trap ctrl_c INT
function ctrl_c() {
    echo -e "\n\n${YELLOW}[!] ABBRUCH DURCH NUTZER. Test gestoppt. Kein Shutdown.${NC}"
    exit 1
}

# Funktion zur Überprüfung und Installation von Abhängigkeiten
function check_dependencies() {
    local missing_deps=()
    for cmd in smartctl badblocks xdg-open less; do
        if ! command -v $cmd &> /dev/null; then
            if [ "$cmd" != "xdg-open" ]; then
                missing_deps+=($cmd)
            fi
        fi
    done

    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${YELLOW}INFO: Folgende Abhängigkeiten fehlen: ${missing_deps[*]}.${NC}"
        read -p "Möchten Sie diese jetzt installieren? (j/n): " INSTALL_CONFIRM
        if [[ "$INSTALL_CONFIRM" =~ ^[JjYy]$ ]]; then
            echo -e "${BLUE}Installiere fehlende Pakete...${NC}"
            sudo apt-get update
            sudo apt-get install -y smartmontools e2fsprogs xdg-utils less
            if [ $? -ne 0 ]; then
                echo -e "${RED}FEHLER: Installation fehlgeschlagen. Bitte installieren Sie die Pakete manuell.${NC}"
                exit 1
            fi
            echo -e "${GREEN}Installation erfolgreich.${NC}"
        else
            echo -e "${RED}FEHLER: Fehlende Abhängigkeiten. Bitte installieren Sie diese manuell oder erlauben Sie die automatische Installation.${NC}"
            exit 1
        fi
    fi
}

clear
echo "======================================================"
echo -e "      ${BLUE}LINUX SAFE DRIVE DIAGNOSTICS (v2.8)${NC}            "
echo "======================================================"
echo -e "Log-Verzeichnis: ${YELLOW}$LOGDIR${NC}"
echo "------------------------------------------------------"

# Abhängigkeiten prüfen und ggf. installieren
check_dependencies

# 2. Hardware auflisten
echo -e "\nVerfügbare Laufwerke und Partitionen:"
printf "%-12s %-8s %-20s %-20s %-15s %-5s\n" "NAME" "SIZE" "MODELL" "LABEL/NAME" "MOUNT" "ROTA"

AVAILABLE_DRIVES=()

# Wir nutzen --pairs und extrahieren die Werte robuster
while read -r line; do
    NAME=$(echo "$line" | grep -oP 'NAME="\K[^"]+')
    SIZE=$(echo "$line" | grep -oP 'SIZE="\K[^"]+')
    MODEL=$(echo "$line" | grep -oP 'MODEL="\K[^"]+')
    LABEL=$(echo "$line" | grep -oP 'LABEL="\K[^"]+')
    MOUNTPOINT=$(echo "$line" | grep -oP 'MOUNTPOINT="\K[^"]+')
    ROTA=$(echo "$line" | grep -oP 'ROTA="\K[^"]+')
    TYPE=$(echo "$line" | grep -oP 'TYPE="\K[^"]+')
    PKNAME=$(echo "$line" | grep -oP 'PKNAME="\K[^"]+')

    DISPLAY_LABEL="${LABEL:-<kein Label>}"
    DISPLAY_MODEL="${MODEL:-<unbekannt>}"
    
    if [ "$TYPE" == "disk" ] || [ -z "$PKNAME" ]; then
        printf "${BLUE}%-12s${NC} %-8s %-20s %-20s %-15s %-5s\n" "$NAME" "$SIZE" "$DISPLAY_MODEL" "$DISPLAY_LABEL" "$MOUNTPOINT" "$ROTA"
        AVAILABLE_DRIVES+=("$NAME")
    else
        printf "  └─%-10s %-8s %-20s ${YELLOW}%-20s${NC} %-15s %-5s\n" "$NAME" "$SIZE" "" "$DISPLAY_LABEL" "$MOUNTPOINT" ""
    fi
done < <(lsblk -no NAME,SIZE,MODEL,LABEL,MOUNTPOINT,ROTA,TYPE,PKNAME --pairs)
echo "------------------------------------------------------"

# 3. Auswahl & Validierung
DRIVE=""
while true; do
    read -p "Welches HAUPT-Laufwerk möchtest du testen (z.B. sda oder mmcblk0)? " USER_DRIVE_INPUT
    USER_DRIVE_INPUT=${USER_DRIVE_INPUT#/dev/}
    
    FOUND=false
    for d in "${AVAILABLE_DRIVES[@]}"; do
        if [ "$d" == "$USER_DRIVE_INPUT" ]; then
            FOUND=true
            break
        fi
    done

    if [ "$FOUND" = true ]; then
        DRIVE="$USER_DRIVE_INPUT"
        break
    else
        echo -e "${RED}FEHLER: '$USER_DRIVE_INPUT' ist kein gültiges Hauptlaufwerk. Bitte wähle ein blau markiertes Laufwerk aus der Liste.${NC}"
    fi
done

DEVICE="/dev/$DRIVE"

DRIVE_LABEL=$(lsblk -dno LABEL "$DEVICE")
DRIVE_MODEL=$(lsblk -dno MODEL "$DEVICE")
PART_LABELS=$(lsblk -no LABEL "$DEVICE" | grep -v '^$' | tr '\n' ',' | sed 's/,$//')

echo -e "\n${GREEN}AUSGEWÄHLT:${NC} $DEVICE"
echo -e "${GREEN}MODELL:${NC}      ${DRIVE_MODEL:-<unbekannt>}"
echo -e "${GREEN}DISK-LABEL:${NC}  ${DRIVE_LABEL:-<Kein Label auf Disk-Ebene>}"
if [ -n "$PART_LABELS" ]; then
    echo -e "${GREEN}PART-LABELS:${NC} ${YELLOW}$PART_LABELS${NC}"
fi
echo "------------------------------------------------------"

read -p "Bist du sicher, dass du DIESE Platte testen willst? (j/n): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[JjYy]$ ]]; then
    echo -e "${YELLOW}Abgebrochen.${NC}"
    exit 0
fi

read -p "Soll der PC nach Abschluss herunterfahren? (j/n): " SHUTDOWN_CHOICE

# 4. Hardware-Erkennung (HDD vs SSD vs MMC)
if [ -f "/sys/block/$DRIVE/queue/rotational" ]; then
    IS_ROTATIONAL=$(cat "/sys/block/$DRIVE/queue/rotational")
else
    IS_ROTATIONAL=0
fi

if [ "$IS_ROTATIONAL" -eq "1" ]; then
    TYPE_DESC="HDD (Mechanisch)"
    BLOCKSIZE="4096"
else
    TYPE_DESC="SSD/Flash (z.B. SD-Karte/USB)"
    BLOCKSIZE="32768"
fi

{
    echo "START: $(date)"
    echo "GERÄT: $DEVICE (Modell: $DRIVE_MODEL)"
    echo "LABELS: $PART_LABELS"
    echo "TYP:   $TYPE_DESC"
    echo "------------------------------------------------------"
} >> "$LOGFILE"

# 5. SMART Check
echo -e "\n${BLUE}[1/2] Prüfe S.M.A.R.T. Status...${NC}" | tee -a "$LOGFILE"
if smartctl -i "$DEVICE" 2>/dev/null | grep -q "SMART support is: Enabled"; then
    smartctl -H "$DEVICE" | tee -a "$LOGFILE"
    smartctl -A "$DEVICE" >> "$LOGFILE" 2>&1
else
    echo -e "${YELLOW}INFO: SMART nicht unterstützt oder deaktiviert (häufig bei SD-Karten/USB).${NC}" | tee -a "$LOGFILE"
fi

# 6. Badblocks Oberflächen-Scan
echo -e "\n${BLUE}[2/2] Starte Scan (Nur-Lesen)... Abbruch mit Strg+C.${NC}"
echo "------------------------------------------------------"

badblocks -sv -b "$BLOCKSIZE" "$DEVICE" 2>&1 | tee -a "$LOGFILE"

echo -e "\n======================================================" | tee -a "$LOGFILE"
echo -e "${GREEN}TEST FERTIG: $(date)${NC}" | tee -a "$LOGFILE"
chown $REAL_USER:$REAL_USER "$LOGFILE"

# 7. Shutdown oder Logdatei öffnen
if [[ "$SHUTDOWN_CHOICE" =~ ^[JjYy]$ ]]; then
    echo -e "${YELLOW}Test abgeschlossen. Logdatei gespeichert unter: ${BLUE}$LOGFILE${NC}"
    echo -e "${RED}PC fährt in 60 Sek. runter. 'shutdown -c' zum Abbrechen.${NC}"
    sleep 60
    shutdown -h now
else
    # Nur fragen, wenn KEIN Shutdown gewählt wurde
    read -p "Möchten Sie die Logdatei jetzt öffnen? (j/n): " OPEN_LOG_CHOICE
    if [[ "$OPEN_LOG_CHOICE" =~ ^[JjYy]$ ]]; then
        echo -e "${BLUE}Öffne Logdatei: ${YELLOW}$LOGFILE${NC}"
        if [ -n "$SUDO_USER" ]; then
            sudo -u "$SUDO_USER" xdg-open "$LOGFILE" &> /dev/null || less "$LOGFILE"
        else
            xdg-open "$LOGFILE" &> /dev/null || less "$LOGFILE"
        fi
    fi
fi
