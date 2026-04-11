"""
gui_grub.py – GRUB Control Center Tab für Peeßi's System Multitool
Separate Datei für einfache Wartung.

Integriert GRUB Control Center v2.1.1 (Shell-Scripts in grub-control-center/)
als GUI-Tab unter System. Alle Shell-Scripts bleiben unberührt.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import os
import sys

# Installationsverzeichnis des Multitools
_INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))
GRUB_DIR     = os.path.join(_INSTALL_DIR, "grub-control-center")
GRUB_MAIN    = os.path.join(GRUB_DIR, "scripts", "grub-control-center.sh")
GRUB_CHECK   = os.path.join(GRUB_DIR, "scripts", "grub-check.sh")
GRUB_CONFIG  = "/etc/default/grub"
GRUB_THEMES  = "/boot/grub/themes"
GRUB_BACKUP  = "/boot/grub.bak"


def _run(cmd: str, timeout: int = 30) -> tuple[int, str, str]:
    """Führt Shell-Befehl aus und gibt (returncode, stdout, stderr) zurück."""
    try:
        r = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout nach {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def _grub_cmd(subcmd: str) -> str:
    """Baut einen Befehl der die GRUB-Bibliotheken lädt und dann subcmd ausführt."""
    lib_sources = " ".join(
        f'source "{GRUB_DIR}/lib/{lib}.sh"'
        for lib in ["config", "logging", "validation", "backup", "grub",
                    "cleanup", "recovery", "theme"]
        if os.path.isfile(f"{GRUB_DIR}/lib/{lib}.sh")
    )
    return f'bash -c \'{lib_sources}; {subcmd}\''


class GrubTab:
    """
    GRUB Control Center Tab.
    Wird von SystemTab._build_grub_tab() instanziiert.
    """

    def __init__(self, nb: ttk.Notebook, app, theme: dict):
        self.app   = app
        self.root  = app.root
        self.T     = theme
        self._build(nb)

    # ──────────────────────────────────────────────────────────────────────
    def _build(self, nb: ttk.Notebook):
        T = self.T
        tab = ttk.Frame(nb)
        nb.add(tab, text="🔧 GRUB")

        # Scrollbarer Bereich
        canvas = tk.Canvas(tab, bg=T["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        pane = tk.Frame(canvas, bg=T["bg"])
        win  = canvas.create_window((0, 0), window=pane, anchor="nw")
        pane.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))
        def _sc(ev):
            if ev.delta: canvas.yview_scroll(int(-1*(ev.delta/120)), "units")
            elif ev.num == 4: canvas.yview_scroll(-1, "units")
            elif ev.num == 5: canvas.yview_scroll(1, "units")
        canvas.bind("<MouseWheel>", _sc)
        canvas.bind("<Button-4>",   _sc)
        canvas.bind("<Button-5>",   _sc)

        inner = tk.Frame(pane, bg=T["bg"])
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        # ── Status ────────────────────────────────────────────────────────
        stat_f = ttk.LabelFrame(inner, text=" GRUB Status ", padding=8)
        stat_f.pack(fill="x", pady=(0, 8))
        self._status_lbl = tk.Label(stat_f, text="Prüfe...",
                                     bg=T["bg"], font=("Arial", 10, "bold"))
        self._status_lbl.pack(anchor="w")
        self._version_lbl = tk.Label(stat_f, text="",
                                      bg=T["bg"], fg=T["fg_dim"], font=("Arial", 9))
        self._version_lbl.pack(anchor="w")
        ttk.Button(stat_f, text="🔄 Status prüfen",
                   command=self._check_status).pack(anchor="w", pady=(6, 0))
        self.root.after(400, self._check_status)

        # ── Boot-Einstellungen ─────────────────────────────────────────────
        boot_f = ttk.LabelFrame(inner, text=" ⚙️ Boot-Einstellungen ", padding=8)
        boot_f.pack(fill="x", pady=(0, 8))

        # Timeout
        to_row = tk.Frame(boot_f, bg=T["bg"])
        to_row.pack(fill="x", pady=(0, 6))
        tk.Label(to_row, text="Boot-Timeout (Sekunden):",
                 bg=T["bg"], fg=T["fg"], font=("Arial", 10)).pack(side="left", padx=(0, 8))
        self._timeout_var = tk.StringVar(value="5")
        ttk.Entry(to_row, textvariable=self._timeout_var, width=8).pack(side="left")
        ttk.Button(to_row, text="✔ Setzen",
                   command=self._set_timeout).pack(side="left", padx=6)
        ttk.Button(to_row, text="📖 Lesen",
                   command=self._read_timeout).pack(side="left")

        # Standard-Eintrag
        def_row = tk.Frame(boot_f, bg=T["bg"])
        def_row.pack(fill="x", pady=(0, 6))
        tk.Label(def_row, text="Standard-Boot-Eintrag (Nummer):",
                 bg=T["bg"], fg=T["fg"], font=("Arial", 10)).pack(side="left", padx=(0, 8))
        self._default_var = tk.StringVar(value="0")
        ttk.Entry(def_row, textvariable=self._default_var, width=8).pack(side="left")
        ttk.Button(def_row, text="✔ Setzen",
                   command=self._set_default).pack(side="left", padx=6)
        ttk.Button(def_row, text="📋 Einträge anzeigen",
                   command=self._list_entries).pack(side="left")

        # ── Design & Themes ────────────────────────────────────────────────
        theme_f = ttk.LabelFrame(inner, text=" 🎨 Design & Themes ", padding=8)
        theme_f.pack(fill="x", pady=(0, 8))

        bg_row = tk.Frame(theme_f, bg=T["bg"])
        bg_row.pack(fill="x", pady=(0, 6))
        tk.Label(bg_row, text="Hintergrundbild:",
                 bg=T["bg"], fg=T["fg"], font=("Arial", 9)).pack(side="left", padx=(0, 6))
        self._bg_var = tk.StringVar()
        ttk.Entry(bg_row, textvariable=self._bg_var, width=40).pack(side="left", padx=(0, 4))
        ttk.Button(bg_row, text="📂",
                   command=lambda: self._bg_var.set(
                       filedialog.askopenfilename(
                           title="Hintergrundbild wählen",
                           filetypes=[("Bilder", "*.png *.jpg *.jpeg *.tga"),
                                      ("Alle", "*")]
                       ) or self._bg_var.get()
                   )).pack(side="left", padx=(0, 4))
        ttk.Button(bg_row, text="✔ Setzen",
                   command=self._set_background).pack(side="left")

        # Theme aktivieren
        th_row = tk.Frame(theme_f, bg=T["bg"])
        th_row.pack(fill="x", pady=(0, 6))
        tk.Label(th_row, text="Theme aktivieren:",
                 bg=T["bg"], fg=T["fg"], font=("Arial", 9)).pack(side="left", padx=(0, 6))
        self._theme_cb = ttk.Combobox(th_row, width=30, state="readonly")
        self._theme_cb.pack(side="left", padx=(0, 4))
        ttk.Button(th_row, text="🔄", width=3,
                   command=self._refresh_themes).pack(side="left", padx=(0, 4))
        ttk.Button(th_row, text="✔ Aktivieren",
                   command=self._activate_theme).pack(side="left")
        self._refresh_themes()

        # Theme downloaden
        dl_row = tk.Frame(theme_f, bg=T["bg"])
        dl_row.pack(fill="x")
        tk.Label(dl_row, text="Theme von GitHub:",
                 bg=T["bg"], fg=T["fg"], font=("Arial", 9)).pack(side="left", padx=(0, 6))
        self._dl_var = tk.StringVar(value="https://github.com/")
        ttk.Entry(dl_row, textvariable=self._dl_var, width=40).pack(side="left", padx=(0, 4))
        ttk.Button(dl_row, text="⬇ Download",
                   command=self._download_theme).pack(side="left")

        # ── Backup & GRUB aktualisieren ────────────────────────────────────
        act_f = ttk.LabelFrame(inner, text=" 🛡️ Backup & Aktionen ", padding=8)
        act_f.pack(fill="x", pady=(0, 8))
        btn_row = tk.Frame(act_f, bg=T["bg"])
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="💾 Backup erstellen",
                   command=self._create_backup).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="📋 Backups anzeigen",
                   command=self._list_backups).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="🔄 GRUB aktualisieren",
                   style="Accent.TButton",
                   command=self._update_grub).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="🔍 System analysieren",
                   command=self._run_check).pack(side="left")

        # ── Vollprogramm starten ───────────────────────────────────────────
        full_f = ttk.LabelFrame(inner,
            text=" 🖥️ Vollprogramm (GRUB Control Center) ", padding=8)
        full_f.pack(fill="x", pady=(0, 8))
        tk.Label(full_f, text=(
            "Startet GRUB Control Center v2.1.1 mit vollständiger GUI (zenity).\n"
            "Enthält Recovery-System, Theme-Download, Backup-Verwaltung u.v.m."
        ), bg=T["bg"], fg=T["fg_dim"], font=("Arial", 9)).pack(anchor="w")
        btn2 = tk.Frame(full_f, bg=T["bg"])
        btn2.pack(fill="x", pady=(8, 0))
        ttk.Button(btn2, text="🚀 Vollprogramm starten",
                   style="Accent.TButton",
                   command=self._start_full).pack(side="left", padx=(0, 6))
        ttk.Button(btn2, text="🔍 Nur System-Analyse",
                   command=self._run_check).pack(side="left")

        # ── Ausgabe-Log ────────────────────────────────────────────────────
        log_f = ttk.LabelFrame(inner, text=" Ausgabe ", padding=6)
        log_f.pack(fill="both", expand=True)
        from tkinter import scrolledtext
        self._log = scrolledtext.ScrolledText(
            log_f, height=12, state="disabled",
            font=("Monospace", 9),
            bg=T.get("bg2", T["bg"]), fg=T["fg"])
        self._log.pack(fill="both", expand=True)
        btn3 = tk.Frame(inner, bg=T["bg"])
        btn3.pack(fill="x", pady=(4, 0))
        ttk.Button(btn3, text="🗑 Log leeren",
                   command=self._clear_log).pack(side="left")
        ttk.Button(btn3, text="📋 Kopieren",
                   command=self._copy_log).pack(side="left", padx=6)

    # ──────────────────────────────────────────────────────────────────────
    # Hilfsfunktionen
    # ──────────────────────────────────────────────────────────────────────
    def _log_write(self, text: str):
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _copy_log(self):
        txt = self._log.get("1.0", "end")
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.root.update()

    def _run_async(self, cmd: str, done_cb=None):
        """Befehl asynchron ausführen, Ausgabe ins Log schreiben."""
        def worker():
            try:
                proc = subprocess.Popen(
                    ["bash", "-c", cmd],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True)
                for line in proc.stdout:
                    self.root.after(0, lambda l=line: self._log_write(l))
                proc.wait()
                self.root.after(0, lambda: self._log_write(
                    f"\n─── Beendet (Exit: {proc.returncode}) ───\n"))
                if done_cb:
                    self.root.after(0, done_cb)
            except Exception as e:
                self.root.after(0, lambda: self._log_write(f"Fehler: {e}\n"))
        threading.Thread(target=worker, daemon=True).start()

    def _scripts_available(self) -> bool:
        if not os.path.isfile(GRUB_MAIN):
            messagebox.showerror("GRUB Control Center fehlt",
                f"Skripte nicht gefunden:\n{GRUB_MAIN}\n\n"
                "Bitte install-peessi-multitool.sh erneut ausführen.")
            return False
        return True

    # ──────────────────────────────────────────────────────────────────────
    # Aktionen
    # ──────────────────────────────────────────────────────────────────────
    def _check_status(self):
        """GRUB-Installation prüfen."""
        def worker():
            ok, out, err = _run("grub-install --version 2>/dev/null || grub2-install --version 2>/dev/null")
            ver = (out + err).strip()[:80]
            cfg_ok = os.path.isfile(GRUB_CONFIG)
            scripts_ok = os.path.isfile(GRUB_MAIN)
            self.root.after(0, lambda: self._update_status(ver, cfg_ok, scripts_ok))
        threading.Thread(target=worker, daemon=True).start()

    def _update_status(self, ver: str, cfg_ok: bool, scripts_ok: bool):
        T = self.T
        if ver and cfg_ok:
            self._status_lbl.config(text="🟢 GRUB installiert", fg=T["success"])
            self._version_lbl.config(
                text=f"Version: {ver}  |  Config: {GRUB_CONFIG}"
                     f"  |  Scripts: {'✅' if scripts_ok else '❌ fehlen'}")
        else:
            self._status_lbl.config(text="🔴 GRUB nicht gefunden", fg=T["danger"])
            self._version_lbl.config(text="GRUB nicht installiert oder nicht erkannt")

    def _read_timeout(self):
        _, out, _ = _run(f"grep GRUB_TIMEOUT= {GRUB_CONFIG} | head -1")
        val = out.strip().replace("GRUB_TIMEOUT=", "").replace('"', "").strip()
        if val:
            self._timeout_var.set(val)
            self._log_write(f"Aktueller Timeout: {val} Sekunden\n")

    def _set_timeout(self):
        t = self._timeout_var.get().strip()
        if not t.isdigit() or not (0 <= int(t) <= 120):
            messagebox.showerror("Fehler", "Timeout muss 0–120 Sekunden sein.")
            return
        if not messagebox.askyesno("Timeout setzen",
            f"GRUB_TIMEOUT auf {t} Sekunden setzen\nund GRUB aktualisieren?"):
            return
        cmd = (f"sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT={t}/' {GRUB_CONFIG} && "
               f"update-grub 2>&1 || grub-mkconfig -o /boot/grub/grub.cfg 2>&1")
        self._clear_log()
        self._run_async(cmd)

    def _set_default(self):
        d = self._default_var.get().strip()
        if not d.isdigit():
            messagebox.showerror("Fehler", "Bitte eine Zahl eingeben.")
            return
        if not messagebox.askyesno("Standard setzen",
            f"Standard-Boot-Eintrag auf {d} setzen\nund GRUB aktualisieren?"):
            return
        cmd = (f"sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT={d}/' {GRUB_CONFIG} && "
               f"update-grub 2>&1 || grub-mkconfig -o /boot/grub/grub.cfg 2>&1")
        self._clear_log()
        self._run_async(cmd)

    def _list_entries(self):
        self._clear_log()
        self._log_write("=== Boot-Einträge ===\n")
        _, out, _ = _run("grep -E '^menuentry|^submenu' /boot/grub/grub.cfg "
                         "| nl -ba 2>/dev/null | head -30")
        self._log_write(out or "Keine Einträge gefunden.\n")

    def _refresh_themes(self):
        themes = []
        if os.path.isdir(GRUB_THEMES):
            themes = [d for d in os.listdir(GRUB_THEMES)
                      if os.path.isdir(os.path.join(GRUB_THEMES, d))]
        self._theme_cb["values"] = themes if themes else ["Kein Theme installiert"]
        if themes:
            self._theme_cb.current(0)

    def _activate_theme(self):
        theme = self._theme_cb.get()
        if not theme or theme == "Kein Theme installiert":
            messagebox.showinfo("Hinweis", "Kein Theme ausgewählt.")
            return
        theme_path = f"{GRUB_THEMES}/{theme}/theme.txt"
        if not os.path.isfile(theme_path):
            messagebox.showerror("Fehler",
                f"theme.txt nicht gefunden:\n{theme_path}")
            return
        if not messagebox.askyesno("Theme aktivieren",
            f"Theme '{theme}' aktivieren und GRUB aktualisieren?"):
            return
        cmd = (f"sed -i 's|^#\\?GRUB_THEME=.*|GRUB_THEME=\"{theme_path}\"|' "
               f"{GRUB_CONFIG} && "
               f"update-grub 2>&1 || grub-mkconfig -o /boot/grub/grub.cfg 2>&1")
        self._clear_log()
        self._run_async(cmd, done_cb=self._refresh_themes)

    def _set_background(self):
        bg = self._bg_var.get().strip()
        if not bg or not os.path.isfile(bg):
            messagebox.showerror("Fehler", "Bitte eine gültige Bilddatei wählen.")
            return
        if not messagebox.askyesno("Hintergrund setzen",
            f"Hintergrundbild setzen:\n{bg}\n\nGRUB aktualisieren?"):
            return
        cmd = (f"sed -i 's|^#\\?GRUB_BACKGROUND=.*|GRUB_BACKGROUND=\"{bg}\"|' "
               f"{GRUB_CONFIG} && "
               f"update-grub 2>&1 || grub-mkconfig -o /boot/grub/grub.cfg 2>&1")
        self._clear_log()
        self._run_async(cmd)

    def _download_theme(self):
        url = self._dl_var.get().strip()
        if not url.startswith("https://github.com/"):
            messagebox.showerror("Fehler",
                "Bitte eine GitHub-URL eingeben:\nhttps://github.com/user/repo")
            return
        if not messagebox.askyesno("Theme herunterladen",
            f"Theme von GitHub herunterladen?\n{url}"):
            return
        import re
        name = re.sub(r"[^a-zA-Z0-9_-]", "_",
                      url.rstrip("/").split("/")[-1])[:30]
        cmd = (f"mkdir -p '{GRUB_THEMES}' && "
               f"git clone --depth=1 '{url}' /tmp/grub-theme-dl 2>&1 && "
               f"cp -r /tmp/grub-theme-dl/* '{GRUB_THEMES}/{name}/' 2>&1 && "
               f"rm -rf /tmp/grub-theme-dl && "
               f"echo 'Theme installiert: {GRUB_THEMES}/{name}'")
        self._clear_log()
        self._run_async(cmd, done_cb=self._refresh_themes)

    def _create_backup(self):
        import datetime
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = f"/boot/grub/grub.cfg.backup_{ts}"
        self._clear_log()
        self._run_async(
            f"cp /boot/grub/grub.cfg '{dst}' && "
            f"cp {GRUB_CONFIG} '{GRUB_CONFIG}.backup_{ts}' && "
            f"echo 'Backups erstellt:' && echo '  {dst}' && "
            f"echo '  {GRUB_CONFIG}.backup_{ts}'")

    def _list_backups(self):
        self._clear_log()
        self._log_write("=== GRUB-Backups ===\n")
        _, out, _ = _run(
            "ls -lh /boot/grub/grub.cfg.backup_* /etc/default/grub.backup_* "
            "2>/dev/null | sort")
        self._log_write(out if out.strip() else "Keine Backups gefunden.\n")

    def _update_grub(self):
        if not messagebox.askyesno("GRUB aktualisieren",
            "GRUB-Konfiguration neu generieren?\n(update-grub)"):
            return
        self._clear_log()
        self._run_async(
            "update-grub 2>&1 || grub-mkconfig -o /boot/grub/grub.cfg 2>&1 || "
            "grub2-mkconfig -o /boot/grub2/grub.cfg 2>&1")

    def _run_check(self):
        if not self._scripts_available():
            # Fallback: einfache Prüfung ohne Script
            self._clear_log()
            self._run_async(
                "echo '=== GRUB Systemanalyse ==='; "
                "echo ''; "
                "grub-install --version 2>/dev/null || echo 'GRUB: nicht gefunden'; "
                "echo ''; "
                "echo '=== /etc/default/grub ==='; "
                "cat /etc/default/grub 2>/dev/null; "
                "echo ''; "
                "echo '=== Boot-Einträge ==='; "
                "grep -E '^menuentry|^submenu' /boot/grub/grub.cfg 2>/dev/null | head -20; "
                "echo ''; "
                "echo '=== Themes ==='; "
                f"ls /boot/grub/themes/ 2>/dev/null || echo 'Keine Themes'; "
                "echo ''; "
                "echo '=== Speicherplatz /boot ==='; "
                "df -h /boot")
            return
        self._clear_log()
        self._run_async(f"bash '{GRUB_CHECK}' 2>&1")

    def _start_full(self):
        if not self._scripts_available():
            return
        if not messagebox.askyesno("GRUB Control Center starten",
            "Startet GRUB Control Center v2.1.1 in einem neuen Terminal.\n\n"
            "Das Programm benötigt Root-Rechte und zenity (GUI)."):
            return
        # In neuem Terminal starten
        for term in ["x-terminal-emulator", "xterm", "gnome-terminal", "xfce4-terminal"]:
            try:
                subprocess.Popen(
                    [term, "-e",
                     f"bash -c 'bash \"{GRUB_MAIN}\" 2>&1; echo; read -p \"Enter zum Schließen...\"'"])
                return
            except FileNotFoundError:
                continue
        # Fallback: direkt im Log
        self._clear_log()
        self._log_write("Kein Terminal gefunden – starte Analyse im Log:\n\n")
        self._run_check()
