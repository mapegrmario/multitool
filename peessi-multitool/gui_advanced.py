"""
gui_advanced.py – Erweiterte Werkzeuge für Peeßi's System Multitool v4.1
Separate Datei für einfache Wartung.

Enthält folgende Tabs (unter Haupt-Tab "🔧 Erweitert"):
  1. 💾 Disk-Images     – Image erstellen/wiederherstellen (dd + gzip)
  2. 🔄 Datenmigration  – rsync mit Live-Ausgabe und Stopp
  3. 💿 LVM             – PV/VG/LV erstellen, Status, vergrößern
  4. 🛡️ RAID            – mdadm Status, erstellen, stoppen
  5. 🩹 Boot-Reparatur  – GRUB-Install, TestDisk, Windows-MBR

Basiert auf Partitionierer V5 (integriert und angepasst an Multitool-Stil).
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import subprocess, threading, os, shutil, re

LC_ENV = {**os.environ, "LC_ALL": "C", "LANG": "C"}

_INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))


def _sh(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, env=LC_ENV)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def _find_terminal():
    for t in ("xterm", "gnome-terminal", "xfce4-terminal",
              "mate-terminal", "lxterminal", "konsole"):
        if shutil.which(t):
            return t
    return None


def _run_in_terminal(cmd_str, title="Peeßi's Multitool"):
    term = _find_terminal()
    if not term:
        messagebox.showerror("Kein Terminal",
            "Kein Terminal-Emulator gefunden.\n"
            "sudo apt install xterm")
        return False
    if term == "xterm":
        args = ["xterm", "-T", title, "-geometry", "120x40", "-e",
                f"bash -c '{cmd_str}; echo; echo \"[Fertig – Enter drücken]\"; read'"]
    elif term == "gnome-terminal":
        args = ["gnome-terminal", "--title", title, "--",
                "bash", "-c", f"{cmd_str}; echo; read"]
    else:
        args = [term, "-e", f"bash -c '{cmd_str}; echo; read'"]
    subprocess.Popen(args)
    return True


class AdvancedTabs:
    """Haupt-Tab ‚🔧 Erweitert' mit sechs Sub-Tabs."""

    def __init__(self, nb_main, app):
        self.app   = app
        self.root  = app.root
        self.T     = app.theme

        # Äußerer Tab im Haupt-Notebook
        outer = ttk.Frame(nb_main)
        nb_main.add(outer, text="🔧 Erweitert")

        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)

        self._build_disk_image(nb)
        self._build_migrate(nb)
        self._build_lvm(nb)
        self._build_raid(nb)
        self._build_boot_repair(nb)

    # ─── Hilfsmethoden ─────────────────────────────────────────────────────
    def _log_w(self, log_widget, text: str):
        clean = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', text)
        log_widget.configure(state="normal")
        log_widget.insert("end", clean)
        log_widget.see("end")
        log_widget.configure(state="disabled")

    def _log_clear(self, log_widget):
        log_widget.configure(state="normal")
        log_widget.delete("1.0", "end")
        log_widget.configure(state="disabled")

    def _log_copy(self, log_widget):
        self.root.clipboard_clear()
        self.root.clipboard_append(log_widget.get("1.0", "end"))
        self.root.update()

    def _make_log(self, parent, height=14) -> scrolledtext.ScrolledText:
        T = self.T
        w = scrolledtext.ScrolledText(parent, height=height, state="disabled",
                                       font=("Monospace", 9),
                                       bg=T.get("bg2", T["bg"]), fg=T["fg"])
        return w

    def _make_tab(self, nb, title) -> tk.Frame:
        """Einfacher (nicht-scrollbarer) Tab – Logs sind schon scrollbar."""
        tab = ttk.Frame(nb)
        nb.add(tab, text=title)
        return tab

    def _run_async(self, cmd, log, btn=None, done_cb=None, env=None):
        """Befehl asynchron ausführen, Ausgabe ins Log streamen."""
        self._log_clear(log)
        env = env or LC_ENV
        if btn:
            btn.config(state="disabled")

        def worker():
            try:
                proc = subprocess.Popen(
                    cmd if isinstance(cmd, list) else cmd,
                    shell=isinstance(cmd, str),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, env=env)
                for line in proc.stdout:
                    self.root.after(0, lambda l=line: self._log_w(log, l))
                proc.wait()
                self.root.after(0, lambda: self._log_w(
                    log, f"\n─── Beendet (Exit: {proc.returncode}) ───\n"))
                if done_cb:
                    self.root.after(0, done_cb)
            except Exception as e:
                self.root.after(0, lambda: self._log_w(log, f"\n❌ {e}\n"))
            finally:
                if btn:
                    self.root.after(0, lambda: btn.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _disk_combobox(self, parent, width=35) -> ttk.Combobox:
        """Combobox mit allen Laufwerken + Aktualisierungs-Button."""
        cb = ttk.Combobox(parent, state="readonly", width=width)
        self._disk_refresh(cb)
        return cb

    def _disk_refresh(self, cb):
        try:
            r = subprocess.run(
                ["lsblk", "-d", "-o", "NAME,SIZE,MODEL", "-n"],
                capture_output=True, text=True, timeout=8)
            items = []
            for line in r.stdout.splitlines():
                p = line.split(None, 2)
                if p:
                    model = p[2].strip() if len(p) > 2 else ""
                    size  = p[1] if len(p) > 1 else ""
                    items.append(f"/dev/{p[0]}  [{size}  {model}]".strip())
            cb["values"] = items or ["Kein Laufwerk erkannt"]
            if items:
                cb.current(0)
        except Exception:
            cb["values"] = ["Fehler – 🔄 klicken"]

    # ════════════════════════════════════════════════════════════════════════
    #  TAB 1 – DISK-IMAGES
    # ════════════════════════════════════════════════════════════════════════
    def _build_disk_image(self, nb):
        T = self.T
        tab = self._make_tab(nb, "💾 Disk-Images")
        p = tk.Frame(tab, bg=T["bg"])
        p.pack(fill="both", expand=True, padx=12, pady=10)

        # ── Image erstellen ───────────────────────────────────────────────
        cf = ttk.LabelFrame(p, text=" Image erstellen (dd → Datei) ", padding=8)
        cf.pack(fill="x", pady=(0, 8))

        r1 = tk.Frame(cf, bg=T["bg"]); r1.pack(fill="x", pady=2)
        tk.Label(r1, text="Quell-Laufwerk:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 8))
        self._img_src_cb = self._disk_combobox(r1)
        self._img_src_cb.pack(side="left", padx=(0, 4))
        ttk.Button(r1, text="🔄", width=3,
                   command=lambda: self._disk_refresh(self._img_src_cb)).pack(side="left")

        r2 = tk.Frame(cf, bg=T["bg"]); r2.pack(fill="x", pady=2)
        tk.Label(r2, text="Ziel-Datei:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 8))
        self._img_dst_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self._img_dst_var, width=40).pack(side="left", padx=(0, 4))
        ttk.Button(r2, text="📂",
                   command=lambda: self._img_dst_var.set(
                       filedialog.asksaveasfilename(
                           title="Image-Datei wählen",
                           filetypes=[("Image", "*.img *.img.gz *.raw"), ("Alle", "*")]
                       ) or self._img_dst_var.get()
                   )).pack(side="left")

        r3 = tk.Frame(cf, bg=T["bg"]); r3.pack(fill="x", pady=4)
        self._img_compress_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r3, text="Komprimieren mit gzip (.img.gz)",
                        variable=self._img_compress_var).pack(side="left")

        self._img_create_btn = ttk.Button(cf, text="💾 Image erstellen",
                                           style="Accent.TButton",
                                           command=self._img_create)
        self._img_create_btn.pack(anchor="w", pady=4)

        # ── Image wiederherstellen ────────────────────────────────────────
        rf = ttk.LabelFrame(p, text=" Image wiederherstellen (Datei → Laufwerk) ", padding=8)
        rf.pack(fill="x", pady=(0, 8))

        r4 = tk.Frame(rf, bg=T["bg"]); r4.pack(fill="x", pady=2)
        tk.Label(r4, text="Quell-Datei:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 8))
        self._rst_src_var = tk.StringVar()
        ttk.Entry(r4, textvariable=self._rst_src_var, width=40).pack(side="left", padx=(0, 4))
        ttk.Button(r4, text="📂",
                   command=lambda: self._rst_src_var.set(
                       filedialog.askopenfilename(
                           title="Image-Datei öffnen",
                           filetypes=[("Image", "*.img *.img.gz *.raw *.gz"), ("Alle", "*")]
                       ) or self._rst_src_var.get()
                   )).pack(side="left")

        r5 = tk.Frame(rf, bg=T["bg"]); r5.pack(fill="x", pady=2)
        tk.Label(r5, text="Ziel-Laufwerk:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 8))
        self._rst_dst_cb = self._disk_combobox(r5)
        self._rst_dst_cb.pack(side="left", padx=(0, 4))
        ttk.Button(r5, text="🔄", width=3,
                   command=lambda: self._disk_refresh(self._rst_dst_cb)).pack(side="left")

        self._img_restore_btn = ttk.Button(rf, text="🔄 Image wiederherstellen",
                                            style="Danger.TButton",
                                            command=self._img_restore)
        self._img_restore_btn.pack(anchor="w", pady=4)

        # Log
        lf = ttk.LabelFrame(p, text=" Ausgabe ", padding=4)
        lf.pack(fill="both", expand=True)
        self._img_log = self._make_log(lf, height=10)
        self._img_log.pack(fill="both", expand=True)
        bf = tk.Frame(p, bg=T["bg"]); bf.pack(fill="x", pady=(4, 0))
        ttk.Button(bf, text="🗑 Leeren",
                   command=lambda: self._log_clear(self._img_log)).pack(side="left")
        ttk.Button(bf, text="📋 Kopieren",
                   command=lambda: self._log_copy(self._img_log)).pack(side="left", padx=6)

    def _img_dev(self, cb):
        sel = cb.get()
        return sel.split()[0] if sel and not sel.startswith("Kein") else ""

    def _img_create(self):
        dev  = self._img_dev(self._img_src_cb)
        path = self._img_dst_var.get().strip()
        if not dev or not path:
            messagebox.showerror("Fehler", "Bitte Laufwerk und Ziel-Datei angeben.")
            return
        if not messagebox.askyesno("Image erstellen",
            f"Laufwerk: {dev}\nDatei: {path}\n\nFortfahren?"):
            return

        self._img_create_btn.config(state="disabled")
        log = self._img_log
        self._log_clear(log)

        if self._img_compress_var.get():
            img_path = path if path.endswith(".gz") else path + ".gz"
            self._log_w(log, f"$ dd if={dev} bs=4M status=progress | gzip > {img_path}\n\n")

            def worker():
                try:
                    dd = subprocess.Popen(
                        ["dd", f"if={dev}", "bs=4M", "status=progress"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    with open(img_path, "wb") as f:
                        gz = subprocess.Popen(["gzip", "-c"], stdin=dd.stdout, stdout=f)
                        dd.stdout.close()
                        gz.wait()
                    dd.wait()
                    for line in dd.stderr:
                        self.root.after(0, lambda l=line.decode(errors="replace"):
                                        self._log_w(log, l))
                    self.root.after(0, lambda: self._log_w(
                        log, f"\n✅ Image erstellt: {img_path}\n"))
                except Exception as e:
                    self.root.after(0, lambda: self._log_w(log, f"\n❌ {e}\n"))
                finally:
                    self.root.after(0, lambda: self._img_create_btn.config(state="normal"))
            threading.Thread(target=worker, daemon=True).start()
        else:
            self._run_async(["dd", f"if={dev}", f"of={path}",
                             "bs=4M", "conv=fsync", "status=progress"],
                            log, self._img_create_btn)

    def _img_restore(self):
        src  = self._rst_src_var.get().strip()
        dev  = self._img_dev(self._rst_dst_cb)
        if not src or not dev:
            messagebox.showerror("Fehler", "Bitte Image-Datei und Ziel-Laufwerk angeben.")
            return
        if not os.path.isfile(src):
            messagebox.showerror("Fehler", f"Datei nicht gefunden:\n{src}")
            return
        if not messagebox.askyesno("Image wiederherstellen",
            f"Image: {src}\nZiel:  {dev}\n\n"
            "⚠️  ALLE DATEN AUF DEM ZIEL WERDEN GELÖSCHT!\nFortfahren?", icon="warning"):
            return

        log = self._img_log
        self._log_clear(log)
        self._img_restore_btn.config(state="disabled")

        if src.endswith(".gz"):
            self._log_w(log, f"$ gzip -dc {src} | dd of={dev} bs=4M status=progress\n\n")
            def worker():
                try:
                    gz = subprocess.Popen(["gzip", "-dc", src], stdout=subprocess.PIPE)
                    dd = subprocess.Popen(["dd", f"of={dev}", "bs=4M", "conv=fsync",
                                          "status=progress"],
                                         stdin=gz.stdout, stderr=subprocess.PIPE)
                    gz.stdout.close()
                    dd.wait(); gz.wait()
                    for line in dd.stderr:
                        self.root.after(0, lambda l=line.decode(errors="replace"):
                                        self._log_w(log, l))
                    self.root.after(0, lambda: self._log_w(log, "\n✅ Wiederhergestellt.\n"))
                except Exception as e:
                    self.root.after(0, lambda: self._log_w(log, f"\n❌ {e}\n"))
                finally:
                    self.root.after(0, lambda: self._img_restore_btn.config(state="normal"))
            threading.Thread(target=worker, daemon=True).start()
        else:
            self._run_async(["dd", f"if={src}", f"of={dev}", "bs=4M",
                             "conv=fsync", "status=progress"],
                            log, self._img_restore_btn)

    # ════════════════════════════════════════════════════════════════════════
    #  TAB 2 – DATENMIGRATION (rsync)
    # ════════════════════════════════════════════════════════════════════════
    def _build_migrate(self, nb):
        T = self.T
        tab = self._make_tab(nb, "🔄 Datenmigration")
        p = tk.Frame(tab, bg=T["bg"])
        p.pack(fill="both", expand=True, padx=12, pady=10)

        if not shutil.which("rsync"):
            tk.Label(p, text="⚠️  rsync nicht installiert.\nsudo apt install rsync",
                     bg=T["bg"], fg=T["danger"], font=("Arial", 11)).pack(expand=True)
            return

        f = ttk.LabelFrame(p, text=" Dateien übertragen (rsync) ", padding=8)
        f.pack(fill="x", pady=(0, 8))

        def browse(var, is_dir=True):
            d = (filedialog.askdirectory(title="Verzeichnis wählen")
                 if is_dir else
                 filedialog.askopenfilename(title="Datei wählen"))
            if d:
                var.set(d)

        r1 = tk.Frame(f, bg=T["bg"]); r1.pack(fill="x", pady=3)
        tk.Label(r1, text="Quelle:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9), width=8).pack(side="left")
        self._mig_src_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self._mig_src_var, width=45).pack(side="left", padx=(0, 4))
        ttk.Button(r1, text="📂",
                   command=lambda: browse(self._mig_src_var)).pack(side="left")

        r2 = tk.Frame(f, bg=T["bg"]); r2.pack(fill="x", pady=3)
        tk.Label(r2, text="Ziel:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9), width=8).pack(side="left")
        self._mig_dst_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self._mig_dst_var, width=45).pack(side="left", padx=(0, 4))
        ttk.Button(r2, text="📂",
                   command=lambda: browse(self._mig_dst_var)).pack(side="left")

        opts = tk.Frame(f, bg=T["bg"]); opts.pack(fill="x", pady=4)
        self._mig_delete    = tk.BooleanVar()
        self._mig_dryrun    = tk.BooleanVar()
        self._mig_hardlinks = tk.BooleanVar(value=True)
        self._mig_excl_var  = tk.StringVar()
        ttk.Checkbutton(opts, text="Spiegel (--delete)",
                        variable=self._mig_delete).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(opts, text="Trockenlauf (--dry-run)",
                        variable=self._mig_dryrun).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(opts, text="Hardlinks erhalten (-H)",
                        variable=self._mig_hardlinks).pack(side="left")

        r3 = tk.Frame(f, bg=T["bg"]); r3.pack(fill="x", pady=3)
        tk.Label(r3, text="Ausschließen:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9), width=12).pack(side="left")
        ttk.Entry(r3, textvariable=self._mig_excl_var, width=35).pack(side="left")
        tk.Label(r3, text="(kommagetrennt, z.B. *.tmp,/proc)",
                 bg=T["bg"], fg=T["fg_dim"], font=("Arial", 8)).pack(side="left", padx=6)

        btn_row = tk.Frame(f, bg=T["bg"]); btn_row.pack(fill="x", pady=4)
        self._mig_start_btn = ttk.Button(btn_row, text="▶ Migration starten",
                                          style="Accent.TButton",
                                          command=self._mig_start)
        self._mig_start_btn.pack(side="left", padx=(0, 6))
        self._mig_stop_btn = ttk.Button(btn_row, text="⏹ Stopp",
                                         style="Danger.TButton",
                                         command=self._mig_stop,
                                         state="disabled")
        self._mig_stop_btn.pack(side="left")
        self._mig_proc = None

        lf = ttk.LabelFrame(p, text=" Ausgabe ", padding=4)
        lf.pack(fill="both", expand=True)
        self._mig_log = self._make_log(lf, height=16)
        self._mig_log.pack(fill="both", expand=True)
        bf = tk.Frame(p, bg=T["bg"]); bf.pack(fill="x", pady=(4, 0))
        ttk.Button(bf, text="🗑 Leeren",
                   command=lambda: self._log_clear(self._mig_log)).pack(side="left")
        ttk.Button(bf, text="📋 Kopieren",
                   command=lambda: self._log_copy(self._mig_log)).pack(side="left", padx=6)

    def _mig_start(self):
        src = self._mig_src_var.get().strip()
        dst = self._mig_dst_var.get().strip()
        if not src or not dst:
            messagebox.showerror("Fehler", "Bitte Quelle und Ziel angeben.")
            return
        if not os.path.isdir(src):
            messagebox.showerror("Fehler", f"Quellverzeichnis nicht gefunden:\n{src}")
            return
        os.makedirs(dst, exist_ok=True)

        flags = ["-aHAXv", "--progress"]
        if self._mig_hardlinks.get(): flags.append("-H")
        if self._mig_delete.get():    flags.append("--delete")
        if self._mig_dryrun.get():    flags.append("--dry-run")
        excl = self._mig_excl_var.get().strip()
        for ex in (excl.split(",") if excl else []):
            ex = ex.strip()
            if ex:
                flags += ["--exclude", ex]
        cmd = ["rsync"] + flags + [src.rstrip("/") + "/", dst]

        self._log_clear(self._mig_log)
        self._log_w(self._mig_log, f"$ {' '.join(cmd)}\n\n")
        self._mig_start_btn.config(state="disabled")
        self._mig_stop_btn.config(state="normal")

        def worker():
            try:
                self._mig_proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1)
                for line in self._mig_proc.stdout:
                    self.root.after(0, lambda l=line: self._log_w(self._mig_log, l))
                self._mig_proc.wait()
                rc = self._mig_proc.returncode
                msg = "\n✅ Migration abgeschlossen.\n" if rc == 0 \
                      else f"\n❌ Fehler (Exit: {rc})\n"
                self.root.after(0, lambda: self._log_w(self._mig_log, msg))
            except Exception as e:
                self.root.after(0, lambda: self._log_w(self._mig_log, f"\n❌ {e}\n"))
            finally:
                self._mig_proc = None
                self.root.after(0, lambda: self._mig_start_btn.config(state="normal"))
                self.root.after(0, lambda: self._mig_stop_btn.config(state="disabled"))
        threading.Thread(target=worker, daemon=True).start()

    def _mig_stop(self):
        if self._mig_proc:
            try: self._mig_proc.terminate()
            except Exception as _e:
                import logging as _l; _l.warning('%s: %s', __file__, _e)
        self._log_w(self._mig_log, "\n⏹ Gestoppt.\n")
        self._mig_stop_btn.config(state="disabled")

    # ════════════════════════════════════════════════════════════════════════
    #  TAB 3 – LVM
    # ════════════════════════════════════════════════════════════════════════
    def _build_lvm(self, nb):
        T = self.T
        tab = self._make_tab(nb, "💿 LVM")
        p = tk.Frame(tab, bg=T["bg"])
        p.pack(fill="both", expand=True, padx=12, pady=10)

        if not shutil.which("lvm") and not shutil.which("pvs"):
            tk.Label(p, text="⚠️  LVM-Tools nicht installiert.\nsudo apt install lvm2",
                     bg=T["bg"], fg=T["danger"], font=("Arial", 11)).pack(expand=True)
            return

        # ── Status ────────────────────────────────────────────────────────
        sf = ttk.LabelFrame(p, text=" LVM-Status ", padding=8)
        sf.pack(fill="x", pady=(0, 8))
        ttk.Button(sf, text="🔄 Status anzeigen (pvs / vgs / lvs)",
                   command=self._lvm_status).pack(anchor="w")

        # ── Erstellen ─────────────────────────────────────────────────────
        cf = ttk.LabelFrame(p, text=" LVM erstellen (PV → VG → LV) ", padding=8)
        cf.pack(fill="x", pady=(0, 8))

        self._lvm_vars = {}
        fields = [
            ("Physical Volume (z.B. /dev/sdb):", "pv", "/dev/"),
            ("Volume Group Name:",               "vg", "myvg"),
            ("Logical Volume Name:",             "lv", "data"),
            ("Größe (z.B. 10G, 500M):",          "sz", "10G"),
        ]
        for row, (lbl, key, ph) in enumerate(fields):
            tk.Label(cf, text=lbl, bg=T["bg"], fg=T["fg"],
                     font=("Arial", 9)).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
            e = ttk.Entry(cf, width=28)
            e.insert(0, ph)
            e.grid(row=row, column=1, sticky="w", pady=2)
            self._lvm_vars[key] = e

        tk.Label(cf, text="Dateisystem:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).grid(row=4, column=0, sticky="w", pady=2)
        self._lvm_fs = ttk.Combobox(cf, values=["(keins)", "ext4", "xfs", "btrfs", "fat32"],
                                     state="readonly", width=12)
        self._lvm_fs.set("ext4")
        self._lvm_fs.grid(row=4, column=1, sticky="w", pady=2)
        ttk.Button(cf, text="▶ LVM erstellen",
                   style="Accent.TButton",
                   command=self._lvm_create).grid(row=5, column=1, sticky="w", pady=6)

        # ── LV vergrößern ─────────────────────────────────────────────────
        ef = ttk.LabelFrame(p, text=" Logical Volume vergrößern ", padding=8)
        ef.pack(fill="x", pady=(0, 8))
        er = tk.Frame(ef, bg=T["bg"]); er.pack(fill="x")
        tk.Label(er, text="LV-Pfad:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 6))
        self._lvm_ext_path = ttk.Entry(er, width=28)
        self._lvm_ext_path.insert(0, "/dev/myvg/data")
        self._lvm_ext_path.pack(side="left", padx=(0, 8))
        tk.Label(er, text="Größe:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 6))
        self._lvm_ext_size = ttk.Entry(er, width=10)
        self._lvm_ext_size.insert(0, "+5G")
        self._lvm_ext_size.pack(side="left", padx=(0, 8))
        self._lvm_resize_fs = tk.BooleanVar(value=True)
        ttk.Checkbutton(er, text="Dateisystem anpassen",
                        variable=self._lvm_resize_fs).pack(side="left")
        ttk.Button(ef, text="▶ Vergrößern",
                   command=self._lvm_extend).pack(anchor="w", pady=4)

        lf = ttk.LabelFrame(p, text=" Ausgabe ", padding=4)
        lf.pack(fill="both", expand=True)
        self._lvm_log = self._make_log(lf)
        self._lvm_log.pack(fill="both", expand=True)
        bf = tk.Frame(p, bg=T["bg"]); bf.pack(fill="x", pady=(4, 0))
        ttk.Button(bf, text="🗑 Leeren",
                   command=lambda: self._log_clear(self._lvm_log)).pack(side="left")
        ttk.Button(bf, text="📋 Kopieren",
                   command=lambda: self._log_copy(self._lvm_log)).pack(side="left", padx=6)

    def _lvm_status(self):
        self._log_clear(self._lvm_log)
        for cmd in [["pvs", "--units", "g"], ["vgs", "--units", "g"], ["lvs", "--units", "g"]]:
            self._log_w(self._lvm_log, f"$ {' '.join(cmd)}\n")
            _, out, err = _sh(cmd, timeout=15)
            self._log_w(self._lvm_log, (out or "") + (err or "") + "\n")

    def _lvm_create(self):
        v = {k: e.get().strip() for k, e in self._lvm_vars.items()}
        if not all(v.values()):
            messagebox.showerror("Fehler", "Bitte alle Felder ausfüllen."); return
        if not messagebox.askyesno("LVM erstellen",
            f"PV: {v['pv']}\nVG: {v['vg']}\nLV: {v['lv']} ({v['sz']})\n\nFortfahren?"):
            return

        lv_dev = f"/dev/{v['vg']}/{v['lv']}"
        fs     = self._lvm_fs.get()
        cmds   = [
            ["pvcreate", v["pv"]],
            ["vgcreate", v["vg"], v["pv"]],
            ["lvcreate", "-L", v["sz"], "-n", v["lv"], v["vg"]],
        ]
        if fs and fs != "(keins)":
            mkfs_map = {
                "ext4":  ["mkfs.ext4", "-F", lv_dev],
                "xfs":   ["mkfs.xfs",  "-f", lv_dev],
                "btrfs": ["mkfs.btrfs", "-f", lv_dev],
                "fat32": ["mkfs.vfat",  "-F32", lv_dev],
            }
            if fs in mkfs_map:
                cmds.append(mkfs_map[fs])

        self._log_clear(self._lvm_log)

        def run_seq(idx=0):
            if idx >= len(cmds):
                self._log_w(self._lvm_log, "\n✅ LVM vollständig erstellt.\n")
                return
            cmd = cmds[idx]
            self._log_w(self._lvm_log, f"$ {' '.join(cmd)}\n")
            rc, out, err = _sh(cmd, timeout=60)
            self._log_w(self._lvm_log, (out or "") + (err or "") + "\n")
            if rc != 0:
                self._log_w(self._lvm_log, f"\n❌ Fehler bei: {' '.join(cmd)}\n")
                return
            self.root.after(100, lambda: run_seq(idx + 1))

        self.root.after(0, run_seq)

    def _lvm_extend(self):
        lv  = self._lvm_ext_path.get().strip()
        ext = self._lvm_ext_size.get().strip()
        if not lv or not ext:
            messagebox.showerror("Fehler", "LV-Pfad und Größe angeben."); return
        if not messagebox.askyesno("LV vergrößern", f"{lv} um {ext} vergrößern?"):
            return
        resize = self._lvm_resize_fs.get()
        self._log_clear(self._lvm_log)

        def worker():
            rc, out, err = _sh(["lvextend", "-L", ext, lv], timeout=30)
            self.root.after(0, lambda: self._log_w(
                self._lvm_log, f"$ lvextend -L {ext} {lv}\n{out}{err}\n"))
            if rc == 0 and resize:
                self.root.after(0, lambda: self._log_w(self._lvm_log, "$ resize2fs ...\n"))
                rc2, o2, e2 = _sh(["resize2fs", lv], timeout=60)
                self.root.after(0, lambda: self._log_w(self._lvm_log, (o2 or "") + (e2 or "")))
                if rc2 != 0:
                    # Fallback: xfs_growfs
                    _sh(["xfs_growfs", lv], timeout=30)
        threading.Thread(target=worker, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════════
    #  TAB 4 – RAID
    # ════════════════════════════════════════════════════════════════════════
    def _build_raid(self, nb):
        T = self.T
        tab = self._make_tab(nb, "🛡️ RAID")
        p = tk.Frame(tab, bg=T["bg"])
        p.pack(fill="both", expand=True, padx=12, pady=10)

        if not shutil.which("mdadm"):
            tk.Label(p, text="⚠️  mdadm nicht installiert.\nsudo apt install mdadm",
                     bg=T["bg"], fg=T["danger"], font=("Arial", 11)).pack(expand=True)
            return

        # ── Status ────────────────────────────────────────────────────────
        sf = ttk.LabelFrame(p, text=" RAID-Status ", padding=8)
        sf.pack(fill="x", pady=(0, 8))
        sr = tk.Frame(sf, bg=T["bg"]); sr.pack(fill="x")
        ttk.Button(sr, text="🔄 /proc/mdstat",
                   command=self._raid_mdstat).pack(side="left", padx=(0, 8))
        tk.Label(sr, text="Details für:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 4))
        self._raid_detail_var = tk.StringVar(value="md0")
        ttk.Entry(sr, textvariable=self._raid_detail_var, width=8).pack(side="left", padx=(0, 4))
        ttk.Button(sr, text="anzeigen",
                   command=self._raid_detail).pack(side="left")

        # ── Erstellen ─────────────────────────────────────────────────────
        cf = ttk.LabelFrame(p, text=" RAID erstellen (mdadm) ", padding=8)
        cf.pack(fill="x", pady=(0, 8))

        # Laufwerke als Checkboxen
        dev_hdr = tk.Frame(cf, bg=T["bg"]); dev_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(dev_hdr, text="Laufwerke auswählen (☑ = RAID-Member):",
                 bg=T["bg"], fg=T["fg"], font=("Arial", 9, "bold")).pack(side="left")
        ttk.Button(dev_hdr, text="🔄",
                   command=lambda: self._raid_refresh_disks()).pack(side="left", padx=6)

        # Scrollbarer Frame für Checkboxen
        cb_outer = tk.Frame(cf, bg=T.get("bg2", T["bg"]),
                            bd=1, relief="sunken")
        cb_outer.pack(fill="x", pady=(0, 6))
        self._raid_cb_frame = tk.Frame(cb_outer, bg=T.get("bg2", T["bg"]))
        self._raid_cb_frame.pack(fill="x", padx=4, pady=4)
        self._raid_disk_vars = {}  # {"/dev/sdX": BooleanVar}

        def _raid_refresh_disks():
            for w in self._raid_cb_frame.winfo_children():
                w.destroy()
            self._raid_disk_vars.clear()
            try:
                r = subprocess.run(
                    ["lsblk", "-d", "-o", "NAME,SIZE,MODEL,TYPE", "-n"],
                    capture_output=True, text=True, timeout=8)
                disks = []
                for line in r.stdout.splitlines():
                    parts = line.split(None, 3)
                    if len(parts) >= 4 and parts[3].strip() == "disk":
                        dev   = f"/dev/{parts[0]}"
                        size  = parts[1]
                        model = parts[2] if len(parts) > 2 else ""
                        disks.append((dev, size, model))
                    elif len(parts) >= 2 and "disk" in line:
                        dev  = f"/dev/{parts[0]}"
                        size = parts[1]
                        disks.append((dev, size, ""))
            except Exception:
                disks = []

            if not disks:
                tk.Label(self._raid_cb_frame,
                         text="Keine Laufwerke gefunden – 🔄 klicken",
                         bg=T.get("bg2", T["bg"]), fg=T["fg_dim"],
                         font=("Arial", 9)).pack(anchor="w")
                return

            for dev, size, model in disks:
                var = tk.BooleanVar(value=False)
                self._raid_disk_vars[dev] = var
                row = tk.Frame(self._raid_cb_frame, bg=T.get("bg2", T["bg"]))
                row.pack(fill="x", pady=1)
                ttk.Checkbutton(row, variable=var).pack(side="left")
                tk.Label(row,
                         text=f"{dev:<12}  {size:>8}   {model}",
                         bg=T.get("bg2", T["bg"]), fg=T["fg"],
                         font=("Monospace", 9), anchor="w").pack(side="left")

        self._raid_refresh_disks = _raid_refresh_disks
        _raid_refresh_disks()  # initial befüllen

        r2 = tk.Frame(cf, bg=T["bg"]); r2.pack(fill="x", pady=4)
        tk.Label(r2, text="RAID-Level:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 8))
        self._raid_level_cb = ttk.Combobox(r2, values=["0","1","5","6","10"],
                                            state="readonly", width=6)
        self._raid_level_cb.set("1")
        self._raid_level_cb.pack(side="left", padx=(0, 16))
        tk.Label(r2, text="MD-Name:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 6))
        self._raid_name_var = tk.StringVar(value="md0")
        ttk.Entry(r2, textvariable=self._raid_name_var, width=10).pack(side="left")

        tk.Label(cf, text=(
            "Min. Devices: RAID 0/1 = 2  |  RAID 5 = 3  |  RAID 6/10 = 4"
        ), bg=T["bg"], fg=T["fg_dim"], font=("Arial", 8)).pack(anchor="w", pady=(0, 4))

        btns = tk.Frame(cf, bg=T["bg"]); btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="▶ RAID erstellen", style="Accent.TButton",
                   command=self._raid_create).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="⏹ RAID stoppen", style="Danger.TButton",
                   command=self._raid_stop).pack(side="left")

        lf = ttk.LabelFrame(p, text=" Ausgabe ", padding=4)
        lf.pack(fill="both", expand=True)
        self._raid_log = self._make_log(lf)
        self._raid_log.pack(fill="both", expand=True)
        bf = tk.Frame(p, bg=T["bg"]); bf.pack(fill="x", pady=(4, 0))
        ttk.Button(bf, text="🗑 Leeren",
                   command=lambda: self._log_clear(self._raid_log)).pack(side="left")

    def _raid_mdstat(self):
        self._log_clear(self._raid_log)
        self._run_async(["cat", "/proc/mdstat"], self._raid_log)

    def _raid_detail(self):
        dev = f"/dev/{self._raid_detail_var.get().strip()}"
        self._log_clear(self._raid_log)
        self._run_async(["mdadm", "--detail", dev], self._raid_log)

    def _raid_create(self):
        devs = [dev for dev, var in self._raid_disk_vars.items() if var.get()]
        level = self._raid_level_cb.get()
        md    = f"/dev/{self._raid_name_var.get().strip() or 'md0'}"
        min_d = {"0": 2, "1": 2, "5": 3, "6": 4, "10": 4}
        if len(devs) < min_d.get(level, 2):
            messagebox.showerror("Fehler",
                f"RAID-{level} benötigt mindestens {min_d.get(level,2)} Devices!"); return
        if not messagebox.askyesno("RAID erstellen",
            f"RAID-{level} auf {md}\nDevices: {' '.join(devs)}\n\n"
            "⚠️  ALLE DATEN AUF DEN DEVICES WERDEN GELÖSCHT!\nFortfahren?", icon="warning"):
            return
        cmd = ["mdadm", "--create", md, "--level", level,
               "--raid-devices", str(len(devs))] + devs
        self._run_async(cmd, self._raid_log)

    def _raid_stop(self):
        md = f"/dev/{self._raid_detail_var.get().strip()}"
        if not messagebox.askyesno("RAID stoppen", f"RAID {md} stoppen?"):
            return
        self._run_async(["mdadm", "--stop", md], self._raid_log)

    # ════════════════════════════════════════════════════════════════════════
    #  TAB 5 – BOOT-REPARATUR
    # ════════════════════════════════════════════════════════════════════════
    def _build_boot_repair(self, nb):
        T = self.T
        tab = self._make_tab(nb, "🩹 Boot-Reparatur")
        p = tk.Frame(tab, bg=T["bg"])
        p.pack(fill="both", expand=True, padx=12, pady=10)

        # ── GRUB-Install ──────────────────────────────────────────────────
        gf = ttk.LabelFrame(p, text=" GRUB auf Laufwerk installieren ", padding=8)
        gf.pack(fill="x", pady=(0, 8))
        tk.Label(gf, text=(
            "Installiert GRUB-Bootloader auf ein Laufwerk.\n"
            "⚠️  Nur verwenden wenn das System nicht mehr bootet!"
        ), bg=T["bg"], fg=T["fg_dim"], font=("Arial", 9)).pack(anchor="w")
        gr = tk.Frame(gf, bg=T["bg"]); gr.pack(fill="x", pady=6)
        tk.Label(gr, text="Ziel-Laufwerk:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 8))
        self._boot_grub_cb = self._disk_combobox(gr)
        self._boot_grub_cb.pack(side="left", padx=(0, 4))
        ttk.Button(gr, text="🔄", width=3,
                   command=lambda: self._disk_refresh(self._boot_grub_cb)).pack(side="left")
        ttk.Button(gf, text="🔧 GRUB installieren",
                   style="Accent.TButton",
                   command=self._boot_grub_install).pack(anchor="w", pady=4)

        # ── TestDisk ──────────────────────────────────────────────────────
        tf = ttk.LabelFrame(p, text=" TestDisk – Partitionen wiederherstellen ", padding=8)
        tf.pack(fill="x", pady=(0, 8))
        tk.Label(tf, text=(
            "Stellt gelöschte Partitionen wieder her, repariert Partitionstabellen.\n"
            "Wird in einem eigenen Terminal gestartet."
        ), bg=T["bg"], fg=T["fg_dim"], font=("Arial", 9)).pack(anchor="w")
        tr = tk.Frame(tf, bg=T["bg"]); tr.pack(fill="x", pady=6)
        tk.Label(tr, text="Laufwerk:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 9)).pack(side="left", padx=(0, 8))
        self._boot_td_cb = self._disk_combobox(tr)
        self._boot_td_cb.pack(side="left", padx=(0, 4))
        self._boot_td_nodisk = tk.BooleanVar()
        ttk.Checkbutton(tr, text="Ohne Vorgabe starten",
                        variable=self._boot_td_nodisk).pack(side="left", padx=8)
        ttk.Button(tf, text="▶ TestDisk starten",
                   command=self._boot_testdisk).pack(anchor="w", pady=4)

        # ── Windows-MBR ───────────────────────────────────────────────────
        mf = ttk.LabelFrame(p, text=" Windows-MBR schreiben (ms-sys) ", padding=8)
        mf.pack(fill="x", pady=(0, 8))
        if shutil.which("ms-sys"):
            tk.Label(mf, text=(
                "Schreibt den originalen Windows-MBR auf ein Laufwerk.\n"
                "⚠️  Nur verwenden wenn Windows nach Linux-Installation nicht mehr bootet!"
            ), bg=T["bg"], fg=T["fg_dim"], font=("Arial", 9)).pack(anchor="w")
            mr = tk.Frame(mf, bg=T["bg"]); mr.pack(fill="x", pady=6)
            tk.Label(mr, text="Laufwerk:", bg=T["bg"], fg=T["fg"],
                     font=("Arial", 9)).pack(side="left", padx=(0, 8))
            self._boot_ms_cb = self._disk_combobox(mr)
            self._boot_ms_cb.pack(side="left", padx=(0, 4))
            ttk.Button(mf, text="⚠️ Windows-MBR schreiben", style="Danger.TButton",
                       command=self._boot_ms_sys).pack(anchor="w", pady=4)
        else:
            tk.Label(mf, text="ms-sys nicht installiert.\nsudo apt install ms-sys",
                     bg=T["bg"], fg=T["fg_dim"], font=("Arial", 9)).pack(anchor="w")

        lf = ttk.LabelFrame(p, text=" Ausgabe ", padding=4)
        lf.pack(fill="both", expand=True)
        self._boot_log = self._make_log(lf, height=8)
        self._boot_log.pack(fill="both", expand=True)

    def _boot_grub_install(self):
        dev = self._img_dev(self._boot_grub_cb)
        if not dev:
            messagebox.showerror("Fehler", "Bitte Laufwerk wählen."); return
        if not messagebox.askyesno("GRUB installieren",
            f"GRUB auf {dev} installieren?\n\n"
            "⚠️  Das Laufwerk muss das Systemlaufwerk sein!"):
            return
        self._run_async(["grub-install", dev], self._boot_log)

    def _boot_testdisk(self):
        if not shutil.which("testdisk"):
            messagebox.showerror("Fehler",
                "testdisk nicht installiert.\nsudo apt install testdisk"); return
        disk = "" if self._boot_td_nodisk.get() else self._img_dev(self._boot_td_cb)
        cmd  = f"testdisk {disk}" if disk else "testdisk"
        _run_in_terminal(cmd, "TestDisk – Partitionswiederherstellung")
        self._log_w(self._boot_log, "TestDisk wurde in neuem Terminal gestartet.\n")

    def _boot_ms_sys(self):
        dev = self._img_dev(self._boot_ms_cb)
        if not dev:
            messagebox.showerror("Fehler", "Bitte Laufwerk wählen."); return
        if not messagebox.askyesno("Windows-MBR",
            f"Windows-MBR auf {dev} schreiben?\n(ms-sys -m)\n\n"
            "⚠️  Überschreibt den Bootsektor unwiderruflich!"):
            return
        self._run_async(["ms-sys", "-m", dev], self._boot_log)

