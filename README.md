# 🛠️ Peeßi's System Multitool – Version 1.0 Beta


![Vorschau](vorschau1.png)

**Autor:** Mario Peeß, Großenhain  
**Kontakt:** mapegr@mailbox.org  
**Lizenz:** GPLv3 / MIT (kompatibel)  
**System:** Linux Mint / Debian / Ubuntu  

---

## Übersicht

Peeßi's System Multitool ist eine umfassende grafische Systemverwaltungs-Anwendung für Linux.
Sie fasst häufig benötigte Werkzeuge für Datenrettung, Laufwerksverwaltung, Systempflege,
Netzwerkanalyse und Live-ISO-Erstellung in einer einheitlichen Oberfläche zusammen.

---

## Funktionen

### 💾 Laufwerke
| Funktion | Beschreibung |
|---|---|
| 🔍 Datenrettung | Defekte Laufwerke retten via `ddrescue` + `photorec` |
| 🧹 Sicheres Löschen | dd, DoD 5220.22-M (3-Pass), Gutmann (35-Pass), ATA/NVMe Secure Erase |
| 📊 SMART-Monitor | Gesundheitsstatus, Temperatur, Verlauf in SQLite |
| 💿 ISO-Brenner | SHA256-Prüfung + Verifikation, `mint_full_installer` |
| 🔁 USB-Clone | 1:1-Klon eines Laufwerks auf ein anderes |
| 🔗 Partition einbinden | Ein-/Aushängen mit automatischem fstab-Backup |
| 🐧 Penguins-Eggs | Live-ISO des laufenden Systems erstellen (Backup/Restore) |

### 🖥️ System
| Funktion | Beschreibung |
|---|---|
| 🧹 Systempflege | apt update/upgrade, autoremove, Flatpak, Journal, Thumbnail-Cache |
| ⚡ Optimierer | Kernel-Tuning (BBR-TCP, Swappiness), Swap-Datei, Firefox Policies |
| 🥾 Boot-Check | fsck beim Boot aktivieren/deaktivieren (pass-Wert in /etc/fstab) |
| ⚙️ BIOS/EFI | Boot-Reihenfolge, Einträge verwalten, Backup/Restore (efibootmgr) |
| 🔄 Update & Shutdown | Automatische Updates + anschließendes Herunterfahren |
| 🚀 Einmal-Starter | Script einmalig beim nächsten Login ausführen |

### 🌐 Netzwerk
| Funktion | Beschreibung |
|---|---|
| Interfaces | IP-Adressen, MAC, Status aller Netzwerkschnittstellen |
| 🏓 Ping | Host anpingen, Anzahl einstellbar |
| 🔌 Verbindungen | Aktive TCP/UDP-Verbindungen mit Prozess-Info (scrollbar) |
| 🔑 WLAN-Passwörter | Gespeicherte WLAN-Keys aus NetworkManager auslesen |

### 📋 Logs & Diagnose
| Funktion | Beschreibung |
|---|---|
| Log-Viewer | Journal, dmesg, syslog, kern.log, auth.log mit Farbmarkierung |
| 🩺 Diagnose | Vollständiger Systembericht als TXT + HTML |

### ❓ Hilfe
Vollständige Inline-Dokumentation aller Funktionen mit Suchfunktion.

---

## Installation

### Voraussetzungen
- Linux Mint, Ubuntu oder Debian (64-bit)
- Python 3.8 oder neuer
- Root-Rechte für die Installation

### Schnellinstallation

```bash
# Alle Dateien in einem Ordner ablegen, dann:
sudo ./install-peessi-multitool.sh
```

Das Skript erledigt automatisch:
1. Prüft alle System-Abhängigkeiten und installiert fehlende Pakete
2. Legt ein Python-venv an
3. Kopiert alle Programmdateien nach `/usr/local/lib/peessi-multitool/`
4. Erstellt Starter in `/usr/local/bin/peessi-multitool`
5. Erstellt Startmenü-Eintrag und Desktop-Verknüpfung
6. Richtet PolicyKit-Regel für passwortlosen GUI-Start ein
7. Installiert Live-ISO-Builder-Abhängigkeiten (install-deps.sh)
8. Kopiert USB-Installer-Dateien (prepare_system.sh, mint_full_installer.py)
9. Fragt nach Installation von penguins-eggs (optional)

### Programm starten

```bash
# Über Terminal:
peessi-multitool

# Oder: Startmenü → System → Peeßi's System Multitool
```

### Deinstallation

```bash
sudo /usr/local/lib/peessi-multitool/uninstall.sh
```

---

## Abhängige Skripte

### Live-ISO-Builder (`live-iso-ersteller/`)
| Datei | Beschreibung |
|---|---|
| `install-deps.sh` | Installiert alle Build-Abhängigkeiten (squashfs, xorriso, grub, live-boot) |
| `make-live.sh` | Hauptskript zum Erstellen einer installierbaren Live-ISO |
| `live-exclude.list` | Dateien/Ordner die aus der ISO ausgeschlossen werden |
| `rsync-test.sh` | Testet rsync-Ausschlüsse vor dem Build |

### USB-Installer (`linux auf usb/`)
| Datei | Beschreibung |
|---|---|
| `prepare_system.sh` | Installiert alle Tools für den USB-Installer; optional: Ventoy + Fresh Eggs |
| `mint_full_installer.py` | Vollständiger Linux Mint USB-Installer mit GUI |

---

## Drittanbieter-Software

Dieses Programm verwendet folgende externe Drittanbieter-Software:

| Software | Autor | Lizenz | URL |
|---|---|---|---|
| **penguins-eggs** | Piero Proietti | GPLv3 | https://github.com/pieroproietti/penguins-eggs |
| **fresh-eggs** | Piero Proietti | GPLv3 | https://github.com/pieroproietti/fresh-eggs |
| **Ventoy** | Ventoy-Team | GPLv3 | https://github.com/ventoy/Ventoy |

Die genannten Projekte werden nicht mitgeliefert, sondern bei Bedarf separat heruntergeladen.
Alle Urheberrechte verbleiben bei den jeweiligen Autoren.

---

## Dateistruktur

```
peessi-multitool/
├── main.py                  # Einstiegspunkt, App-Klasse
├── config.py                # Pfade, Themes, Einstellungen
├── models.py                # DriveInfo, DriveScanner, USBInfo
├── database.py              # SmartDatabase (SQLite-Verlauf)
├── security.py              # SecurityManager, Audit-Log, fstab-Backup
├── smart_engine.py          # SMART-Auswertung
├── wipe_engine.py           # Sicheres Löschen
├── recovery_engine.py       # Datenrettung via ddrescue + photorec
├── gui_base.py              # Basis-Klasse: Theme, Log-Hilfsmethoden
├── gui_drives.py            # Laufwerke-Tabs (inkl. Penguins-Eggs)
├── gui_system.py            # System/Netzwerk/Logs/Einstellungen/Über/Hilfe
├── install-peessi-multitool.sh  # Installationsskript
└── README.md                # Diese Datei

live-iso-ersteller/
├── install-deps.sh          # Build-Abhängigkeiten installieren
├── make-live.sh             # Live-ISO erstellen
├── live-exclude.list        # Ausschlussliste für rsync
└── rsync-test.sh            # Ausschlüsse testen

linux auf usb/
├── prepare_system.sh        # System für USB-Installer vorbereiten
└── mint_full_installer.py   # Vollständiger USB-Installer
```

---

## Konfiguration

Einstellungen werden gespeichert unter:
```
~/.config/peessi-multitool/settings.json
```

Audit-Log (Aktionen mit Root-Rechten):
```
~/.local/share/peessi-multitool/audit.log
```

SMART-Verlauf:
```
~/.config/peessi-multitool/smart_history.db
```

Fehlerprotokoll:
```
~/peessi_multitool_fehler.log
```

---

## Bekannte Einschränkungen (Beta)

- Penguins-Eggs: `syncfrom` / `syncto` benötigt eine laufende eggs-Installation
- BIOS/EFI-Funktionen erfordern UEFI-System und `efibootmgr`
- ATA Secure Erase ist nur auf nicht-eingebundenen, nicht-gefrorenen Laufwerken möglich
- Der Live-ISO-Builder benötigt ca. 8–15 GB freien Speicher

---

## Changelog

### Version 1.0 Beta (2026-03)
- Neuer Tab: 🐧 **Penguins-Eggs** (Live-ISO erstellen, Backup/Restore, Installation)
- Neuer Tab: ❓ **Hilfe** mit vollständiger Inline-Dokumentation und Suchfunktion
- Fix: **Über-Tab** – E-Mail-Link funktioniert jetzt korrekt (xdg-open)
- Fix: **Netzwerk/Verbindungen** – zeigt jetzt Daten korrekt an (ss-Parsing überarbeitet)
- Neu: **Mouse-Scrolling** in allen scrollbaren Bereichen (Dashboard, Hilfe, Penguins-Eggs)
- Neu: **Drittanbieter-Hinweise** (penguins-eggs, fresh-eggs, Ventoy) in Über-Tab und Code
- Erweiterung: **install-peessi-multitool.sh** bindet install-deps.sh, prepare_system.sh,
  mint_full_installer.py und optionale penguins-eggs-Installation ein
- Erweiterung: **ISO-Brenner** – mint_full_installer.py integriert
- Version als **1.0 Beta** gekennzeichnet

---

*Peeßi's System Multitool – Open Source, made in Großenhain 🇩🇪*
