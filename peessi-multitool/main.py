#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║         Peeßi's System Multitool  –  Version 4.1               ║
║                                                                  ║
║  Autor  : Mario Peeß, Großenhain  |  mapegr@mailbox.org         ║
║  Lizenz : GPLv3 / MIT (kompatibel)                              ║
║  System : Linux Mint / Debian / Ubuntu                          ║
╚══════════════════════════════════════════════════════════════════╝

Einstiegspunkt. Startet nur die App-Klasse.

Module:
  config.py          Pfade, Themes, Einstellungen
  models.py          DriveInfo, DriveScanner, USBInfo
  database.py        SmartDatabase (SQLite-Verlauf)
  security.py        SecurityManager, Audit-Log, fstab-Backup
  smart_engine.py    SMART-Auswertung (korrekter Exit-Code!)
  wipe_engine.py     Sicheres Löschen
  recovery_engine.py Datenrettung via ddrescue + photorec
  gui_base.py        Theme, Hilfsmethoden (GuiBase)
  gui_drives.py      Laufwerke-Tabs (DrivesTabs)
  gui_system.py      System/Netzwerk/Logs/Einstellungen/Über
  main.py            ← diese Datei
"""

import sys
import os

# ── venv site-packages einbinden (fuer zukuenftige optionale Pakete) ─────────

_VENV_SITE = "/usr/local/lib/peessi-multitool/venv/lib/python3.12/site-packages"
_VENV_SITE_FALLBACK_PATTERN = "/usr/local/lib/peessi-multitool/venv/lib/python3.*/site-packages"

def _inject_venv_path():
    """Fügt venv site-packages in sys.path ein, falls noch nicht vorhanden."""
    import glob as _glob

    # Zuerst exakten Pfad versuchen (python3.12)
    candidates = [_VENV_SITE]

    # Fallback: alle python3.x Versionen im venv
    candidates += _glob.glob(_VENV_SITE_FALLBACK_PATTERN)

    for site in candidates:
        if os.path.isdir(site) and site not in sys.path:
            # An Position 1 einfügen (nach '' für lokale Importe, vor System-Paketen)
            sys.path.insert(1, site)
            return True
    return False

_venv_injected = _inject_venv_path()

# ── Ab hier normaler Programmablauf ──────────────────────────────────────────
import traceback
import datetime
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

# ── Früher Import-Check & Fehlerlog ──────────────────────────────────────────
from config import ERROR_LOG_FILE, ORIGINAL_USER, VERSION, THEMES, load_settings
from config import INSTALL_DIR

def _log_exception(exc_type, exc_value, exc_tb):
    try:
        with open(ERROR_LOG_FILE, "a") as f:
            f.write(f"\n--- {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _log_exception

# ── Tkinter sicherstellen ─────────────────────────────────────────────────────
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
except ImportError:
    print("FEHLER: python3-tk fehlt!")
    print("Bitte installieren: sudo apt install python3-tk")
    sys.exit(1)

# ── Alle eigenen Module importieren ───────────────────────────────────────────
try:
    from security       import SecurityManager
    from database       import SmartDatabase
    from models         import DriveScanner, USBInfo
    from wipe_engine    import WipeEngine
    from recovery_engine import RecoveryEngine
    from gui_base       import GuiBase
    from gui_drives     import DrivesTabs
    from gui_system     import (DashboardTab, SystemTab, NetworkTab,
                                LogsTab, SettingsTab, AboutTab)
except ImportError as e:
    print(f"FEHLER: Modul konnte nicht geladen werden: {e}")
    print(f"Installationsverzeichnis: {INSTALL_DIR}")
    print("Bitte neu installieren: sudo ./install-peessi-multitool.sh")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
#  HAUPT-APP
# ══════════════════════════════════════════════════════════════════════════════
class App:
    def __init__(self):
        self.settings = load_settings()
        self.theme    = THEMES[self.settings.get("theme", "light")]

        # Kern-Objekte
        self.sec      = SecurityManager()
        self.smart_db = SmartDatabase()
        self.scanner  = DriveScanner(self.sec)
        self.wipe_eng = WipeEngine(self.sec, self._progress)
        self.rec_eng  = RecoveryEngine(self.sec, self._progress, self._set_progress_pct)
        self.usb_info = USBInfo(self.sec)

        self.all_drives            = []
        self._progress_pct_var     = None  # wird von DrivesTabs gesetzt
        self._log_widgets          = []

        # Tkinter-Root
        self.root = tk.Tk()
        self.root.title(f"Peeßi's System Multitool  v{VERSION}")
        self.root.geometry("1400x900")
        self.root.minsize(1100, 750)

        self._build_ui()
        self._startup_checks()
        self.refresh_drives()
        self._start_dashboard_updater()
        self.sec.log_action("APPLICATION_START", details=f"v{VERSION}")

    # ── UI-Aufbau ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        T = self.theme

        # Header
        hdr = tk.Frame(self.root, bg=T["bg_header"], height=64)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🛠️ Peeßi's System Multitool",
                 font=('Arial', 20, 'bold'),
                 bg=T["bg_header"], fg=T["fg_header"]).pack(side='left', padx=20, pady=14)
        tk.Label(hdr, text=f"v{VERSION}  |  👤 {ORIGINAL_USER}",
                 font=('Arial', 10),
                 bg=T["bg_header"], fg="#aab").pack(side='left', padx=10, pady=14)

        right = tk.Frame(hdr, bg=T["bg_header"])
        right.pack(side='right', padx=15)
        icon = "🌙" if self.settings["theme"] == "light" else "☀️"
        self.theme_btn = tk.Button(right, text=icon,
                                   font=('Arial', 14), bg=T["bg_header"],
                                   fg=T["fg_header"], bd=0, cursor='hand2',
                                   command=self._toggle_theme)
        self.theme_btn.pack(side='right', padx=8, pady=14)
        root_text = "🟢 Root" if os.geteuid() == 0 else "🔴 Kein Root"
        tk.Label(right, text=root_text, font=('Arial', 10),
                 bg=T["bg_header"], fg=T["fg_header"]).pack(side='right', padx=8)

        # Haupt-Notebook
        self.nb_main = ttk.Notebook(self.root)
        self.nb_main.pack(fill='both', expand=True, padx=8, pady=(4, 0))

        # Alle Tabs erzeugen (Reihenfolge = Anzeige-Reihenfolge)
        self.dashboard_tab = DashboardTab(self.nb_main, self)
        self.drives_tab    = DrivesTabs(self.nb_main, self)
        self.system_tab    = SystemTab(self.nb_main, self)
        self.network_tab   = NetworkTab(self.nb_main, self)
        self.logs_tab      = LogsTab(self.nb_main, self)
        self.settings_tab  = SettingsTab(self.nb_main, self)
        self.about_tab     = AboutTab(self.nb_main, self)

        # Statusleiste
        tk.Frame(self.root, bg=T["border"], height=1).pack(fill='x')
        sbar = tk.Frame(self.root, bg=T["bg2"], height=28)
        sbar.pack(fill='x')
        self.status_var = tk.StringVar(value="Bereit.")
        tk.Label(sbar, textvariable=self.status_var, font=('Arial', 9),
                 bg=T["bg2"], fg=T["fg_dim"], anchor='w').pack(side='left', padx=12, pady=5)
        ttk.Button(sbar, text="Beenden",
                   command=self.root.quit).pack(side='right', padx=8, pady=3)

        # Theme auf alle Widgets anwenden
        self.settings_tab.apply_theme()

    # ── Theme umschalten ──────────────────────────────────────────────────────
    def _toggle_theme(self):
        new = "dark" if self.settings["theme"] == "light" else "light"
        self.settings["theme"] = new
        self.theme = THEMES[new]
        from config import save_settings
        save_settings(self.settings)
        # Alle Tab-Instanzen informieren
        for tab in [self.dashboard_tab, self.drives_tab, self.system_tab,
                    self.network_tab, self.logs_tab, self.settings_tab, self.about_tab]:
            tab.theme = self.theme
        self.settings_tab.apply_theme()
        self.settings_tab.rebuild_log_colors()
        icon = "☀️" if new == "light" else "🌙"
        self.theme_btn.config(text=icon)

    # ── Startup-Prüfungen ─────────────────────────────────────────────────────
    def _startup_checks(self):
        # Root-Prüfung
        if os.geteuid() != 0:
            messagebox.showerror("Root-Rechte fehlen",
                "Bitte mit Root-Rechten starten:\n\n"
                "  pkexec peessi-multitool\n"
                "  sudo python3 /usr/local/lib/peessi-multitool/main.py")
            self.sec.log_action("PRIVILEGE_ERROR")
            sys.exit(1)

        # Fehlende Tools anbieten
        missing = []
        for tool, pkg in {
            'ddrescue':   'gddrescue',
            'photorec':   'testdisk',
            'smartctl':   'smartmontools',
            'hdparm':     'hdparm',
        }.items():
            if not shutil.which(tool):
                missing.append(f"• {tool}  (Paket: {pkg})")
        if missing:
            if messagebox.askyesno("Fehlende Tools",
                "Folgende Tools fehlen:\n" + "\n".join(missing) + "\n\nJetzt installieren?"):
                pkgs = [m.split("Paket: ")[1].rstrip(")") for m in missing]
                subprocess.run(['apt', 'install', '-y'] + pkgs, check=False)

    # ── Laufwerke aktualisieren ───────────────────────────────────────────────
    def refresh_drives(self):
        self.all_drives = self.scanner.scan()
        self.drives_tab.refresh_drives(self.all_drives)
        self.status_var.set(f"Laufwerke: {len(self.all_drives)} erkannt.")

    # ── Progress-Callbacks (von Engines) ─────────────────────────────────────
    def _progress(self, message: str):
        """Leitet Engine-Nachrichten ins richtige Log-Widget."""
        if not message:
            return
        # Heuristik: in welchem Haupt-Tab sind wir gerade?
        try:
            tab_text = self.nb_main.tab(self.nb_main.select(), "text")
        except Exception:
            tab_text = ""
        if "Laufwerke" in tab_text:
            self.root.after(0, lambda m=message:
                            self.drives_tab.log_to(self.drives_tab.rec_log, m + "\n"))
        else:
            self.root.after(0, lambda m=message:
                            self.drives_tab.log_to(self.drives_tab.rec_log, m + "\n"))

    def _set_progress_pct(self, pct: float):
        if self._progress_pct_var:
            self.root.after(0, lambda: self._progress_pct_var.set(pct))

    # ── Dashboard-Aktualisierung ──────────────────────────────────────────────
    def _start_dashboard_updater(self):
        self._dash_tick_count = 0

        def _tick():
            try:
                self._dash_tick_count += 1
                # System-Karten (CPU/RAM/Disk): jeden Tick (5s)
                self.dashboard_tab._update_system_cards()
                # Laufwerke + SMART + Partitionsbalken: alle 6 Ticks (30s)
                # und beim ersten Start (tick 1)
                if self._dash_tick_count == 1 or self._dash_tick_count % 6 == 0:
                    self.dashboard_tab._update_drive_table(self.all_drives)
            except Exception:
                pass
            self.root.after(5000, _tick)
        self.root.after(800, _tick)

    # ── Programmstart ─────────────────────────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ── Einstieg ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.run()
