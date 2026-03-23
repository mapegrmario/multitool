# 🛠️ Peeßi's System Multitool – Version 1.0 Alpha

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

Drittanbieter-Software (penguins-eggs, Ventoy, fresh-eggs) unterliegt den jeweiligen Lizenzen
und Haftungsausschlüssen der Autoren.

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
| 🔍 Datenrettung | Defekte Laufwerke retten via `ddrescue` + `photorec` |
| 🧹 Sicheres Löschen | dd, DoD 5220.22-M, Gutmann, ATA/NVMe Secure Erase |
| 📊 SMART-Monitor | Gesundheitsstatus, Temperatur, Verlauf in SQLite |
| 💿 ISO-Brenner | SHA256-Prüfung, Verifikation, USB-Clone-Sub-Tab |
| 🔁 USB-Clone | 1:1-Klon mit optionaler cmp-Verifikation |
| 🔗 Partition einbinden | Ein-/Aushängen mit automatischem fstab-Backup |
| 🐧 Penguins-Eggs | Live-ISO erstellen, Backup/Restore, fresh-eggs Installation |
| 🍃 Mint-Installer | DD/Full/Ventoy/Clone-Modi, Info, Systemvorbereitung |

### 🖥️ System
| Funktion | Beschreibung |
|---|---|
| 🧹 Systempflege | apt, Flatpak, Journal, Thumbnail-Cache |
| ⚡ Optimierer | Kernel-Tuning, Swap-Datei, Firefox Policies |
| 🥾 Boot-Check | fsck aktivieren/deaktivieren |
| ⚙️ BIOS/EFI | Boot-Reihenfolge, Einträge, Backup (efibootmgr) |
| 🔄 Update & Shutdown | Automatische Updates + Herunterfahren |
| 🚀 Einmal-Starter | Script einmalig beim nächsten Login ausführen |

### 🌐 Netzwerk
| Funktion | Beschreibung |
|---|---|
| Interfaces | IP, MAC, Status aller Netzwerkschnittstellen |
| 🏓 Ping | Host anpingen |
| 🔌 Verbindungen | Aktive TCP/UDP-Verbindungen, sortierbar, kopierbar |
| 🔑 WLAN-Passwörter | Gespeicherte Keys aus NetworkManager |

### 📋 Logs & Diagnose
Vollständiger Log-Viewer + HTML-Systembericht

### ❓ Hilfe
Inline-Dokumentation mit Suchfunktion und Haftungsausschluss

---

## Installation

```bash
sudo bash install-peessi-multitool.sh
```

Das Skript installiert alle Abhängigkeiten, kopiert Dateien nach
`/usr/local/lib/peessi-multitool/` und erstellt Startmenü-Eintrag.

### Update (ohne Neuinstallation)

```bash
sudo bash update.sh
```

### Diagnose bei Problemen

```bash
bash diagnose.sh
bash netzwerk-diagnose.sh
```

### Starten

```bash
peessi-multitool
```

### Deinstallation

```bash
sudo /usr/local/lib/peessi-multitool/uninstall.sh
```

---

## Drittanbieter-Software

| Software | Autor | Lizenz | URL |
|---|---|---|---|
| **penguins-eggs** | Piero Proietti | GPLv3 | https://github.com/pieroproietti/penguins-eggs |
| **fresh-eggs** | Piero Proietti | GPLv3 | https://github.com/pieroproietti/fresh-eggs |
| **Ventoy** | Ventoy-Team | GPLv3 | https://github.com/ventoy/Ventoy |

---

## Changelog

### Version 1.0 Alpha (2026-03)
- Erste öffentliche Alpha-Version
- Haftungsausschluss in Über-Tab, Hilfe-Tab und README
- Mint-Installer Info-Tab: nutzt jetzt korrekte Laufwerks-Erkennung
- Netzwerk/Verbindungen: asynchrones Laden, sortierbar, Fallback auf netstat
- eggs AppImage: GitHub API + Dateigrößen-Validierung
- USB-Clone als Sub-Tab im ISO-Brenner
- bind_all/unbind_all entfernt (X11-Schutz)
- Maus-Scrolling in allen scrollbaren Bereichen

---

*Peeßi's System Multitool – Open Source, made in Großenhain 🇩🇪*
