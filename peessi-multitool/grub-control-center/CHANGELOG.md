# Changelog - GRUB Control Center

## Version 2.1.0 (April 2026)

### 🔴 Kritische Fehler behoben

#### 1. Recovery-System Boot-Parameter repariert
**Problem**: Hardcodiertes `root=LABEL=ROOT` funktionierte nur auf Systemen mit diesem Label  
**Lösung**: 
- Automatische Erkennung der Root-Partition mit `findmnt`
- UUID-basierte Boot-Parameter
- Drei Recovery-Modi: Recovery, Notfall-Shell, Single User Mode
- **Dateien**: `lib/recovery.sh`, `install.sh`

#### 2. URL-Regex Logikfehler korrigiert
**Problem**: Verwendete `&&` statt `||`, lehnte gültige GitHub-URLs ab  
**Lösung**: 
- Korrekter Regex mit OR-Logik
- Unterstützung für Punkte in Benutzernamen
- **Dateien**: `lib/validation.sh`, `lib/theme.sh`

#### 3. Race Condition bei Backups behoben
**Problem**: Schnelle Aufrufe innerhalb derselben Sekunde überschrieben Backups  
**Lösung**: 
- Timestamp mit Nanosekunden
- PID hinzugefügt
- Random-String für zusätzliche Eindeutigkeit
- **Dateien**: `lib/backup.sh`

#### 4. Logging-System repariert
**Problem**: Doppelte Shell-Umleitungen funktionierten nicht  
**Lösung**: 
- Separate echo-Statements für jedes Log
- Korrekte Fehlerbehandlung
- **Dateien**: `lib/logging.sh`

### 🔒 Sicherheitsverbesserungen

#### 5. Vollständiges Quoting implementiert
**Problem**: Fehlende Quotes bei Variablen führten zu Wortsplitting  
**Lösung**: 
- Alle Variablen korrekt gequotet
- Sanitization von Disk/Partition-Namen
- **Dateien**: Alle Scripts

#### 6. Sichere temporäre Dateien
**Problem**: Vorhersehbare Temp-Namen (Race Condition möglich)  
**Lösung**: 
- mktemp für alle temporären Dateien/Verzeichnisse
- Automatische Registrierung für Cleanup
- **Dateien**: `lib/cleanup.sh`, `lib/theme.sh`

#### 7. Input-Validierung verbessert
**Problem**: Ungeprüfte Benutzereingaben  
**Lösung**: 
- Validierungsfunktionen für alle Eingabetypen
- Timeout-Bereichsprüfung (0-120)
- Block-Device-Validierung
- **Dateien**: `lib/validation.sh`

#### 8. Bildvalidierung implementiert
**Problem**: Keine Größen- oder Format-Prüfung  
**Lösung**: 
- Max. 5MB Größenprüfung
- MIME-Type-Validierung
- Sichere Konvertierung (JPEG→PNG)
- **Dateien**: `lib/validation.sh`, `lib/grub.sh`

### 📦 Code-Qualität & Wartbarkeit

#### 9. Modulare Struktur eingeführt
**Problem**: Monolithischer Code, schwer wartbar  
**Lösung**: 
- Bibliotheken in `lib/`
- Skripte in `scripts/`
- Zentrale Konfiguration in `lib/config.sh`
- **Dateien**: Komplette Neustrukturierung

#### 10. Code-Duplizierung entfernt
**Problem**: Recovery-Script 3x im Code vorhanden  
**Lösung**: 
- Einzelne Recovery-Script-Datei
- Wird von Installer kopiert
- **Dateien**: `scripts/recovery.sh`

#### 11. Rollback-Funktion hinzugefügt
**Problem**: Kein Rollback bei fehlgeschlagenem GRUB-Update  
**Lösung**: 
- Automatisches Backup vor Änderungen
- Rollback bei Fehler
- Funktion: `update_grub_with_rollback()`
- **Dateien**: `lib/grub.sh`, `lib/backup.sh`

#### 12. Cleanup-Handler implementiert
**Problem**: Temporäre Dateien wurden nicht aufgeräumt  
**Lösung**: 
- Trap-Handler für EXIT/INT/TERM
- Automatische Registrierung von Temp-Dateien
- **Dateien**: `lib/cleanup.sh`

#### 13. Distributionsunabhängigkeit
**Problem**: Nur `update-grub` (Ubuntu/Debian) unterstützt  
**Lösung**: 
- Unterstützt: update-grub, grub-mkconfig, grub2-mkconfig
- Automatische Erkennung
- **Dateien**: `lib/grub.sh`

#### 14. Zentrale Konfiguration
**Problem**: Hardcodierte Pfade überall  
**Lösung**: 
- Alle Konstanten in `lib/config.sh`
- Exportierte Variablen
- **Dateien**: `lib/config.sh`

#### 15. Sichere GRUB-Konfigurationsänderung
**Problem**: Keine Fehlerbehandlung bei sed  
**Lösung**: 
- Funktion `set_grub_config()` mit Fehlerprüfung
- Backup vor jeder Änderung
- **Dateien**: `lib/grub.sh`

### ✨ Neue Features

#### 16. Backup-Verwaltung
- Liste verfügbare Backups
- Automatische Bereinigung (max. 10 Backups)
- **Dateien**: `lib/backup.sh`

#### 17. Verbessertes Recovery-System
- 3 Recovery-Modi statt 1
- System-Informationen im Recovery-Menü
- Bessere Validierung
- **Dateien**: `scripts/recovery.sh`

#### 18. Debug-Modus
- Debug-Logging optional
- Variable: `DEBUG_MODE=1`
- **Dateien**: `lib/logging.sh`

#### 19. Fortschrittsanzeige
- Bei Theme-Download
- Funktion: `show_progress()`
- **Dateien**: `lib/logging.sh`, `scripts/grub-control-center.sh`

#### 20. Erweiterte Systemanalyse
- UUID-Validierung
- Root-Partition-Info
- Backup-Anzahl
- **Dateien**: `scripts/grub-check.sh`

### 🐛 Weitere Bugfixes

- Git-Clone mit `GIT_TERMINAL_PROMPT=0` (verhindert Passwort-Prompts)
- Theme-Suche rekursiv bis Tiefe 3
- Korrekte Behandlung leerer Arrays
- Verbesserte Fehlerausgaben
- Sichere `eval`-Nutzung entfernt

### 📊 Statistiken

- **Zeilen Code**: ~2500 (vorher: ~800)
- **Anzahl Funktionen**: 50+ (vorher: ~20)
- **Dateien**: 13 (vorher: 4)
- **Behobene Fehler**: 20
- **Neue Features**: 10+

### 🔄 Migration von v1.0

Die neue Version ist **nicht rückwärtskompatibel** mit v1.0.

**Migrations-Schritte**:
1. Deinstalliere alte Version (optional)
2. Installiere neue Version mit `sudo ./install.sh`
3. Das Recovery-System wird automatisch mit korrekter UUID neu erstellt
4. Alte Backups bleiben erhalten

### 📝 Breaking Changes

- Verzeichnisstruktur geändert (lib/ statt inline)
- Recovery-Script-Pfad: `/boot/grub/custom/recovery.sh` (unverändert)
- Neue Kommandos: `grub-check` zusätzlich zu `grub-control-center`

### 🎯 Getestete Umgebungen

- ✅ Ubuntu 20.04, 22.04, 24.04
- ✅ Debian 11, 12
- ✅ Linux Mint 21
- ⚠️ Fedora 39 (grundlegend getestet)
- ⚠️ Arch Linux (grundlegend getestet)

### 📚 Dokumentation

- Neue README mit vollständiger Dokumentation
- Inline-Kommentare in allen Funktionen
- Beispiele für jede Funktion

### 🔜 Bekannte Einschränkungen

- UEFI Secure Boot kann Recovery-Menü beeinträchtigen
- Theme-Download nur von GitHub
- GUI benötigt X11 (keine Wayland-spezifischen Features)

---

## Version 1.0 (März 2023)

Ursprüngliche Version mit bekannten Problemen (siehe Bugfixes in v2.1)
