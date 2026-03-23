# 🛠️ Peeßi's System Multitool – Version 1.0 Alpha

> **🚧 Alpha-Version – nicht für produktiven Einsatz auf Produktivsystemen empfohlen.**

**Autor:** Mario Peeß, Großenhain | **Kontakt:** mapegr@mailbox.org  
**Lizenz:** GPLv3 / MIT (kompatibel) | **System:** Linux Mint / Debian / Ubuntu

---

## ⚠️ Haftungsausschluss

**Ohne jede Gewährleistung.** Nutzung auf eigenes Risiko.

- Löschen, Formatieren, ISO schreiben, Klonen → **IRREVERSIBEL, Datenverlust!**
- Vor jeder Operation **Backup erstellen**
- Kein Haftung für Datenverlust oder Schäden

---

## Funktionen (Übersicht)

| Tab | Funktion |
|---|---|
| 💾 **Laufwerke** | Datenrettung (ddrescue+photorec), Sicheres Löschen (dd/DoD/Gutmann/NVMe), SMART-Monitor |
| 💿 **ISO-Brenner** | SHA256-Prüfung, Verifikation, 🔁 USB-Clone direkt integriert |
| 🍃 **Mint-Installer** | DD/Full/Ventoy/Clone-Modi, Laufwerke, Info, Systemvorbereitung |
| 🐧 **Penguins-Eggs** | Live-ISO erstellen, fresh-eggs, AppImage, calamares, Backup/Restore |
| 🖥️ **System** | Pflege, Optimierer, Boot-Check, BIOS/EFI, Update+Shutdown, Einmal-Starter |
| 🌐 **Netzwerk** | Interfaces, Ping, Verbindungen (sortierbar+kopierbar), WLAN-Passwörter |
| 📋 **Logs & Diagnose** | Viewer, dmesg/syslog/journal, HTML-Systembericht |
| ❓ **Hilfe** | Vollständige Dokumentation mit Suchfunktion |
| ⚙️ **Einstellungen** | Theme, Farben, Schriftgrößen, Verhalten |

---

## Installation

```bash
sudo bash install-peessi-multitool.sh
```

### Update (ohne Neuinstallation)
```bash
sudo bash update.sh
```

### Diagnose bei Problemen
```bash
sudo bash ~/peessi-analyse.sh
```

### Starten / Deinstallieren
```bash
peessi-multitool
sudo /usr/local/lib/peessi-multitool/uninstall.sh
```

---

## Penguins-Eggs reparieren

Falls eggs defekt (wenige Bytes):
```bash
# Im Programm: Penguins-Eggs Tab → "🗑 Defekte eggs-Datei entfernen"
# Dann: "📦 fresh-eggs installieren"

# Oder manuell:
sudo rm /usr/bin/eggs /usr/local/bin/eggs 2>/dev/null
cd /tmp && rm -rf fresh-eggs
git clone https://github.com/pieroproietti/fresh-eggs
cd fresh-eggs && bash fresh-eggs.sh
```

---

## Drittanbieter

| Software | Autor | Lizenz |
|---|---|---|
| penguins-eggs | Piero Proietti | GPLv3 |
| fresh-eggs | Piero Proietti | GPLv3 |
| Ventoy | Ventoy-Team | GPLv3 |

---

## Changelog 1.0 Alpha (2026-03)

- Optimierer: Shell-Syntax-Fehler behoben (kein Heredoc mehr)
- Scrolling: Rekursive Bindung – funktioniert jetzt auf allen Child-Widgets
- fresh-eggs: Non-interaktive .deb-Installation (DEBIAN_FRONTEND=noninteractive)
- USB-Clone als Sub-Tab im ISO-Brenner integriert
- Netzwerk/Verbindungen: asynchron, sortierbar, netstat-Fallback
- eggs: Dateigröße-Validierung + "Defekte Datei entfernen"-Button
- Haftungsausschluss in Über-Tab, Hilfe-Tab und README
- Analyse-Script: 15 Bereiche, vollständiges Log nach ~/
