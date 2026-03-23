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


def _bind_mousewheel(canvas):
    """
    Bindet Mausrad-Scrolling NUR an den Canvas selbst (KEIN bind_all/unbind_all).
    bind_all/unbind_all entfernt interne Tkinter-Bindings → kann X11/Cinnamon
    zum Absturz bringen. Stattdessen: direkte Bindung ans Canvas-Widget.
    """
    def _scroll(ev):
        if ev.delta:
            canvas.yview_scroll(int(-1*(ev.delta/120)), "units")
        elif ev.num == 4:
            canvas.yview_scroll(-1, "units")
        elif ev.num == 5:
            canvas.yview_scroll(1, "units")
    canvas.bind("<MouseWheel>", _scroll)
    canvas.bind("<Button-4>",   _scroll)
    canvas.bind("<Button-5>",   _scroll)

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
        self._build_smart_tab(nb)
        self._build_iso_tab(nb)
        self._build_usb_clone_tab(nb)
        self._build_partition_tab(nb)
        self._build_eggs_tab(nb)
        self._build_mint_installer_tab(nb)

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
            if d.is_system_drive:
                continue
            label = "USB" if d.is_usb else ("Wechsel" if d.removable else "Extern/HDD")
            vals.append(f"{d.device}  |  {d.model}  |  {d.get_size_human()}  |  {label}")
        self.iso_target_cb['values'] = vals
        if vals:
            self.iso_target_cb.current(0)

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: DATENRETTUNG
    # ══════════════════════════════════════════════════════════════════════
    def _build_recovery_tab(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🔍 Datenrettung")
        pane = tk.Frame(tab, bg=T["bg"])
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
        _bind_mousewheel(canvas)

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
        tab = ttk.Frame(nb)
        nb.add(tab, text="💿 ISO-Brenner")
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

    def _build_iso_clone_subtab(self, sub_nb, T):
        """USB-Clone direkt als Sub-Tab im ISO-Brenner."""
        tab = ttk.Frame(sub_nb)
        sub_nb.add(tab, text="🔁 USB-Clone")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)
        desc = ttk.LabelFrame(pane, text=" Beschreibung ", padding=8)
        desc.pack(fill='x', pady=(0, 8))
        tk.Label(desc, text=(
            "Klont ein USB-Laufwerk 1:1 auf ein anderes (dd bs=4M).\n"
            "Optionale Verifikation via cmp. ⚠️  Alle Daten auf dem Ziel werden gelöscht!"
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')
        src_f = ttk.LabelFrame(pane, text=" Quelle ", padding=8)
        src_f.pack(fill='x', pady=(0, 6))
        src_row = tk.Frame(src_f, bg=T["bg"])
        src_row.pack(fill='x')
        self.iso_clone_src_var = tk.StringVar()
        self.iso_clone_src_cb  = ttk.Combobox(src_row, textvariable=self.iso_clone_src_var,
                                               state='readonly', font=('Arial', 10))
        self.iso_clone_src_cb.pack(side='left', fill='x', expand=True, padx=(0, 6))
        dst_f = ttk.LabelFrame(pane, text=" Ziel (wird überschrieben) ", padding=8)
        dst_f.pack(fill='x', pady=(0, 6))
        dst_row = tk.Frame(dst_f, bg=T["bg"])
        dst_row.pack(fill='x')
        self.iso_clone_dst_var = tk.StringVar()
        self.iso_clone_dst_cb  = ttk.Combobox(dst_row, textvariable=self.iso_clone_dst_var,
                                               state='readonly', font=('Arial', 10))
        self.iso_clone_dst_cb.pack(side='left', fill='x', expand=True, padx=(0, 6))
        def _ref():
            vals = [f"{d.device}  |  {d.model}  |  {d.get_size_human()}"
                    for d in self.all_drives if not d.is_system_drive]
            self.iso_clone_src_cb["values"] = vals
            self.iso_clone_dst_cb["values"] = vals
            if vals: self.iso_clone_src_cb.current(0)
            if len(vals) > 1: self.iso_clone_dst_cb.current(1)
        ttk.Button(src_row, text="🔄", width=3, command=_ref).pack(side='left')
        ttk.Button(dst_row, text="🔄", width=3, command=_ref).pack(side='left')
        opt_f = ttk.LabelFrame(pane, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', pady=(0, 6))
        self.iso_clone_verify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_f, text="Nach dem Klonen verifizieren (cmp)",
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
        self.app.root.after(500, _ref)

    def _start_iso_clone(self):
        src = self.iso_clone_src_var.get().split("|")[0].strip()
        dst = self.iso_clone_dst_var.get().split("|")[0].strip()
        if not src or not dst:
            messagebox.showerror("Fehler", "Bitte Quelle und Ziel auswählen.")
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
                self.root.after(0, lambda: self.log_to(
                    self.iso_clone_log,
                    "✅ Klonen abgeschlossen.\n" if ok else f"❌ Fehler (Exit {proc.returncode})\n"))
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

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: USB-STICK KLONEN
    # ══════════════════════════════════════════════════════════════════════
    def _build_usb_clone_tab(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="📋 USB-Klon")
        pane = tk.Frame(tab, bg=T["bg"])
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
        tab = ttk.Frame(nb)
        nb.add(tab, text="🔗 Partition einbinden")
        pane = tk.Frame(tab, bg=T["bg"])
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
    #  TAB: PENGUINS-EGGS (Live-ISO erstellen)
    #  Verwendet: penguins-eggs von Piero Proietti
    #  https://github.com/pieroproietti/penguins-eggs  |  Lizenz: GPLv3
    # ══════════════════════════════════════════════════════════════════════
    def _build_eggs_tab(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🐧 Penguins-Eggs")

        # Scrollbarer Hauptbereich
        canvas = tk.Canvas(tab, bg=T["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        pane = tk.Frame(canvas, bg=T["bg"])
        win  = canvas.create_window((0, 0), window=pane, anchor='nw')
        pane.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win, width=e.width))

        _bind_mousewheel(canvas)

        # ── Drittanbieter-Hinweis ────────────────────────────────────────
        notice_f = ttk.LabelFrame(pane, text=" ℹ️ Drittanbieter-Software ", padding=8)
        notice_f.pack(fill='x', padx=12, pady=(10, 4))
        tk.Label(notice_f,
            text="🐧  Penguins-Eggs von Piero Proietti  |  Lizenz: GPLv3\n"
                 "   https://github.com/pieroproietti/penguins-eggs",
            bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9), justify='left').pack(anchor='w')

        # ── Status ───────────────────────────────────────────────────────
        status_f = ttk.LabelFrame(pane, text=" Status ", padding=8)
        status_f.pack(fill='x', padx=12, pady=4)
        self.eggs_status_lbl = tk.Label(status_f, text="Prüfe eggs-Installation...",
                                         bg=T["bg"], fg=T["fg"], font=('Arial', 10, 'bold'))
        self.eggs_status_lbl.pack(anchor='w')
        self.eggs_version_lbl = tk.Label(status_f, text="",
                                          bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9))
        self.eggs_version_lbl.pack(anchor='w')
        ttk.Button(status_f, text="🔄 Status prüfen",
                   command=self._eggs_check_status).pack(anchor='w', pady=(4, 0))

        # ── Installation ─────────────────────────────────────────────────
        install_f = ttk.LabelFrame(pane, text=" Installation von penguins-eggs ", padding=8)
        install_f.pack(fill='x', padx=12, pady=4)
        tk.Label(install_f,
            text="Falls eggs nicht installiert ist, hier installieren:\n"
                 "Methode 1: fresh-eggs (empfohlen) – klont das Repository und installiert\n"
                 "Methode 2: AppImage (direkter Download der neuesten Version)",
            bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w', pady=(0, 6))
        btn_row_inst = tk.Frame(install_f, bg=T["bg"])
        btn_row_inst.pack(anchor='w')
        ttk.Button(btn_row_inst, text="📦 fresh-eggs installieren", style='Accent.TButton',
                   command=self._eggs_install_fresh).pack(side='left', padx=(0, 6))
        ttk.Button(btn_row_inst, text="📥 AppImage herunterladen",
                   command=self._eggs_install_appimage).pack(side='left', padx=(0, 6))
        ttk.Button(btn_row_inst, text="🔧 eggs calamares einrichten",
                   command=lambda: self._eggs_run_cmd("calamares")).pack(side='left')

        # ── ISO erstellen (produce) ───────────────────────────────────────
        produce_f = ttk.LabelFrame(pane, text=" 🐚 ISO erstellen (eggs produce) ", padding=8)
        produce_f.pack(fill='x', padx=12, pady=4)
        opt_row = tk.Frame(produce_f, bg=T["bg"])
        opt_row.pack(fill='x', pady=(0, 6))
        self.eggs_compression_var = tk.StringVar(value="zstd")
        tk.Label(opt_row, text="Kompression:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 6))
        ttk.Combobox(opt_row, textvariable=self.eggs_compression_var,
                     values=["zstd", "xz", "gzip", "lzo"],
                     state='readonly', width=8).pack(side='left', padx=(0, 12))
        self.eggs_max_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_row, text="Maximale Kompression (--max)",
                        variable=self.eggs_max_var).pack(side='left', padx=(0, 8))
        self.eggs_backup_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_row, text="Backup-Modus (--backup, inkl. Benutzerdaten)",
                        variable=self.eggs_backup_var).pack(side='left')

        name_row = tk.Frame(produce_f, bg=T["bg"])
        name_row.pack(fill='x', pady=(0, 6))
        tk.Label(name_row, text="ISO-Name (optional):", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 6))
        self.eggs_name_var = tk.StringVar()
        ttk.Entry(name_row, textvariable=self.eggs_name_var, width=30).pack(side='left')

        # Zielordner wählbar
        dest_row = tk.Frame(produce_f, bg=T["bg"])
        dest_row.pack(fill='x', pady=(0, 6))
        tk.Label(dest_row, text="Zielordner (leer = Standard):", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 6))
        self.eggs_dest_var = tk.StringVar()
        ttk.Entry(dest_row, textvariable=self.eggs_dest_var, width=30).pack(side='left', padx=(0,6))
        ttk.Button(dest_row, text="📂",
                   command=lambda: self.eggs_dest_var.set(
                       filedialog.askdirectory(title="ISO-Zielordner wählen")
                       or self.eggs_dest_var.get()
                   )).pack(side='left')

        # Herunterfahren nach Fertigstellung
        self.eggs_shutdown_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(produce_f,
            text="🔌 Rechner nach Fertigstellung herunterfahren",
            variable=self.eggs_shutdown_var).pack(anchor='w', pady=(4, 0))

        btn_produce = ttk.Button(produce_f, text="▶ ISO erstellen",
                                  style='Accent.TButton',
                                  command=self._eggs_produce)
        btn_produce.pack(anchor='w', pady=(4, 0))

        # ── Sync-Funktionen ───────────────────────────────────────────────
        sync_f = ttk.LabelFrame(pane, text=" 🔄 Sync / Backup / Restore ", padding=8)
        sync_f.pack(fill='x', padx=12, pady=4)
        tk.Label(sync_f,
            text="syncto:   Sichert Home-Verzeichnis und Konfiguration ins ISO\n"
                 "syncfrom: Stellt Home-Verzeichnis und Konfiguration vom ISO wieder her",
            bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w', pady=(0, 6))
        sync_btn_row = tk.Frame(sync_f, bg=T["bg"])
        sync_btn_row.pack(anchor='w')
        ttk.Button(sync_btn_row, text="📤 syncto (Backup)",
                   command=lambda: self._eggs_run_cmd("syncto")).pack(side='left', padx=(0, 6))
        ttk.Button(sync_btn_row, text="📥 syncfrom (Restore)",
                   command=lambda: self._eggs_run_cmd("syncfrom")).pack(side='left', padx=(0, 6))
        ttk.Button(sync_btn_row, text="🔍 mom (Status)",
                   command=lambda: self._eggs_run_cmd("mom")).pack(side='left', padx=(0, 6))
        ttk.Button(sync_btn_row, text="🧹 kill (Aufräumen)",
                   command=lambda: self._eggs_run_cmd("kill")).pack(side='left')

        # ── ISO-Verwaltung ────────────────────────────────────────────────
        mgmt_f = ttk.LabelFrame(pane, text=" 📂 ISO-Verwaltung ", padding=8)
        mgmt_f.pack(fill='x', padx=12, pady=4)
        tk.Label(mgmt_f,
            text="Zeigt erstellte ISOs, ermöglicht Prüfsummen-Verifikation.",
            bg=T["bg"], fg=T["fg"], font=('Arial', 9)).pack(anchor='w', pady=(0, 6))
        mgmt_btn_row = tk.Frame(mgmt_f, bg=T["bg"])
        mgmt_btn_row.pack(anchor='w')
        ttk.Button(mgmt_btn_row, text="📋 ISO-Liste anzeigen",
                   command=self._eggs_list_isos).pack(side='left', padx=(0, 6))
        ttk.Button(mgmt_btn_row, text="🔍 Prüfsumme verifizieren",
                   command=self._eggs_verify_checksum).pack(side='left', padx=(0, 6))
        ttk.Button(mgmt_btn_row, text="📂 ISO-Ordner öffnen",
                   command=self._eggs_open_folder).pack(side='left')

        # ── Ausgabe-Log ───────────────────────────────────────────────────
        log_f = ttk.LabelFrame(pane, text=" Ausgabe ", padding=8)
        log_f.pack(fill='both', expand=True, padx=12, pady=(4, 12))
        self.eggs_log = self.make_log_widget(log_f, height=16)
        self.eggs_log.pack(fill='both', expand=True)
        btn_f = tk.Frame(log_f, bg=T["bg"])
        btn_f.pack(fill='x', pady=(4, 0))
        ttk.Button(btn_f, text="📋 Kopieren",
                   command=lambda: self.copy_log(self.eggs_log)).pack(side='right', padx=4)
        ttk.Button(btn_f, text="🗑 Leeren",
                   command=lambda: self.clear_log(self.eggs_log)).pack(side='right', padx=4)

        # Status beim Start prüfen
        self.app.root.after(1500, self._eggs_check_status)

    # ── Eggs-Hilfsmethoden ────────────────────────────────────────────────────
    def _eggs_check_status(self):
        import shutil as _shutil
        if _shutil.which("eggs"):
            try:
                import subprocess as _sp
                r = _sp.run(["eggs", "--version"], capture_output=True, text=True, timeout=5)
                ver = r.stdout.strip() or r.stderr.strip()
                self.eggs_status_lbl.config(
                    text="🟢 penguins-eggs ist installiert",
                    fg=self.theme["success"])
                self.eggs_version_lbl.config(text=f"Version: {ver[:80]}")
            except Exception as e:
                self.eggs_status_lbl.config(
                    text="🟡 eggs gefunden, aber Version nicht lesbar",
                    fg=self.theme["warning"])
                self.eggs_version_lbl.config(text=str(e)[:80])
        else:
            self.eggs_status_lbl.config(
                text="🔴 penguins-eggs ist NICHT installiert",
                fg=self.theme["danger"])
            self.eggs_version_lbl.config(text="Bitte über die Installations-Schaltflächen installieren.")

    def _eggs_install_fresh(self):
        # Installiert penguins-eggs über fresh-eggs (Piero Proietti, GPLv3)
        # Quelle: https://github.com/pieroproietti/fresh-eggs
        if not messagebox.askyesno("Installation",
            "Installiert penguins-eggs via fresh-eggs.\n"
            "Autor: Piero Proietti | Lizenz: GPLv3\n"
            "https://github.com/pieroproietti/fresh-eggs\n\n"
            "Benötigt Internet und Root-Rechte. Fortfahren?"):
            return
        cmd = ("bash -c '"
               "rm -rf /tmp/fresh-eggs; "
               "cd /tmp && git clone https://github.com/pieroproietti/fresh-eggs && "
               "cd fresh-eggs && bash ./fresh-eggs.sh'")
        self.run_shell_async(cmd, self.eggs_log,
                             done_cb=self._eggs_check_status)

    def _eggs_install_appimage(self):
        if not messagebox.askyesno("AppImage herunterladen",
            "Lädt penguins-eggs AppImage von GitHub herunter (über API).\n"
            "Autor: Piero Proietti | Lizenz: GPLv3\n"
            "https://github.com/pieroproietti/penguins-eggs\n\n"
            "Fortfahren?"):
            return
        # GitHub API → echte Download-URL ermitteln + Datei validieren
        cmd = r"""bash -c '
set -e
echo "Ermittle aktuelle Version via GitHub API..."
API_URL="https://api.github.com/repos/pieroproietti/penguins-eggs/releases/latest"
RELEASE=$(curl -s "$API_URL" 2>/dev/null || wget -qO- "$API_URL" 2>/dev/null)
if [ -z "$RELEASE" ]; then
    echo "FEHLER: GitHub API nicht erreichbar."
    exit 1
fi
# URL des AppImage aus JSON extrahieren (grep-Fallback ohne jq)
DL_URL=$(echo "$RELEASE" | grep -o '"browser_download_url": *"[^"]*AppImage"' | grep -o "https://[^"]*" | head -1)
if [ -z "$DL_URL" ]; then
    echo "FEHLER: Kein AppImage in den Release-Assets gefunden."
    echo "Assets:"
    echo "$RELEASE" | grep "browser_download_url" | head -10
    exit 1
fi
echo "Download-URL: $DL_URL"
TMP=/tmp/penguins-eggs-new.AppImage
wget -O "$TMP" "$DL_URL" || curl -L -o "$TMP" "$DL_URL"
SIZE=$(stat -c%s "$TMP" 2>/dev/null || echo 0)
echo "Dateigröße: $SIZE Bytes"
if [ "$SIZE" -lt 1000000 ]; then
    echo "FEHLER: Datei zu klein ($SIZE Bytes) – Download fehlgeschlagen."
    cat "$TMP" 2>/dev/null
    rm -f "$TMP"
    exit 1
fi
cp "$TMP" /usr/local/bin/eggs
chmod +x /usr/local/bin/eggs
rm -f "$TMP"
echo "Fertig: $(eggs --version 2>/dev/null || echo installiert)"
' """
        self.run_shell_async(cmd, self.eggs_log,
                             done_cb=self._eggs_check_status)

    def _eggs_produce(self):
        import shutil as _shutil
        eggs_path = _shutil.which("eggs") or "/usr/local/bin/eggs"
        if not os.path.isfile(eggs_path):
            messagebox.showerror("Fehler", "penguins-eggs ist nicht installiert.\nBitte fresh-eggs installieren.")
            return
        if os.path.getsize(eggs_path) < 1000:
            messagebox.showerror("Defekte Installation",
                "Die eggs-Datei ist defekt (zu klein).\n"
                "Bitte 'fresh-eggs installieren' erneut ausführen.")
            return
        comp  = self.eggs_compression_var.get()
        args  = ["produce", f"--compression={comp}"]
        if self.eggs_max_var.get():
            args.append("--max")
        if self.eggs_backup_var.get():
            args.append("--backup")
        name = self.eggs_name_var.get().strip()
        if name:
            args += ["--basename", name]
        dest = self.eggs_dest_var.get().strip()
        if dest and os.path.isdir(dest):
            args += ["--destdir", dest]
        args_str = " ".join(args)
        shutdown = getattr(self, "eggs_shutdown_var", None)
        do_shutdown = shutdown and shutdown.get()
        shutdown_suffix = " && sleep 5 && systemctl poweroff" if do_shutdown else ""
        cmd = f"bash -c 'PATH=/usr/local/bin:/usr/bin:/bin:$PATH eggs {args_str}{shutdown_suffix}'"
        msg = (f"Erstellt eine Live-ISO des laufenden Systems.\n\n"
               f"Kompression: {comp}  |  Max: {self.eggs_max_var.get()}  "
               f"|  Backup: {self.eggs_backup_var.get()}\n")
        if dest:
            msg += f"Zielordner: {dest}\n"
        if do_shutdown:
            msg += "\n⚠️  Der Rechner wird nach Fertigstellung heruntergefahren!\n"
        msg += "\nDies kann 15–60 Minuten dauern. Fortfahren?"
        if not messagebox.askyesno("ISO erstellen", msg):
            return
        self.run_shell_async(cmd, self.eggs_log)

    def _eggs_run_cmd(self, subcmd: str):
        import shutil as _shutil
        eggs_path = _shutil.which("eggs") or "/usr/local/bin/eggs"
        # Validieren: ist eggs ein echtes Executable (> 100 Bytes)?
        if not os.path.isfile(eggs_path):
            messagebox.showerror("Fehler", "penguins-eggs ist nicht installiert.\n"
                "Bitte über 'fresh-eggs installieren' einrichten.")
            return
        size = os.path.getsize(eggs_path)
        if size < 1000:
            messagebox.showerror("Defekte Installation",
                f"Die eggs-Datei ist nur {size} Bytes groß und daher defekt.\n\n"
                "Wahrscheinlich wurde ein fehlgeschlagener AppImage-Download\n"
                "über eine funktionierende fresh-eggs-Installation kopiert.\n\n"
                "Bitte 'fresh-eggs installieren' erneut ausführen.")
            return
        # Hinweis bei calamares
        if subcmd == "calamares":
            self.log_to(self.eggs_log,
                "ℹ️  eggs calamares richtet den Krill-Installer ein (Ersatz für Calamares).\n"
                "    Exit 0 = Erfolg. Die ISO wird damit installierbar.\n\n")
        cmd = f"bash -c 'PATH=/usr/local/bin:/usr/bin:/bin:$PATH eggs {subcmd}'"
        self.run_shell_async(cmd, self.eggs_log)

    def _eggs_list_isos(self):
        self.clear_log(self.eggs_log)
        import subprocess as _sp
        self.log_to(self.eggs_log, "Suche ISO-Dateien...\n")
        def _worker():
            found = []
            # eggs speichert ISOs unter /home/eggs oder /var/local/eggs
            for search_dir in ["/home/eggs", "/var/local/eggs", str(USER_HOME)]:
                if not os.path.isdir(search_dir):
                    continue
                try:
                    r = _sp.run(
                        ["find", search_dir, "-maxdepth", "3",
                         "-name", "*.iso", "-printf", "%s\t%f\t%p\n"],
                        capture_output=True, text=True, timeout=15)
                    for line in r.stdout.splitlines():
                        parts = line.split("\t", 2)
                        if len(parts) == 3:
                            size_bytes = int(parts[0]) if parts[0].isdigit() else 0
                            size_gb    = f"{size_bytes / 1024**3:.1f} GB" if size_bytes else "?"
                            found.append(f"  {size_gb}  {parts[2]}")
                except Exception:
                    pass
            if found:
                out = "\n".join(found)
                self.root.after(0, lambda: self.log_to(
                    self.eggs_log, f"=== Gefundene ISOs ({len(found)}) ===\n{out}\n"))
            else:
                self.root.after(0, lambda: self.log_to(
                    self.eggs_log, "Keine ISOs gefunden (Pfade: /home/eggs, /var/local/eggs).\n"))
        import threading as _t
        _t.Thread(target=_worker, daemon=True).start()

    def _eggs_verify_checksum(self):
        iso = filedialog.askopenfilename(
            title="ISO-Datei auswählen", filetypes=[("ISO-Dateien", "*.iso"), ("Alle", "*")])
        if not iso:
            return
        self.clear_log(self.eggs_log)
        # Suche passende Prüfsummen-Datei
        found_sum = None
        for ext in [".sha256", ".sha512", ".md5", ".sha1"]:
            candidate = iso + ext
            if os.path.isfile(candidate):
                found_sum = candidate
                break
            # auch ohne .iso-Extension
            base = os.path.splitext(iso)[0]
            candidate2 = base + ext
            if os.path.isfile(candidate2):
                found_sum = candidate2
                break
        if found_sum:
            algo = os.path.splitext(found_sum)[1].lstrip(".")
            self.run_shell_async(f"{algo}sum -c '{found_sum}'", self.eggs_log)
        else:
            # Kein Prüfsummen-File → SHA256 berechnen
            self.log_to(self.eggs_log, "Keine Prüfsummendatei gefunden. Berechne SHA256...\n")
            self.run_shell_async(f"sha256sum '{iso}'", self.eggs_log)

    def _eggs_open_folder(self):
        import subprocess as _sp
        folder = "/home/eggs"
        if not os.path.isdir(folder):
            folder = str(USER_HOME)
        _sp.Popen(["xdg-open", folder])


    # ══════════════════════════════════════════════════════════════════════
    #  TAB: MINT USB-INSTALLER (Integration von mint_full_installer.py)
    #  Alle 6 Modi als GUI-Oberfläche mit direktem Import der Klassen
    # ══════════════════════════════════════════════════════════════════════

    def _mint_import(self):
        """
        Importiert mint_full_installer.py – gecacht, wird nur 1× geladen.
        Beim Import wird logging.basicConfig aufgerufen → danach erst cachen.
        """
        # Cache: nach erstem Import nicht erneut laden
        if hasattr(self, "_mint_mod_cache"):
            return self._mint_mod_cache

        import importlib.util as _ilu
        candidates = [
            "/usr/local/lib/peessi-multitool/mint_full_installer.py",
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "linux auf usb", "mint_full_installer.py"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "mint_full_installer.py"),
        ]
        for path in candidates:
            path = os.path.abspath(path)
            if os.path.isfile(path):
                try:
                    spec = _ilu.spec_from_file_location("mint_full_installer", path)
                    mod  = _ilu.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    self._mint_mod_cache = mod   # cachen
                    return mod
                except Exception as e:
                    log_w = self.mint_log if hasattr(self, "mint_log") else self.iso_log
                    self.log_to(log_w, f"Import-Fehler: {e}\n")
                    self._mint_mod_cache = None
                    return None
        self._mint_mod_cache = None
        return None

    def _build_mint_installer_tab(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🍃 Mint-Installer")

        # Sub-Notebook für die 6 Modi
        sub_nb = ttk.Notebook(tab)
        sub_nb.pack(fill='both', expand=True, padx=4, pady=4)

        self._mint_build_dd(sub_nb, T)
        self._mint_build_full(sub_nb, T)
        self._mint_build_ventoy(sub_nb, T)
        self._mint_build_clone(sub_nb, T)
        self._mint_build_info(sub_nb, T)
        self._mint_build_settings(sub_nb, T)

    # ── Gemeinsames Log-Widget ────────────────────────────────────────────────
    def _mint_make_log(self, parent, T):
        log_f = ttk.LabelFrame(parent, text=" Ausgabe ", padding=6)
        log_f.pack(fill='both', expand=True, padx=12, pady=(4, 8))
        log_w = self.make_log_widget(log_f, height=14)
        log_w.pack(fill='both', expand=True)
        btn_row = tk.Frame(log_f, bg=T["bg"])
        btn_row.pack(fill='x', pady=(4, 0))
        ttk.Button(btn_row, text="📋 Kopieren",
                   command=lambda: self.copy_log(log_w)).pack(side='right', padx=4)
        ttk.Button(btn_row, text="🗑 Leeren",
                   command=lambda: self.clear_log(log_w)).pack(side='right', padx=4)
        return log_w

    # ── Gemeinsame ISO-Auswahl ────────────────────────────────────────────────
    def _mint_iso_row(self, parent, T, var_name: str):
        f = ttk.LabelFrame(parent, text=" ISO-Datei ", padding=8)
        f.pack(fill='x', padx=12, pady=(10, 4))
        row = tk.Frame(f, bg=T["bg"])
        row.pack(fill='x')
        var = tk.StringVar()
        setattr(self, var_name, var)
        ttk.Entry(row, textvariable=var, font=('Arial', 10)
                  ).pack(side='left', fill='x', expand=True, padx=(0, 6))
        def _browse():
            p = filedialog.askopenfilename(
                title="ISO wählen",
                filetypes=[("ISO-Dateien", "*.iso"), ("Alle", "*")])
            if p:
                var.set(p)
        ttk.Button(row, text="📂 Wählen", command=_browse).pack(side='left')
        return var

    # ── Gemeinsame Laufwerk-Auswahl ───────────────────────────────────────────
    def _mint_drive_row(self, parent, T, var_name: str, label="Ziel-Laufwerk"):
        f = ttk.LabelFrame(parent, text=f" {label} ", padding=8)
        f.pack(fill='x', padx=12, pady=4)
        row = tk.Frame(f, bg=T["bg"])
        row.pack(fill='x')
        var = tk.StringVar()
        setattr(self, var_name, var)
        cb = ttk.Combobox(row, textvariable=var, state='readonly', font=('Arial', 10), width=50)
        cb.pack(side='left', fill='x', expand=True, padx=(0, 6))
        def _refresh():
            mod = self._mint_import()
            if not mod:
                cb['values'] = ["❌ mint_full_installer.py nicht gefunden"]
                return
            try:
                drives = mod.DriveDetector.get_all_drives()
                vals = [
                    f"{d.path}  |  {d.model[:30]}  |  {d.size_str}  |  {d.type.value.upper()}"
                    for d in drives
                ]
                cb['values'] = vals if vals else ["Keine Laufwerke gefunden"]
                if vals:
                    cb.current(0)
                # Drive-Objekte merken
                setattr(self, f"_mint_drives_{var_name}", drives)
            except Exception as e:
                cb['values'] = [f"Fehler: {e}"]
        ttk.Button(row, text="🔄 Laufwerke laden", command=_refresh).pack(side='left')
        # KEIN sofortiger _refresh() – wird erst bei Klick oder Tab-Wechsel geladen
        # Verhindert 5× mint_full_installer-Import + lsblk beim Programmstart
        cb['values'] = ["← Bitte 'Laufwerke laden' klicken"]
        return var

    def _mint_get_drive(self, var_name: str):
        """Gibt das Drive-Objekt für die aktuell gewählte Combobox-Auswahl zurück."""
        drives = getattr(self, f"_mint_drives_{var_name}", [])
        var    = getattr(self, var_name)
        val    = var.get()
        for i, d in enumerate(drives):
            if val.startswith(d.path):
                return d
        return None

    def _mint_log_stream(self, log_w, text: str):
        """Streamt Text ins Log-Widget (thread-safe über root.after)."""
        import re as _re
        clean = _re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', text)  # ANSI entfernen
        self.root.after(0, lambda t=clean: self.log_to(log_w, t))

    # ══════════════════════════════════════════════════════════════════════
    #  MODUS 1: DD mit Verifikation + Auto-Shutdown
    # ══════════════════════════════════════════════════════════════════════
    def _mint_build_dd(self, nb, T):
        tab  = ttk.Frame(nb)
        nb.add(tab, text="💿 DD-Modus")

        desc = ttk.LabelFrame(tab, text=" Beschreibung ", padding=8)
        desc.pack(fill='x', padx=12, pady=(10, 4))
        tk.Label(desc,
            text="Schreibt ISO 1:1 auf USB-Stick (dd) mit optionaler SHA256-Prüfung\n"
                 "vor dem Schreiben und Verifikation danach. Schnellste Methode.",
            bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        self._mint_iso_row(tab, T, "mint_dd_iso")
        self._mint_drive_row(tab, T, "mint_dd_drive")

        opt_f = ttk.LabelFrame(tab, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', padx=12, pady=4)

        # Hash-Prüfung vor dem Schreiben
        self.mint_dd_prehash_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_f, text="SHA256 vor dem Schreiben prüfen",
                        variable=self.mint_dd_prehash_var).pack(anchor='w')
        hash_row = tk.Frame(opt_f, bg=T["bg"])
        hash_row.pack(fill='x', pady=(4, 0))
        tk.Label(hash_row, text="Erwarteter SHA256:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 6))
        self.mint_dd_hash_var = tk.StringVar()
        ttk.Entry(hash_row, textvariable=self.mint_dd_hash_var,
                  font=('Arial', 9), width=68).pack(side='left', fill='x', expand=True)

        # Verifikation nach dem Schreiben
        self.mint_dd_verify_var = tk.StringVar(value="schnell")
        ver_f = tk.Frame(opt_f, bg=T["bg"])
        ver_f.pack(anchor='w', pady=(6, 0))
        tk.Label(ver_f, text="Verifikation nach Schreiben:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 6))
        for lbl, val in [("Keine", "keine"), ("Schnelltest", "schnell"),
                         ("25% Tiefenprüfung", "tief"), ("Vollständig (100%)", "voll")]:
            ttk.Radiobutton(ver_f, text=lbl, variable=self.mint_dd_verify_var,
                            value=val).pack(side='left', padx=4)

        # Auto-Shutdown
        self.mint_dd_shutdown_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_f, text="Auto-Shutdown nach Abschluss",
                        variable=self.mint_dd_shutdown_var).pack(anchor='w', pady=(6, 0))

        # Fortschritt
        prog_f = ttk.LabelFrame(tab, text=" Fortschritt ", padding=6)
        prog_f.pack(fill='x', padx=12, pady=4)
        self.mint_dd_pct = tk.DoubleVar()
        ttk.Progressbar(prog_f, variable=self.mint_dd_pct, maximum=100).pack(fill='x')

        self.mint_log = self._mint_make_log(tab, T)

        btn_f = tk.Frame(tab, bg=T["bg"])
        btn_f.pack(fill='x', padx=12, pady=(4, 12))
        self.mint_dd_btn = ttk.Button(btn_f, text="🔥 Schreiben starten",
                                       style='Danger.TButton',
                                       command=self._mint_run_dd)
        self.mint_dd_btn.pack(side='right', padx=4)
        ttk.Button(btn_f, text="🔍 Nur SHA256 prüfen",
                   command=self._mint_check_hash).pack(side='right', padx=4)

    def _mint_check_hash(self):
        iso  = getattr(self, "mint_dd_iso", tk.StringVar()).get().strip()
        exp  = getattr(self, "mint_dd_hash_var", tk.StringVar()).get().strip().lower()
        if not iso or not os.path.isfile(iso):
            messagebox.showerror("Fehler", "Bitte ISO-Datei auswählen.")
            return
        def worker():
            mod = self._mint_import()
            if not mod:
                self._mint_log_stream(self.mint_log, "❌ mint_full_installer.py nicht gefunden.\n")
                return
            self._mint_log_stream(self.mint_log, "Berechne SHA256...\n")
            actual = mod.ChecksumManager.calculate_checksum(iso, 'sha256')
            if exp:
                ok = actual and actual.lower() == exp
                self._mint_log_stream(self.mint_log,
                    f"{'✅' if ok else '❌'} SHA256: {actual}\n"
                    f"Erwartet: {exp}\n")
            else:
                self._mint_log_stream(self.mint_log, f"SHA256: {actual}\n")
        threading.Thread(target=worker, daemon=True).start()

    def _mint_run_dd(self):
        iso   = getattr(self, "mint_dd_iso", tk.StringVar()).get().strip()
        drive = self._mint_get_drive("mint_dd_drive")
        if not iso or not os.path.isfile(iso):
            messagebox.showerror("Fehler", "Bitte ISO-Datei auswählen.")
            return
        if not drive:
            messagebox.showerror("Fehler", "Bitte Ziel-Laufwerk auswählen.")
            return
        if not messagebox.askyesno("Bestätigung",
            f"⚠️  ALLE DATEN auf {drive.path} ({drive.size_str}) werden GELÖSCHT!\n\n"
            f"ISO: {os.path.basename(iso)}\nFortfahren?", icon='warning'):
            return

        verify_mode = self.mint_dd_verify_var.get()
        prehash     = self.mint_dd_prehash_var.get()
        exp_hash    = self.mint_dd_hash_var.get().strip().lower()
        shutdown    = self.mint_dd_shutdown_var.get()
        self.mint_dd_btn.config(state='disabled')
        self.clear_log(self.mint_log)

        def worker():
            mod = self._mint_import()
            if not mod:
                self._mint_log_stream(self.mint_log, "❌ mint_full_installer.py nicht gefunden.\n")
                self.root.after(0, lambda: self.mint_dd_btn.config(state='normal'))
                return

            log = self.mint_log

            # 1. SHA256 vor dem Schreiben
            if prehash:
                self._mint_log_stream(log, "🔍 Prüfe SHA256 der ISO...\n")
                actual = mod.ChecksumManager.calculate_checksum(iso, 'sha256')
                self._mint_log_stream(log, f"   SHA256: {actual}\n")
                if exp_hash and actual and actual.lower() != exp_hash:
                    self._mint_log_stream(log, "❌ SHA256 stimmt NICHT überein – Abbruch.\n")
                    self.root.after(0, lambda: self.mint_dd_btn.config(state='normal'))
                    return
                elif exp_hash and actual:
                    self._mint_log_stream(log, "✅ SHA256 stimmt überein.\n")

            # 2. dd schreiben
            self._mint_log_stream(log, f"\n💿 Schreibe {os.path.basename(iso)} → {drive.path}...\n")
            try:
                import subprocess as _sp
                proc = _sp.Popen(
                    ['dd', f'if={iso}', f'of={drive.path}',
                     'bs=4M', 'status=progress', 'oflag=sync'],
                    stdout=_sp.PIPE, stderr=_sp.STDOUT, text=True
                )
                for line in proc.stdout:
                    self._mint_log_stream(log, line)
                proc.wait()
                if proc.returncode != 0:
                    self._mint_log_stream(log, f"❌ dd fehlgeschlagen (Exit {proc.returncode})\n")
                    self.root.after(0, lambda: self.mint_dd_btn.config(state='normal'))
                    return
                _sp.run(['sync'], check=False)
                self._mint_log_stream(log, "✅ Schreibvorgang abgeschlossen.\n")
            except Exception as e:
                self._mint_log_stream(log, f"❌ Fehler: {e}\n")
                self.root.after(0, lambda: self.mint_dd_btn.config(state='normal'))
                return

            # 3. Verifikation nach dem Schreiben
            if verify_mode != "keine":
                self._mint_log_stream(log, f"\n🔎 Verifikation ({verify_mode})...\n")
                try:
                    if verify_mode == "schnell":
                        ok, msg = mod.VerificationManager.verify_usb_write(iso, drive, 'dd')
                    elif verify_mode == "tief":
                        ok, msg = mod.AdvancedVerification.deep_verify(iso, drive, 25)
                    else:
                        ok, msg = mod.AdvancedVerification.verify_with_progress(iso, drive)
                    self._mint_log_stream(log, f"{'✅' if ok else '❌'} {msg}\n")
                except Exception as e:
                    self._mint_log_stream(log, f"⚠️ Verifikation fehlgeschlagen: {e}\n")

            # 4. Auto-Shutdown
            if shutdown:
                self._mint_log_stream(log, "\n⏻ System wird in 10 Sekunden heruntergefahren...\n")
                import time as _t
                _t.sleep(10)
                import subprocess as _sp2
                _sp2.Popen(['systemctl', 'poweroff'])
            else:
                self._mint_log_stream(log, "\n🏁 Fertig.\n")

            self.root.after(0, lambda: self.mint_dd_btn.config(state='normal'))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  MODUS 2: Full-Modus (Vollinstallation mit squashfs)
    # ══════════════════════════════════════════════════════════════════════
    def _mint_build_full(self, nb, T):
        tab = ttk.Frame(nb)
        nb.add(tab, text="📦 Full-Modus")

        desc = ttk.LabelFrame(tab, text=" Beschreibung ", padding=8)
        desc.pack(fill='x', padx=12, pady=(10, 4))
        tk.Label(desc,
            text="Vollinstallation: Partitioniert USB-Stick (EFI + Root), extrahiert\n"
                 "squashfs aus der ISO und installiert GRUB. Erstellt Benutzerkonto.\n"
                 "⚠️ Dauert 15–30 Minuten. Nur für Offline-Nutzung geeignet.",
            bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        self._mint_iso_row(tab, T, "mint_full_iso")
        self._mint_drive_row(tab, T, "mint_full_drive")

        user_f = ttk.LabelFrame(tab, text=" Benutzerkonto ", padding=8)
        user_f.pack(fill='x', padx=12, pady=4)
        urow = tk.Frame(user_f, bg=T["bg"])
        urow.pack(fill='x')
        tk.Label(urow, text="Benutzername:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 6))
        self.mint_full_user = tk.StringVar(value="user")
        ttk.Entry(urow, textvariable=self.mint_full_user, width=20).pack(side='left', padx=(0, 12))
        tk.Label(urow, text="Passwort:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 6))
        self.mint_full_pw = tk.StringVar()
        ttk.Entry(urow, textvariable=self.mint_full_pw, show="●", width=20).pack(side='left')

        self.mint_full_shutdown = tk.BooleanVar(value=False)
        ttk.Checkbutton(tab, text="Auto-Shutdown nach Abschluss",
                        variable=self.mint_full_shutdown).pack(anchor='w', padx=12, pady=4)

        log_w = self._mint_make_log(tab, T)
        self.mint_full_log = log_w

        btn_f = tk.Frame(tab, bg=T["bg"])
        btn_f.pack(fill='x', padx=12, pady=(4, 12))
        self.mint_full_btn = ttk.Button(btn_f, text="🚀 Vollinstallation starten",
                                         style='Danger.TButton',
                                         command=lambda: self._mint_run_full(log_w))
        self.mint_full_btn.pack(side='right', padx=4)

    def _mint_run_full(self, log_w):
        iso   = getattr(self, "mint_full_iso", tk.StringVar()).get().strip()
        drive = self._mint_get_drive("mint_full_drive")
        user  = self.mint_full_user.get().strip()
        pw    = self.mint_full_pw.get()
        if not iso or not os.path.isfile(iso):
            messagebox.showerror("Fehler", "Bitte ISO-Datei auswählen.")
            return
        if not drive:
            messagebox.showerror("Fehler", "Bitte Ziel-Laufwerk auswählen.")
            return
        if not user or not pw:
            messagebox.showerror("Fehler", "Benutzername und Passwort eingeben.")
            return
        if not messagebox.askyesno("Bestätigung",
            f"⚠️  VOLLINSTALLATION auf {drive.path} ({drive.size_str})\n"
            f"ALLE DATEN WERDEN GELÖSCHT!\n\nDas dauert 15–30 Minuten.\nFortfahren?",
            icon='warning'):
            return

        shutdown = self.mint_full_shutdown.get()
        self.mint_full_btn.config(state='disabled')
        self.clear_log(log_w)

        def worker():
            mod = self._mint_import()
            if not mod:
                self._mint_log_stream(log_w, "❌ mint_full_installer.py nicht gefunden.\n")
                self.root.after(0, lambda: self.mint_full_btn.config(state='normal'))
                return
            try:
                # USBInstaller instantiieren, aber _create_user überschreiben
                installer = mod.USBInstaller()
                # Monkey-patch _create_user um GUI-Eingaben zu verwenden
                def _gui_create_user(target_root):
                    import subprocess as _sp, crypt as _crypt
                    _sp.run(['chroot', target_root, 'useradd', '-m', '-s', '/bin/bash',
                             '-G', 'sudo,audio,video,netdev,plugdev', user], check=True)
                    proc = _sp.Popen(['chroot', target_root, 'chpasswd'],
                                     stdin=_sp.PIPE, text=True)
                    proc.communicate(f'{user}:{pw}')
                installer._create_user = _gui_create_user

                # Stdout umleiten
                import io, sys as _sys, contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    success, msg = installer.mode_full(iso, drive)

                output = buf.getvalue()
                for line in output.splitlines(keepends=True):
                    self._mint_log_stream(log_w, line)

                self._mint_log_stream(log_w,
                    f"\n{'✅' if success else '❌'} {msg}\n")

                if success and shutdown:
                    self._mint_log_stream(log_w, "\n⏻ Shutdown in 10s...\n")
                    import time as _t; _t.sleep(10)
                    import subprocess as _sp2
                    _sp2.Popen(['systemctl', 'poweroff'])
            except Exception as e:
                self._mint_log_stream(log_w, f"❌ Fehler: {e}\n")
            finally:
                self.root.after(0, lambda: self.mint_full_btn.config(state='normal'))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  MODUS 3: Ventoy mit Fresh Eggs
    # ══════════════════════════════════════════════════════════════════════
    def _mint_build_ventoy(self, nb, T):
        tab = ttk.Frame(nb)
        nb.add(tab, text="🗂️ Ventoy-Modus")

        desc = ttk.LabelFrame(tab, text=" Beschreibung ", padding=8)
        desc.pack(fill='x', padx=12, pady=(10, 4))
        tk.Label(desc,
            text="Installiert Ventoy (Multi-ISO-Boot) auf USB-Stick.\n"
                 "Ventoy: Ventoy-Team | Lizenz: GPLv3 | https://github.com/ventoy/Ventoy\n"
                 "Optionaler Fresh Eggs Plugin für persistente Daten.\n"
                 "Danach können mehrere ISO-Dateien auf den Stick kopiert werden.",
            bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        self._mint_drive_row(tab, T, "mint_ventoy_drive")

        opt_f = ttk.LabelFrame(tab, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', padx=12, pady=4)

        self.mint_ventoy_fresh = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_f, text="Fresh Eggs Plugin installieren (falls verfügbar)",
                        variable=self.mint_ventoy_fresh).pack(anchor='w')

        self.mint_ventoy_persist = tk.BooleanVar(value=False)
        p_row = tk.Frame(opt_f, bg=T["bg"])
        p_row.pack(anchor='w', pady=4)
        ttk.Checkbutton(p_row, text="Persistenz-Datei erstellen  (GB):",
                        variable=self.mint_ventoy_persist).pack(side='left')
        self.mint_ventoy_persist_gb = tk.StringVar(value="4")
        ttk.Spinbox(p_row, from_=1, to=32,
                    textvariable=self.mint_ventoy_persist_gb,
                    width=5).pack(side='left', padx=6)

        # ISO-Liste für Ventoy
        iso_list_f = ttk.LabelFrame(tab, text=" ISO-Dateien für Multi-Boot ", padding=8)
        iso_list_f.pack(fill='x', padx=12, pady=4)
        self.mint_ventoy_isos = []
        iso_lb_frame = tk.Frame(iso_list_f, bg=T["bg"])
        iso_lb_frame.pack(fill='x')
        self.mint_ventoy_lb = tk.Listbox(iso_lb_frame, height=5,
                                          bg=T["bg2"], fg=T["fg"], selectmode='single')
        self.mint_ventoy_lb.pack(side='left', fill='x', expand=True)
        lb_sb = ttk.Scrollbar(iso_lb_frame, orient='vertical',
                              command=self.mint_ventoy_lb.yview)
        self.mint_ventoy_lb.configure(yscrollcommand=lb_sb.set)
        lb_sb.pack(side='left', fill='y')
        lb_btn = tk.Frame(iso_list_f, bg=T["bg"])
        lb_btn.pack(anchor='w', pady=(4, 0))
        def _add_iso():
            p = filedialog.askopenfilename(
                title="ISO hinzufügen",
                filetypes=[("ISO-Dateien", "*.iso"), ("Alle", "*")])
            if p:
                self.mint_ventoy_isos.append(p)
                self.mint_ventoy_lb.insert('end', os.path.basename(p))
        def _rem_iso():
            sel = self.mint_ventoy_lb.curselection()
            if sel:
                idx = sel[0]
                self.mint_ventoy_lb.delete(idx)
                self.mint_ventoy_isos.pop(idx)
        ttk.Button(lb_btn, text="➕ ISO hinzufügen", command=_add_iso).pack(side='left', padx=4)
        ttk.Button(lb_btn, text="➖ Entfernen", command=_rem_iso).pack(side='left', padx=4)

        log_w = self._mint_make_log(tab, T)
        self.mint_ventoy_log = log_w

        btn_f = tk.Frame(tab, bg=T["bg"])
        btn_f.pack(fill='x', padx=12, pady=(4, 12))
        self.mint_ventoy_btn = ttk.Button(btn_f, text="🚀 Ventoy installieren",
                                           style='Accent.TButton',
                                           command=lambda: self._mint_run_ventoy(log_w))
        self.mint_ventoy_btn.pack(side='right', padx=4)

    def _mint_run_ventoy(self, log_w):
        drive = self._mint_get_drive("mint_ventoy_drive")
        if not drive:
            messagebox.showerror("Fehler", "Bitte Laufwerk auswählen.")
            return
        if not messagebox.askyesno("Bestätigung",
            f"Ventoy auf {drive.path} ({drive.size_str}) installieren?\n"
            f"ALLE DATEN WERDEN GELÖSCHT!\nFortfahren?", icon='warning'):
            return

        use_fresh  = self.mint_ventoy_fresh.get()
        use_persist = self.mint_ventoy_persist.get()
        persist_gb = int(self.mint_ventoy_persist_gb.get() or "4")
        isos       = list(self.mint_ventoy_isos)
        self.mint_ventoy_btn.config(state='disabled')
        self.clear_log(log_w)

        def worker():
            mod = self._mint_import()
            if not mod:
                self._mint_log_stream(log_w, "❌ mint_full_installer.py nicht gefunden.\n")
                self.root.after(0, lambda: self.mint_ventoy_btn.config(state='normal'))
                return
            try:
                ventoy = mod.VentoyManager()
                if not ventoy.available:
                    self._mint_log_stream(log_w, "❌ Ventoy nicht gefunden.\n"
                        "Bitte Ventoy installieren: https://github.com/ventoy/Ventoy\n"
                        "Oder: prepare_system.sh ausführen (mit Ventoy-Option).\n")
                    return

                self._mint_log_stream(log_w, "🔧 Installiere Ventoy...\n")
                ok, msg = ventoy.install(drive.path)
                self._mint_log_stream(log_w, f"{'✅' if ok else '❌'} {msg}\n")
                if not ok:
                    return

                if use_fresh and ventoy.fresh_eggs_available:
                    self._mint_log_stream(log_w, "🥚 Installiere Fresh Eggs Plugin...\n")
                    ok2, msg2 = ventoy.install_fresh_eggs(drive.path)
                    self._mint_log_stream(log_w, f"{'✅' if ok2 else '⚠️'} {msg2}\n")
                elif use_fresh:
                    self._mint_log_stream(log_w, "⚠️ Fresh Eggs Plugin nicht verfügbar.\n"
                        "prepare_system.sh ausführen um Ventoy + Fresh Eggs zu installieren.\n")

                if isos:
                    import time as _t, tempfile as _tmp, subprocess as _sp
                    _t.sleep(2)
                    mp = _tmp.mkdtemp(prefix='ventoy_')
                    try:
                        _sp.run(['mount', f"{drive.path}1", mp], check=True)
                        self._mint_log_stream(log_w, f"📂 Kopiere {len(isos)} ISO(s)...\n")
                        ok3, msg3 = ventoy.configure_multi_iso(mp, isos)
                        self._mint_log_stream(log_w, f"{'✅' if ok3 else '❌'} {msg3}\n")
                        if use_persist:
                            self._mint_log_stream(log_w, f"💾 Erstelle Persistenz ({persist_gb}GB)...\n")
                            ok4, msg4 = ventoy.create_persistence(mp, persist_gb)
                            self._mint_log_stream(log_w, f"{'✅' if ok4 else '❌'} {msg4}\n")
                    finally:
                        _sp.run(['umount', mp], check=False)
                        import shutil as _sh
                        _sh.rmtree(mp, ignore_errors=True)

                self._mint_log_stream(log_w, "\n🏁 Ventoy-Modus abgeschlossen.\n")
            except Exception as e:
                self._mint_log_stream(log_w, f"❌ Fehler: {e}\n")
            finally:
                self.root.after(0, lambda: self.mint_ventoy_btn.config(state='normal'))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  MODUS 4+5: Clone + Verifikation
    # ══════════════════════════════════════════════════════════════════════
    def _mint_build_clone(self, nb, T):
        tab = ttk.Frame(nb)
        nb.add(tab, text="🔁 Clone-Modus")

        desc = ttk.LabelFrame(tab, text=" Beschreibung ", padding=8)
        desc.pack(fill='x', padx=12, pady=(10, 4))
        tk.Label(desc,
            text="Klont ein USB-Laufwerk 1:1 auf ein anderes (dd bs=4M).\n"
                 "Optionale Verifikation via cmp nach dem Klonen.\n"
                 "⚠️ Quelle und Ziel dürfen nicht identisch sein!",
            bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        self._mint_drive_row(tab, T, "mint_clone_src", label="Quelle (zu kopierender Stick)")
        self._mint_drive_row(tab, T, "mint_clone_dst", label="Ziel (wird überschrieben)")

        opt_f = ttk.LabelFrame(tab, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', padx=12, pady=4)
        self.mint_clone_verify = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_f, text="Nach dem Klonen verifizieren (cmp)",
                        variable=self.mint_clone_verify).pack(anchor='w')

        log_w = self._mint_make_log(tab, T)
        self.mint_clone_log = log_w

        btn_f = tk.Frame(tab, bg=T["bg"])
        btn_f.pack(fill='x', padx=12, pady=(4, 12))
        self.mint_clone_btn = ttk.Button(btn_f, text="🔁 Klonen starten",
                                          style='Danger.TButton',
                                          command=lambda: self._mint_run_clone(log_w))
        self.mint_clone_btn.pack(side='right', padx=4)

    def _mint_run_clone(self, log_w):
        src = self._mint_get_drive("mint_clone_src")
        dst = self._mint_get_drive("mint_clone_dst")
        if not src or not dst:
            messagebox.showerror("Fehler", "Bitte Quelle und Ziel auswählen.")
            return
        if src.path == dst.path:
            messagebox.showerror("Fehler", "Quelle und Ziel sind identisch!")
            return
        if not messagebox.askyesno("Bestätigung",
            f"Klone {src.path} ({src.size_str}) → {dst.path} ({dst.size_str})\n"
            f"ALLE DATEN AUF {dst.path} WERDEN GELÖSCHT!\nFortfahren?", icon='warning'):
            return

        verify = self.mint_clone_verify.get()
        self.mint_clone_btn.config(state='disabled')
        self.clear_log(log_w)

        def worker():
            mod = self._mint_import()
            if not mod:
                self._mint_log_stream(log_w, "❌ mint_full_installer.py nicht gefunden.\n")
                self.root.after(0, lambda: self.mint_clone_btn.config(state='normal'))
                return
            try:
                self._mint_log_stream(log_w, f"🔁 Klone {src.path} → {dst.path}...\n")
                ok, msg = mod.USBCloneManager.clone_usb(src, dst)
                self._mint_log_stream(log_w, f"{'✅' if ok else '❌'} {msg}\n")
                if ok and verify:
                    self._mint_log_stream(log_w, "🔎 Verifiziere Klon...\n")
                    vok, vmsg = mod.USBCloneManager.verify_clone(src, dst)
                    self._mint_log_stream(log_w, f"{'✅' if vok else '❌'} {vmsg}\n")
            except Exception as e:
                self._mint_log_stream(log_w, f"❌ Fehler: {e}\n")
            finally:
                self.root.after(0, lambda: self.mint_clone_btn.config(state='normal'))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  INFO-MODUS
    # ══════════════════════════════════════════════════════════════════════
    def _mint_build_info(self, nb, T):
        tab = ttk.Frame(nb)
        nb.add(tab, text="ℹ️ Info")

        desc = ttk.LabelFrame(tab, text=" Systeminformationen ", padding=8)
        desc.pack(fill='x', padx=12, pady=(10, 4))
        tk.Label(desc,
            text="Zeigt erkannte Laufwerke, Ventoy-Status und Prüfsummen-Unterstützung.",
            bg=T["bg"], fg=T["fg"], font=('Arial', 9)).pack(anchor='w')

        log_w = self._mint_make_log(tab, T)
        self.mint_info_log = log_w

        btn_f = tk.Frame(tab, bg=T["bg"])
        btn_f.pack(fill='x', padx=12, pady=(4, 12))
        ttk.Button(btn_f, text="🔄 Systeminformationen laden",
                   style='Accent.TButton',
                   command=lambda: self._mint_run_info(log_w)).pack(side='right', padx=4)

    def _mint_run_info(self, log_w):
        self.clear_log(log_w)
        def worker():
            mod = self._mint_import()
            if not mod:
                self._mint_log_stream(log_w, "❌ mint_full_installer.py nicht gefunden.\n")
                return
            try:
                import platform as _plat
                self._mint_log_stream(log_w,
                    f"=== Linux USB Ultimate Installer v{mod.VERSION} ===\n\n"
                    f"System:      {_plat.system()} {_plat.release()}\n"
                    f"Architektur: {_plat.machine()}\n\n"
                    f"=== Erkannte Laufwerke ===\n")
                drives = mod.DriveDetector.get_all_drives()
                if drives:
                    for d in drives:
                        self._mint_log_stream(log_w,
                            f"\n  {d.path}\n"
                            f"    Typ:    {d.type.value.upper()}\n"
                            f"    Modell: {d.model}\n"
                            f"    Größe:  {d.size_str}\n"
                            f"    Mounts: {', '.join(d.mount_points) or '–'}\n")
                else:
                    self._mint_log_stream(log_w, "  Keine Laufwerke gefunden.\n")

                ventoy = mod.VentoyManager()
                self._mint_log_stream(log_w,
                    f"\n=== Ventoy ===\n"
                    f"  Status:     {'✅ verfügbar' if ventoy.available else '❌ nicht gefunden'}\n"
                    f"  Pfad:       {ventoy.ventoy_path or '–'}\n"
                    f"  Fresh Eggs: {'✅ verfügbar' if ventoy.fresh_eggs_available else '❌ nicht gefunden'}\n")

                self._mint_log_stream(log_w,
                    f"\n=== Prüfsummen ===\n"
                    f"  MD5, SHA1, SHA256, SHA512 – alle verfügbar\n\n"
                    f"=== Installationsmodi ===\n"
                    f"  1. DD-Modus     – ISO schreiben + Verifikation\n"
                    f"  2. Full-Modus   – Vollinstallation (squashfs + GRUB)\n"
                    f"  3. Ventoy-Modus – Multi-ISO + Fresh Eggs\n"
                    f"  4. Clone-Modus  – USB-Stick klonen\n")
            except Exception as e:
                self._mint_log_stream(log_w, f"❌ Fehler: {e}\n")

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  EINSTELLUNGEN (prepare_system.sh)
    # ══════════════════════════════════════════════════════════════════════
    def _mint_build_settings(self, nb, T):
        tab = ttk.Frame(nb)
        nb.add(tab, text="⚙️ Vorbereitung")

        desc = ttk.LabelFrame(tab, text=" Systemvorbereitung ", padding=8)
        desc.pack(fill='x', padx=12, pady=(10, 4))
        tk.Label(desc,
            text="Installiert alle benötigten Tools für den USB-Installer:\n"
                 "Partitionierung, Dateisystem, GRUB, rsync, squashfs, Ventoy, Fresh Eggs.\n"
                 "Führt prepare_system.sh aus (Root benötigt).",
            bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        opt_f = ttk.LabelFrame(tab, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', padx=12, pady=4)
        self.mint_prep_ventoy = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_f,
            text="Ventoy + Fresh Eggs automatisch installieren (benötigt Internet)",
            variable=self.mint_prep_ventoy).pack(anchor='w')

        log_w = self._mint_make_log(tab, T)
        self.mint_prep_log = log_w

        btn_f = tk.Frame(tab, bg=T["bg"])
        btn_f.pack(fill='x', padx=12, pady=(4, 12))
        ttk.Button(btn_f, text="🔧 Systemvorbereitung starten",
                   style='Accent.TButton',
                   command=lambda: self._mint_run_prepare(log_w)).pack(side='right', padx=4)

    def _mint_run_prepare(self, log_w):
        candidates = [
            "/usr/local/lib/peessi-multitool/prepare_system.sh",
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "linux auf usb", "prepare_system.sh"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "prepare_system.sh"),
        ]
        script = None
        for c in candidates:
            if os.path.isfile(os.path.abspath(c)):
                script = os.path.abspath(c)
                break

        if not script:
            messagebox.showinfo("Nicht gefunden",
                "prepare_system.sh nicht gefunden.\n"
                "Bitte sicherstellen dass die Datei unter\n"
                "/usr/local/lib/peessi-multitool/ vorhanden ist.")
            return

        # Ventoy-Antwort vorbereiten (j/n)
        answer = "j" if self.mint_prep_ventoy.get() else "n"
        cmd = f'echo "{answer}" | bash "{script}"'
        self.run_shell_async(cmd, log_w)
