"""
gui_drive_health.py – Laufwerk-Diagnose Tab für Peeßi's System Multitool
Separate Datei für einfache Wartung.

Vereint: S.M.A.R.T. Monitor + Badblocks-Oberflächenscan
Logs: ~/DriveTests/
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import subprocess, threading, os, datetime, re

try:
    from smart_engine import query_smart_attributes
    _SMART_ENGINE = True
except ImportError:
    _SMART_ENGINE = False

try:
    from database import SmartDatabase as _SmDB
    _SMART_DB = True
except ImportError:
    _SMART_DB = False

_INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))


class DriveHealthTab:
    """Laufwerk-Diagnose: S.M.A.R.T. + Badblocks – übersichtlich in einem Tab."""

    def __init__(self, nb, app, theme):
        self.app   = app
        self.root  = app.root
        self.T     = theme
        self._proc = None  # laufender Badblocks-Prozess
        self._smart_db = _SmDB() if _SMART_DB else None
        self._build(nb)

    # ─── Aufbau ────────────────────────────────────────────────────────────
    def _build(self, nb):
        T = self.T

        # Scrollbarer Tab via GuiBase-Hilfsmethode
        # (Mausrad auf Canvas + alle Kind-Widgets)
        _, inner = self._make_scrollable_tab(nb, "🩺 Laufwerk-Diagnose")
        inner.configure(padx=12, pady=10)

        # ── Laufwerk ───────────────────────────────────────────────────────
        drv_f = ttk.LabelFrame(inner, text=" Laufwerk ", padding=8)
        drv_f.pack(fill="x", pady=(0, 6))
        drv_row = tk.Frame(drv_f, bg=T["bg"])
        drv_row.pack(fill="x")
        tk.Label(drv_row, text="Gerät:", bg=T["bg"], fg=T["fg"],
                 font=("Arial", 10)).pack(side="left", padx=(0, 8))
        self._drv_cb = ttk.Combobox(drv_row, state="readonly",
                                     font=("Arial", 10), width=50)
        self._drv_cb.pack(side="left", padx=(0, 6))
        self._drv_cb.bind("<<ComboboxSelected>>", self._on_select)
        ttk.Button(drv_row, text="🔄",
                   command=self._refresh_drives).pack(side="left")

        self._drv_info = tk.Label(drv_f, text="", bg=T["bg"],
                                   fg=T["fg_dim"], font=("Monospace", 9))
        self._drv_info.pack(anchor="w", pady=(4, 0))

        # ── Sub-Notebook: SMART | Badblocks ────────────────────────────────
        sub = ttk.Notebook(inner)
        sub.pack(fill="both", expand=True, pady=(6, 0))

        self._build_smart_sub(sub, T)
        self._build_badblocks_sub(sub, T)

        self.root.after(500, self._refresh_drives)

    # ─── Sub-Tab: SMART ────────────────────────────────────────────────────
    def _build_smart_sub(self, sub, T):
        tab = ttk.Frame(sub)
        sub.add(tab, text="📊 S.M.A.R.T.")
        p = tk.Frame(tab, bg=T["bg"])
        p.pack(fill="both", expand=True, padx=8, pady=8)

        # Buttons
        btn = tk.Frame(p, bg=T["bg"]); btn.pack(fill="x", pady=(0, 6))
        self._smart_run_btn = ttk.Button(btn, text="🔍 SMART auslesen",
                                          style="Accent.TButton",
                                          command=self._smart_read)
        self._smart_run_btn.pack(side="left", padx=(0, 6))
        ttk.Button(btn, text="💾 In DB",     command=self._smart_save_db ).pack(side="left", padx=(0, 6))
        ttk.Button(btn, text="📈 Verlauf",   command=self._smart_history ).pack(side="left", padx=(0, 6))
        ttk.Button(btn, text="📋 Kopieren",  command=self._smart_copy    ).pack(side="left", padx=(0, 6))
        ttk.Button(btn, text="💾 Als TXT",   command=self._smart_save_txt).pack(side="left")

        # Attribut-Tabelle
        tf = ttk.LabelFrame(p, text=" Attribute ", padding=4)
        tf.pack(fill="both", expand=True)
        scols = ("ID", "Attribut", "Wert", "Worst", "Thresh", "Raw", "Status")
        self._smart_tree = ttk.Treeview(tf, columns=scols, show="headings", height=12)
        sw = {"ID":40,"Attribut":200,"Wert":55,"Worst":55,"Thresh":55,"Raw":110,"Status":100}
        for c in scols:
            self._smart_tree.heading(c, text=c)
            self._smart_tree.column(c, width=sw.get(c, 100))
        self._smart_tree.tag_configure("warn", background=T.get("tag_system","#fffacc"))
        self._smart_tree.tag_configure("crit", background=T.get("tag_internal","#ffcccc"))
        sm_sb = ttk.Scrollbar(tf, orient="vertical", command=self._smart_tree.yview)
        self._smart_tree.configure(yscrollcommand=sm_sb.set)
        self._smart_tree.pack(side="left", fill="both", expand=True)
        sm_sb.pack(side="right", fill="y")

    # ─── Sub-Tab: Badblocks ────────────────────────────────────────────────
    def _build_badblocks_sub(self, sub, T):
        tab = ttk.Frame(sub)
        sub.add(tab, text="🔬 Badblocks-Scan")
        p = tk.Frame(tab, bg=T["bg"])
        p.pack(fill="both", expand=True, padx=8, pady=8)

        # Infos
        tk.Label(p, text=(
            "Nur-Lesen Oberflächenscan – nicht destruktiv.\n"
            "Blockgröße: HDD = 4096 | SSD/Flash = 32768  |  "
            "Logs: ~/DriveTests/\n"
            "⚠️  HDD-Scans können mehrere Stunden dauern."
        ), bg=T["bg"], fg=T["fg_dim"], font=("Arial", 9),
           justify="left").pack(anchor="w", pady=(0, 6))

        # Optionen
        opt = tk.Frame(p, bg=T["bg"]); opt.pack(fill="x", pady=(0, 6))
        self._do_smart    = tk.BooleanVar(value=True)
        self._do_bb       = tk.BooleanVar(value=True)
        self._do_shutdown = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="SMART-Check vor dem Scan durchführen",
                        variable=self._do_smart).pack(side="left", padx=(0,12))
        ttk.Checkbutton(opt, text="🔌 Shutdown nach Abschluss",
                        variable=self._do_shutdown).pack(side="left")

        # Buttons
        btn = tk.Frame(p, bg=T["bg"]); btn.pack(fill="x", pady=(0, 6))
        self._bb_start_btn = ttk.Button(btn, text="▶ Scan starten",
                                         style="Accent.TButton",
                                         command=self._bb_start)
        self._bb_start_btn.pack(side="left", padx=(0, 6))
        self._bb_stop_btn = ttk.Button(btn, text="⏹ Abbrechen",
                                        style="Danger.TButton",
                                        command=self._bb_stop,
                                        state="disabled")
        self._bb_stop_btn.pack(side="left", padx=(0, 6))
        ttk.Button(btn, text="📁 Log-Ordner",
                   command=self._open_logdir).pack(side="left", padx=(0, 6))
        ttk.Button(btn, text="📋 Kopieren",
                   command=self._bb_copy).pack(side="left", padx=(0, 6))
        ttk.Button(btn, text="🗑 Leeren",
                   command=self._bb_clear).pack(side="left")

        # Ausgabe (ein Fenster)
        lf = ttk.LabelFrame(p, text=" Ausgabe ", padding=4)
        lf.pack(fill="both", expand=True)
        self._bb_log = scrolledtext.ScrolledText(
            lf, height=16, state="disabled",
            font=("Monospace", 9), bg=T.get("bg2", T["bg"]), fg=T["fg"])
        self._bb_log.pack(fill="both", expand=True)

    # ─── Scrollbarer Tab ───────────────────────────────────────────────────
    def _make_scrollable_tab(self, nb, title: str):
        """Erstellt scrollbaren Tab – Mausrad funktioniert überall."""
        T = self.T
        outer = ttk.Frame(nb)
        nb.add(outer, text=title)
        canvas = tk.Canvas(outer, bg=T["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=T["bg"])
        win   = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))

        def _scroll(ev):
            if ev.delta:
                canvas.yview_scroll(int(-1*(ev.delta/120)), "units")
            elif ev.num == 4:
                canvas.yview_scroll(-1, "units")
            elif ev.num == 5:
                canvas.yview_scroll(1, "units")

        def _bind_all(w):
            w.bind("<MouseWheel>", _scroll, add="+")
            w.bind("<Button-4>",   _scroll, add="+")
            w.bind("<Button-5>",   _scroll, add="+")
            for c in w.winfo_children():
                _bind_all(c)

        _bind_all(canvas)
        inner.bind("<Configure>", lambda e: _bind_all(canvas), add="+")
        self._canvas_scroll = _scroll  # für späteres Nachbinden
        self._bind_scroll   = _bind_all
        self._canvas        = canvas
        return outer, inner

    # ─── Hilfsfunktionen ───────────────────────────────────────────────────
    def _sh(self, cmd, timeout=15):
        try:
            r = subprocess.run(["bash", "-c", cmd],
                               capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout, r.stderr
        except Exception as e:
            return -1, "", str(e)

    def _bb_write(self, text: str):
        clean = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', text)
        self._bb_log.configure(state="normal")
        self._bb_log.insert("end", clean)
        self._bb_log.see("end")
        self._bb_log.configure(state="disabled")

    def _bb_clear(self):
        self._bb_log.configure(state="normal")
        self._bb_log.delete("1.0", "end")
        self._bb_log.configure(state="disabled")

    def _bb_copy(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self._bb_log.get("1.0", "end"))
        self.root.update()

    def _open_logdir(self):
        os.makedirs(os.path.expanduser("~/DriveTests"), exist_ok=True)
        subprocess.Popen(["xdg-open", os.path.expanduser("~/DriveTests")])

    def _dev(self) -> str:
        sel = self._drv_cb.get()
        return "" if (not sel or sel.startswith("Kein") or sel.startswith("Fehler")) \
               else sel.split("|")[0].strip()

    # ─── Laufwerke laden ───────────────────────────────────────────────────
    def _refresh_drives(self):
        drives = getattr(self.app, "all_drives", [])
        if drives:
            vals = [f"{d.device}  |  {d.model}  |  {d.get_size_human()}  |  {d.get_type_label()}"
                    for d in drives]
        else:
            _, out, _ = self._sh(
                "lsblk -d -o NAME,SIZE,MODEL,TYPE -n | awk '$4==\"disk\"{print \"/dev/\"$1\"  |  \"$3\"  |  \"$2}'")
            vals = [l.strip() for l in out.splitlines() if l.strip()] or ["Kein Laufwerk"]
        self._drv_cb["values"] = vals
        if vals:
            self._drv_cb.current(0)
            self._on_select(None)

    def _on_select(self, _):
        dev = self._dev()
        if not dev: return
        def worker():
            _, o1, _ = self._sh(f"lsblk -dno SIZE,ROTA,TRAN '{dev}' 2>/dev/null")
            _, o2, _ = self._sh(
                f"smartctl -i '{dev}' 2>/dev/null | grep -E 'Device Model|Serial|Capacity|health|SMART' | head -4")
            parts = o1.strip().split()
            size = parts[0] if parts else "?"
            rota = parts[1] if len(parts)>1 else "0"
            tran = parts[2] if len(parts)>2 else ""
            typ  = "HDD" if rota=="1" else ("USB" if tran=="usb" else "SSD/Flash")
            info = f"Typ: {typ}  |  Größe: {size}  |  Schnittstelle: {tran.upper() or '–'}"
            if o2.strip():
                info += "\n" + "\n".join("  "+l.strip() for l in o2.splitlines()[:3])
            self.root.after(0, lambda: self._drv_info.config(text=info))
        threading.Thread(target=worker, daemon=True).start()

    # ─── SMART ─────────────────────────────────────────────────────────────
    def _smart_read(self):
        dev = self._dev()
        if not dev:
            messagebox.showinfo("Hinweis", "Bitte Laufwerk auswählen."); return
        for row in self._smart_tree.get_children():
            self._smart_tree.delete(row)

        def worker():
            rows = []
            if _SMART_ENGINE:
                try:
                    attrs = query_smart_attributes(dev)
                    if attrs:
                        for a in attrs:
                            rows.append((
                                a["id"], a["name"], a["value"], a["worst"],
                                a["thresh"], a["raw"], a["status"],
                                (a["tag"],) if a.get("tag") else ()))
                except Exception:
                    pass
            if not rows:
                _, out, _ = self._sh(f"smartctl -A '{dev}' 2>&1", timeout=20)
                for line in out.splitlines():
                    p = line.split()
                    if len(p) >= 10 and p[0].isdigit():
                        rows.append((p[0],p[1],p[3],p[4],p[5],p[9],"OK",()))
            self.root.after(0, lambda: self._smart_fill(rows, dev))

        threading.Thread(target=worker, daemon=True).start()

    def _smart_fill(self, rows, dev):
        for row in self._smart_tree.get_children():
            self._smart_tree.delete(row)
        if rows:
            for r in rows:
                self._smart_tree.insert("", "end", values=r[:7], tags=r[7])
            # Scrollbinding auf neuen Tree aktualisieren
            if hasattr(self, "_bind_scroll"):
                self._bind_scroll(self._canvas)
        else:
            messagebox.showinfo("SMART",
                f"Keine SMART-Daten für {dev}.\n"
                "SMART nicht unterstützt oder deaktiviert (typisch bei SD/USB).")

    def _smart_as_text(self) -> str:
        dev = self._dev() or "Unbekannt"
        ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cols = ("ID","Attribut","Wert","Worst","Thresh","Raw","Status")
        widths = [len(c) for c in cols]
        rows = [[str(v) for v in self._smart_tree.item(i)["values"]]
                for i in self._smart_tree.get_children()]
        for r in rows:
            for i,v in enumerate(r): widths[i]=max(widths[i],len(v))
        sep = "-"*(sum(widths)+len(widths)*3+1)
        hdr = "| "+" | ".join(c.ljust(widths[i]) for i,c in enumerate(cols))+" |"
        out = [f"SMART: {dev}", f"Stand: {ts}", sep, hdr, sep]
        for r in rows:
            out.append("| "+" | ".join(v.ljust(widths[i]) for i,v in enumerate(r))+" |")
        out.append(sep)
        return "\n".join(out)

    def _smart_save_db(self):
        dev = self._dev()
        if not dev or not self._smart_db:
            messagebox.showinfo("Hinweis","Kein Gerät oder keine DB."); return
        attrs = {}
        for row in self._smart_tree.get_children():
            v = self._smart_tree.item(row)["values"]
            if v:
                try: attrs[str(v[1])] = {"normalized":int(v[2]),"raw":int(str(v[5]).split()[0])}
                except: pass
        if attrs:
            self._smart_db.record(dev, attrs)
            messagebox.showinfo("SMART", f"✅ {len(attrs)} Attribute gespeichert.")
        else:
            messagebox.showinfo("SMART","Tabelle leer – zuerst SMART auslesen.")

    def _smart_history(self):
        dev = self._dev()
        if not dev or not self._smart_db:
            messagebox.showinfo("Hinweis","Kein Gerät oder keine DB."); return
        try: attrs = self._smart_db.get_attributes(dev)
        except: attrs = []
        if not attrs:
            messagebox.showinfo("Verlauf",
                f"Keine Verlaufsdaten für {dev}.\nBitte zuerst 'In DB' klicken."); return
        lines = [f"SMART-Verlauf: {dev}",
                 f"Stand: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                 "="*60]
        for attr in attrs:
            try: data = self._smart_db.get_history(dev, attr, days=90)
            except: data = []
            if not data: continue
            lines += [f"\n{attr} ({len(data)} Messwerte)",
                      f"  {'Zeitstempel':<20}  {'Raw':>10}",
                      f"  {'-'*20}  {'-'*10}"]
            for ts,val in data:
                lines.append(f"  {str(ts)[:19]:<20}  {str(val or 0):>10}")
        # Als Dialog anzeigen
        win = tk.Toplevel(self.root)
        win.title(f"SMART-Verlauf: {dev}")
        win.geometry("700x500")
        st = scrolledtext.ScrolledText(win, font=("Monospace",9))
        st.pack(fill="both", expand=True, padx=8, pady=8)
        st.insert("end", "\n".join(lines))
        st.configure(state="disabled")

    def _smart_copy(self):
        if not self._smart_tree.get_children():
            messagebox.showinfo("SMART","Tabelle leer."); return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._smart_as_text())
        self.root.update()
        messagebox.showinfo("Kopiert","SMART-Tabelle kopiert.")

    def _smart_save_txt(self):
        if not self._smart_tree.get_children():
            messagebox.showinfo("SMART","Tabelle leer."); return
        dev = (self._dev() or "laufwerk").replace("/dev/","").replace("/","_")
        ts  = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        path = filedialog.asksaveasfilename(
            title="SMART speichern",
            initialfile=f"smart_{dev}_{ts}.txt",
            defaultextension=".txt",
            filetypes=[("Text","*.txt"),("Alle","*")])
        if path:
            try:
                open(path,"w").write(self._smart_as_text())
                messagebox.showinfo("Gespeichert", path)
            except Exception as e:
                messagebox.showerror("Fehler", str(e))

    # ─── Badblocks ─────────────────────────────────────────────────────────
    def _bb_start(self):
        dev = self._dev()
        if not dev:
            messagebox.showerror("Fehler","Bitte Laufwerk auswählen."); return
        _, rota, _ = self._sh(
            f"cat /sys/block/{dev.replace('/dev/','')}/queue/rotational 2>/dev/null")
        blocksize = "4096" if rota.strip()=="1" else "32768"
        typ = "HDD" if rota.strip()=="1" else "SSD/Flash"

        msg = (f"Laufwerk: {dev}  [{typ}]\n"
               f"Blockgröße: {blocksize}\n\n"
               f"{'SMART-Check wird vorher durchgeführt.'+chr(10) if self._do_smart.get() else ''}"
               f"{'🔌 Rechner fährt nach Abschluss herunter!'+chr(10) if self._do_shutdown.get() else ''}"
               f"\nScan jetzt starten?")
        if not messagebox.askyesno("Scan starten", msg, icon="warning"): return

        self._bb_clear()
        self._bb_start_btn.config(state="disabled")
        self._bb_stop_btn.config(state="normal")

        real_user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"
        logdir  = f"/home/{real_user}/DriveTests"
        ts      = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logfile = f"{logdir}/test_{ts}.log"

        def worker():
            env = os.environ.copy()
            env.setdefault("SUDO_USER", real_user)
            log_lines = []

            def out(t):
                self.root.after(0, lambda x=t: self._bb_write(x))
                log_lines.append(t)

            out(f"{'='*54}\n  LAUFWERK-SCAN  {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                f"  Gerät: {dev}  [{typ}]  Blockgröße: {blocksize}\n{'='*54}\n\n")

            # SMART vorher
            if self._do_smart.get():
                out("[1/2] S.M.A.R.T. Check...\n" + "-"*40 + "\n")
                _, s, _ = self._sh(f"smartctl -H '{dev}' 2>&1; smartctl -A '{dev}' 2>&1",
                                   timeout=30)
                out((s or "SMART nicht verfügbar.\n") + "\n")

            # Badblocks
            out(f"[{'2/2' if self._do_smart.get() else '1/1'}] Badblocks (Nur-Lesen)...\n"
                + "-"*40 + "\n")
            self._proc = subprocess.Popen(
                ["badblocks", "-sv", "-b", blocksize, dev],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=env)
            for line in self._proc.stdout:
                self.root.after(0, lambda l=line: self._bb_write(l))
                log_lines.append(line)
            self._proc.wait()
            rc = self._proc.returncode
            self._proc = None

            result = ("✅ Keine defekten Sektoren." if rc==0 else
                      "⏹ Abgebrochen." if rc==-1 else
                      f"⚠️  Exit-Code: {rc}")
            out(f"\n{result}\n\n{'='*54}\n"
                f"Fertig: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n{'='*54}\n")

            # Log schreiben
            try:
                os.makedirs(logdir, exist_ok=True)
                with open(logfile,"w") as f:
                    f.writelines(log_lines)
                subprocess.run(["chown",f"{real_user}:{real_user}",logfile],
                               capture_output=True)
                self.root.after(0, lambda: self._bb_write(f"📁 Log: {logfile}\n"))
            except Exception as e:
                self.root.after(0, lambda: self._bb_write(f"Log-Fehler: {e}\n"))

            self.root.after(0, self._bb_done)

            if self._do_shutdown.get() and rc==0:
                self.root.after(0, lambda: self._bb_write("🔌 Shutdown in 60s...\n"))
                import time; time.sleep(60)
                subprocess.run(["shutdown","-h","now"])

        threading.Thread(target=worker, daemon=True).start()

    def _bb_stop(self):
        if self._proc:
            try: self._proc.terminate()
            except: pass
            self._proc = None
            self._bb_write("\n⏹ Abgebrochen.\n")
        self._bb_done()

    def _bb_done(self):
        self._bb_start_btn.config(state="normal")
        self._bb_stop_btn.config(state="disabled")
