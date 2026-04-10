#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: gui_drives.py  –  Laufwerke-Tab
  Sub-Tabs: Datenrettung, Sicheres Löschen, SMART-Monitor, ISO-Brenner,
            Partition einbinden
"""

import os
import re
import shutil
import hashlib
import sqlite3
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog, scrolledtext
from typing import List, Optional

from config import ORIGINAL_USER, USER_HOME, RECOVERY_ROOT, SMART_DB_FILE
from wipe_engine import WipeEngine
from smart_engine import query_smart, query_smart_attributes, is_failed
from gui_base import GuiBase

# Laufwerk-Diagnose Tab (separate Datei für Wartung)
try:
    from gui_drive_health import DriveHealthTab
    _HEALTH_AVAILABLE = True
except ImportError:
    _HEALTH_AVAILABLE = False

# matplotlib entfernt – SMART-Verlauf als Texttabelle
HAS_MATPLOTLIB = False


class DrivesTabs(GuiBase):

    def __init__(self, nb_main, app):
        super().__init__(app.root, app.settings, app.theme, app._log_widgets)
        self.app      = app
        self.nb_main  = nb_main
        self.wipe_eng = app.wipe_eng
        self.rec_eng  = app.rec_eng
        self.smart_db = app.smart_db
        self.sec      = app.sec

        self.all_drives              = []
        self.selected_wipe_drv       = None
        self._progress_pct_var       = None

        self._build()

    def _build(self):
        tab = ttk.Frame(self.nb_main)
        self.nb_main.add(tab, text="💾 Laufwerke")
        nb = ttk.Notebook(tab)
        nb.pack(fill='both', expand=True, padx=4, pady=4)
        self._build_recovery_tab(nb)
        self._build_wipe_tab(nb)
        self._build_iso_tab(nb)
        self._build_usb_clone_tab(nb)
        self._build_partition_tab(nb)
        self._build_drive_health_tab(nb)

    # ── Laufwerke aktualisieren ───────────────────────────────────────────────
    def refresh_drives(self, drives: list):
        self.all_drives = drives
        self._update_recovery_combo()
        self._update_wipe_list()
        self._update_smart_combo()
        self._update_iso_targets()
        self._update_clone_combos()

    def _update_recovery_combo(self):
        if not hasattr(self, 'rec_dev_combo'):
            return
        vals = [f"{d.device}  |  {d.model}  |  {d.get_size_human()}"
                for d in self.all_drives]
        self.rec_dev_combo['values'] = vals
        if vals:
            self.rec_dev_combo.current(0)

    def _update_wipe_list(self):
        if not hasattr(self, 'wipe_tree'):
            return
        for row in self.wipe_tree.get_children():
            self.wipe_tree.delete(row)
        for d in self.all_drives:
            tag = ('system'   if d.is_system_drive else
                   'internal' if not d.removable and not d.is_usb else
                   'removable')
            if not self.show_internal_var.get() and tag == 'internal':
                continue
            # Bezeichnung: Modell + Gerätetyp-Hinweis
            typ    = d.get_type_label()
            model  = d.model or "Unbekannt"
            bezeichnung = f"{model}  [{typ}]"
            self.wipe_tree.insert('', 'end', iid=d.device,
                values=(d.device, bezeichnung, typ,
                        d.get_size_human(), d.fs_type or "—",
                        d.mount_point or "—",
                        "✓" if d.is_ssd or d.is_nvme else ""),
                tags=(tag,))

    def _update_smart_combo(self):
        if not hasattr(self, 'smart_dev_cb'):
            return
        vals = [d.device for d in self.all_drives]
        self.smart_dev_cb['values'] = vals
        if vals and not self.smart_dev_var.get():
            self.smart_dev_cb.current(0)

    def _update_iso_targets(self):
        if not hasattr(self, 'iso_target_cb'):
            return
        vals = []
        for d in self.all_drives:
            label = d.get_type_label()
            warn  = "  ⚠️SYSTEM" if d.is_system_drive else ""
            vals.append(f"{d.device}  |  {d.model}  |  {d.get_size_human()}  |  {label}{warn}")
        self.iso_target_cb['values'] = vals if vals else ["Kein Laufwerk – 🔄 klicken"]
        # Vorauswahl: erstes Nicht-Systemlaufwerk bevorzugen
        for i, d in enumerate(self.all_drives):
            if not d.is_system_drive:
                self.iso_target_cb.current(i)
                return
        if vals:
            self.iso_target_cb.current(0)

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: DATENRETTUNG
    # ══════════════════════════════════════════════════════════════════════
    def _build_recovery_tab(self, nb):
        T   = self.theme
        _, pane = self.make_scrollable_tab(nb, "🔍 Datenrettung")
        pane = tk.Frame(pane, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        sel = ttk.LabelFrame(pane, text=" Defektes Gerät ", padding=10)
        sel.pack(fill='x', pady=(0, 8))
        self.rec_dev_var   = tk.StringVar()
        self.rec_dev_combo = ttk.Combobox(sel, textvariable=self.rec_dev_var,
                                          state='readonly', font=('Helvetica', 10))
        self.rec_dev_combo.pack(fill='x', side='left', expand=True, padx=(0, 8))
        ttk.Button(sel, text="🔄", width=3,
                   command=self.app.refresh_drives).pack(side='left')

        info_f = ttk.LabelFrame(pane, text=" Speicherort ", padding=10)
        info_f.pack(fill='x', pady=(0, 8))
        tk.Label(info_f, text=f"Ziel: {RECOVERY_ROOT}",
                 bg=T["bg"], fg=T["fg"], font=('Arial', 9)).pack(anchor='w')
        tk.Label(info_f, text="⚠️  Wählen Sie NIE Ihre Systemplatte aus!",
                 bg=T["bg"], fg=T["danger"], font=('Arial', 9, 'bold')).pack(anchor='w', pady=(4,0))

        prog_f = ttk.LabelFrame(pane, text=" Rettungsvorgang ", padding=10)
        prog_f.pack(fill='both', expand=True)
        self._rec_pct_var = tk.DoubleVar()
        ttk.Progressbar(prog_f, variable=self._rec_pct_var, maximum=100).pack(fill='x', pady=(0,6))
        self._progress_pct_var    = self._rec_pct_var
        self.app._progress_pct_var = self._rec_pct_var
        self.rec_log = self.make_log_widget(prog_f, height=10)
        self.rec_log.pack(fill='both', expand=True)

        btn_f = tk.Frame(prog_f, bg=T["bg"])
        btn_f.pack(fill='x', pady=(8, 0))
        self.rec_start_btn = ttk.Button(btn_f, text="🚀 Rettung starten",
                                        style='Accent.TButton',
                                        command=self._confirm_recovery)
        self.rec_start_btn.pack(side='right', padx=4)
        self.rec_abort_btn = ttk.Button(btn_f, text="⏹ Abbruch",
                                        state='disabled', command=self._abort_recovery)
        self.rec_abort_btn.pack(side='right', padx=4)
        ttk.Button(btn_f, text="📋 Kopieren",
                   command=lambda: self.copy_log(self.rec_log)).pack(side='left')

    def _confirm_recovery(self):
        sel = self.rec_dev_var.get()
        if not sel:
            messagebox.showwarning("Keine Auswahl", "Bitte Gerät auswählen.")
            return
        dev = sel.split('|')[0].strip()
        try:
            size_b = int(subprocess.check_output(
                ['blockdev', '--getsize64', dev], timeout=5).decode().strip())
            size_g = size_b / 1024**3
        except Exception:
            size_g = 0
        free_g = shutil.disk_usage(USER_HOME).free / 1024**3
        if size_g > free_g * 0.9:
            if not messagebox.askyesno("Speicherplatz knapp",
                f"Gerät: {size_g:.1f} GB,  Frei: {free_g:.1f} GB\nTrotzdem?"):
                return
        if messagebox.askyesno("Rettung bestätigen",
            f"Gerät: {dev}\nDauer: Stunden bis Tage.\nJetzt starten?", icon='warning'):
            self._start_recovery(dev)

    def _start_recovery(self, dev):
        self.rec_start_btn.config(state='disabled')
        self.rec_abort_btn.config(state='normal')
        self._rec_pct_var.set(0)
        def worker():
            ok = self.rec_eng.recover(dev)
            self.root.after(0, lambda: self._on_recovery_done(ok))
        threading.Thread(target=worker, daemon=True).start()

    def _on_recovery_done(self, ok):
        self.rec_start_btn.config(state='normal')
        self.rec_abort_btn.config(state='disabled')
        if ok:
            messagebox.showinfo("Fertig", "✅ Datenrettung abgeschlossen!")
        else:
            messagebox.showerror("Fehler", "❌ Fehlgeschlagen oder abgebrochen.")

    def _abort_recovery(self):
        self.rec_eng.stop()
        self.rec_abort_btn.config(state='disabled')

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: SICHERES LÖSCHEN
    # ══════════════════════════════════════════════════════════════════════
    def _build_wipe_tab(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="\U0001f9f9 Sicheres Löschen")

        # Scrollbarer Bereich
        canvas = tk.Canvas(tab, bg=T["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        pane = tk.Frame(canvas, bg=T["bg"])
        win  = canvas.create_window((0, 0), window=pane, anchor='nw')

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
        def _on_canvas_configure(e):
            canvas.itemconfig(win, width=e.width)
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        def _on_mousewheel_linux(e):
            canvas.yview_scroll(-1 if e.num == 4 else 1, 'units')

        pane.bind('<Configure>', _on_frame_configure)
        canvas.bind('<Configure>', _on_canvas_configure)
        canvas.bind('<MouseWheel>', _on_mousewheel)
        canvas.bind('<Button-4>', _on_mousewheel_linux)
        canvas.bind('<Button-5>', _on_mousewheel_linux)
        tab.bind('<MouseWheel>', _on_mousewheel)
        tab.bind('<Button-4>', _on_mousewheel_linux)
        tab.bind('<Button-5>', _on_mousewheel_linux)

        # Innenabstand
        pane_inner = tk.Frame(pane, bg=T["bg"])
        pane_inner.pack(fill='both', expand=True, padx=14, pady=10)
        pane = pane_inner

        # ── Laufwerksliste ────────────────────────────────────────────────────
        list_f = ttk.LabelFrame(pane, text=" Verfügbare Laufwerke ", padding=8)
        list_f.pack(fill='both', expand=True, pady=(0, 8))

        cols = ('Gerät', 'Bezeichnung', 'Typ', 'Größe', 'Dateisystem', 'Eingehängt', 'SSD')
        self.wipe_tree = ttk.Treeview(list_f, columns=cols, show='headings', height=6)
        widths = {
            'Gerät':80, 'Bezeichnung':220, 'Typ':80,
            'Größe':80, 'Dateisystem':85, 'Eingehängt':130, 'SSD':45
        }
        for c in cols:
            self.wipe_tree.heading(c, text=c)
            self.wipe_tree.column(c, width=widths.get(c, 100), minwidth=40)
        sb = ttk.Scrollbar(list_f, orient='vertical', command=self.wipe_tree.yview)
        self.wipe_tree.configure(yscrollcommand=sb.set)
        self.wipe_tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.wipe_tree.bind('<<TreeviewSelect>>', self._on_wipe_select)
        self.wipe_tree.tag_configure('system',    background=T["tag_system"])
        self.wipe_tree.tag_configure('internal',  background=T["tag_internal"])
        self.wipe_tree.tag_configure('removable', background=T["tag_removable"])

        # ── Optionen ──────────────────────────────────────────────────────────
        opt_f = ttk.LabelFrame(pane, text=" Lösch-Optionen ", padding=8)
        opt_f.pack(fill='x', pady=(0, 8))

        row1 = tk.Frame(opt_f, bg=T["bg"])
        row1.pack(fill='x', pady=4)
        tk.Label(row1, text="Methode:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 10)).pack(side='left', padx=(0, 8))
        self.wipe_method_var = tk.StringVar()
        self.wipe_method_cb  = ttk.Combobox(row1, textvariable=self.wipe_method_var,
                                             state='readonly', width=40,
                                             font=('Arial', 10))
        self.wipe_method_cb['values'] = [v['name'] for v in WipeEngine.METHODS.values()]
        self.wipe_method_cb.current(0)
        self.wipe_method_cb.pack(side='left')
        self._method_map = {v['name']: k for k, v in WipeEngine.METHODS.items()}

        self.wipe_ssd_hint = tk.Label(row1, text="", bg=T["bg"], fg=T["warning"],
                                      font=('Arial', 10, 'bold'))
        self.wipe_ssd_hint.pack(side='left', padx=12)

        self.show_internal_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_f,
            text="⚠️  Interne / System-Laufwerke anzeigen (gefährlich!)",
            variable=self.show_internal_var,
            command=self._update_wipe_list).pack(anchor='w', pady=4)

        # Ausgewähltes Laufwerk anzeigen
        self.wipe_sel_lbl = tk.Label(opt_f, text="Kein Laufwerk ausgewählt",
                                     bg=T["bg"], fg=T["fg_dim"],
                                     font=('Arial', 10, 'italic'))
        self.wipe_sel_lbl.pack(anchor='w', pady=(0, 2))

        # ── Fortschritt ───────────────────────────────────────────────────────
        prog_f = ttk.LabelFrame(pane, text=" Fortschritt ", padding=8)
        prog_f.pack(fill='x', pady=(0, 8))
        self.wipe_pbar = ttk.Progressbar(prog_f, mode='indeterminate')
        self.wipe_pbar.pack(fill='x', pady=(0, 6))
        self.wipe_log = self.make_log_widget(prog_f, height=6)
        self.wipe_log.pack(fill='both', expand=True)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(0, 0))
        self.wipe_start_btn = ttk.Button(btn_f,
            text="\U0001f525 Laufwerk komplett löschen",
            style='Danger.TButton', state='disabled',
            command=self._confirm_wipe)
        self.wipe_start_btn.pack(side='left', padx=4)
        self.wipe_stop_btn = ttk.Button(btn_f, text="\U0001f6d1 Abbrechen",
                                         state='disabled', command=self._stop_wipe)
        self.wipe_stop_btn.pack(side='left', padx=4)
        ttk.Button(btn_f, text="\U0001f504 Aktualisieren",
                   command=self.app.refresh_drives).pack(side='left', padx=4)
        ttk.Button(btn_f, text="nwipe (Terminal)",
                   command=self._wipe_nwipe).pack(side='left', padx=4)
        ttk.Button(btn_f, text="\U0001f4cb Log kopieren",
                   command=lambda: self.copy_log(self.wipe_log)).pack(side='right', padx=4)

        # ── Freien Speicherplatz löschen ──────────────────────────────────────
        free_f = ttk.LabelFrame(pane,
            text=" \U0001f9f9 Freien Speicherplatz löschen (Daten bleiben erhalten) ",
            padding=10)
        free_f.pack(fill='x', pady=(12, 0))

        tk.Label(free_f, text=(
            "Ueberschreibt nur den FREIEN Speicherplatz – vorhandene Dateien bleiben erhalten.\n"
            "Bereits geloeschte Dateien werden dadurch unwiederbringlich vernichtet."
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 10), justify='left'
        ).pack(anchor='w', pady=(0, 8))

        # Einhängepunkt-Auswahl
        sel_row = tk.Frame(free_f, bg=T["bg"])
        sel_row.pack(fill='x', pady=(0, 6))
        tk.Label(sel_row, text="Partition:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 8))
        self.free_mount_var = tk.StringVar()
        self.free_mount_cb  = ttk.Combobox(sel_row, textvariable=self.free_mount_var,
                                            state='readonly', width=58,
                                            font=('Arial', 10))
        self.free_mount_cb.pack(side='left', padx=(0, 8))
        ttk.Button(sel_row, text="\U0001f504 Aktualisieren",
                   command=self._refresh_free_mounts).pack(side='left')

        # Freier Speicher Info-Label
        self.free_info_lbl = tk.Label(free_f, text="",
                                      bg=T["bg"], fg=T["fg_dim"],
                                      font=('Arial', 9))
        self.free_info_lbl.pack(anchor='w', pady=(0, 6))
        self.free_mount_cb.bind('<<ComboboxSelected>>', lambda e: self._update_free_info())

        # Methode
        meth_row = tk.Frame(free_f, bg=T["bg"])
        meth_row.pack(fill='x', pady=(0, 8))
        tk.Label(meth_row, text="Methode:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 10)).pack(side='left', padx=(0, 8))
        self.free_method_var = tk.StringVar(value="sfill (sicher, empfohlen)")
        ttk.Combobox(meth_row, textvariable=self.free_method_var,
                     values=["sfill (sicher, empfohlen)",
                             "dd Nullen (schnell, ein Durchgang)"],
                     state='readonly', width=36,
                     font=('Arial', 10)).pack(side='left')
        tk.Label(meth_row, text="  sfill: sudo apt install secure-delete",
                 bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9)).pack(side='left', padx=8)

        # Buttons
        # Fortschrittsbalken
        self.free_pbar = ttk.Progressbar(free_f, mode='indeterminate')
        self.free_pbar.pack(fill='x', pady=(0, 4))
        self.free_status_lbl = tk.Label(free_f, text='',
                                        bg=T['bg'], fg=T['fg_dim'],
                                        font=('Arial', 9))
        self.free_status_lbl.pack(anchor='w', pady=(0, 6))

        free_btn_f = tk.Frame(free_f, bg=T["bg"])
        free_btn_f.pack(fill='x')
        self.free_start_btn = ttk.Button(free_btn_f,
            text="\U0001f9f9 Freien Speicher löschen",
            style='Accent.TButton',
            command=self._confirm_free_wipe)
        self.free_start_btn.pack(side='left', padx=4)
        self.free_stop_btn = ttk.Button(free_btn_f, text="\U0001f6d1 Abbrechen",
                                         state='disabled',
                                         command=self._stop_free_wipe)
        self.free_stop_btn.pack(side='left', padx=4)

        self._free_wipe_proc = None
        self._free_wipe_stop = False
        self._refresh_free_mounts()

    def _on_wipe_select(self, _event=None):
        sel = self.wipe_tree.focus()
        if not sel:
            self.selected_wipe_drv = None
            self.wipe_start_btn.config(state='disabled')
            self.wipe_sel_lbl.config(text="Kein Laufwerk ausgewählt", fg=self.theme["fg_dim"])
            return
        self.selected_wipe_drv = next(
            (d for d in self.all_drives if d.device == sel), None)
        if self.selected_wipe_drv:
            d = self.selected_wipe_drv
            self.wipe_start_btn.config(state='normal')
            # Info-Label aktualisieren
            info = (f"Ausgewählt:  {d.device}  –  {d.model}  "
                    f"[{d.get_type_label()}]  {d.get_size_human()}")
            color = self.theme["danger"] if d.is_system_drive else self.theme["fg"]
            self.wipe_sel_lbl.config(text=info, fg=color, font=('Arial', 10, 'bold'))
            # SSD-Hinweis + Methoden-Vorauswahl
            if d.is_ssd or d.is_nvme:
                hint   = "⚠️ SSD/NVMe erkannt → Secure Erase empfohlen!"
                method = 'secure_erase_nvme' if d.is_nvme else 'secure_erase_hdd'
                for name, key in self._method_map.items():
                    if key == method:
                        self.wipe_method_cb.set(name)
                        break
            else:
                hint = ""
            self.wipe_ssd_hint.config(text=hint)
            if d.is_system_drive:
                messagebox.showwarning("Warnung",
                    "Systemlaufwerk ausgewählt!\nLöschen macht das Betriebssystem unbrauchbar.")
        else:
            self.wipe_start_btn.config(state='disabled')
            self.wipe_sel_lbl.config(text="Kein Laufwerk ausgewählt", fg=self.theme["fg_dim"])

    def _confirm_wipe(self):
        d = self.selected_wipe_drv
        if not d:
            return
        for prompt, expected in [
            (f"Gerät: {d.device}\nGerätenamen zur Bestätigung eingeben:", d.device),
            ("Finale Bestätigung – Eingabe: LÖSCHEN", "LÖSCHEN"),
        ]:
            v = simpledialog.askstring("Bestätigung", prompt, parent=self.root)
            if v != expected:
                messagebox.showinfo("Abgebrochen", "Abgebrochen.")
                return
        method_name = self.wipe_method_var.get()
        method_key  = self._method_map.get(method_name, 'quick')
        self.wipe_start_btn.config(state='disabled')
        self.wipe_stop_btn.config(state='normal')
        self.wipe_pbar.start()
        def worker():
            ok = self.wipe_eng.wipe(d, method_key)
            self.root.after(0, lambda: self._on_wipe_done(ok))
        threading.Thread(target=worker, daemon=True).start()

    def _on_wipe_done(self, ok):
        self.wipe_start_btn.config(state='normal')
        self.wipe_stop_btn.config(state='disabled')
        self.wipe_pbar.stop()
        self.app.refresh_drives()
        if ok:
            messagebox.showinfo("Fertig", "✅ Löschvorgang abgeschlossen!")
        else:
            messagebox.showerror("Fehler", "❌ Fehlgeschlagen oder abgebrochen.")

    def _stop_wipe(self):
        self.wipe_eng.stop()
        self.wipe_stop_btn.config(state='disabled')

    def _refresh_free_mounts(self):
        """Alle eingehängten Partitionen mit Bezeichnung anbieten."""
        if not hasattr(self, 'free_mount_cb'):
            return
        try:
            r = subprocess.run(
                ['lsblk', '-ln', '-o', 'NAME,MOUNTPOINT,FSTYPE,SIZE,MODEL,TYPE'],
                capture_output=True, text=True)
            vals = []
            for line in r.stdout.strip().split(chr(10)):
                cols = line.split(None, 5)
                if len(cols) < 2:
                    continue
                name = cols[0]
                mnt  = cols[1] if len(cols) > 1 else ''
                if not mnt.startswith('/'):
                    continue
                fs    = cols[2] if len(cols) > 2 else ''
                size  = cols[3] if len(cols) > 3 else ''
                model = cols[4] if len(cols) > 4 else ''
                # Gerätetyp aus all_drives ermitteln
                dev_path = '/dev/' + name
                drv_type = ''
                for d in self.all_drives:
                    if d.device == dev_path or dev_path.startswith(d.device):
                        drv_type = d.get_type_label()
                        if not model:
                            model = d.model
                        break
                # Anzeige: Mountpoint  |  Gerät  |  Bezeichnung  |  FS  |  Größe
                label_parts = []
                if model and model != 'Unbekannt':
                    label_parts.append(model)
                if drv_type:
                    label_parts.append('[' + drv_type + ']')
                label_parts.append(fs or '?')
                label_parts.append(size)
                # ||| als sicheres Trennzeichen (kommt nie in Pfaden vor)
                display = "  ".join(label_parts)
                entry = f"{mnt}|||{dev_path}|||{display}"
                vals.append(entry)
            # Anzeigetext: Mountpoint + Geräteinfo (ohne internen Trennzeichen)
            display_vals = []
            for v in vals:
                parts = v.split('|||')
                mnt_p   = parts[0] if parts else ''
                dev_p   = parts[1] if len(parts) > 1 else ''
                info_p  = parts[2] if len(parts) > 2 else ''
                display_vals.append(f"{mnt_p:<26}  {dev_p:<12}  {info_p}")
            self._free_mount_keys = vals   # interne Werte mit |||
            self.free_mount_cb['values'] = display_vals
            if display_vals:
                for i, v in enumerate(vals):
                    mnt_p = v.split('|||')[0]
                    if mnt_p.startswith('/home'):
                        self.free_mount_cb.current(i)
                        self._update_free_info()
                        return
                self.free_mount_cb.current(0)
                self._update_free_info()
        except Exception as e:
            self.log_to(self.wipe_log, "Fehler beim Lesen der Mountpoints: " + str(e) + chr(10))

    def _update_free_info(self):
        """Zeigt freien/belegten Speicher der gewaehlten Partition an."""
        if not hasattr(self, 'free_info_lbl'):
            return
        idx = self.free_mount_cb.current()
        if idx < 0 or not hasattr(self, '_free_mount_keys') or idx >= len(self._free_mount_keys):
            return
        mnt = self._free_mount_keys[idx].split('|||')[0]
        try:
            st       = os.statvfs(mnt)
            total_gb = st.f_blocks * st.f_frsize / 1024**3
            free_gb  = st.f_bavail * st.f_frsize / 1024**3
            used_gb  = total_gb - free_gb
            pct_used = int(used_gb / total_gb * 100) if total_gb else 0
            self.free_info_lbl.config(
                text=(f"Gesamt: {total_gb:.1f} GB  |  "
                      f"Belegt: {used_gb:.1f} GB ({pct_used}%)  |  "
                      f"Frei: {free_gb:.1f} GB  ← wird überschrieben"))
        except Exception:
            self.free_info_lbl.config(text="")

    def _confirm_free_wipe(self):
        idx = self.free_mount_cb.current()
        if idx < 0 or not hasattr(self, '_free_mount_keys') or idx >= len(self._free_mount_keys):
            messagebox.showerror("Fehler", "Bitte Partition auswaehlen.")
            return
        key        = self._free_mount_keys[idx]
        mountpoint = key.split('|||')[0]
        dev_path   = key.split('|||')[1] if '|||' in key else ''
        if not mountpoint or not os.path.isdir(mountpoint):
            messagebox.showerror("Fehler",
                f"Mountpoint nicht gefunden: '{mountpoint}'" + chr(10) +
                "Bitte Aktualisieren klicken.")
            return
        method     = self.free_method_var.get()

        # Freien Speicherplatz ermitteln
        try:
            st    = os.statvfs(mountpoint)
            free  = st.f_bavail * st.f_frsize
            total = st.f_blocks * st.f_frsize
            free_gb  = free  / 1024**3
            total_gb = total / 1024**3
        except Exception as e:
            messagebox.showerror("Fehler", f"Kann Speicherplatz nicht lesen: {e}")
            return

        if not messagebox.askyesno("Bestätigung",
            f"Freien Speicherplatz auf '{mountpoint}' überschreiben?" + chr(10) +
            f"Frei: {free_gb:.1f} GB von {total_gb:.1f} GB" + chr(10) +
            f"Methode: {method}" + chr(10) + chr(10) +
            "Vorhandene Dateien bleiben erhalten." + chr(10) +
            "Dieser Vorgang kann lange dauern.",
            icon='warning'):
            return

        self.free_start_btn.config(state='disabled')
        self.free_stop_btn.config(state='normal')
        self._free_wipe_stop = False
        self.free_pbar.start(10)
        self.free_status_lbl.config(text="Lauft...")
        self.clear_log(self.wipe_log)
        self.log_to(self.wipe_log,
            f"Starte: Freien Speicher löschen auf {mountpoint}" + chr(10) +
            f"Methode: {method}" + chr(10) +
            f"Freier Speicher: {free_gb:.1f} GB" + chr(10) + chr(10))

        threading.Thread(
            target=self._run_free_wipe,
            args=(mountpoint, method, free_gb),
            daemon=True
        ).start()

    def _run_free_wipe(self, mountpoint, method, free_gb):
        import tempfile
        try:
            if 'sfill' in method:
                self._free_wipe_sfill(mountpoint)
            else:
                self._free_wipe_dd(mountpoint, free_gb)
        except Exception as e:
            self.root.after(0, lambda: self.log_to(
                self.wipe_log, f"Fehler: {e}" + chr(10)))
        finally:
            self.root.after(0, self._on_free_wipe_done)

    def _free_wipe_sfill(self, mountpoint):
        """sfill aus dem secure-delete Paket – sicheres Überschreiben."""
        import shutil
        if not shutil.which('sfill'):
            self.root.after(0, lambda: self.log_to(self.wipe_log,
                "sfill nicht gefunden." + chr(10) +
                "Installieren: sudo apt install secure-delete" + chr(10) +
                "Verwende dd-Methode als Fallback..." + chr(10)))
            self._free_wipe_dd(mountpoint, None)
            return

        self.root.after(0, lambda: self.log_to(
            self.wipe_log, "Starte sfill -l -l (2 Durchgaenge)..." + chr(10)))
        proc = subprocess.Popen(
            ['sfill', '-l', '-l', '-v', mountpoint],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        self._free_wipe_proc = proc
        for line in proc.stdout:
            if self._free_wipe_stop:
                proc.terminate()
                break
            stripped = line.strip()
            if stripped:
                self.root.after(0, lambda l=stripped: self.log_to(
                    self.wipe_log, l + chr(10)))
        proc.wait()
        self._free_wipe_proc = None

    def _free_wipe_dd(self, mountpoint, free_gb):
        """Freien Speicher mit dd + Nullen ueberschreiben."""
        from config import ORIGINAL_USER
        tmpfile = os.path.join(mountpoint, '.peessi_freewipe_tmp')

        # Pruefe ob Mountpoint als vfat/exfat eingehaengt ist
        # Diese Dateisysteme haben feste uid/gid – root kann nicht schreiben
        # wenn sie mit uid=1000 eingehaengt sind
        is_fat = False
        try:
            r = subprocess.run(['findmnt', '-n', '-o', 'FSTYPE', mountpoint],
                               capture_output=True, text=True)
            fstype = r.stdout.strip().lower()
            is_fat = fstype in ('vfat', 'fat32', 'fat16', 'exfat', 'ntfs')
        except Exception:
            pass

        self.root.after(0, lambda: self.log_to(
            self.wipe_log,
            "Schreibe Nullen nach " + tmpfile + "..." + chr(10) +
            ("Hinweis: FAT/NTFS-Dateisystem – schreibe als Benutzer '" +
             ORIGINAL_USER + "'" + chr(10) if is_fat else "") +
            "Dies dauert je nach freiem Speicher einige Minuten." + chr(10)))
        try:
            # Bei FAT/NTFS als normaler Benutzer schreiben (uid-Mountoption)
            if is_fat:
                cmd = ['sudo', '-u', ORIGINAL_USER,
                       'dd', 'if=/dev/zero', 'of=' + tmpfile,
                       'bs=1M', 'status=progress']
            else:
                cmd = ['dd', 'if=/dev/zero', 'of=' + tmpfile,
                       'bs=1M', 'status=progress']

            proc = subprocess.Popen(cmd,
                stderr=subprocess.PIPE, universal_newlines=True)
            self._free_wipe_proc = proc
            for line in proc.stderr:
                if self._free_wipe_stop:
                    proc.terminate()
                    break
                line = line.strip()
                if line:
                    self.root.after(0, lambda l=line: self.log_to(
                        self.wipe_log, l + chr(10)))
            proc.wait()
            self._free_wipe_proc = None
        except Exception as e:
            self.root.after(0, lambda: self.log_to(
                self.wipe_log, "dd Fehler: " + str(e) + chr(10)))
        finally:
            try:
                if os.path.exists(tmpfile):
                    os.remove(tmpfile)
                    subprocess.run(['sync'], check=False)
                    self.root.after(0, lambda: self.log_to(
                        self.wipe_log,
                        "Temporaerdatei geloescht: " + tmpfile + chr(10)))
            except Exception as e:
                self.root.after(0, lambda: self.log_to(
                    self.wipe_log,
                    "Konnte Temp-Datei nicht loeschen: " + str(e) + chr(10)))

    def _stop_free_wipe(self):
        self._free_wipe_stop = True
        if self._free_wipe_proc and self._free_wipe_proc.poll() is None:
            self._free_wipe_proc.terminate()
        self.free_stop_btn.config(state='disabled')
        self.free_status_lbl.config(text="Abbruch angefordert...")
        self.log_to(self.wipe_log, "Abbruch angefordert..." + chr(10))

    def _on_free_wipe_done(self):
        self.free_start_btn.config(state='normal')
        self.free_stop_btn.config(state='disabled')
        self.free_pbar.stop()
        if self._free_wipe_stop:
            self.free_status_lbl.config(text="Abgebrochen.")
            self.log_to(self.wipe_log, chr(10) + "Abgebrochen." + chr(10))
        else:
            self.free_status_lbl.config(text="Fertig – freier Speicher geloescht.")
            self.log_to(self.wipe_log,
                chr(10) + "Freier Speicher erfolgreich geloescht." + chr(10) +
                "Geloeschte Dateien sind nun nicht mehr wiederherstellbar." + chr(10))
            messagebox.showinfo("Fertig",
                "Freier Speicherplatz wurde ueberschrieben." + chr(10) +
                "Geloeschte Dateien sind nicht mehr wiederherstellbar.")
        self.sec.log_action("FREE_WIPE_DONE", self.free_mount_var.get().split()[0] if self.free_mount_var.get() else "")

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: SMART-MONITOR
    # ══════════════════════════════════════════════════════════════════════
    def _build_smart_tab(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="📊 SMART-Monitor")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        sel_f = ttk.LabelFrame(pane, text=" Gerät auswählen ", padding=8)
        sel_f.pack(fill='x', pady=(0, 8))
        self.smart_dev_var = tk.StringVar()
        self.smart_dev_cb  = ttk.Combobox(sel_f, textvariable=self.smart_dev_var,
                                          state='readonly', width=30)
        self.smart_dev_cb.pack(side='left', padx=(0, 8))
        ttk.Button(sel_f, text="🔍 SMART auslesen",
                   command=self._read_smart).pack(side='left', padx=4)
        ttk.Button(sel_f, text="📈 Verlauf anzeigen",
                   command=self._show_smart_history).pack(side='left', padx=4)
        ttk.Button(sel_f, text="💾 In DB speichern",
                   command=self._save_smart_to_db).pack(side='left', padx=4)

        attr_f = ttk.LabelFrame(pane, text=" SMART-Attribute ", padding=8)
        attr_f.pack(fill='both', expand=True, pady=(0, 8))
        scols = ('ID', 'Attribut', 'Wert', 'Worst', 'Thresh', 'Raw', 'Status')
        self.smart_tree = ttk.Treeview(attr_f, columns=scols, show='headings', height=10)
        sw = {'ID':40,'Attribut':200,'Wert':55,'Worst':55,'Thresh':55,'Raw':110,'Status':100}
        for c in scols:
            self.smart_tree.heading(c, text=c)
            self.smart_tree.column(c, width=sw.get(c, 100))
        self.smart_tree.tag_configure('warn', background=T["tag_system"])
        self.smart_tree.tag_configure('crit', background=T["tag_internal"])
        ssb = ttk.Scrollbar(attr_f, orient='vertical', command=self.smart_tree.yview)
        self.smart_tree.configure(yscrollcommand=ssb.set)
        self.smart_tree.pack(side='left', fill='both', expand=True)
        ssb.pack(side='right', fill='y')

        smart_btn_f = tk.Frame(pane, bg=T["bg"])
        smart_btn_f.pack(fill='x', pady=(0, 8))
        ttk.Button(smart_btn_f, text="📋 Tabelle kopieren",
                   command=self._copy_smart_table).pack(side='left', padx=4)
        ttk.Button(smart_btn_f, text="💾 Als Textdatei speichern",
                   command=self._save_smart_as_txt).pack(side='left', padx=4)

        hist_f = ttk.LabelFrame(pane, text=" SMART-Verlauf (letzte 90 Tage) ", padding=8)
        hist_f.pack(fill='both', expand=True)
        self.smart_hist_log = self.make_log_widget(hist_f, height=8)
        self.smart_hist_log.pack(fill='both', expand=True)

    def _read_smart(self):
        dev = self.smart_dev_var.get()
        if not dev:
            return
        for row in self.smart_tree.get_children():
            self.smart_tree.delete(row)
        attrs = query_smart_attributes(dev)
        if not attrs:
            messagebox.showinfo("SMART", f"Keine Daten für {dev}.")
            return
        for a in attrs:
            self.smart_tree.insert('', 'end',
                values=(a['id'], a['name'], a['value'], a['worst'],
                        a['thresh'], a['raw'], a['status']),
                tags=(a['tag'],) if a['tag'] else ())

    def _save_smart_to_db(self):
        dev = self.smart_dev_var.get()
        if not dev:
            return
        attrs = {}
        for row in self.smart_tree.get_children():
            vals = self.smart_tree.item(row)['values']
            if vals:
                try:
                    attrs[str(vals[1])] = {
                        "normalized": int(vals[2]),
                        "raw": int(str(vals[5]).split()[0]) if str(vals[5]).split() else 0
                    }
                except Exception:
                    pass
        if attrs:
            self.smart_db.record(dev, attrs)
            messagebox.showinfo("SMART", f"✅ {len(attrs)} Attribute gespeichert.")

    def _smart_table_as_text(self) -> str:
        import datetime
        dev    = self.smart_dev_var.get() or "Unbekannt"
        ts     = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cols   = ('ID', 'Attribut', 'Wert', 'Worst', 'Thresh', 'Raw', 'Status')
        widths = [len(c) for c in cols]
        rows   = []
        for iid in self.smart_tree.get_children():
            vals = [str(v) for v in self.smart_tree.item(iid)['values']]
            rows.append(vals)
            for i, v in enumerate(vals):
                widths[i] = max(widths[i], len(v))
        sep    = "-" * (sum(widths) + len(widths) * 3 + 1)
        header = "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols)) + " |"
        out    = ["SMART-Bericht: " + dev, "Erstellt:      " + ts, sep, header, sep]
        for vals in rows:
            out.append("| " + " | ".join(v.ljust(widths[i]) for i, v in enumerate(vals)) + " |")
        out.append(sep)
        return "\n".join(out)

    def _copy_smart_table(self):
        if not self.smart_tree.get_children():
            messagebox.showinfo("SMART", "Tabelle leer – bitte zuerst SMART auslesen.")
            return
        text = self._smart_table_as_text()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        messagebox.showinfo("Kopiert", "SMART-Tabelle kopiert.")

    def _save_smart_as_txt(self):
        if not self.smart_tree.get_children():
            messagebox.showinfo("SMART", "Tabelle leer – bitte zuerst SMART auslesen.")
            return
        import datetime
        dev  = self.smart_dev_var.get().replace("/dev/", "").replace("/", "_")
        ts   = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        path = filedialog.asksaveasfilename(
            title="SMART-Tabelle speichern",
            initialfile=f"smart_{dev}_{ts}.txt",
            initialdir=str(USER_HOME),
            defaultextension=".txt",
            filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._smart_table_as_text())
            messagebox.showinfo("Gespeichert", "Gespeichert: " + path)
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def _show_smart_history(self):
        dev = self.smart_dev_var.get()
        if not dev:
            return
        attrs = self.smart_db.get_attributes(dev)
        if not attrs:
            messagebox.showinfo("Kein Verlauf",
                f"Keine Verlaufsdaten für {dev}.\nBitte zuerst 'In DB speichern'.")
            return
        import datetime
        lines_out = [f"SMART-Verlauf: {dev}",
                     f"Erstellt: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                     "=" * 60]
        for attr in attrs:
            data = self.smart_db.get_history(dev, attr, days=90)
            if not data:
                continue
            lines_out.append(f"\nAttribut: {attr}  ({len(data)} Messwerte)")
            lines_out.append(f"  {'Zeitstempel':<20}  {'Raw-Wert':>12}")
            lines_out.append(f"  {'-'*20}  {'-'*12}")
            for ts, val in data:
                lines_out.append(f"  {str(ts)[:19]:<20}  {str(val or 0):>12}")
        lines_out.append("\n" + "=" * 60)
        self.log_to(self.smart_hist_log, "\n".join(lines_out), clear=True)

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: ISO-BRENNER
    # ══════════════════════════════════════════════════════════════════════
    def _build_iso_tab(self, nb):
        T   = self.theme
        outer = ttk.Frame(nb)
        nb.add(outer, text="💿 ISO-Brenner")
        # Sub-Notebook: ISO brennen + USB-Clone
        sub = ttk.Notebook(outer)
        sub.pack(fill='both', expand=True)
        # Sub-Tab 1: ISO brennen (bisheriger Inhalt)
        tab = ttk.Frame(sub)
        sub.add(tab, text="💿 ISO brennen")
        # Sub-Tab 2: USB-Clone
        self._build_iso_clone_subtab(sub, T)

        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        desc = ttk.LabelFrame(pane, text=" Beschreibung ", padding=10)
        desc.pack(fill='x', pady=(0, 8))
        tk.Label(desc, text=(
            "Schreibt ein ISO-Image auf USB-Stick oder externe Festplatte.\n"
            "Optionale SHA256-Prüfung vor dem Schreiben.\n"
            "Nach dem Schreiben: automatischer Vergleich ISO vs. Zielgerät.\n"
            "Systemlaufwerke werden nicht als Ziel angezeigt.\n"
            "⚠️  Alle Daten auf dem Zielgerät werden unwiderruflich gelöscht!"
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        iso_f = ttk.LabelFrame(pane, text=" ISO-Datei ", padding=8)
        iso_f.pack(fill='x', pady=(0, 8))
        iso_row = tk.Frame(iso_f, bg=T["bg"])
        iso_row.pack(fill='x')
        self.iso_path_var = tk.StringVar()
        ttk.Entry(iso_row, textvariable=self.iso_path_var, width=55
                  ).pack(side='left', padx=(0, 6), expand=True, fill='x')
        ttk.Button(iso_row, text="📂 Wählen",
                   command=self._browse_iso).pack(side='left')
        hash_row = tk.Frame(iso_f, bg=T["bg"])
        hash_row.pack(fill='x', pady=(6, 0))
        tk.Label(hash_row, text="SHA256 (optional):",
                 bg=T["bg"], fg=T["fg"], font=('Arial', 9)).pack(side='left', padx=(0, 6))
        self.iso_hash_var = tk.StringVar()
        ttk.Entry(hash_row, textvariable=self.iso_hash_var, width=68
                  ).pack(side='left', fill='x', expand=True)

        usb_f = ttk.LabelFrame(pane, text=" Zielgerät (USB / externe Festplatte) ", padding=8)
        usb_f.pack(fill='x', pady=(0, 8))
        usb_row = tk.Frame(usb_f, bg=T["bg"])
        usb_row.pack(fill='x')
        self.iso_target_var = tk.StringVar()
        self.iso_target_cb  = ttk.Combobox(usb_row, textvariable=self.iso_target_var,
                                            state='readonly', width=55)
        self.iso_target_cb.pack(side='left', padx=(0, 8))
        ttk.Button(usb_row, text="🔄",
                   command=self._update_iso_targets).pack(side='left')
        tk.Label(usb_f, text="ℹ️  Systemlaufwerke werden nicht angezeigt.",
                 bg=T["bg"], fg=T["fg_dim"], font=('Arial', 8)).pack(anchor='w', pady=(4, 0))

        opt_f = ttk.LabelFrame(pane, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', pady=(0, 8))
        self.iso_verify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_f,
            text="Nach dem Schreiben automatisch verifizieren (ISO vs. Gerät)",
            variable=self.iso_verify_var).pack(anchor='w')

        prog_f = ttk.LabelFrame(pane, text=" Fortschritt ", padding=8)
        prog_f.pack(fill='both', expand=True)
        self.iso_pct_var   = tk.DoubleVar()
        self.iso_pct_label = tk.Label(prog_f, text="",
                                      bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9))
        self.iso_pct_label.pack(anchor='w')
        ttk.Progressbar(prog_f, variable=self.iso_pct_var, maximum=100
                        ).pack(fill='x', pady=(0, 6))
        self.iso_log = self.make_log_widget(prog_f, height=8)
        self.iso_log.pack(fill='both', expand=True)

        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(8, 0))
        ttk.Button(btn_f, text="🔥 Schreiben + Verifizieren", style='Danger.TButton',
                   command=self._start_iso_write).pack(side='right', padx=4)
        ttk.Button(btn_f, text="🔍 Nur Hash prüfen",
                   command=self._check_iso_hash).pack(side='right', padx=4)
        ttk.Button(btn_f, text="📋 Log kopieren",
                   command=lambda: self.copy_log(self.iso_log)).pack(side='left', padx=4)

    def _browse_iso(self):
        p = filedialog.askopenfilename(
            title="ISO-Datei wählen",
            filetypes=[("ISO-Images", "*.iso"), ("Alle Dateien", "*")])
        if p:
            self.iso_path_var.set(p)

    def _sha256_file(self, path, max_bytes=None, progress_cb=None):
        sha  = hashlib.sha256()
        read = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                sha.update(chunk)
                read += len(chunk)
                if progress_cb and max_bytes:
                    progress_cb(min(read / max_bytes * 100, 100))
                if max_bytes and read >= max_bytes:
                    break
        return sha.hexdigest()

    def _check_iso_hash(self):
        iso      = self.iso_path_var.get().strip()
        expected = self.iso_hash_var.get().strip().lower()
        if not iso or not os.path.isfile(iso):
            messagebox.showerror("Fehler", "ISO-Datei nicht gefunden.")
            return
        if not expected:
            messagebox.showinfo("Hash", "Kein erwarteter Hash angegeben.")
            return
        def worker():
            self.root.after(0, lambda: self.log_to(
                self.iso_log, "Berechne SHA256...\n"))
            actual = self._sha256_file(iso)
            if actual == expected:
                msg = "✅ Hash korrekt!\n  " + actual + "\n"
            else:
                msg = ("❌ Hash-Mismatch!\n"
                       "  Erwartet : " + expected + "\n"
                       "  Berechnet: " + actual + "\n")
            self.root.after(0, lambda: self.log_to(self.iso_log, msg))
        threading.Thread(target=worker, daemon=True).start()

    def _start_iso_write(self):
        iso        = self.iso_path_var.get().strip()
        target_sel = self.iso_target_var.get()
        # Warnen wenn Systemlaufwerk gewählt
        if "⚠️SYSTEM" in target_sel:
            if not messagebox.askyesno("⚠️ ACHTUNG – Systemlaufwerk!",
                "Du hast ein SYSTEMLAUFWERK als Ziel gewählt!\n\n"
                "Das laufende System wird ZERSTÖRT.\n"
                "Der Rechner wird danach NICHT mehr starten!\n\n"
                "Bist du absolut sicher?", icon='warning'):
                return
        if not iso or not os.path.isfile(iso):
            messagebox.showerror("Fehler", "ISO-Datei nicht gefunden.")
            return
        if not target_sel:
            messagebox.showerror("Fehler", "Kein Zielgerät ausgewählt.")
            return
        target   = target_sel.split('|')[0].strip()
        iso_size = os.path.getsize(iso)

        try:
            dev_size = int(subprocess.check_output(
                ['blockdev', '--getsize64', target],
                stderr=subprocess.DEVNULL).decode().strip())
            if iso_size > dev_size:
                messagebox.showerror("Fehler",
                    f"ISO ({iso_size // 1024**2} MB) ist größer als "
                    f"das Zielgerät ({dev_size // 1024**2} MB)!")
                return
        except Exception:
            pass

        expected = self.iso_hash_var.get().strip().lower()
        if expected:
            self.log_to(self.iso_log, "Prüfe SHA256 der ISO...\n", clear=True)
            actual = self._sha256_file(iso)
            if actual != expected:
                if not messagebox.askyesno("Hash-Fehler",
                    "SHA256-Hash stimmt nicht!\n"
                    "Erwartet : " + expected + "\n"
                    "Berechnet: " + actual + "\n\nTrotzdem schreiben?",
                    icon='warning'):
                    return
            else:
                self.log_to(self.iso_log, "✅ ISO-Hash korrekt.\n")

        v = simpledialog.askstring("Bestätigung",
            "ISO  : " + os.path.basename(iso) +
            "  (" + str(iso_size // 1024**2) + " MB)\n"
            "Ziel : " + target + "\n\n"
            "ALLE DATEN auf " + target + " werden gelöscht!\n\n"
            "Zum Bestätigen eingeben:  SCHREIBEN",
            parent=self.root)
        if v != "SCHREIBEN":
            messagebox.showinfo("Abgebrochen", "Abgebrochen.")
            return

        self.clear_log(self.iso_log)
        self.iso_pct_var.set(0)
        do_verify = self.iso_verify_var.get()
        self.sec.log_action("ISO_WRITE_START", target, iso)

        def worker():
            pct_max = 50 if do_verify else 100
            ph1 = "Phase 1/" + ("2" if do_verify else "1") + ": Schreiben..."
            self.root.after(0, lambda: (
                self.log_to(self.iso_log,
                    ph1 + "\nSchreibe " + os.path.basename(iso) + " auf " + target + "\n"),
                self.iso_pct_label.config(text=ph1)))
            try:
                proc = subprocess.Popen(
                    ['dd', 'if=' + iso, 'of=' + target,
                     'bs=4M', 'status=progress', 'conv=fdatasync'],
                    stderr=subprocess.PIPE, universal_newlines=True)
                for line in proc.stderr:
                    line = line.strip()
                    if not line:
                        continue
                    m = re.search(r'([0-9]+)\s+bytes', line)
                    if m and iso_size > 0:
                        pct = min(int(int(m.group(1)) / iso_size * pct_max), pct_max)
                        self.root.after(0, lambda l=line, p=pct: (
                            self.log_to(self.iso_log, "  " + l + "\n"),
                            self.iso_pct_var.set(p)))
                    else:
                        self.root.after(0, lambda l=line:
                            self.log_to(self.iso_log, "  " + l + "\n"))
                proc.wait()
                if proc.returncode != 0:
                    self.root.after(0, lambda: (
                        messagebox.showerror("Fehler", "❌ Schreiben fehlgeschlagen."),
                        self.iso_pct_var.set(0),
                        self.iso_pct_label.config(text="")))
                    self.sec.log_action("ISO_WRITE_FAIL", target, iso)
                    return

                self.root.after(0, lambda: self.log_to(
                    self.iso_log, "✅ Schreiben abgeschlossen.\n"))
                self.sec.log_action("ISO_WRITE_OK", target, iso)

                if not do_verify:
                    self.root.after(0, lambda: (
                        self.iso_pct_var.set(100),
                        self.iso_pct_label.config(text="Fertig."),
                        messagebox.showinfo("Fertig",
                            "✅ ISO erfolgreich geschrieben!\n(Verifikation deaktiviert)")))
                    return

                # Phase 2: Verifizieren
                self.root.after(0, lambda: (
                    self.log_to(self.iso_log, "\nPhase 2/2: Verifizieren...\n"),
                    self.iso_pct_label.config(text="Phase 2/2: Verifizieren...")))

                self.root.after(0, lambda: self.log_to(
                    self.iso_log, "  Berechne SHA256 der ISO...\n"))
                hash_iso = self._sha256_file(iso)
                self.root.after(0, lambda h=hash_iso: self.log_to(
                    self.iso_log, "  ISO  : " + h + "\n"))

                self.root.after(0, lambda: self.log_to(
                    self.iso_log, "  Lese zurück vom Gerät...\n"))

                def _upd(pct):
                    self.root.after(0, lambda p=50 + pct / 2:
                        self.iso_pct_var.set(p))

                hash_dev = self._sha256_file(target, max_bytes=iso_size, progress_cb=_upd)
                self.root.after(0, lambda h=hash_dev: self.log_to(
                    self.iso_log, "  Gerät: " + h + "\n"))

                if hash_iso == hash_dev:
                    self.root.after(0, lambda: (
                        self.iso_pct_var.set(100),
                        self.iso_pct_label.config(text="✅ Verifikation erfolgreich!"),
                        self.log_to(self.iso_log,
                            "\n✅ VERIFIKATION OK – Daten identisch!\n"),
                        messagebox.showinfo("Fertig",
                            "✅ ISO geschrieben und verifiziert!\n"
                            "ISO und Gerät sind byte-identisch.")))
                    self.sec.log_action("ISO_VERIFY_OK", target, iso)
                else:
                    self.root.after(0, lambda: (
                        self.iso_pct_var.set(100),
                        self.iso_pct_label.config(text="❌ Verifikation fehlgeschlagen!"),
                        self.log_to(self.iso_log,
                            "\n❌ VERIFIKATION FEHLGESCHLAGEN!\n"
                            "Hashes stimmen nicht überein.\n"
                            "Gerät könnte defekt sein.\n"),
                        messagebox.showerror("Verifikation fehlgeschlagen",
                            "❌ Daten auf dem Gerät stimmen nicht mit der ISO überein!\n"
                            "Bitte erneut versuchen.")))
                    self.sec.log_action("ISO_VERIFY_FAIL", target, iso)

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Fehler", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _update_clone_combos(self):
        if not hasattr(self, 'clone_src_cb'):
            return
        vals = []
        for d in self.all_drives:
            if d.is_system_drive:
                continue
            label = "USB" if d.is_usb else ("Wechsel" if d.removable else "Extern/HDD")
            vals.append(f"{d.device}  |  {d.model}  |  {d.get_size_human()}  |  {label}")
        self.clone_src_cb['values'] = vals
        self.clone_dst_cb['values'] = vals
        if vals:
            self.clone_src_cb.current(0)
            if len(vals) > 1:
                self.clone_dst_cb.current(1)

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: USB-STICK KLONEN
    # ══════════════════════════════════════════════════════════════════════
    def _build_iso_clone_subtab(self, sub_nb, T):
        """USB-Clone als Sub-Tab direkt im ISO-Brenner."""
        _, pane_outer = self.make_scrollable_tab(sub_nb, "🔁 USB-Clone")
        pane = tk.Frame(pane_outer, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        desc = ttk.LabelFrame(pane, text=" Beschreibung ", padding=8)
        desc.pack(fill='x', pady=(0, 8))
        tk.Label(desc, text=(
            "Klont ein USB-Laufwerk 1:1 auf ein anderes (dd bs=4M).\n"
            "Optionale Verifikation via cmp nach dem Klonen.\n"
            "⚠️  Alle Daten auf dem Zielgerät werden unwiderruflich gelöscht!"
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        src_f = ttk.LabelFrame(pane, text=" Quelle (Laufwerk das kopiert wird) ", padding=8)
        src_f.pack(fill='x', pady=(0, 6))
        src_row = tk.Frame(src_f, bg=T["bg"])
        src_row.pack(fill='x')
        self.iso_clone_src_var = tk.StringVar()
        self.iso_clone_src_cb  = ttk.Combobox(src_row, textvariable=self.iso_clone_src_var,
                                               state='readonly', font=('Arial', 10))
        self.iso_clone_src_cb.pack(side='left', fill='x', expand=True, padx=(0, 6))

        dst_f = ttk.LabelFrame(pane, text=" Ziel (wird überschrieben!) ", padding=8)
        dst_f.pack(fill='x', pady=(0, 6))
        dst_row = tk.Frame(dst_f, bg=T["bg"])
        dst_row.pack(fill='x')
        self.iso_clone_dst_var = tk.StringVar()
        self.iso_clone_dst_cb  = ttk.Combobox(dst_row, textvariable=self.iso_clone_dst_var,
                                               state='readonly', font=('Arial', 10))
        self.iso_clone_dst_cb.pack(side='left', fill='x', expand=True, padx=(0, 6))

        def _refresh():
            vals = [
                f"{d.device}  |  {d.model}  |  {d.get_size_human()}  |  {d.get_type_label()}"
                for d in self.all_drives if not d.is_system_drive
            ]
            no = ["← Bitte 🔄 klicken"]
            self.iso_clone_src_cb['values'] = vals if vals else no
            self.iso_clone_dst_cb['values'] = vals if vals else no
            if vals:
                self.iso_clone_src_cb.current(0)
                if len(vals) > 1:
                    self.iso_clone_dst_cb.current(1)

        ttk.Button(src_row, text="🔄", width=3, command=_refresh).pack(side='left')
        ttk.Button(dst_row, text="🔄", width=3, command=_refresh).pack(side='left')

        opt_f = ttk.LabelFrame(pane, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', pady=(0, 6))
        self.iso_clone_verify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_f, text="Nach dem Klonen verifizieren (cmp – dauert länger)",
                        variable=self.iso_clone_verify_var).pack(anchor='w')

        log_f = ttk.LabelFrame(pane, text=" Ausgabe ", padding=6)
        log_f.pack(fill='both', expand=True)
        self.iso_clone_log = self.make_log_widget(log_f, height=10)
        self.iso_clone_log.pack(fill='both', expand=True)

        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(8, 0))
        self.iso_clone_btn = ttk.Button(btn_f, text="🔁 Klonen starten",
                                        style='Danger.TButton',
                                        command=self._start_iso_clone)
        self.iso_clone_btn.pack(side='right', padx=4)
        ttk.Button(btn_f, text="📋 Log kopieren",
                   command=lambda: self.copy_log(self.iso_clone_log)).pack(side='left', padx=4)
        self.app.root.after(600, _refresh)

    def _start_iso_clone(self):
        src = self.iso_clone_src_var.get().split("|")[0].strip()
        dst = self.iso_clone_dst_var.get().split("|")[0].strip()
        if not src or not dst or src.startswith("←"):
            messagebox.showerror("Fehler", "Bitte Quelle und Ziel auswählen (🔄 klicken).")
            return
        if src == dst:
            messagebox.showerror("Fehler", "Quelle und Ziel sind identisch!")
            return
        if not messagebox.askyesno("Bestätigung",
            f"⚠️  ALLE DATEN auf {dst} werden GELÖSCHT!\nKlone: {src} → {dst}\n\nFortfahren?",
            icon='warning'):
            return
        verify = self.iso_clone_verify_var.get()
        self.iso_clone_btn.config(state='disabled')
        self.clear_log(self.iso_clone_log)
        def worker():
            import subprocess as _sp
            try:
                self.root.after(0, lambda: self.log_to(
                    self.iso_clone_log, f"🔁 Klone {src} → {dst}...\n"))
                proc = _sp.Popen(
                    ["dd", f"if={src}", f"of={dst}", "bs=4M", "status=progress"],
                    stdout=_sp.PIPE, stderr=_sp.STDOUT, text=True)
                for line in proc.stdout:
                    self.root.after(0, lambda l=line: self.log_to(self.iso_clone_log, l))
                proc.wait()
                _sp.run(["sync"], check=False)
                ok = proc.returncode == 0
                self.root.after(0, lambda: self.log_to(self.iso_clone_log,
                    "✅ Klonen abgeschlossen.\n" if ok
                    else f"❌ Fehler (Exit {proc.returncode})\n"))
                if ok and verify:
                    self.root.after(0, lambda: self.log_to(
                        self.iso_clone_log, "🔎 Verifiziere (cmp)...\n"))
                    r2 = _sp.run(["cmp", "-l", src, dst], capture_output=True, text=True)
                    msg = "✅ Verifikation OK.\n" if r2.returncode == 0                           else f"❌ Verifikation fehlgeschlagen.\n{r2.stdout[:200]}"
                    self.root.after(0, lambda m=msg: self.log_to(self.iso_clone_log, m))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_to(
                    self.iso_clone_log, f"❌ Fehler: {err}\n"))
            finally:
                self.root.after(0, lambda: self.iso_clone_btn.config(state='normal'))
        import threading as _th
        _th.Thread(target=worker, daemon=True).start()

    def _build_usb_clone_tab(self, nb):
        T   = self.theme
        _, pane = self.make_scrollable_tab(nb, "📋 USB-Klon")
        pane = tk.Frame(pane, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        desc = ttk.LabelFrame(pane, text=" Beschreibung ", padding=10)
        desc.pack(fill='x', pady=(0, 8))
        tk.Label(desc, text=(
            "Klont einen USB-Stick 1:1 auf einen anderen Stick.\n"
            "Quell-Stick wird byte-genau auf den Ziel-Stick kopiert (dd).\n"
            "Optional: Verifikation nach dem Klonen (SHA256-Vergleich).\n"
            "⚠️  Der Ziel-Stick muss mindestens so groß sein wie der Quell-Stick!\n"
            "⚠️  Alle Daten auf dem Ziel-Stick werden unwiderruflich überschrieben!"
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        # Quell-Gerät
        src_f = ttk.LabelFrame(pane, text=" Quell-Stick (Quelle) ", padding=8)
        src_f.pack(fill='x', pady=(0, 6))
        src_row = tk.Frame(src_f, bg=T["bg"])
        src_row.pack(fill='x')
        self.clone_src_var = tk.StringVar()
        self.clone_src_cb  = ttk.Combobox(src_row, textvariable=self.clone_src_var,
                                           state='readonly', width=58)
        self.clone_src_cb.pack(side='left', padx=(0, 8))
        ttk.Button(src_row, text="🔄",
                   command=self._update_clone_combos).pack(side='left')
        tk.Label(src_f, text="ℹ️  Systemlaufwerke werden nicht angezeigt.",
                 bg=T["bg"], fg=T["fg_dim"], font=('Arial', 8)).pack(anchor='w', pady=(4, 0))

        # Ziel-Gerät
        dst_f = ttk.LabelFrame(pane, text=" Ziel-Stick (Kopie wird hier erstellt) ", padding=8)
        dst_f.pack(fill='x', pady=(0, 6))
        dst_row = tk.Frame(dst_f, bg=T["bg"])
        dst_row.pack(fill='x')
        self.clone_dst_var = tk.StringVar()
        self.clone_dst_cb  = ttk.Combobox(dst_row, textvariable=self.clone_dst_var,
                                           state='readonly', width=58)
        self.clone_dst_cb.pack(side='left', padx=(0, 8))
        tk.Label(dst_f,
                 text="⚠️  Quell- und Ziel-Stick dürfen NICHT identisch sein!",
                 bg=T["bg"], fg=T["warning"] if "warning" in T else "#e67e22",
                 font=('Arial', 8)).pack(anchor='w', pady=(4, 0))

        # Optionen
        opt_f = ttk.LabelFrame(pane, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', pady=(0, 6))
        self.clone_verify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_f,
            text="Nach dem Klonen verifizieren (SHA256 Quell- vs. Ziel-Stick)",
            variable=self.clone_verify_var).pack(anchor='w')
        self.clone_bs_var = tk.StringVar(value="4M")
        bs_row = tk.Frame(opt_f, bg=T["bg"])
        bs_row.pack(anchor='w', pady=(4, 0))
        tk.Label(bs_row, text="Block-Größe (dd bs=):",
                 bg=T["bg"], fg=T["fg"], font=('Arial', 9)).pack(side='left', padx=(0, 6))
        ttk.Combobox(bs_row, textvariable=self.clone_bs_var,
                     values=["1M", "4M", "8M", "16M", "64M"],
                     state='readonly', width=8).pack(side='left')
        tk.Label(bs_row, text="(4M empfohlen)",
                 bg=T["bg"], fg=T["fg_dim"], font=('Arial', 8)).pack(side='left', padx=6)

        # Fortschritt
        prog_f = ttk.LabelFrame(pane, text=" Fortschritt ", padding=8)
        prog_f.pack(fill='both', expand=True)
        self.clone_pct_var   = tk.DoubleVar()
        self.clone_pct_label = tk.Label(prog_f, text="",
                                        bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9))
        self.clone_pct_label.pack(anchor='w')
        ttk.Progressbar(prog_f, variable=self.clone_pct_var, maximum=100
                        ).pack(fill='x', pady=(0, 6))
        self.clone_log = self.make_log_widget(prog_f, height=8)
        self.clone_log.pack(fill='both', expand=True)

        # Buttons
        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(8, 0))
        ttk.Button(btn_f, text="📋 Sticks klonen", style='Danger.TButton',
                   command=self._start_clone).pack(side='right', padx=4)
        ttk.Button(btn_f, text="📋 Log kopieren",
                   command=lambda: self.copy_log(self.clone_log)).pack(side='left', padx=4)

        self._update_clone_combos()

    def _start_clone(self):
        src_sel = self.clone_src_var.get()
        dst_sel = self.clone_dst_var.get()
        if not src_sel:
            messagebox.showerror("Fehler", "Bitte Quell-Stick auswählen.")
            return
        if not dst_sel:
            messagebox.showerror("Fehler", "Bitte Ziel-Stick auswählen.")
            return
        src = src_sel.split('|')[0].strip()
        dst = dst_sel.split('|')[0].strip()
        if src == dst:
            messagebox.showerror("Fehler",
                "Quell- und Ziel-Stick sind identisch!\n"
                "Bitte zwei verschiedene Geräte auswählen.")
            return

        # Größenprüfung
        try:
            src_size = int(subprocess.check_output(
                ['blockdev', '--getsize64', src],
                stderr=subprocess.DEVNULL).decode().strip())
            dst_size = int(subprocess.check_output(
                ['blockdev', '--getsize64', dst],
                stderr=subprocess.DEVNULL).decode().strip())
            if dst_size < src_size:
                messagebox.showerror("Fehler",
                    f"Ziel-Stick ({dst_size // 1024**3:.1f} GB) ist kleiner als\n"
                    f"Quell-Stick ({src_size // 1024**3:.1f} GB)!\n\n"
                    "Bitte einen größeren Ziel-Stick verwenden.")
                return
        except Exception as e:
            if not messagebox.askyesno("Warnung",
                f"Größenprüfung fehlgeschlagen: {e}\n\nTrotzdem fortfahren?",
                icon='warning'):
                return
            src_size = 0

        v = simpledialog.askstring("Bestätigung",
            f"Quelle : {src}  ({src_size // 1024**3:.1f} GB)\n"
            f"Ziel   : {dst}  ({dst_size // 1024**3:.1f} GB)\n\n"
            f"ALLE DATEN auf {dst} werden überschrieben!\n\n"
            "Zum Bestätigen eingeben:  KLONEN",
            parent=self.root)
        if v != "KLONEN":
            messagebox.showinfo("Abgebrochen", "Abgebrochen.")
            return

        self.clear_log(self.clone_log)
        self.clone_pct_var.set(0)
        do_verify = self.clone_verify_var.get()
        bs        = self.clone_bs_var.get()

        def worker():
            pct_max = 50 if do_verify else 100
            ph1     = "Phase 1/" + ("2" if do_verify else "1") + ": Klonen..."
            self.root.after(0, lambda: (
                self.log_to(self.clone_log,
                    f"{ph1}\nKlone {src} → {dst}  (bs={bs})\n"),
                self.clone_pct_label.config(text=ph1)))
            try:
                # Alle Mounts des Ziel-Geräts lösen
                subprocess.run(['umount', '-f', dst], capture_output=True)
                for part in [dst + str(i) for i in range(1, 10)]:
                    subprocess.run(['umount', '-f', part], capture_output=True)

                proc = subprocess.Popen(
                    ['dd', f'if={src}', f'of={dst}',
                     f'bs={bs}', 'status=progress', 'conv=fdatasync'],
                    stderr=subprocess.PIPE, universal_newlines=True)

                for line in proc.stderr:
                    line = line.strip()
                    if not line:
                        continue
                    m = re.search(r'([0-9]+)\s+bytes', line)
                    if m and src_size > 0:
                        pct = min(int(int(m.group(1)) / src_size * pct_max), pct_max)
                        self.root.after(0, lambda l=line, p=pct: (
                            self.log_to(self.clone_log, "  " + l + "\n"),
                            self.clone_pct_var.set(p)))
                    else:
                        self.root.after(0, lambda l=line:
                            self.log_to(self.clone_log, "  " + l + "\n"))
                proc.wait()

                if proc.returncode != 0:
                    self.root.after(0, lambda: (
                        messagebox.showerror("Fehler", "❌ Klonen fehlgeschlagen."),
                        self.clone_pct_var.set(0),
                        self.clone_pct_label.config(text="")))
                    return

                self.root.after(0, lambda: self.log_to(
                    self.clone_log, "✅ Klonen abgeschlossen.\n"))

                if not do_verify:
                    self.root.after(0, lambda: (
                        self.clone_pct_var.set(100),
                        self.clone_pct_label.config(text="Fertig."),
                        messagebox.showinfo("Fertig",
                            "✅ USB-Stick erfolgreich geklont!\n(Verifikation deaktiviert)")))
                    return

                # Phase 2: Verifikation
                self.root.after(0, lambda: (
                    self.log_to(self.clone_log, "\nPhase 2/2: Verifizieren...\n"),
                    self.clone_pct_label.config(text="Phase 2/2: Verifizieren...")))

                self.root.after(0, lambda: self.log_to(
                    self.clone_log, "  Berechne SHA256 der Quelle...\n"))
                hash_src = self._sha256_file(src, max_bytes=src_size if src_size else None)
                self.root.after(0, lambda h=hash_src: self.log_to(
                    self.clone_log, "  Quelle: " + h + "\n"))

                self.root.after(0, lambda: self.log_to(
                    self.clone_log, "  Berechne SHA256 des Ziels...\n"))

                def _upd(pct):
                    self.root.after(0, lambda p=50 + pct / 2:
                        self.clone_pct_var.set(p))

                hash_dst = self._sha256_file(
                    dst, max_bytes=src_size if src_size else None, progress_cb=_upd)
                self.root.after(0, lambda h=hash_dst: self.log_to(
                    self.clone_log, "  Ziel  : " + h + "\n"))

                if hash_src == hash_dst:
                    self.root.after(0, lambda: (
                        self.clone_pct_var.set(100),
                        self.clone_pct_label.config(text="✅ Verifikation erfolgreich!"),
                        self.log_to(self.clone_log, "\n✅ VERIFIKATION OK – Daten identisch!\n"),
                        messagebox.showinfo("Fertig",
                            "✅ USB-Stick geklont und verifiziert!\n"
                            "Quell- und Ziel-Stick sind byte-identisch.")))
                else:
                    self.root.after(0, lambda: (
                        self.clone_pct_var.set(100),
                        self.clone_pct_label.config(text="❌ Verifikation fehlgeschlagen!"),
                        self.log_to(self.clone_log,
                            "\n❌ VERIFIKATION FEHLGESCHLAGEN!\n"
                            "Hashes stimmen nicht überein.\n"
                            "Ziel-Stick könnte defekt sein.\n"),
                        messagebox.showerror("Verifikation fehlgeschlagen",
                            "❌ Daten auf dem Ziel-Stick stimmen nicht mit der Quelle überein!\n"
                            "Bitte erneut versuchen oder anderen Stick verwenden.")))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Fehler", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: PARTITION EINBINDEN
    # ══════════════════════════════════════════════════════════════════════
    def _build_partition_tab(self, nb):
        T   = self.theme
        _, pane = self.make_scrollable_tab(nb, "🔗 Partition einbinden")
        pane = tk.Frame(pane, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        desc = ttk.LabelFrame(pane, text=" Beschreibung ", padding=10)
        desc.pack(fill='x', pady=(0, 8))
        tk.Label(desc, text=(
            "Bindet eine Partition dauerhaft via /etc/fstab ein.\n"
            "Vor jeder Änderung wird automatisch ein Backup von /etc/fstab erstellt.\n"
            "⚠️  Benötigt Root-Rechte."
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        part_f = ttk.LabelFrame(pane, text=" Partition auswählen ", padding=8)
        part_f.pack(fill='x', pady=(0, 8))
        self.part_var = tk.StringVar()
        self.part_cb  = ttk.Combobox(part_f, textvariable=self.part_var,
                                      state='readonly', width=65)
        self.part_cb.pack(fill='x', pady=(0, 6))
        ttk.Button(part_f, text="🔄 Aktualisieren",
                   command=self._refresh_partitions).pack(anchor='w')

        mnt_f = ttk.LabelFrame(pane, text=" Einhängepunkt ", padding=8)
        mnt_f.pack(fill='x', pady=(0, 8))
        mnt_row = tk.Frame(mnt_f, bg=T["bg"])
        mnt_row.pack(fill='x')
        tk.Label(mnt_row, text="Label:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 6))
        self.part_label_var = tk.StringVar(value="Daten")
        ttk.Entry(mnt_row, textvariable=self.part_label_var, width=25).pack(side='left')
        self.part_mnt_hint = tk.Label(mnt_f,
            text=f"→ /media/{ORIGINAL_USER}/Daten",
            bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9))
        self.part_mnt_hint.pack(anchor='w', pady=(4, 0))
        self.part_label_var.trace_add('write', lambda *_: self.part_mnt_hint.config(
            text=f"→ /media/{ORIGINAL_USER}/{self.part_label_var.get()}"))

        log_f = ttk.LabelFrame(pane, text=" Ausgabe ", padding=8)
        log_f.pack(fill='both', expand=True)
        self.part_log = self.make_log_widget(log_f, height=8)
        self.part_log.pack(fill='both', expand=True)

        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(8, 0))
        ttk.Button(btn_f, text="📋 fstab anzeigen",
                   command=self._show_fstab).pack(side='left', padx=4)
        ttk.Button(btn_f, text="↩️ fstab-Backup wiederherstellen",
                   command=self._restore_fstab_backup).pack(side='left', padx=4)
        ttk.Button(btn_f, text="🔗 Einbinden", style='Accent.TButton',
                   command=self._mount_partition).pack(side='right', padx=4)

        self._refresh_partitions()

    def _refresh_partitions(self):
        try:
            r = subprocess.run(['lsblk', '-ln', '-o', 'NAME,FSTYPE,SIZE,LABEL'],
                               capture_output=True, text=True)
            parts = []
            for line in r.stdout.strip().split('\n'):
                cols = line.split()
                if len(cols) >= 2 and cols[0].startswith(('sd', 'nvme', 'mmcblk')):
                    name   = f"/dev/{cols[0]}"
                    fstype = cols[1] if len(cols) > 1 else ""
                    size   = cols[2] if len(cols) > 2 else ""
                    label  = cols[3] if len(cols) > 3 else ""
                    parts.append(f"{name}  {fstype}  {size}  {label}".strip())
            self.part_cb['values'] = parts
            if parts:
                self.part_cb.current(0)
        except Exception as e:
            self.log_to(self.part_log, f"Fehler: {e}\n")

    def _show_fstab(self):
        try:
            with open('/etc/fstab') as f:
                content = f.read()
            self.log_to(self.part_log, "─── /etc/fstab ───\n" + content + "\n", clear=True)
        except Exception as e:
            self.log_to(self.part_log, f"Fehler: {e}\n")

    def _restore_fstab_backup(self):
        import glob
        backups = sorted(glob.glob('/etc/fstab.bak.*'), reverse=True)
        if not backups:
            messagebox.showinfo("Keine Backups", "Keine fstab-Backups gefunden.")
            return
        choices = "\n".join(f"{i+1}) {b}" for i, b in enumerate(backups[:10]))
        sel = simpledialog.askstring("Backup wählen",
            f"Verfügbare Backups:\n{choices}\n\nNummer eingeben:", parent=self.root)
        if not sel or not sel.strip().isdigit():
            return
        idx = int(sel.strip()) - 1
        if not (0 <= idx < len(backups)):
            return
        if messagebox.askyesno("Wiederherstellen",
            f"fstab aus Backup wiederherstellen?\n{backups[idx]}"):
            try:
                shutil.copy2(backups[idx], "/etc/fstab")
                self.log_to(self.part_log, f"✅ fstab wiederhergestellt: {backups[idx]}\n")
            except Exception as e:
                self.log_to(self.part_log, f"❌ Fehler: {e}\n")

    def _mount_partition(self):
        sel = self.part_var.get().strip()
        if not sel:
            messagebox.showerror("Fehler", "Bitte Partition wählen.")
            return
        partition  = sel.split()[0]
        label      = self.part_label_var.get().strip() or "Daten"
        mountpoint = f"/media/{ORIGINAL_USER}/{label}"
        if not messagebox.askyesno("Bestätigen",
            f"Partition {partition} dauerhaft nach\n{mountpoint}\neinbinden?"):
            return
        from security import SecurityManager
        def worker():
            backup = SecurityManager.backup_fstab()
            if backup:
                self.root.after(0, lambda: self.log_to(
                    self.part_log, f"📋 fstab-Backup: {backup}\n"))
            try:
                r_uuid = subprocess.run(
                    ['blkid', '-s', 'UUID', '-o', 'value', partition],
                    capture_output=True, text=True)
                uuid = r_uuid.stdout.strip()
                if not uuid:
                    self.root.after(0, lambda: self.log_to(
                        self.part_log, "❌ UUID nicht ermittelbar.\n"))
                    return
                r_fs   = subprocess.run(
                    ['blkid', '-s', 'TYPE', '-o', 'value', partition],
                    capture_output=True, text=True)
                fstype = r_fs.stdout.strip() or 'ext4'
                opts_map = {
                    'vfat':  'defaults,user,auto,nofail,umask=0022',
                    'ntfs':  'defaults,user,auto,nofail,uid=1000,gid=1000',
                    'exfat': 'defaults,user,auto,nofail',
                }
                opts       = opts_map.get(fstype, 'defaults,user,auto,nofail')
                fstab_line = f"UUID={uuid} {mountpoint} {fstype} {opts} 0 2"
                cmds = [
                    ['sed', '-i.bak', f'|{mountpoint}|d', '/etc/fstab'],
                    ['bash', '-c', f"echo '{fstab_line}' >> /etc/fstab"],
                    ['mkdir', '-p', mountpoint],
                    ['chown', '-R', f'{ORIGINAL_USER}:{ORIGINAL_USER}', mountpoint],
                    ['mount', mountpoint],
                ]
                for cmd in cmds:
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    ok  = res.returncode == 0
                    lbl = ' '.join(cmd[-2:])
                    self.root.after(0, lambda l=lbl, o=ok: self.log_to(
                        self.part_log, f"{'✓' if o else '✗'} {l}\n"))
                self.root.after(0, lambda: self.log_to(
                    self.part_log, f"\n✅ Eingebunden: {mountpoint}\n"))
                self.sec.log_action("PARTITION_MOUNT", partition, mountpoint)
            except Exception as e:
                self.root.after(0, lambda: self.log_to(self.part_log, f"❌ {e}\n"))
        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: LAUFWERK-DIAGNOSE (gui_drive_health.py)
    # ══════════════════════════════════════════════════════════════════════
    def _build_drive_health_tab(self, nb):
        """Laufwerk-Diagnose Tab – Implementierung in gui_drive_health.py."""
        if _HEALTH_AVAILABLE:
            self._health_tab = DriveHealthTab(nb, self.app, self.theme)
        else:
            T = self.theme
            tab = ttk.Frame(nb)
            nb.add(tab, text="🩺 Laufwerk-Diagnose")
            tk.Label(tab,
                text="⚠️  gui_drive_health.py nicht gefunden.\n\n"
                     "Bitte install-peessi-multitool.sh erneut ausführen.",
                bg=T["bg"], fg=T["danger"],
                font=("Arial", 11)).pack(expand=True)

    def _wipe_nwipe(self):
        """nwipe im Terminal starten."""
        import shutil as _sh
        if not _sh.which("nwipe"):
            messagebox.showerror("nwipe fehlt",
                "nwipe ist nicht installiert.\n\n"
                "sudo apt install nwipe")
            return
        # Gewähltes Laufwerk aus Wipe-Tab
        sel = self.wipe_tree.selection()
        dev = ""
        if sel:
            dev = self.wipe_tree.item(sel[0])['values'][0]
        if not dev:
            messagebox.showinfo("Hinweis",
                "Bitte zuerst ein Laufwerk in der Liste auswählen.")
            return
        if not messagebox.askyesno("nwipe starten",
            f"nwipe für {dev} im Terminal starten?\n\n"
            "⚠️  ALLE DATEN werden unwiderruflich gelöscht!",
            icon="warning"):
            return
        # Terminal finden und nwipe starten
        import subprocess as _sp
        term = None
        for t in ("xterm","gnome-terminal","xfce4-terminal","mate-terminal","lxterminal"):
            if _sh.which(t):
                term = t; break
        if not term:
            messagebox.showerror("Fehler",
                "Kein Terminal-Emulator gefunden.\nsudo apt install xterm")
            return
        cmd_str = f"nwipe {dev}"
        if term == "xterm":
            args = ["xterm","-T","nwipe – Sicheres Löschen","-geometry","100x35",
                    "-e",f"bash -c '{cmd_str}; echo; echo Fertig – Enter; read'"]
        elif term == "gnome-terminal":
            args = ["gnome-terminal","--title","nwipe","--","bash","-c",
                    f"{cmd_str}; echo; read"]
        else:
            args = [term,"-e",f"bash -c '{cmd_str}; echo; read'"]
        _sp.Popen(args)
        self.log_to(self.wipe_log,
            f"nwipe für {dev} wurde in einem Terminal gestartet.\n")
