# CONTRIBUTING – Peeßi's System Multitool v4.2

> Dieses Dokument erklärt Entwicklern wie das Programm aufgebaut ist
> und wie neue Funktionen korrekt hinzugefügt werden.

---

## Architektur-Überblick

```
main.py               → App-Klasse: Root-Fenster, Tabs registrieren, Statusleiste
config.py             → Einstellungen laden/speichern, Konstanten (VERSION, ORIGINAL_USER)
i18n.py               → Übersetzungen DE/EN – T("schlüssel") gibt den Text zurück
gui_base.py           → GuiBase-Basisklasse: Log, Shell-Async, Scrollbar, Sicherheit
gui_system.py         → System-Tabs (Dashboard, Pflege, Boot, BIOS, Netzwerk, Logs, Einstellungen)
gui_drives.py         → Laufwerks-Tabs (Rettung, Löschen, ISO, Clone, Partition)
gui_drive_health.py   → Diagnose-Tab (SMART, Badblocks)
gui_grub.py           → GRUB Control Center Tab
gui_advanced.py       → Erweiterte Tabs (Images, Migration, LVM, RAID, Boot-Reparatur)
```

---

## Neuen Tab hinzufügen

### 1. Einfacher Tab (ohne Scroll)
```python
class MeinTab(GuiBase):
    def __init__(self, nb_main, app):
        super().__init__(app)
        self._build(nb_main)

    def _build(self, nb):
        T = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🔧 Mein Tab")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill="both", expand=True, padx=12, pady=10)
        # Widgets hier...
```

### 2. Scrollbarer Tab
```python
def _build(self, nb):
    _, pane = self.make_scrollable_tab(nb, "📋 Mein Scroll-Tab")
    pane.configure(padx=12, pady=10)
    # Widgets in pane packen...
```

### 3. Shell-Tab (Befehl ausführen + Log)
```python
def _build(self, nb):
    self.make_shell_tab(nb,
        title="🔧 Mein Tab",
        description="Kurze Erklärung was der Tab tut.",
        btn_label="Ausführen",
        command="bash /pfad/zum/script.sh"
    )
```

### 4. In main.py registrieren
```python
# in App._build_ui():
self.mein_tab = MeinTab(self.nb_main, self)
```

---

## Wichtige Hilfsmethoden (gui_base.py)

| Methode | Verwendung |
|---|---|
| `self.make_log_widget(parent, height)` | Scrollbares Log-Widget erstellen |
| `self.log_to(widget, text)` | Text ins Log schreiben (auto-farbig) |
| `self.clear_log(widget)` | Log leeren |
| `self.copy_log(widget)` | Log in Zwischenablage |
| `self.run_shell_async(cmd, log, btn)` | Befehl asynchron, Output ins Log |
| `self.make_scrollable_tab(nb, title)` | Scrollbarer Canvas-Tab |
| `self.make_shell_tab(nb, ...)` | Fertig-Tab mit Beschreibung+Log+Button |
| `GuiBase.check_device_safe(dev)` | Systemlaufwerk-Schutz vor destruktiven Ops |
| `GuiBase.is_system_device(dev)` | True wenn dev gemountet/kritisch |

---

## Sicherheits-Regeln

```python
# VOR jedem dd/shred/mdadm/lvcreate IMMER prüfen:
if not self.check_device_safe(dev):
    return  # Dialog wurde bereits gezeigt

# Bestätigung vor destruktiver Aktion:
if not messagebox.askyesno("Titel", "Wirklich?", icon="warning"):
    return
```

---

## Mehrsprachigkeit (i18n)

```python
from i18n import T

# Im Code statt hardcodiertem Text:
ttk.Button(f, text=T("btn_refresh"))   # "Aktualisieren" / "Refresh"
tk.Label(f,  text=T("lbl_output"))    # "Ausgabe" / "Output"

# Neue Übersetzung hinzufügen → i18n.py _STRINGS dict:
"mein_schluessel": {"de": "Deutsch", "en": "English"},
```

---

## Log-Farben (automatisch)

`log_to()` erkennt den Typ der Zeile automatisch:

| Zeilenbeginn | Farbe |
|---|---|
| `✅`, `OK`, `Fertig`, `installed` | 🟢 grün |
| `❌`, `Fehler`, `Error`, `failed` | 🔴 rot |
| `⚠️`, `Warning`, `Warnung` | 🟡 orange |
| `──`, `===`, `$ ...` | ⚫ grau |

---

## Konventionen

- **Alle Befehle asynchron** via `run_shell_async()` oder `threading.Thread`
- **Niemals `shell=True` mit User-Input** (Shell-Injection)
- **Destruktive Buttons** → `style="Danger.TButton"` + `⚠️` im Label
- **Theme-Farben** immer aus `T = self.theme` – nie hardcodierte Hex-Werte
- **Prozesse** in `self._proc` speichern damit `_on_close()` sie beenden kann
- **Exceptions** nie mit `except: pass` – mindestens `logging.warning()`

---

## Dateien die NICHT verändert werden sollten

| Datei | Grund |
|---|---|
| `security.py` | Sicherheits-Audit-Log – nur mit Bedacht ändern |
| `models.py` | Datenmodelle – Änderungen brechen DB-Kompatibilität |
| `database.py` | SQLite-Schema – Migration nötig bei Änderungen |
| `grub-control-center/` | Externe Komponente (MIT-Lizenz) |

---

## Branches / Releases

- Änderungen werden als `peessi-fixNN.zip` geliefert
- Major-Versionen (v4.1 → v4.2): config.py + main.py + gui_system.py VERSION-String
- CHANGELOG.md bei jedem Release aktualisieren
