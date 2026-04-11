#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: gui_base.py  –  Basis-Klasse: Theme, Header, Statusbar, Hilfsmethoden
"""

import os
import logging as _logging
import sys
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import List, Optional

from config import THEMES, ORIGINAL_USER, VERSION
from wipe_engine import WipeEngine


class GuiBase:
    """
    Basisklasse für alle GUI-Teile.
    Stellt theme-Zugriff, log-Hilfsmethoden und den Haupt-Rahmen bereit.
    """

    def __init__(self, root: tk.Tk, settings: dict, theme: dict,
                 log_widgets_ref: list):
        self.root        = root
        self.settings    = settings
        self.theme       = theme
        self._log_widgets = log_widgets_ref   # gemeinsame Liste, alle Tabs eintragen

    # ── Theme-System ──────────────────────────────────────────────────────────
    def apply_theme(self):
        T = self.theme
        self.root.configure(bg=T["bg"])
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        style.configure('.', background=T["bg"], foreground=T["fg"],
                        fieldbackground=T["bg2"], troughcolor=T["bg"],
                        bordercolor=T["border"], darkcolor=T["bg"], lightcolor=T["bg2"])
        style.configure('TLabel',       background=T["bg"],  foreground=T["fg"])
        style.configure('TFrame',       background=T["bg"])
        style.configure('TLabelframe',  background=T["bg"],  foreground=T["fg"],
                        bordercolor=T["border"])
        style.configure('TLabelframe.Label', background=T["bg"],
                        foreground=T["accent"], font=('Helvetica', 10, 'bold'))
        style.configure('TNotebook',    background=T["bg"],  borderwidth=0)
        style.configure('TNotebook.Tab', background=T["bg2"], foreground=T["fg_dim"],
                        padding=[12, 6], font=('Arial', 9))
        style.map('TNotebook.Tab',
                  background=[('selected', T["accent"])],
                  foreground=[('selected', '#ffffff')])
        style.configure('TButton', background=T["btn_bg"], foreground=T["btn_fg"],
                        borderwidth=0, relief='flat', padding=[10, 5], font=('Arial', 9))
        style.map('TButton',
                  background=[('active', T["accent2"]), ('disabled', T["border"])],
                  foreground=[('active', '#ffffff'),    ('disabled', T["fg_dim"])])
        style.configure('Accent.TButton', background=T["accent"], foreground='#ffffff',
                        font=('Arial', 10, 'bold'), padding=[14, 7])
        style.configure('Danger.TButton', background=T["danger"], foreground='#ffffff',
                        font=('Arial', 10, 'bold'), padding=[14, 7])
        style.configure('TProgressbar', troughcolor=T["bg2"], background=T["accent"])
        style.configure('TCombobox',    fieldbackground=T["bg2"], background=T["bg"],
                        foreground=T["fg"], selectbackground=T["sel_bg"])
        style.configure('TEntry',       fieldbackground=T["bg2"], foreground=T["fg"],
                        insertcolor=T["fg"])
        style.configure('TCheckbutton', background=T["bg"], foreground=T["fg"])
        style.configure('Treeview',     background=T["bg2"], fieldbackground=T["bg2"],
                        foreground=T["fg"], rowheight=24)
        style.configure('Treeview.Heading', background=T["bg"],
                        foreground=T["accent"], font=('Arial', 9, 'bold'))
        style.map('Treeview',
                  background=[('selected', T["sel_bg"])],
                  foreground=[('selected', T["sel_fg"])])

    def rebuild_log_colors(self):
        """Alle Log-Widgets nach Theme-Wechsel neu einfärben."""
        T = self.theme
        for w in self._log_widgets:
            try:
                w.config(bg=T["log_bg"], fg=T["log_fg"], insertbackground=T["fg"])
            except Exception:
                pass
        self.root.configure(bg=T["bg"])

    # ── Log-Hilfsmethoden (für alle Tabs) ────────────────────────────────────
    def log_to(self, widget, text: str, clear: bool = False):
        try:
            widget.config(state='normal')
            if clear:
                widget.delete('1.0', tk.END)
            widget.insert(tk.END, text)
            widget.see(tk.END)
            widget.config(state='disabled')
        except Exception:
            pass

    def clear_log(self, widget):
        try:
            widget.config(state='normal')
            widget.delete('1.0', tk.END)
            widget.config(state='disabled')
        except Exception:
            pass

    def copy_log(self, widget):
        try:
            content = widget.get('1.0', tk.END).strip()
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("Kopiert", "✅ In Zwischenablage kopiert.")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))


    # ─── CB-1: Systemlaufwerk-Schutz ────────────────────────────────────────
    @staticmethod
    def is_system_device(dev: str) -> bool:
        """Gibt True zurück wenn dev einen kritischen Mount-Punkt enthält."""
        try:
            import subprocess as _sp
            r = _sp.run(["lsblk", "-no", "MOUNTPOINT", dev],
                        capture_output=True, text=True, timeout=5)
            critical = {"/", "/boot", "/boot/efi", "/home", "/usr",
                        "/var", "/etc", "/opt"}
            for mp in (m.strip() for m in r.stdout.splitlines() if m.strip()):
                if mp in critical or mp.startswith("/boot"):
                    return True
        except Exception:
            return True  # Im Zweifel: gesperrt
        return False

    @staticmethod
    def check_device_safe(dev: str) -> bool:
        """
        CB-1: Vollständige Sicherheitsprüfung vor destruktiven Operationen.
        Gibt True zurück wenn Operation sicher, False + Dialog bei Systemlaufwerk.
        """
        from tkinter import messagebox as _mb
        if not dev or not dev.startswith("/dev/"):
            _mb.showerror("Ungültiges Gerät", f"Kein gültiges Blockgerät: {dev!r}")
            return False
        if GuiBase.is_system_device(dev):
            _mb.showerror("⛔ Systemlaufwerk geschützt",
                f"{dev} enthält einen kritischen Mount-Punkt (/, /boot, ...)\n"
                f"und ist für destruktive Operationen gesperrt.\n\n"
                f"Wenn du sicher bist: Gerät abtrennen und neu anschließen.")
            return False
        return True

    def make_scrollable_tab(self, nb, title: str):
        """
        Erstellt einen scrollbaren Tab mit Canvas.
        Gibt (tab_frame, inner_frame) zurück – Widgets in inner_frame packen.
        Mausrad-Scrolling funktioniert auch über alle Kind-Widgets.
        """
        T = self.theme
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

        def _bind_rec(w):
            w.bind("<MouseWheel>", _scroll, add="+")
            w.bind("<Button-4>",   _scroll, add="+")
            w.bind("<Button-5>",   _scroll, add="+")
            for child in w.winfo_children():
                _bind_rec(child)

        _bind_rec(canvas)
        inner.bind("<Configure>", lambda e: _bind_rec(canvas), add="+")
        return outer, inner

    def make_log_widget(self, parent, height=10) -> scrolledtext.ScrolledText:
        T = self.theme
        w = scrolledtext.ScrolledText(parent, height=height, state='disabled',
                                       font=('Monospace', self.settings.get('font_size', 9)),
                                       bg=T["log_bg"], fg=T["log_fg"])
        self._log_widgets.append(w)
        return w

    def run_shell_async(self, command: str, log_widget,
                        run_btn=None, done_cb=None):
        """Führt einen Shell-Befehl asynchron aus und streamt Ausgabe ins log_widget."""
        import re as _re
        self.clear_log(log_widget)
        if run_btn:
            run_btn.config(state='disabled')

        def worker():
            try:
                env = os.environ.copy()
                env['TERM'] = 'xterm-256color'
                proc = subprocess.Popen(
                    command, shell=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=env, bufsize=1
                )
                for line in proc.stdout:
                    clean = _re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', line)
                    self.root.after(0, lambda l=clean: self.log_to(log_widget, l))
                proc.wait()
                self.root.after(0, lambda: self.log_to(
                    log_widget, f"\n─── Beendet (Exit: {proc.returncode}) ───\n"))
            except Exception as e:
                self.root.after(0, lambda: self.log_to(log_widget, f"\nFehler: {e}\n"))
            finally:
                if run_btn:
                    self.root.after(0, lambda: run_btn.config(state='normal'))
                if done_cb:
                    self.root.after(0, done_cb)

        threading.Thread(target=worker, daemon=True).start()

    def make_shell_tab(self, nb, title: str, description: str,
                       btn_label: str, command: str):
        """Universeller Shell-Tab mit Beschreibung, Log und Start-Button."""
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text=title)

        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        desc_f = ttk.LabelFrame(pane, text=" Beschreibung ", padding=8)
        desc_f.pack(fill='x', pady=(0, 8))
        tk.Label(desc_f, text=description, bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9), justify='left', wraplength=900).pack(anchor='w')

        log_f = ttk.LabelFrame(pane, text=" Ausgabe ", padding=8)
        log_f.pack(fill='both', expand=True)
        log_w = self.make_log_widget(log_f, height=20)
        log_w.pack(fill='both', expand=True)

        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(8, 0))

        run_btn = ttk.Button(btn_f, text=f"▶ {btn_label}", style='Accent.TButton')
        run_btn.pack(side='right', padx=4)
        ttk.Button(btn_f, text="📋 Kopieren",
                   command=lambda: self.copy_log(log_w)).pack(side='right', padx=4)
        ttk.Button(btn_f, text="🗑 Leeren",
                   command=lambda: self.clear_log(log_w)).pack(side='right', padx=4)

        run_btn.config(command=lambda: self.run_shell_async(command, log_w, run_btn))
        return tab
