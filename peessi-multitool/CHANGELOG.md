# Changelog – Peeßi's System Multitool

## v4.2 (April 2026)

### Neue Funktionen
- **🔧 Erweitert-Tab** (gui_advanced.py) mit 5 Sub-Tabs:
  - 💾 Disk-Images (dd + gzip, komprimiert/unkomprimiert)
  - 🔄 Datenmigration (rsync, Live-Ausgabe, Stopp)
  - 💿 LVM (PV/VG/LV, Checkbox-Auswahl, vergrößern)
  - 🛡️ RAID (mdadm 0/1/5/6/10, Checkbox-Auswahl)
  - 🩹 Boot-Reparatur (GRUB, TestDisk, ms-sys)
- **⚙️ BIOS/EFI-Tab** komplett überarbeitet: Treeview-Tabelle, Inline-Eingaben
- **🔐 nwipe** in Sicheres-Löschen-Tab integriert
- **🌐 i18n.py** – Zweisprachigkeit DE/EN, Umschalter in Einstellungen
- **ms-sys 2.8.0** wird automatisch aus Quelltext gebaut
- **Logs & Diagnose**: Export aller Logs in frei wählbaren Ordner

### UX-Verbesserungen
- **Farbiges Log** (Nr. 2): ✅ grün / ❌ rot / ⚠️ orange – automatisch erkannt
- **Statusleiste** (Nr. 6): zeigt aktuell laufenden Prozess + Laufzeit
- **Willkommens-Dialog** (Nr. 5): beim ersten Start, erklärt die 3 Hauptfunktionen
- **Zeitanzeige** (Nr. 7): jede Aktion zeigt Laufzeit in Sekunden
- **Danger-Buttons** (Nr. 4): destruktive Aktionen rot hervorgehoben
- Einheitliche Laufwerksauswahl via Checkboxen in allen Advanced-Tabs

### Sicherheitsfixes (Produktionsreife)
- **CB-1**: Systemlaufwerk-Schutz vor dd/shred/mdadm/lvcreate
- **CB-2**: threading.Lock für Badblocks-Prozess (Race Condition behoben)
- **CB-3**: RotatingFileHandler (max. 1 MB, 3 Backups)
- **CB-4**: Shell-Injection in GRUB-Theme-Download behoben (shell=False)
- **HP-1**: Alle Prozesse werden beim Schließen sauber beendet
- **HP-2**: SQLite WAL-Modus (Korruptions-Schutz)
- **HP-5**: ISO-Dateien erhalten korrekte Ownership (chown)
- **HP-7**: grub-cc/scripts/recovery.sh Syntaxfehler behoben

### Fehlerbehebungen
- eggs-iso: Menüpunkt „Programme & Design" entfernt
- GRUB-Tab: Vollprogramm/Systemanalyse-Buttons entfernt
- Systempflege + Optimierer in einem Tab vereint
- Update-Shutdown läuft jetzt als normaler User (nicht Root)
- Mail-Button öffnet xdg-open als ORIGINAL_USER
- grub-cc/lib/config.sh: SUDO_USER-Fallback robuster

## v4.1 (März 2026)
- Laufwerk-Diagnose Tab (S.M.A.R.T. + Badblocks)
- GRUB Control Center Integration
- Eggs-ISO Tab (penguins-eggs)
- Log-Export-Funktion
- Scroll-Fixes in allen scrollbaren Tabs
