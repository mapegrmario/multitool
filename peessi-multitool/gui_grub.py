"""
gui_grub.py – GRUB Control Center Tab für Peeßi's System Multitool v4.1
Separate Datei für einfache Wartung.

Integriert GRUB Control Center v2.1.1 direkt ins Multitool.
Alle GRUB-Operationen werden direkt in Python/Bash ausgeführt –
kein separater Prozess oder Terminal nötig.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import subprocess, threading, os, datetime, re

_INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))
GRUB_DIR     = os.path.join(_INSTALL_DIR, "grub-control-center")
GRUB_CHECK   = os.path.join(GRUB_DIR, "scripts", "grub-check.sh")
GRUB_CONFIG  = "/etc/default/grub"
GRUB_CFG     = "/boot/grub/grub.cfg"
GRUB_THEMES  = "/boot/grub/themes"


def _sh(cmd: str, timeout: int = 30) -> tuple:
    """Bash-Befehl ausführen → (rc, stdout, stderr)."""
    env = os.environ.copy()
    env.setdefault("SUDO_USER", env.get("USER", "root"))
    try:
        r = subprocess.run(["bash", "-c", cmd],
                           capture_output=True, text=True,
                           timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout ({timeout}s)"
    except Exception as e:
        return -1, "", str(e)


def _read_grub_value(key: str) -> str:
    """Wert aus /etc/default/grub lesen."""
    _, out, _ = _sh(f"grep -E '^{key}=' {GRUB_CONFIG} | head -1")
    val = out.strip().split("=", 1)[-1].strip().strip('"')
    return val


def _write_grub_value(key: str, value: str) -> bool:
    """Wert in /etc/default/grub setzen (erstellt falls nicht vorhanden)."""
    escaped = value.replace("/", "\\/").replace('"', '\\"')
    rc, _, err = _sh(
        f"grep -qE '^{key}=' {GRUB_CONFIG} && "
        f"sed -i 's|^{key}=.*|{key}=\"{escaped}\"|' {GRUB_CONFIG} || "
        f"echo '{key}=\"{value}\"' >> {GRUB_CONFIG}")
    return rc == 0


def _update_grub_cmd() -> str:
    """Ermittelt den richtigen update-grub Befehl."""
    for cmd in ["update-grub", "grub-mkconfig -o /boot/grub/grub.cfg",
                "grub2-mkconfig -o /boot/grub2/grub.cfg"]:
        rc, _, _ = _sh(f"command -v {cmd.split()[0]}")
        if rc == 0:
            return cmd
    return "update-grub"


class GrubTab:
    """GRUB Control Center – direkt integriert ins Multitool."""

    def __init__(self, nb, app, theme):
        self.app   = app
        self.root  = app.root
        self.T     = theme
        self._build(nb)

    # ─── Aufbau ────────────────────────────────────────────────────────────
    def _build(self, nb):
        T = self.T
        tab = ttk.Frame(nb)
        nb.add(tab, text="🔧 GRUB")

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
        for ev, d in [("<MouseWheel>", None), ("<Button-4>", -1), ("<Button-5>", 1)]:
            canvas.bind(ev, lambda e, _d=d: canvas.yview_scroll(
                _d if _d else int(-1*(e.delta/120)), "units"))

        inner = tk.Frame(pane, bg=T["bg"])
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        # ── Status ─────────────────────────────────────────────────────────
        sf = ttk.LabelFrame(inner, text=" GRUB Status ", padding=8)
        sf.pack(fill="x", pady=(0, 8))
        self._stat_lbl = tk.Label(sf, text="Prüfe...", bg=T["bg"],
                                   font=("Arial", 10, "bold"))
        self._stat_lbl.pack(anchor="w")
        self._ver_lbl  = tk.Label(sf, text="", bg=T["bg"],
                                   fg=T["fg_dim"], font=("Arial", 9))
        self._ver_lbl.pack(anchor="w")
        ttk.Button(sf, text="🔄 Status prüfen",
                   command=self._check_status).pack(anchor="w", pady=(6,0))
        self.root.after(500, self._check_status)

        # ── Boot-Einstellungen ──────────────────────────────────────────────
        bf = ttk.LabelFrame(inner, text=" ⚙️ Boot-Einstellungen ", padding=8)
        bf.pack(fill="x", pady=(0, 8))

        r1 = tk.Frame(bf, bg=T["bg"]); r1.pack(fill="x", pady=(0,6))
        tk.Label(r1, text="Timeout (Sek):", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 10)).pack(side="left", padx=(0,8))
        self._timeout_var = tk.StringVar(value="5")
        ttk.Entry(r1, textvariable=self._timeout_var, width=6).pack(side="left")
        ttk.Button(r1, text="📖 Lesen",  command=self._read_timeout ).pack(side="left", padx=4)
        ttk.Button(r1, text="✔ Setzen",  command=self._set_timeout  ).pack(side="left", padx=4)

        r2 = tk.Frame(bf, bg=T["bg"]); r2.pack(fill="x", pady=(0,6))
        tk.Label(r2, text="Standard-Eintrag (Nr.):", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 10)).pack(side="left", padx=(0,8))
        self._default_var = tk.StringVar(value="0")
        ttk.Entry(r2, textvariable=self._default_var, width=6).pack(side="left")
        ttk.Button(r2, text="📖 Lesen",  command=self._read_default ).pack(side="left", padx=4)
        ttk.Button(r2, text="✔ Setzen",  command=self._set_default  ).pack(side="left", padx=4)
        ttk.Button(r2, text="📋 Einträge anzeigen",
                   command=self._list_entries).pack(side="left", padx=4)

        # ── Design & Themes ─────────────────────────────────────────────────
        tf = ttk.LabelFrame(inner, text=" 🎨 Design & Themes ", padding=8)
        tf.pack(fill="x", pady=(0, 8))

        r3 = tk.Frame(tf, bg=T["bg"]); r3.pack(fill="x", pady=(0,6))
        tk.Label(r3, text="Hintergrundbild:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0,6))
        self._bg_var = tk.StringVar()
        ttk.Entry(r3, textvariable=self._bg_var, width=38).pack(side="left", padx=(0,4))
        ttk.Button(r3, text="📂", command=self._browse_bg).pack(side="left", padx=(0,4))
        ttk.Button(r3, text="✔ Setzen", command=self._set_bg).pack(side="left")

        r4 = tk.Frame(tf, bg=T["bg"]); r4.pack(fill="x", pady=(0,6))
        tk.Label(r4, text="Theme aktivieren:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0,6))
        self._theme_cb = ttk.Combobox(r4, width=28, state="readonly")
        self._theme_cb.pack(side="left", padx=(0,4))
        ttk.Button(r4, text="🔄", width=3, command=self._refresh_themes).pack(side="left", padx=(0,4))
        ttk.Button(r4, text="✔ Aktivieren", command=self._activate_theme).pack(side="left")
        self._refresh_themes()

        r5 = tk.Frame(tf, bg=T["bg"]); r5.pack(fill="x")
        tk.Label(r5, text="Theme von GitHub:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0,6))
        self._dl_var = tk.StringVar(value="https://github.com/")
        ttk.Entry(r5, textvariable=self._dl_var, width=38).pack(side="left", padx=(0,4))
        ttk.Button(r5, text="⬇ Download", command=self._download_theme).pack(side="left")

        # ── Backup & Aktionen ───────────────────────────────────────────────
        af = ttk.LabelFrame(inner, text=" 🛡️ Backup & Aktionen ", padding=8)
        af.pack(fill="x", pady=(0, 8))
        r6 = tk.Frame(af, bg=T["bg"]); r6.pack(fill="x")
        ttk.Button(r6, text="💾 Backup erstellen",
                   command=self._create_backup).pack(side="left", padx=(0,6))
        ttk.Button(r6, text="📋 Backups anzeigen",
                   command=self._list_backups).pack(side="left", padx=(0,6))
        ttk.Button(r6, text="🔄 GRUB aktualisieren", style="Accent.TButton",
                   command=self._update_grub).pack(side="left", padx=(0,6))
        ttk.Button(r6, text="🔍 System analysieren",
                   command=self._run_check).pack(side="left")

        # ── Ausgabe ────────────────────────────────────────────────────────
        lf = ttk.LabelFrame(inner, text=" Ausgabe ", padding=6)
        lf.pack(fill="both", expand=True)
        self._log = scrolledtext.ScrolledText(lf, height=14, state="disabled",
            font=("Monospace", 9), bg=T.get("bg2", T["bg"]), fg=T["fg"])
        self._log.pack(fill="both", expand=True)
        r7 = tk.Frame(inner, bg=T["bg"]); r7.pack(fill="x", pady=(4,0))
        ttk.Button(r7, text="🗑 Leeren",   command=self._clear_log ).pack(side="left")
        ttk.Button(r7, text="📋 Kopieren", command=self._copy_log  ).pack(side="left", padx=6)

    # ─── Hilfsfunktionen ───────────────────────────────────────────────────
    def _log_w(self, text: str):
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self._log.get("1.0", "end"))
        self.root.update()

    def _run_async(self, cmd: str, done_cb=None):
        env = os.environ.copy()
        env.setdefault("SUDO_USER", env.get("USER", "root"))
        def worker():
            try:
                proc = subprocess.Popen(
                    ["bash", "-c", cmd],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=env)
                for line in proc.stdout:
                    self.root.after(0, lambda l=line: self._log_w(l))
                proc.wait()
                self.root.after(0, lambda: self._log_w(
                    f"\n─── Beendet (Exit: {proc.returncode}) ───\n"))
                if done_cb:
                    self.root.after(0, done_cb)
            except Exception as e:
                self.root.after(0, lambda: self._log_w(f"Fehler: {e}\n"))
        threading.Thread(target=worker, daemon=True).start()

    # ─── Status ────────────────────────────────────────────────────────────
    def _check_status(self):
        def worker():
            _, out, _ = _sh("grub-install --version 2>/dev/null || grub2-install --version 2>/dev/null")
            ver = out.strip()[:80]
            cfg  = os.path.isfile(GRUB_CONFIG)
            gcfg = os.path.isfile(GRUB_CFG)
            self.root.after(0, lambda: self._upd_status(ver, cfg, gcfg))
        threading.Thread(target=worker, daemon=True).start()

    def _upd_status(self, ver, cfg_ok, gcfg_ok):
        T = self.T
        if ver and cfg_ok:
            self._stat_lbl.config(text="🟢 GRUB installiert", fg=T["success"])
            self._ver_lbl.config(text=(
                f"Version: {ver}  |  "
                f"Config: {'✅' if cfg_ok else '❌'}  |  "
                f"grub.cfg: {'✅' if gcfg_ok else '❌'}"))
        else:
            self._stat_lbl.config(text="🔴 GRUB nicht erkannt", fg=T["danger"])
            self._ver_lbl.config(text="GRUB fehlt oder kein Root-Zugriff")

    # ─── Timeout ───────────────────────────────────────────────────────────
    def _read_timeout(self):
        val = _read_grub_value("GRUB_TIMEOUT")
        self._timeout_var.set(val or "5")
        self._log_w(f"Aktueller Timeout: {val or '(nicht gesetzt)'} Sekunden\n")

    def _set_timeout(self):
        t = self._timeout_var.get().strip()
        if not t.isdigit() or not (0 <= int(t) <= 120):
            messagebox.showerror("Fehler", "Timeout muss 0–120 Sekunden sein."); return
        if not messagebox.askyesno("Timeout setzen",
            f"GRUB_TIMEOUT auf {t} Sekunden setzen und GRUB aktualisieren?"): return
        self._clear_log()
        self._run_async(
            f"sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT={t}/' {GRUB_CONFIG} && "
            f"{_update_grub_cmd()} 2>&1")

    # ─── Standard-Eintrag ──────────────────────────────────────────────────
    def _read_default(self):
        val = _read_grub_value("GRUB_DEFAULT")
        self._default_var.set(val or "0")
        self._log_w(f"Aktueller Standard-Eintrag: {val or '0'}\n")

    def _set_default(self):
        d = self._default_var.get().strip()
        if not re.match(r'^\d+$', d):
            messagebox.showerror("Fehler", "Bitte eine Zahl eingeben."); return
        if not messagebox.askyesno("Standard setzen",
            f"Standard-Boot-Eintrag auf {d} setzen und GRUB aktualisieren?"): return
        self._clear_log()
        self._run_async(
            f"sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT={d}/' {GRUB_CONFIG} && "
            f"{_update_grub_cmd()} 2>&1")

    def _list_entries(self):
        self._clear_log()
        self._log_w("=== Boot-Einträge ===\n")
        _, out, _ = _sh(
            f"grep -E '^menuentry|^submenu' {GRUB_CFG} | "
            "nl -ba | head -30")
        self._log_w(out or "Keine Einträge gefunden (grub.cfg fehlt?).\n")

    # ─── Themes ────────────────────────────────────────────────────────────
    def _refresh_themes(self):
        themes = []
        if os.path.isdir(GRUB_THEMES):
            themes = [d for d in os.listdir(GRUB_THEMES)
                      if os.path.isdir(os.path.join(GRUB_THEMES, d))]
        self._theme_cb["values"] = themes or ["(keine Themes installiert)"]
        if themes:
            self._theme_cb.current(0)

    def _activate_theme(self):
        theme = self._theme_cb.get()
        if not theme or theme.startswith("("):
            messagebox.showinfo("Hinweis", "Kein Theme vorhanden."); return
        tp = f"{GRUB_THEMES}/{theme}/theme.txt"
        if not os.path.isfile(tp):
            messagebox.showerror("Fehler", f"theme.txt nicht gefunden:\n{tp}"); return
        if not messagebox.askyesno("Theme aktivieren",
            f"Theme '{theme}' aktivieren und GRUB aktualisieren?"): return
        self._clear_log()
        self._run_async(
            f"sed -i 's|^#\\?GRUB_THEME=.*|GRUB_THEME=\"{tp}\"|' {GRUB_CONFIG} || "
            f"echo 'GRUB_THEME=\"{tp}\"' >> {GRUB_CONFIG}; "
            f"{_update_grub_cmd()} 2>&1")

    def _browse_bg(self):
        p = filedialog.askopenfilename(
            title="Hintergrundbild wählen",
            filetypes=[("Bilder", "*.png *.jpg *.jpeg *.tga"), ("Alle", "*")])
        if p:
            self._bg_var.set(p)

    def _set_bg(self):
        bg = self._bg_var.get().strip()
        if not bg or not os.path.isfile(bg):
            messagebox.showerror("Fehler", "Bitte eine gültige Bilddatei wählen."); return
        if not messagebox.askyesno("Hintergrund setzen",
            f"Hintergrundbild setzen:\n{bg}\n\nGRUB aktualisieren?"): return
        self._clear_log()
        self._run_async(
            f"sed -i 's|^#\\?GRUB_BACKGROUND=.*|GRUB_BACKGROUND=\"{bg}\"|' {GRUB_CONFIG} || "
            f"echo 'GRUB_BACKGROUND=\"{bg}\"' >> {GRUB_CONFIG}; "
            f"{_update_grub_cmd()} 2>&1")

    def _download_theme(self):
        url = self._dl_var.get().strip()
        if not url.startswith("https://github.com/"):
            messagebox.showerror("Fehler",
                "Bitte eine GitHub-URL angeben:\nhttps://github.com/user/repo"); return
        if not messagebox.askyesno("Theme herunterladen",
            f"Theme herunterladen von:\n{url}"): return
        name = re.sub(r"[^a-zA-Z0-9_-]", "_", url.rstrip("/").split("/")[-1])[:30]
        self._clear_log()
        self._run_async(
            f"mkdir -p '{GRUB_THEMES}' && "
            f"rm -rf /tmp/grub-theme-dl && "
            f"git clone --depth=1 '{url}' /tmp/grub-theme-dl 2>&1 && "
            f"mkdir -p '{GRUB_THEMES}/{name}' && "
            f"cp -r /tmp/grub-theme-dl/* '{GRUB_THEMES}/{name}/' 2>&1 && "
            f"rm -rf /tmp/grub-theme-dl && "
            f"echo 'Theme installiert: {GRUB_THEMES}/{name}'",
            done_cb=self._refresh_themes)

    # ─── Backup & Aktionen ─────────────────────────────────────────────────
    def _create_backup(self):
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = f"/boot/grub/grub.cfg.bak_{ts}"
        self._clear_log()
        self._run_async(
            f"cp {GRUB_CFG} '{dst}' 2>&1 && "
            f"cp {GRUB_CONFIG} '{GRUB_CONFIG}.bak_{ts}' 2>&1 && "
            f"echo 'Backup erstellt:' && echo '  {dst}' && "
            f"echo '  {GRUB_CONFIG}.bak_{ts}'")

    def _list_backups(self):
        self._clear_log()
        self._log_w("=== GRUB-Backups ===\n")
        _, out, _ = _sh(
            "ls -lh /boot/grub/grub.cfg.bak_* "
            "/etc/default/grub.bak_* 2>/dev/null | sort")
        self._log_w(out if out.strip() else "Keine Backups vorhanden.\n")

    def _update_grub(self):
        if not messagebox.askyesno("GRUB aktualisieren",
            "GRUB-Konfiguration neu generieren?\n(update-grub)"): return
        self._clear_log()
        self._run_async(f"{_update_grub_cmd()} 2>&1")

    def _run_check(self):
        self._clear_log()
        if os.path.isfile(GRUB_CHECK):
            # Mit gesetztem SUDO_USER aufrufen
            import getpass
            user = os.environ.get("SUDO_USER") or os.environ.get("USER") or getpass.getuser()
            self._run_async(
                f"export SUDO_USER='{user}'; "
                f"export USER='{user}'; "
                f"bash '{GRUB_CHECK}' 2>&1")
        else:
            # Einfacher Fallback direkt in Python
            self._run_async(
                "echo '=== GRUB System-Analyse ==='; echo ''; "
                "grub-install --version 2>/dev/null || echo 'grub-install: nicht gefunden'; "
                "echo ''; echo '=== /etc/default/grub ==='; "
                f"cat {GRUB_CONFIG} 2>/dev/null; "
                "echo ''; echo '=== Boot-Einträge ==='; "
                f"grep -cE '^menuentry' {GRUB_CFG} 2>/dev/null | xargs -I{{}} echo '{{}} Einträge'; "
                "echo ''; echo '=== Themes ==='; "
                f"ls {GRUB_THEMES}/ 2>/dev/null || echo 'Keine Themes'; "
                "echo ''; echo '=== /boot Speicher ==='; df -h /boot 2>/dev/null")
