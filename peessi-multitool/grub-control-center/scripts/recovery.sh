#!/bin/bash
# ============================================
# GRUB Control Center - Recovery System
# ============================================

# Hole Festplattenliste
get_disks() { 
    lsblk -d -o NAME,SIZE,MODEL 2>/dev/null | tail -n +2
}

# Hole Partitionsliste
get_partitions() { 
    lsblk -o NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null | grep -E "part|lvm" | grep -v "\[SWAP\]"
}

# Disk auswählen (mit korrektem Quoting)
select_disk() {
    echo "Verfügbare Festplatten:"
    mapfile -t DISKS < <(get_disks)
    
    if [ ${#DISKS[@]} -eq 0 ]; then
        echo "Keine Festplatten gefunden!"
        return 1
    fi
    
    for i in "${!DISKS[@]}"; do 
        echo "$i) ${DISKS[$i]}"
    done
    read -p "Disk wählen (Nummer): " d
    
    # Validierung
    if [[ ! "$d" =~ ^[0-9]+$ ]] || [ "$d" -ge "${#DISKS[@]}" ]; then
        echo "Ungültige Auswahl!"
        return 1
    fi
    
    # KORRIGIERT: Richtiges Quoting und Sanitization
    local disk_name
    disk_name=$(echo "${DISKS[$d]}" | awk '{print $1}' | tr -cd '[:alnum:]')
    DISK="/dev/${disk_name}"
    
    # Validierung
    if [ ! -b "$DISK" ]; then
        echo "FEHLER: $DISK ist kein gültiges Block-Device!"
        return 1
    fi
    
    echo "Ausgewählt: $DISK"
    return 0
}

# Partition auswählen (mit korrektem Quoting)
select_partition() {
    echo "Verfügbare Partitionen:"
    mapfile -t PARTS < <(get_partitions)
    
    if [ ${#PARTS[@]} -eq 0 ]; then
        echo "Keine Partitionen gefunden!"
        return 1
    fi
    
    for i in "${!PARTS[@]}"; do 
        echo "$i) ${PARTS[$i]}"
    done
    read -p "Partition wählen (Nummer): " p
    
    # Validierung
    if [[ ! "$p" =~ ^[0-9]+$ ]] || [ "$p" -ge "${#PARTS[@]}" ]; then
        echo "Ungültige Auswahl!"
        return 1
    fi
    
    # KORRIGIERT: Richtiges Quoting und Sanitization
    local part_name
    part_name=$(echo "${PARTS[$p]}" | awk '{print $1}' | tr -cd '[:alnum:]')
    PART="/dev/${part_name}"
    
    # Validierung
    if [ ! -b "$PART" ]; then
        echo "FEHLER: $PART ist kein gültiges Block-Device!"
        return 1
    fi
    
    echo "Ausgewählt: $PART"
    return 0
}

# Hauptmenü
while true; do
    clear
    echo "========================================="
    echo "      RECOVERY SYSTEM v2.1"
    echo "========================================="
    echo "1) Shell (Notfall-Shell)"
    echo "2) GRUB reparieren (install)"
    echo "3) Dateisystem prüfen (fsck)"
    echo "4) Timeshift Snapshot wiederherstellen"
    echo "5) GRUB Control Center starten"
    echo "6) System-Informationen"
    echo "7) Neustart"
    echo "8) Ausschalten"
    echo "0) Zurück zum Hauptmenü"
    echo "========================================="
    read -p "Auswahl: " c

    case "$c" in
        1) 
            echo "Starte Notfall-Shell... (exit zum Zurückkehren)"
            bash
            ;;
        2) 
            if select_disk; then
                echo ""
                echo "WARNUNG: Dies installiert GRUB auf $DISK"
                read -p "Fortfahren? (j/n): " confirm
                if [ "$confirm" = "j" ] || [ "$confirm" = "J" ]; then
                    echo "Installiere GRUB auf $DISK..."
                    if grub-install "$DISK" 2>&1; then
                        echo "GRUB erfolgreich installiert"
                        
                        # Update GRUB
                        echo "Aktualisiere GRUB-Konfiguration..."
                        if command -v update-grub &>/dev/null; then
                            update-grub && echo "GRUB-Konfiguration aktualisiert"
                        elif command -v grub-mkconfig &>/dev/null; then
                            grub-mkconfig -o /boot/grub/grub.cfg && echo "GRUB-Konfiguration aktualisiert"
                        fi
                    else
                        echo "FEHLER: GRUB-Installation fehlgeschlagen!"
                    fi
                fi
                read -p "Enter drücken zum Fortfahren..."
            fi
            ;;
        3) 
            if select_partition; then
                echo ""
                echo "WARNUNG: Dateisystem-Check kann bei gemounteten Partitionen"
                echo "         Datenverlust verursachen!"
                echo "         Partition sollte unmounted sein."
                echo ""
                read -p "Fortfahren? (j/n): " confirm
                if [ "$confirm" = "j" ] || [ "$confirm" = "J" ]; then
                    echo "Führe fsck auf $PART aus..."
                    fsck -f -y "$PART" 2>&1
                    echo ""
                    echo "Dateisystem-Check abgeschlossen"
                fi
                read -p "Enter drücken zum Fortfahren..."
            fi
            ;;
        4)
            if command -v timeshift &>/dev/null; then
                echo "Verfügbare Snapshots:"
                timeshift --list
                echo ""
                read -p "Snapshot-Namen eingeben (oder 'exit'): " s
                if [ "$s" != "exit" ] && [ -n "$s" ]; then
                    echo "WARNUNG: Dies überschreibt das aktuelle System!"
                    read -p "Wirklich fortfahren? (j/n): " confirm
                    if [ "$confirm" = "j" ] || [ "$confirm" = "J" ]; then
                        echo "Stelle Snapshot $s wieder her..."
                        timeshift --restore --snapshot "$s"
                    fi
                fi
            else
                echo "Timeshift nicht installiert!"
                read -p "Enter drücken zum Fortfahren..."
            fi
            ;;
        5)
            if [ -f "/usr/local/grub-master-center/grub-control-center.sh" ]; then
                /usr/local/grub-master-center/grub-control-center.sh
            else
                echo "GRUB Control Center nicht gefunden!"
                read -p "Enter drücken zum Fortfahren..."
            fi
            ;;
        6)
            echo ""
            echo "=== SYSTEM-INFORMATIONEN ==="
            echo "Kernel: $(uname -r)"
            echo "Hostname: $(hostname)"
            echo "Architektur: $(uname -m)"
            echo ""
            echo "Festplatten:"
            lsblk -d -o NAME,SIZE,MODEL 2>/dev/null
            echo ""
            echo "Partitionen:"
            lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT 2>/dev/null | grep -v "loop"
            echo ""
            echo "Speicher:"
            free -h 2>/dev/null
            echo ""
            read -p "Enter drücken zum Fortfahren..."
            ;;
        7) 
            echo "Starte Neustart..."
            sleep 2
            reboot
            ;;
        8) 
            echo "Fahre System herunter..."
            sleep 2
            poweroff
            ;;
        0) 
            exit 0
            ;;
        *)
            echo "Ungültige Auswahl!"
            sleep 2
            ;;
    esac
done
