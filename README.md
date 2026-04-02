# 🛠️ Peeßi's System Multitool – Version 4.1

![Vorschau](vorschau1.png) # diese zeile bitte stehen lassen

> **🚧 Entwicklungsversion (Alpha) – nicht für produktiven Einsatz auf Produktivsystemen empfohlen.**

**Autor:** Mario Peeß, Großenhain  
**Kontakt:** mapegr@mailbox.org  
**Lizenz:** GPLv3 / MIT (kompatibel)  
**System:** Linux Mint / Debian / Ubuntu  

---

## ⚠️ Haftungsausschluss

**Dieses Programm wird OHNE JEDE GEWÄHRLEISTUNG bereitgestellt**, weder ausdrücklich noch implizit,
einschließlich der impliziten Gewährleistung der Marktgängigkeit oder Eignung für einen bestimmten Zweck.

**Die Nutzung erfolgt vollständig auf eigenes Risiko.**

- Operationen wie **Löschen (Wipe), ISO schreiben (dd), Formatieren und Klonen** sind **IRREVERSIBEL**
- Alle Daten auf dem Zielgerät werden **unwiderruflich gelöscht**
- **Immer Backup erstellen** bevor Sie fortfahren!
- Der Autor übernimmt **keine Haftung** für Datenverlust, Hardwareschäden oder sonstige Schäden

---

## Übersicht

Peeßi's System Multitool ist eine grafische Systemverwaltungs-Anwendung für Linux.
Sie fasst Werkzeuge für Datenrettung, Laufwerksverwaltung, Systempflege,
Netzwerkanalyse und Live-ISO-Erstellung in einer einheitlichen Oberfläche zusammen.

---

## Funktionen

### 💾 Laufwerke
| Funktion | Beschreibung |
|---|---|
| 🔍 Datenrettung | Defekte Laufwerke retten via `ddrescue` + `photorec`, Ergebnisse unter `~/Datenrettung_Ergebnisse` |
| 🧹 Sicheres Löschen | dd, DoD 5220.22-M, Gutmann, ATA/NVMe Secure Erase, Freien Speicher löschen (sfill/dd) |
| 📊 SMART-Monitor | Gesundheitsstatus, Temperatur, Verlauf in SQLite, als TXT exportierbar |
| 💿 ISO-Brenner | Alle Laufwerke wählbar (Systemlaufwerke mit Warnung), SHA256-Prüfung, automatische Verifikation |
| 🔁 USB-Clone | 1:1-Klon via dd mit optionaler cmp-Verifikation (Sub-Tab im ISO-Brenner) |
| 🔗 Partition einbinden | Dauerhaft via fstab, automatisches Backup vor jeder Änderung |

### 🖥️ System
| Funktion | Beschreibung |
|---|---|
| 🏠 Dashboard | CPU, RAM, Swap, Laufwerke, Uptime, Partitionsbalken in Echtzeit |
| 🧹 Systempflege | apt (Update/Upgrade/Autoremove), Flatpak, Journal leeren, Thumbnail-Cache |
| ⚡ Optimierer | Kernel-Tuning (BBR TCP, Swappiness), dynamische Swap-Datei, Firefox Low-Memory-Policies |
| 🥾 Boot-Check | fsck für / aktivieren/deaktivieren |
| ⚙️ BIOS/EFI | Boot-Reihenfolge, Einträge löschen, Timeout, Backup via efibootmgr |
| 🔄 Update & Shutdown | Automatische Updates + anschließendes Herunterfahren |
| 🚀 Einmal-Starter | Script einmalig beim nächsten Login ausführen (via .bashrc) |
| 🐧 Eggs-ISO | Live-ISO des laufenden Systems erstellen (siehe unten) |

### 🐧 Eggs-ISO (System-Tab)

Erstellt bootfähige Live-ISOs des laufenden Systems mit **penguins-eggs**.

| Option | Beschreibung |
|---|---|
| **ISO-Name** | Name erscheint im Boot-Menü (GRUB/rEFInd) |
| **Zielverzeichnis** | Erkannte Laufwerke als Auswahlliste (inkl. externer Festplatten/USB), 🔄 aktualisierbar, 📂 freie Auswahl |
| **Temp-Verzeichnis** | Temporäre Arbeitsdateien auf externes Laufwerk umleiten (sinnvoll bei ISO > 8 GB) |
| **Modus: Nur Programme** | System ohne persönliche Daten und Design |
| **Modus: Programme & Design** | Inkl. Theme, Icons, Wallpaper |
| **Modus: Vollklon** | Komplettes 1:1-Abbild des Systems |
| **Calamares** | Grafischen Installer in die ISO einbinden |
| **Bereinigen** | `apt-get clean && autoremove` vor der Erstellung |
| **Shutdown** | Rechner nach Fertigstellung automatisch herunterfahren |

> Vor der ersten Erstellung **„System vorbereiten (eggs dad -d)"** ausführen.  
> Voraussetzung: penguins-eggs installiert (wird von `install-peessi-multitool.sh` automatisch eingerichtet).

### 🌐 Netzwerk
| Funktion | Beschreibung |
|---|---|
| Interfaces | IP, MAC, Status aller Netzwerkschnittstellen |
| 🏓 Ping | Host anpingen (wählbare Anzahl) |
| 🔌 Verbindungen | Aktive TCP/UDP-Verbindungen (ss), sortierbar, in Zwischenablage kopierbar |
| 🔑 WLAN-Passwörter | Gespeicherte Keys aus NetworkManager auslesen (Root erforderlich) |

### 📋 Logs & Diagnose
| Funktion | Beschreibung |
|---|---|
| Log-Viewer | Journal, dmesg, syslog, auth.log, Peessi-Fehlerlog – mit Suche und Farbmarkierung |
| 🩺 Diagnose | Vollständiger Systembericht (Hardware, SMART, Netzwerk, Pakete) als TXT und HTML |

### ⚙️ Einstellungen
| Funktion | Beschreibung |
|---|---|
| Theme | Light / Dark (Catppuccin Mocha / Standard-Hell) |
| Schriftgrößen | UI und Monospace separat einstellbar |
| Farben | Benutzerdefinierte Farben für Haupttext, Akzent, Hintergrund |
| Fenster | Startgröße wählen (1400×900, 1200×800, 1600×1000, 1920×1080, Maximiert) |
| Verhalten | Standard-Löschmethode, SMART-Intervall, Desktop-Benachrichtigungen |

---

## Installation

```bash
sudo bash install-peessi-multitool.sh
```

Das Script installiert alle Abhängigkeiten, richtet Python-venv ein, kopiert Dateien nach
`/usr/local/lib/peessi-multitool/`, erstellt Starter, Startmenü-Eintrag und PolicyKit-Regel.
**penguins-eggs** wird automatisch via fresh-eggs installiert.

**Protokoll:** `~/peessi-install-DATUM.log`

### Update
```bash
sudo bash update.sh
```

### Starten
```bash
peessi-multitool
```

### Diagnose
```bash
sudo bash ~/peessi-analyse.sh
```
Erstellt `~/peessi-analyse-DATUM.log` + `~/peessi-analyse-kurz.txt`

### Deinstallieren
```bash
sudo /usr/local/lib/peessi-multitool/uninstall.sh
```

---

## penguins-eggs manuell reparieren

Falls eggs defekt oder nicht gefunden:

```bash
cd /tmp && rm -rf fresh-eggs
git clone https://github.com/pieroproietti/fresh-eggs
cd fresh-eggs && yes "" | bash fresh-eggs.sh
```

---

## Drittanbieter

| Software | Autor | Lizenz | URL |
|---|---|---|---|
| penguins-eggs | Piero Proietti | GPLv3 | https://github.com/pieroproietti/penguins-eggs |
| fresh-eggs | Piero Proietti | GPLv3 | https://github.com/pieroproietti/fresh-eggs |
| Ventoy | Ventoy-Team | GPLv3 | https://github.com/ventoy/Ventoy |
