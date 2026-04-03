# GRUB Control Center v2.1

Ein vollständig überarbeitetes und fehlerbereinigtes Tool zur Verwaltung und Konfiguration des GRUB-Bootloaders.

## 🆕 Was ist neu in v2.1?

### Kritische Fehler behoben:
✅ **Recovery-System repariert** - Verwendet jetzt automatisch erkannte UUIDs statt hardcodierter Labels  
✅ **URL-Validierung korrigiert** - Logikfehler im GitHub-URL-Regex behoben  
✅ **Sichere Backups** - Race Conditions durch PID + Nanosekunden-Timestamps behoben  
✅ **Logging repariert** - Doppelte Shell-Umleitungen korrigiert  

### Sicherheitsverbesserungen:
🔒 **Korrektes Quoting** - Alle Variablen korrekt gequotet gegen Wortsplitting  
🔒 **Sichere Temp-Dateien** - Verwendet mktemp statt vorhersehbarer Namen  
🔒 **Input-Validierung** - Umfassende Validierung aller Benutzereingaben  
🔒 **Bildvalidierung** - Größen- und Format-Prüfung für GRUB-Hintergründe  

### Code-Qualität:
📦 **Modulare Struktur** - Bibliotheken in lib/, Skripte in scripts/  
📦 **Keine Code-Duplizierung** - Recovery-Script nur einmal definiert  
📦 **Rollback-Funktion** - Automatisches Rollback bei GRUB-Update-Fehlern  
📦 **Cleanup-Handler** - Automatische Bereinigung temporärer Dateien  
📦 **Distributionsunabhängig** - Funktioniert mit update-grub, grub-mkconfig und grub2-mkconfig  

## 📋 Funktionen

### Hauptfunktionen
- ✨ **Grafische Benutzeroberfläche** (mit zenity)
- 📝 **Textbasierter Modus** (Fallback)
- ⚙️ **Boot-Einstellungen** (Standard-Boot-Eintrag, Timeout)
- 🎨 **Design & Themes** (Hintergrund, GRUB-Themes)
- 📥 **Theme-Download** von GitHub (mit korrekter URL-Validierung)
- 🛡️ **Recovery-System** mit automatischer UUID-Erkennung
- 📊 **Umfassende Systemanalyse**
- 💾 **Backup-Verwaltung** mit automatischem Rollback

### Recovery-Funktionen
- 🐚 Notfall-Shell
- 🔧 GRUB-Reparatur
- 🔍 Dateisystem-Check (fsck)
- 📸 Timeshift-Snapshot-Wiederherstellung
- ℹ️ System-Informationen
- 🔄 Neustart / Herunterfahren

### Analyse-Funktionen
- ✅ Prüfung aller GRUB-Dateien
- 🔧 Tool-Verfügbarkeitsprüfung
- 🔐 Berechtigungsprüfungen
- 📋 Menüeintrags-Analyse
- 💽 Festplatten- und Partitionsübersicht
- 📏 Speicherplatzprüfung
- 🆔 UUID-Validierung

## 💻 Systemvoraussetzungen

- Linux mit GRUB 2
- Root-Rechte (sudo)
- Bash 4.0+

### Benötigte Pakete
- `zenity` - GUI-Dialoge
- `git` - Theme-Download
- `os-prober` - Erkennung anderer Betriebssysteme
- `timeshift` - Snapshots (optional)

### Unterstützte Distributionen
- ✅ Debian / Ubuntu und Derivate
- ✅ Fedora / RedHat / CentOS
- ✅ Arch Linux
- ✅ Andere Linux-Distributionen mit GRUB 2

## 📦 Installation

### Schnellinstallation

```bash
# 1. Entpacke das Archiv
unzip grub-control-center-v2.1.zip
cd grub-control-center-fixed

# 2. Mache das Installationsskript ausführbar
chmod +x install.sh

# 3. Führe die Installation aus
sudo ./install.sh
```

Das Installationsskript:
- Erstellt alle benötigten Verzeichnisse
- Prüft und installiert Abhängigkeiten
- Kopiert alle Dateien
- Richtet das Recovery-System mit korrekter UUID ein
- Aktualisiert GRUB
- Erstellt Symlinks und Desktop-Eintrag

## 🚀 Verwendung

### Hauptprogramm starten
```bash
sudo grub-control-center
```

### System-Analyse durchführen
```bash
sudo grub-check
```

### Recovery-System
Das Recovery-System ist im GRUB-Boot-Menü verfügbar:
- **🛠 GRUB Recovery System** - Recovery-Modus
- **🛠 GRUB Notfall-Shell** - Direkter Shell-Zugriff
- **🛠 GRUB Single User Mode** - Single-User-Modus

## 📁 Projektstruktur

```
grub-control-center-fixed/
├── lib/                          # Bibliotheken
│   ├── config.sh                 # Zentrale Konfiguration
│   ├── logging.sh                # Logging-Funktionen
│   ├── validation.sh             # Input-Validierung
│   ├── backup.sh                 # Backup & Rollback
│   ├── grub.sh                   # GRUB-Operationen
│   ├── cleanup.sh                # Cleanup-Handler
│   ├── recovery.sh               # Recovery-Setup
│   └── theme.sh                  # Theme-Management
├── scripts/                      # Ausführbare Skripte
│   ├── grub-control-center.sh    # Hauptprogramm
│   ├── grub-check.sh             # System-Analyse
│   └── recovery.sh               # Recovery-Script
├── docs/                         # Dokumentation
│   ├── CHANGELOG.md              # Änderungsprotokoll
│   └── BUGFIXES.md               # Liste behobener Fehler
└── install.sh                    # Installationsskript
```

## 🔧 Konfiguration

### Zentrale Konfiguration
Alle Einstellungen in `lib/config.sh`:
- Installationsverzeichnisse
- Log-Dateien
- Limits (Backup-Anzahl, Bildgröße, etc.)

### Log-Dateien
- **Benutzer-Log**: `~/grub-control-center.log`
- **Fehler-Log**: `~/grub-control-center_errors.log`
- **System-Log**: `/var/log/grub-control-center/system.log`
- **Installations-Log**: `/var/log/grub-control-center/install.log`

## 🛠️ Fehlerbehebung

### Problem: Recovery-Menü bootet nicht
**Lösung**: Führe `sudo grub-check` aus und prüfe, ob die UUID korrekt erkannt wurde.

### Problem: Theme-Download schlägt fehl
**Lösung**: 
- Prüfe Internetverbindung
- Validiere GitHub-URL (Format: https://github.com/user/repo)
- Prüfe ob git installiert ist

### Problem: GRUB-Update fehlgeschlagen
**Lösung**: 
- Das Programm führt automatisch einen Rollback durch
- Prüfe die Logs in `~/grub-control-center_errors.log`
- Führe `sudo grub-check` aus

## 📊 Unterschiede zu v1.0

| Feature | v1.0 | v2.1 |
|---------|------|------|
| Recovery-UUID | ❌ Hardcoded | ✅ Automatisch erkannt |
| URL-Validierung | ❌ Logikfehler | ✅ Korrekt |
| Backup-System | ⚠️ Race Condition | ✅ Sicher |
| Logging | ❌ Defekt | ✅ Funktioniert |
| Code-Struktur | ⚠️ Monolithisch | ✅ Modular |
| Rollback | ❌ Nicht vorhanden | ✅ Automatisch |
| Quoting | ⚠️ Teilweise | ✅ Vollständig |
| Temp-Dateien | ⚠️ Unsicher | ✅ Sicher (mktemp) |
| Distribution | ⚠️ Ubuntu-fokussiert | ✅ Unabhängig |

## 🔒 Sicherheit

- Alle Benutzereingaben werden validiert
- Temporäre Dateien werden sicher erstellt (mktemp)
- Automatische Cleanup-Handler verhindern Datei-Leaks
- Korrektes Quoting verhindert Code-Injection
- Bildvalidierung (Format, Größe)
- Rollback-Funktion bei Fehlern

## 📝 Lizenz

Dieses Projekt steht unter der MIT-Lizenz.

## 👥 Mitwirken

Fehlerberichte und Pull Requests sind willkommen!

## 📞 Support

Bei Problemen:
1. Führe `sudo grub-check` aus
2. Prüfe die Log-Dateien
3. Erstelle ein Issue mit den Logs

## 🙏 Danksagung

Basiert auf dem Original GRUB Control Center, vollständig überarbeitet mit:
- 20+ behobenen Fehlern und Sicherheitsproblemen
- Modularer Architektur
- Verbesserter Fehlerbehandlung
- Distributionsunabhängigkeit

---

**Version**: 2.1.0  
**Datum**: April 2026  
**Status**: Produktionsreif ✅
