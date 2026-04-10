#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: gui_system.py  –  Alle nicht-Laufwerks-Tabs:
  Dashboard, System (Pflege/Optimierer/Prozesse/Dienste/Boot/BIOS/Update-Shutdown),
  Netzwerk, Logs & Diagnose, Einstellungen, Über
"""

import os
import re
import pwd
import time
import shutil
import socket
import hashlib
import datetime
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from pathlib import Path
from typing import List, Optional
from shlex import quote as shlex_quote

from config import (ORIGINAL_USER, USER_HOME, VERSION,
                    THEMES, load_settings, save_settings)
from smart_engine import query_smart, is_failed
from wipe_engine import WipeEngine
from security import SecurityManager
from gui_base import GuiBase

# GRUB Control Center Tab (separate Datei für Wartungsfreundlichkeit)
try:
    from gui_grub import GrubTab
    _GRUB_AVAILABLE = True
except ImportError:
    _GRUB_AVAILABLE = False


class DashboardTab(GuiBase):
    def __init__(self, nb_main, app):
        super().__init__(app.root, app.settings, app.theme, app._log_widgets)
        self.app = app
        self._dash_cards: dict = {}
        self._build(nb_main)

    def _build(self, nb_main):
        T   = self.theme
        tab = ttk.Frame(nb_main)
        nb_main.add(tab, text="🏠 Dashboard")

        canvas = tk.Canvas(tab, bg=T["bg"], highlightthickness=0)
        sb     = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = tk.Frame(canvas, bg=T["bg"])
        win   = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        grid = tk.Frame(inner, bg=T["bg"])
        grid.pack(fill='both', expand=True, padx=16, pady=16)

        cards = [
            ("cpu",      "🖥️ CPU",     "-", T["accent"]),
            ("ram",      "🧠 RAM",      "-", T["success"]),
            ("swap",     "💾 Swap",     "-", T["warning"]),
            ("disk",     "💿 Root-FS",  "-", T["accent2"]),
            ("uptime",   "⏱ Uptime",   "-", T["fg_dim"]),
            ("hostname", "🌐 Hostname", socket.gethostname(), T["fg_dim"]),
        ]
        for i, (key, label, val, color) in enumerate(cards):
            card = self._make_card(grid, label, val, color)
            card.grid(row=i // 3, column=i % 3, padx=8, pady=8, sticky='nsew')
            self._dash_cards[key] = card.val_label
            grid.columnconfigure(i % 3, weight=1)

        sep = tk.Frame(inner, bg=T["border"], height=1)
        sep.pack(fill='x', padx=16, pady=(4, 8))

        drives_frame = ttk.LabelFrame(inner, text=" 💽 Laufwerke Übersicht ", padding=10)
        drives_frame.pack(fill='x', padx=16, pady=(0, 8))

        cols = ('Gerät', 'Modell', 'Typ', 'Größe', 'SMART', 'Temp')
        self.dash_tree = ttk.Treeview(drives_frame, columns=cols, show='headings', height=5)
        for c in cols:
            self.dash_tree.heading(c, text=c)
            self.dash_tree.column(c, width=130 if c == 'Modell' else 85)
        self.dash_tree.pack(fill='x')

        self.dash_smart_warn = tk.Label(inner, text="",
                                        font=('Arial', 10, 'bold'),
                                        bg=T["bg"], fg=T["danger"])
        self.dash_smart_warn.pack(anchor='w', padx=16, pady=(0, 8))

        # Partitionsbalken
        part_frame = ttk.LabelFrame(inner, text=" 📊 Partitionierung ", padding=10)
        part_frame.pack(fill='x', padx=16, pady=(0, 12))
        self.dash_part_frame = part_frame
        self.dash_part_canvas_list = []

    def _make_card(self, parent, title, value, color):
        T    = self.theme
        card = tk.Frame(parent, bg=T["bg2"], relief='flat', bd=0, padx=16, pady=14)
        tk.Frame(card, bg=color, width=4).pack(side='left', fill='y', padx=(0, 12))
        content = tk.Frame(card, bg=T["bg2"])
        content.pack(side='left', fill='both', expand=True)
        tk.Label(content, text=title, font=('Arial', 9),
                 bg=T["bg2"], fg=T["fg_dim"]).pack(anchor='w')
        val_lbl = tk.Label(content, text=value, font=('Arial', 18, 'bold'),
                           bg=T["bg2"], fg=T["fg"])
        val_lbl.pack(anchor='w')
        card.val_label = val_lbl
        return card

    def update(self, drives: list):
        """Systemdaten und Laufwerksliste aktualisieren."""
        self._update_system_cards()
        self._update_drive_table(drives)

    def _update_system_cards(self):
        # CPU
        try:
            self._dash_cards["cpu"].config(text=f"{self._cpu_pct()}%")
        except Exception:
            pass

        # RAM + Swap: free -m, robust gegen deutsche Lokalisierung
        try:
            r = subprocess.run(['free', '-m'], capture_output=True, text=True)
            ram_set = swap_set = False
            for line in r.stdout.splitlines():
                cols = line.split()
                if len(cols) < 3:
                    continue
                # erste Spalte kann "Mem:" oder "Speicher:" sein
                if cols[0].lower() in ('mem:', 'speicher:', 'memory:'):
                    try:
                        total = int(cols[1])
                        # 'used' ist Spalte 2, aber manche Versionen haben
                        # eine extra Spalte – /proc/meminfo ist zuverlaessiger
                        ram_set = True
                    except Exception:
                        pass
                if cols[0].lower() in ('swap:', 'auslagerungsspeicher:'):
                    try:
                        st, su = int(cols[1]), int(cols[2])
                        spct = int(su / st * 100) if st else 0
                        self._dash_cards["swap"].config(
                            text=f"{spct}%  ({su}/{st} MB)" if st else "—")
                        swap_set = True
                    except Exception:
                        pass

            # RAM direkt aus /proc/meminfo lesen – zuverlaessiger als free
            mem = {}
            with open('/proc/meminfo') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        mem[parts[0].rstrip(':')] = int(parts[1])
            total_kb = mem.get('MemTotal', 0)
            avail_kb = mem.get('MemAvailable', mem.get('MemFree', 0))
            used_kb  = total_kb - avail_kb
            total_mb = total_kb // 1024
            used_mb  = used_kb  // 1024
            pct = int(used_kb / total_kb * 100) if total_kb else 0
            self._dash_cards["ram"].config(text=f"{pct}%  ({used_mb}/{total_mb} MB)")

            if not swap_set:
                swap_total = mem.get('SwapTotal', 0)
                swap_free  = mem.get('SwapFree',  0)
                swap_used  = swap_total - swap_free
                if swap_total > 0:
                    spct = int(swap_used / swap_total * 100)
                    st_mb = swap_total // 1024
                    su_mb = swap_used  // 1024
                    self._dash_cards["swap"].config(
                        text=f"{spct}%  ({su_mb}/{st_mb} MB)")
                else:
                    self._dash_cards["swap"].config(text="—")
        except Exception as e:
            self._dash_cards["ram"].config(text=f"Fehler: {e}")

        # Disk
        try:
            du   = shutil.disk_usage("/")
            dpct = int(du.used / du.total * 100)
            dfree = du.free / 1024**3
            self._dash_cards["disk"].config(text=f"{dpct}%  ({dfree:.1f} GB frei)")
        except Exception:
            pass

        # Uptime
        try:
            with open('/proc/uptime') as f:
                secs = int(float(f.read().split()[0]))
            h, m = divmod(secs // 60, 60)
            d, h = divmod(h, 24)
            self._dash_cards["uptime"].config(
                text=f"{d}d {h}h {m}m" if d else f"{h}h {m}m")
        except Exception:
            pass

    def _cpu_pct(self) -> int:
        try:
            def read():
                with open('/proc/stat') as f:
                    line = f.readline()
                vals = list(map(int, line.split()[1:]))
                return vals[3], sum(vals)
            i1, t1 = read()
            time.sleep(0.15)
            i2, t2 = read()
            dt = t2 - t1
            return int((1 - (i2 - i1) / dt) * 100) if dt else 0
        except Exception:
            return 0

    def _update_drive_table(self, drives: list):
        for row in self.dash_tree.get_children():
            self.dash_tree.delete(row)
        warnings = []
        for d in drives:
            status, temp, _ = query_smart(d.device, timeout=4)
            if is_failed(status):
                warnings.append(f"⚠️ {d.device}: SMART FAILED!")
            self.dash_tree.insert('', 'end', values=(
                d.device, d.model, d.get_type_label(),
                d.get_size_human(), status, temp))
        self.dash_smart_warn.config(text="\n".join(warnings))
        # Partitionsbalken nur neu bauen wenn sich die Laufwerksliste geändert hat
        new_devs = [d.device for d in drives]
        if new_devs != getattr(self, '_last_part_devs', None):
            self._last_part_devs = new_devs
            self._update_partition_bars(drives)

    # Farben für Partitionsbalken (Dateisystem → Farbe)
    _FS_COLORS = {
        'ext4':   '#3498db',
        'ext3':   '#2980b9',
        'ext2':   '#1a6fa0',
        'btrfs':  '#27ae60',
        'xfs':    '#16a085',
        'ntfs':   '#8e44ad',
        'vfat':   '#e67e22',
        'fat32':  '#e67e22',
        'exfat':  '#f39c12',
        'swap':   '#e74c3c',
        '[SWAP]': '#e74c3c',
        'iso9660':'#95a5a6',
    }
    _FREE_COLOR  = '#2ecc71'
    _UNKN_COLOR  = '#7f8c8d'

    def _update_partition_bars(self, drives: list):
        """Baut die Partitionsbalken als farbige Frame-Segmente auf."""
        # Alte Widgets entfernen
        for w in self.dash_part_canvas_list:
            try:
                w.destroy()
            except Exception:
                pass
        self.dash_part_canvas_list.clear()

        T = self.theme

        for d in drives:
            parts = self._get_partitions(d.device)
            if not parts:
                continue
            disk_size = self._parse_size(d.size)
            if disk_size <= 0:
                continue

            # Äussere Zeile: Geräte-Label + Balken
            row = tk.Frame(self.dash_part_frame, bg=T["bg"])
            row.pack(fill='x', pady=3)
            self.dash_part_canvas_list.append(row)

            # Geräte-Label links
            tk.Label(row, text=d.device,
                     font=('Monospace', 8), bg=T["bg"], fg=T["fg_dim"],
                     width=10, anchor='w').pack(side='left', padx=(0, 6))

            # Balken-Container – fill='x' expand=True sorgt für volle Breite
            bar_outer = tk.Frame(row, bg=T["border"], height=24,
                                 relief='flat', bd=1)
            bar_outer.pack(side='left', fill='x', expand=True)
            bar_outer.pack_propagate(False)
            self.dash_part_canvas_list.append(bar_outer)

            # Innerer Frame für die Segmente (place-basiert)
            bar_inner = tk.Frame(bar_outer, bg=T["bg2"])
            bar_inner.place(relx=0, rely=0, relwidth=1, relheight=1)

            # Segmente mit place() positionieren
            total_used = sum(p['size'] for p in parts if p['size'] > 0)
            x_rel = 0.0
            tooltip_parts = []

            for p in parts:
                psize = p['size']
                if psize <= 0:
                    continue
                w_rel = psize / disk_size
                fs    = p['fstype'] or ''
                mnt   = p['mountpoint'] or ''
                color = self._FS_COLORS.get(fs, self._UNKN_COLOR)
                size_gb = psize / 1024**3
                # Beschriftung: FS-Typ + Größe (immer anzeigen)
                display = f"{fs or '?'}  {size_gb:.1f}G"

                seg = tk.Frame(bar_inner, bg=color, cursor='hand2')
                seg.place(relx=x_rel, rely=0, relwidth=w_rel, relheight=1)

                # Text im Segment – immer sichtbar
                lbl = tk.Label(seg, text=display, bg=color, fg='#ffffff',
                               font=('Arial', 8, 'bold'), anchor='center')
                lbl.place(relx=0, rely=0, relwidth=1, relheight=1)

                info = f"{p['name']} {fs or '?'} {size_gb:.1f}G" +                        (f" [{mnt}]" if mnt else "")
                tooltip_parts.append(info)

                # Klick zeigt Details
                for w in (seg, lbl):
                    w.bind("<Button-1>",
                           lambda e, dev=d.device, inf=chr(10).join(tooltip_parts):
                           messagebox.showinfo(f"Partitionen: {dev}", inf))
                x_rel += w_rel

            # Freier Platz
            free_rel = 1.0 - x_rel
            if free_rel > 0.005:
                free_gb = (disk_size - total_used) / 1024**3
                seg = tk.Frame(bar_inner, bg=self._FREE_COLOR)
                seg.place(relx=x_rel, rely=0, relwidth=free_rel, relheight=1)
                lbl = tk.Label(seg, text=f"frei {free_gb:.1f}G",
                               bg=self._FREE_COLOR, fg='#ffffff',
                               font=('Arial', 7), anchor='center')
                lbl.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _parse_size(self, val) -> int:
        """Parst lsblk-Größe robust – auch mit Komma oder Einheiten."""
        if val is None:
            return 0
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
        try:
            # Lokalisierung: "238,5G" → float → Bytes
            s = str(val).replace(',', '.').strip()
            # Einheiten entfernen falls vorhanden
            for unit, factor in [('T', 1024**4), ('G', 1024**3),
                                  ('M', 1024**2), ('K', 1024)]:
                if s.upper().endswith(unit):
                    return int(float(s[:-1]) * factor)
            return int(float(s))
        except Exception:
            return 0

    def _get_partitions(self, device: str) -> list:
        """Gibt Partitionsliste zurück: [{name, size, fstype, mountpoint, label}]"""
        try:
            # LANG=C damit lsblk keine lokalisierten Zahlen ausgibt
            env = dict(__import__('os').environ, LANG='C', LC_ALL='C')
            r = subprocess.run(
                ['lsblk', '-J', '-b', '-o',
                 'NAME,SIZE,FSTYPE,MOUNTPOINT,LABEL,TYPE', device],
                capture_output=True, text=True, timeout=5, env=env)
            if r.returncode != 0:
                return []
            import json as _json
            data = _json.loads(r.stdout)
            devs = data.get('blockdevices', [])
            if not devs:
                return []
            disk = devs[0]
            children = disk.get('children', [])
            if not children:
                return [{
                    'name':       disk.get('name', ''),
                    'size':       self._parse_size(disk.get('size')),
                    'fstype':     disk.get('fstype') or '',
                    'mountpoint': disk.get('mountpoint') or '',
                    'label':      disk.get('label') or '',
                }]
            result = []
            for c in children:
                if c.get('type') in ('part', 'lvm', 'md', None):
                    result.append({
                        'name':       c.get('name', ''),
                        'size':       self._parse_size(c.get('size')),
                        'fstype':     c.get('fstype') or '',
                        'mountpoint': c.get('mountpoint') or '',
                        'label':      c.get('label') or '',
                    })
            return result
        except Exception as e:
            return []

class SystemTab(GuiBase):
    def __init__(self, nb_main, app):
        super().__init__(app.root, app.settings, app.theme, app._log_widgets)
        self.app = app
        self.sec = app.sec
        self._build(nb_main)

    def _build(self, nb_main):
        tab = ttk.Frame(nb_main)
        nb_main.add(tab, text="🖥️ System")
        nb = ttk.Notebook(tab)
        nb.pack(fill='both', expand=True, padx=4, pady=4)

        self._build_cleanup(nb)
        self._build_optimizer(nb)
        self._build_boot(nb)
        self._build_bios(nb)
        self._build_update_shutdown(nb)
        self._build_einmal_starter(nb)
        self._build_eggs_iso(nb)
        self._build_grub_tab(nb)

    # ── Systempflege ──────────────────────────────────────────────────────────
    def _build_cleanup(self, nb):
        self.make_shell_tab(nb,
            "🧹 Systempflege",
            "Aktualisiert Pakete, räumt auf (autoremove, clean), bereinigt Flatpak,\n"
            "Journal (7 Tage), Thumbnail-Cache.  ⚠️ Benötigt Root.",
            "Systempflege starten",
            ("bash -c 'echo \"=== Pakete ===\"; "
             "(command -v nala >/dev/null 2>&1 && nala update && nala upgrade -y "
             "&& nala autoremove -y && nala clean) "
             "|| (apt update && apt upgrade -y && apt autoremove -y && apt clean); "
             "echo; echo \"=== Flatpak ===\"; "
             "command -v flatpak >/dev/null 2>&1 && flatpak uninstall --unused -y "
             "|| echo \"Flatpak n.v.\"; "
             "echo; echo \"=== Journal ===\"; journalctl --vacuum-time=7d; "
             "echo; echo \"=== Thumbnails ===\"; "
             f"rm -rf -- {shlex_quote(str(USER_HOME / '.cache' / 'thumbnails'))}/*; "
             "echo; echo \"=== Speicher ===\"; df -h /; echo; echo \"✅ Fertig.\"'")
        )

    # ── Optimierer ───────────────────────────────────────────────────────────
    def _build_optimizer(self, nb):
        import os as _os
        T    = self.theme
        INSTALL_DIR = _os.path.dirname(_os.path.abspath(__file__))
        script = _os.path.join(INSTALL_DIR, "optimizer.sh")
        # Fallback: Script direkt nach /tmp schreiben wenn nicht vorhanden
        if not _os.path.isfile(script):
            script = "/tmp/peessi_optimizer.sh"
        cmd = f"bash '{script}'"
        self.make_shell_tab(nb,
            "⚡ Optimierer",
            "Kernel-Tuning (BBR falls verfügbar, Swappiness), dynamische Swap-Datei,\n"
            "Firefox Low-Memory-Policies (nur wenn Firefox installiert).\n"
            "Funktioniert auf allen Debian/Ubuntu/Mint-Systemen.  ⚠️ Benötigt Root. Neustart empfohlen.",
            "Optimieren",
            cmd
        )
    # ── Prozesse ─────────────────────────────────────────────────────────────
    def _build_boot(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🥾 Boot-Check")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        self.boot_status = tk.Label(pane, text="Status wird geprüft...",
                                    bg=T["bg"], fg=T["fg"], font=('Arial', 12, 'bold'))
        self.boot_status.pack(anchor='w', pady=(0, 8))

        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(0, 8))
        ttk.Button(btn_f, text="✅ Aktivieren", style='Accent.TButton',
                   command=lambda: self._boot_set("1")).pack(side='left', padx=4)
        ttk.Button(btn_f, text="🚫 Deaktivieren", style='Danger.TButton',
                   command=lambda: self._boot_set("0")).pack(side='left', padx=4)
        ttk.Button(btn_f, text="🔄 Status",
                   command=self._boot_refresh).pack(side='left', padx=4)

        log_f = ttk.LabelFrame(pane, text=" Ausgabe ", padding=8)
        log_f.pack(fill='both', expand=True)
        self.boot_log = self.make_log_widget(log_f, height=18)
        self.boot_log.pack(fill='both', expand=True)
        self._boot_refresh()

    def _boot_refresh(self):
        """Liest den fsck-Pass-Wert fuer / aus /etc/fstab."""
        try:
            status = self._boot_get_pass()
            if status == 1:
                self.boot_status.config(
                    text="🟢 Boot-Check (fsck) ist AKTIVIERT  (pass=1)",
                    fg=self.theme["success"])
            elif status == 0:
                self.boot_status.config(
                    text="🔴 Boot-Check (fsck) ist DEAKTIVIERT  (pass=0)",
                    fg=self.theme["danger"])
            else:
                self.boot_status.config(
                    text="⚠️  Root-Eintrag in /etc/fstab nicht gefunden",
                    fg=self.theme["warning"])
        except Exception as e:
            self.boot_status.config(text=f"Fehler: {e}", fg=self.theme["warning"])

    def _boot_get_pass(self):
        """Gibt den fsck-Pass-Wert (letzte Spalte) des /-Eintrags zurueck."""
        with open('/etc/fstab') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 6 and parts[1] == '/':
                    return int(parts[5])
        return None

    def _boot_set(self, value: str):
        """Setzt den fsck-Pass-Wert fuer den /-Eintrag in /etc/fstab."""
        action = "aktivieren" if value == "1" else "deaktivieren"
        if not messagebox.askyesno("Boot-Check",
            f"fsck Boot-Check wirklich {action}?\n\n"
            "(Aendert den Pass-Wert des /-Eintrags in /etc/fstab)"):
            return
        backup = SecurityManager.backup_fstab()
        if backup:
            self.log_to(self.boot_log, f"📋 fstab-Backup: {backup}\n")
        try:
            with open('/etc/fstab') as f:
                lines = f.readlines()
            changed = False
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    parts = stripped.split()
                    if len(parts) >= 6 and parts[1] == '/':
                        parts[5] = value
                        new_lines.append(' '.join(parts) + chr(10))
                        changed = True
                        continue
                new_lines.append(line)
            if changed:
                with open('/etc/fstab', 'w') as f:
                    f.writelines(new_lines)
                self.log_to(self.boot_log,
                    f"✓ Boot-Check {'aktiviert' if value == '1' else 'deaktiviert'}.\n")
                self._boot_refresh()
            else:
                self.log_to(self.boot_log,
                    "⚠️  Kein /-Eintrag in /etc/fstab gefunden.\n")
        except Exception as e:
            self.log_to(self.boot_log, f"❌ Fehler: {e}\n")

    # ── BIOS/EFI ─────────────────────────────────────────────────────────────
    def _build_bios(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="⚙️ BIOS/EFI")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        btn_grid = tk.Frame(pane, bg=T["bg"])
        btn_grid.pack(fill='x', pady=(0, 8))
        actions = [
            ("🖫 USB-Boot forcieren",     self._bios_usb_boot),
            ("🔧 Ins BIOS neu starten",   self._bios_reboot_bios),
            ("🧹 Boot-Menü aufräumen",     self._bios_cleanup),
            ("🗑 Eintrag löschen",         self._bios_delete_single),
            ("⏱ Timeout einstellen",       self._bios_timeout),
            ("↕ Boot-Reihenfolge",         self._bios_bootorder),
            ("✔ Ein-/Ausschalten",         self._bios_toggle_entry),
            ("💾 EFI-Backup",              self._bios_backup),
            ("♻ Backup wiederherstellen",  self._bios_restore),
            ("🔄 Aktualisieren",           self._bios_refresh_info),
        ]
        for i, (label, cmd) in enumerate(actions):
            ttk.Button(btn_grid, text=label, command=cmd).grid(
                row=i // 5, column=i % 5, padx=4, pady=3, sticky='ew')
            btn_grid.columnconfigure(i % 5, weight=1)

        log_f = ttk.LabelFrame(pane, text=" efibootmgr Ausgabe ", padding=8)
        log_f.pack(fill='both', expand=True)
        self.bios_log = self.make_log_widget(log_f, height=22)
        self.bios_log.pack(fill='both', expand=True)
        self._bios_refresh_info()

    def _bios_run(self, cmd: list):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return r.stdout.strip(), r.returncode
        except Exception as e:
            return str(e), 1

    def _bios_log_msg(self, msg: str):
        self.log_to(self.bios_log, msg + "\n")

    def _bios_refresh_info(self):
        self.clear_log(self.bios_log)
        def worker():
            out, rc = self._bios_run(['efibootmgr', '-v'])
            self.root.after(0, lambda: self._bios_log_msg(
                out if rc == 0 else f"Fehler: {out}"))
        threading.Thread(target=worker, daemon=True).start()

    def _bios_usb_boot(self):
        def worker():
            out, _ = self._bios_run(['efibootmgr'])
            ids = re.findall(
                r'Boot([0-9A-Fa-f]{4})[* ].*?(?:USB|removable|Kingston|SanDisk)',
                out, re.IGNORECASE)
            if not ids:
                self.root.after(0, lambda: messagebox.showwarning(
                    "Nicht gefunden", "Kein USB-Boot-Eintrag."))
                return
            sel = simpledialog.askstring("USB-Boot",
                f"Boot-IDs:\n{chr(10).join(ids)}\n\nID eingeben:", parent=self.root)
            if not sel or not re.match(r'^[0-9A-Fa-f]{4}$', sel.strip()):
                return
            sel = sel.strip().upper()
            if messagebox.askyesno("Bestätigung",
                f"Boot{sel} für nächsten Start + Neustart?"):
                _, rc = self._bios_run(['efibootmgr', '-n', sel])
                if rc == 0:
                    self._bios_log_msg(f"✅ Boot{sel} gesetzt. Reboot...")
                    subprocess.Popen(['reboot'])
        threading.Thread(target=worker, daemon=True).start()

    def _bios_reboot_bios(self):
        if messagebox.askyesno("BIOS/UEFI", "Jetzt ins BIOS/UEFI neu starten?"):
            subprocess.Popen(['systemctl', 'reboot', '--firmware-setup'])

    def _bios_cleanup(self):
        def worker():
            out, _ = self._bios_run(['efibootmgr'])
            ids = re.findall(r'Boot([0-9A-Fa-f]{4})[* ].*?(?:debian|lmde|grub)',
                             out, re.IGNORECASE)
            if not ids:
                self.root.after(0, lambda: self._bios_log_msg(
                    "Keine veralteten Einträge gefunden."))
                return
            self.root.after(0, lambda: self._bios_log_msg(f"Gefunden: {ids}"))
            if messagebox.askyesno("Aufräumen", f"Einträge löschen: {ids}?"):
                for uid in ids:
                    _, rc = self._bios_run(['efibootmgr', '-b', uid, '-B'])
                    self.root.after(0, lambda u=uid, r=rc:
                        self._bios_log_msg(f"{'✅' if r==0 else '❌'} Boot{u}"))
                self.root.after(0, self._bios_refresh_info)
        threading.Thread(target=worker, daemon=True).start()

    def _bios_delete_single(self):
        def worker():
            out, _ = self._bios_run(['efibootmgr'])
            self.root.after(0, lambda: self._bios_log_msg(out))
            del_id = simpledialog.askstring("Eintrag löschen",
                "Boot-ID (4 Hex-Zeichen):", parent=self.root)
            if not del_id or not re.match(r'^[0-9A-Fa-f]{4}$', del_id.strip()):
                return
            del_id = del_id.strip().upper()
            if messagebox.askyesno("Löschen", f"Boot{del_id} wirklich löschen?"):
                _, rc = self._bios_run(['efibootmgr', '-b', del_id, '-B'])
                self.root.after(0, lambda: (
                    self._bios_log_msg(f"{'✅' if rc==0 else '❌'} Boot{del_id}"),
                    self._bios_refresh_info()))
        threading.Thread(target=worker, daemon=True).start()

    def _bios_timeout(self):
        def worker():
            t = simpledialog.askstring("Timeout",
                "Neue Wartezeit in Sekunden (Empfehlung: 3–5):", parent=self.root)
            if t and t.strip().isdigit():
                _, rc = self._bios_run(['efibootmgr', '-t', t.strip()])
                self.root.after(0, lambda: (
                    self._bios_log_msg(f"{'✅' if rc==0 else '❌'} Timeout: {t}s"),
                    self._bios_refresh_info()))
        threading.Thread(target=worker, daemon=True).start()

    def _bios_bootorder(self):
        def worker():
            order = simpledialog.askstring("Boot-Reihenfolge",
                "Reihenfolge (z.B. 0000,0002,0005):", parent=self.root)
            if order and re.match(r'^[0-9A-Fa-f]{4}(,[0-9A-Fa-f]{4})*$', order.strip()):
                _, rc = self._bios_run(['efibootmgr', '-o', order.strip()])
                self.root.after(0, lambda: (
                    self._bios_log_msg(f"{'✅' if rc==0 else '❌'} Reihenfolge: {order}"),
                    self._bios_refresh_info()))
        threading.Thread(target=worker, daemon=True).start()

    def _bios_toggle_entry(self):
        def worker():
            out, _ = self._bios_run(['efibootmgr'])
            tid = simpledialog.askstring("Ein-/Ausschalten",
                "Boot-ID eingeben:", parent=self.root)
            if not tid or not re.match(r'^[0-9A-Fa-f]{4}$', tid.strip()):
                return
            tid    = tid.strip().upper()
            active = any(f'Boot{tid}*' in l for l in out.splitlines())
            flag   = '-A' if active else '-a'
            action = "deaktivieren" if active else "aktivieren"
            if messagebox.askyesno(action.title(), f"Boot{tid} {action}?"):
                _, rc = self._bios_run(['efibootmgr', '-b', tid, flag])
                self.root.after(0, lambda: (
                    self._bios_log_msg(f"{'✅' if rc==0 else '❌'} Boot{tid} {action}t"),
                    self._bios_refresh_info()))
        threading.Thread(target=worker, daemon=True).start()

    def _bios_backup(self):
        def worker():
            backup_dir = USER_HOME / "efi_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = backup_dir / f"efi_backup_{ts}.txt"
            out, rc = self._bios_run(['efibootmgr', '-v'])
            if rc == 0:
                path.write_text(out)
                self.root.after(0, lambda: self._bios_log_msg(f"✅ Backup: {path}"))
            else:
                self.root.after(0, lambda: self._bios_log_msg(f"❌ Fehler: {out}"))
        threading.Thread(target=worker, daemon=True).start()

    def _bios_restore(self):
        def worker():
            import glob
            backups = sorted(glob.glob(str(USER_HOME / "efi_backups" / "efi_backup_*.txt")))
            if not backups:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Keine Backups", "Keine EFI-Backups gefunden."))
                return
            choices = "\n".join(f"{i+1}) {Path(b).name}" for i, b in enumerate(backups))
            sel = simpledialog.askstring("Backup wählen",
                f"{choices}\n\nNummer:", parent=self.root)
            if not sel or not sel.strip().isdigit():
                return
            idx = int(sel.strip()) - 1
            if not (0 <= idx < len(backups)):
                return
            content = Path(backups[idx]).read_text()
            for line in content.splitlines():
                if line.startswith("BootOrder:"):
                    order = line.split(":", 1)[1].strip()
                    if messagebox.askyesno("Wiederherstellen",
                        f"BootOrder '{order}' wiederherstellen?"):
                        _, rc = self._bios_run(['efibootmgr', '-o', order])
                        self.root.after(0, lambda r=rc: (
                            self._bios_log_msg(f"{'✅' if r==0 else '❌'} BootOrder: {order}"),
                            self._bios_refresh_info()))
                    return
            self.root.after(0, lambda: messagebox.showerror(
                "Fehler", "Keine BootOrder im Backup gefunden."))
        threading.Thread(target=worker, daemon=True).start()

    # ── Update & Shutdown ────────────────────────────────────────────────────
    def _build_update_shutdown(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🔄 Update & Shutdown")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        desc = ttk.LabelFrame(pane, text=" Beschreibung ", padding=8)
        desc.pack(fill='x', pady=(0, 8))
        tk.Label(desc, text=(
            "Installiert update-shutdown.sh in ~/bin/ und richtet passwortlose sudo-Regel ein.\n"
            "Das Skript führt alle System-Updates durch und fährt danach automatisch herunter.\n"
            "Ideal als Tastenkürzel (Cinnamon: Einstellungen → Tastatur → Tastenkürzel)."
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')

        self.upshut_status = tk.Label(pane, text="Status wird geprüft...",
                                      bg=T["bg"], fg=T["fg"], font=('Arial', 12, 'bold'))
        self.upshut_status.pack(anchor='w', pady=(0, 8))

        log_f = ttk.LabelFrame(pane, text=" Ausgabe ", padding=8)
        log_f.pack(fill='both', expand=True)
        self.upshut_log = self.make_log_widget(log_f, height=16)
        self.upshut_log.pack(fill='both', expand=True)

        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(8, 0))
        ttk.Button(btn_f, text="⚙️ Installieren", style='Accent.TButton',
                   command=self._upshut_install).pack(side='left', padx=4)
        ttk.Button(btn_f, text="▶ Jetzt ausführen (→ Shutdown!)", style='Danger.TButton',
                   command=self._upshut_run).pack(side='left', padx=4)
        ttk.Button(btn_f, text="🔄 Status",
                   command=self._upshut_status_check).pack(side='left', padx=4)
        ttk.Button(btn_f, text="🗑 Deinstallieren",
                   command=self._upshut_uninstall).pack(side='right', padx=4)
        self._upshut_status_check()

    def _upshut_script(self) -> str:
        return str(USER_HOME / "bin" / "update-shutdown.sh")

    def _upshut_status_check(self):
        script = self._upshut_script()
        if os.path.isfile(script):
            self.upshut_status.config(
                text=f"✅ update-shutdown.sh ist installiert  ({script})",
                fg=self.theme["success"])
        else:
            self.upshut_status.config(
                text="❌ update-shutdown.sh ist NICHT installiert",
                fg=self.theme["danger"])

    def _upshut_install(self):
        if not messagebox.askyesno("Installation",
            "update-shutdown.sh wird nach ~/bin/ installiert\n"
            "und eine passwortlose sudo-Regel wird eingerichtet.\nFortfahren?"):
            return
        bin_dir = str(USER_HOME / "bin")
        script  = self._upshut_script()
        os.makedirs(bin_dir, exist_ok=True)
        content = r"""#!/bin/bash
# update-shutdown.sh – Automatische Updates + Herunterfahren
set -euo pipefail
GREEN="\033[1;32m"; YELLOW="\033[1;33m"; RED="\033[1;31m"; RESET="\033[0m"
LOG="/var/log/update-shutdown.log"
CONF="$HOME/.config/update-shutdown.conf"
ERR=0
AUTOCLEAN=true; DIST_UPGRADE=true; FLATPAK_UPDATES=true
CLEAN_CACHE=false; NOTIFICATIONS=true
[ -f "$CONF" ] && source "$CONF"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
run() { local name="$1"; shift; echo -e "\n${YELLOW}▶ $name${RESET}"; \
if "$@" >> "$LOG" 2>&1; then echo -e "${GREEN}✓ OK${RESET}"; \
else echo -e "${RED}✗ Fehler${RESET}"; ((ERR++)); fi; }
[[ $EUID -ne 0 ]] && exec sudo "$0" "$@"
log "=== UPDATE-SHUTDOWN START ==="
run "APT update"  apt update -y
run "APT upgrade" apt upgrade -y --with-new-pkgs
$DIST_UPGRADE && run "dist-upgrade" apt dist-upgrade -y
$FLATPAK_UPDATES && command -v flatpak >/dev/null && run "Flatpak" flatpak update --system -y
run "Autoremove"  apt autoremove -y --purge
$AUTOCLEAN && run "Autoclean" apt autoclean -y
run "Journal" journalctl --vacuum-time=7d
log "=== FERTIG (Fehler: $ERR) ==="
df -h /
echo -e "\n${YELLOW}Shutdown in 5s...${RESET}"
for i in {5..1}; do printf "\r%d..." "$i"; sleep 1; done
sync; sleep 1; systemctl poweroff
"""
        try:
            with open(script, 'w') as f:
                f.write(content)
            os.chmod(script, 0o755)
            sudoers_line = f"{ORIGINAL_USER} ALL=(ALL) NOPASSWD: {script}"
            sudoers_file = "/etc/sudoers.d/update-shutdown"
            r = subprocess.run(
                ['bash', '-c',
                 f"echo '{sudoers_line}' > {sudoers_file} && chmod 440 {sudoers_file}"],
                capture_output=True, text=True)
            self.log_to(self.upshut_log, f"✅ Skript: {script}\n")
            if r.returncode == 0:
                self.log_to(self.upshut_log, f"✅ Sudoers: {sudoers_file}\n")
            else:
                self.log_to(self.upshut_log, f"⚠️ Sudoers-Fehler: {r.stderr}\n")
            self._upshut_status_check()
        except Exception as e:
            self.log_to(self.upshut_log, f"❌ Fehler: {e}\n")

    def _upshut_run(self):
        script = self._upshut_script()
        if not os.path.isfile(script):
            messagebox.showerror("Nicht installiert", "Bitte zuerst installieren.")
            return
        if not messagebox.askyesno("Warnung",
            "Das System wird nach Updates HERUNTERGEFAHREN!\n\nWirklich jetzt?",
            icon='warning'):
            return
        def worker():
            proc = subprocess.Popen([script],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                self.root.after(0, lambda l=line: self.log_to(self.upshut_log, l))
            proc.wait()
        threading.Thread(target=worker, daemon=True).start()

    def _upshut_uninstall(self):
        script  = self._upshut_script()
        sudoers = "/etc/sudoers.d/update-shutdown"
        if not messagebox.askyesno("Deinstallieren",
            f"Löscht:\n  {script}\n  {sudoers}\n\nFortfahren?"):
            return
        for f in [script, sudoers]:
            if os.path.isfile(f):
                try:
                    subprocess.run(['rm', '-f', f], check=True, capture_output=True)
                    self.log_to(self.upshut_log, f"✓ Gelöscht: {f}\n")
                except Exception as e:
                    self.log_to(self.upshut_log, f"✗ {e}\n")
        self._upshut_status_check()


# ══════════════════════════════════════════════════════════════════════════════
#  NETZWERK-TAB
# ══════════════════════════════════════════════════════════════════════════════

    # ── Einmal-Starter ───────────────────────────────────────────────────────
    def _build_einmal_starter(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="\U0001f680 Einmal-Starter")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        desc = ttk.LabelFrame(pane, text=" Beschreibung ", padding=10)
        desc.pack(fill='x', pady=(0, 10))
        tk.Label(desc, text=(
            "Richtet ein Script oder Programm als Einmal-Autostart ein.\n"
            "Das Script wird beim naechsten Login automatisch gestartet\n"
            "und loescht sich danach selbst aus dem Autostart."
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 10), justify='left').pack(anchor='w')

        # Script-Auswahl
        file_f = ttk.LabelFrame(pane, text=" Script / Programm ", padding=8)
        file_f.pack(fill='x', pady=(0, 8))
        file_row = tk.Frame(file_f, bg=T["bg"])
        file_row.pack(fill='x')
        self.einmal_path_var = tk.StringVar()
        ttk.Entry(file_row, textvariable=self.einmal_path_var,
                  font=('Arial', 10), width=55
                  ).pack(side='left', padx=(0, 6), expand=True, fill='x')
        ttk.Button(file_row, text="\U0001f4c2 Auswaehlen",
                   command=self._einmal_browse).pack(side='left')

        # Optionen
        opt_f = ttk.LabelFrame(pane, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', pady=(0, 8))

        self.einmal_root_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_f,
            text="Mit Root-Rechten starten (pkexec)",
            variable=self.einmal_root_var).pack(anchor='w', pady=2)

        self.einmal_terminal_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_f,
            text="In Terminal-Fenster ausfuehren (sichtbare Ausgabe)",
            variable=self.einmal_terminal_var).pack(anchor='w', pady=2)

        delay_row = tk.Frame(opt_f, bg=T["bg"])
        delay_row.pack(anchor='w', pady=2)
        tk.Label(delay_row, text="Verzoegerung beim Start:",
                 bg=T["bg"], fg=T["fg"], font=('Arial', 10)).pack(side='left', padx=(0, 8))
        self.einmal_delay_var = tk.StringVar(value="0")
        ttk.Spinbox(delay_row, from_=0, to=60,
                    textvariable=self.einmal_delay_var,
                    width=5, font=('Arial', 10)).pack(side='left')
        tk.Label(delay_row, text="Sekunden",
                 bg=T["bg"], fg=T["fg"], font=('Arial', 10)).pack(side='left', padx=(4, 0))

        # Aktive Einmal-Starter anzeigen
        list_f = ttk.LabelFrame(pane, text=" Eingerichtete Einmal-Starter ", padding=8)
        list_f.pack(fill='both', expand=True, pady=(0, 8))

        cols = ('Name', 'Script/Programm', 'Root', 'Status')
        self.einmal_tree = ttk.Treeview(list_f, columns=cols,
                                         show='headings', height=6)
        cw = {'Name': 180, 'Script/Programm': 380, 'Root': 55, 'Status': 80}
        for c in cols:
            self.einmal_tree.heading(c, text=c)
            self.einmal_tree.column(c, width=cw.get(c, 120))
        esb = ttk.Scrollbar(list_f, orient='vertical',
                             command=self.einmal_tree.yview)
        self.einmal_tree.configure(yscrollcommand=esb.set)
        self.einmal_tree.pack(side='left', fill='both', expand=True)
        esb.pack(side='right', fill='y')

        # Buttons
        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(4, 0))
        ttk.Button(btn_f, text="\U00002795 Einrichten",
                   style='Accent.TButton',
                   command=self._einmal_einrichten).pack(side='left', padx=4)
        ttk.Button(btn_f, text="\U0001f5d1 Ausgewaehlten loeschen",
                   command=self._einmal_loeschen).pack(side='left', padx=4)
        ttk.Button(btn_f, text="\U0001f504 Aktualisieren",
                   command=self._einmal_refresh).pack(side='left', padx=4)

        # Log
        log_f = ttk.LabelFrame(pane, text=" Ausgabe ", padding=6)
        log_f.pack(fill='x', pady=(8, 0))
        self.einmal_log = self.make_log_widget(log_f, height=4)
        self.einmal_log.pack(fill='both', expand=True)

        self._einmal_refresh()

    def _einmal_browse(self):
        from tkinter import filedialog
        from config import USER_HOME
        path = filedialog.askopenfilename(
            title="Script oder Programm auswaehlen",
            initialdir=str(USER_HOME),
            filetypes=[
                ("Ausfuehrbare Dateien", "*.sh *.py *.bash"),
                ("Shell-Scripts",  "*.sh"),
                ("Python-Scripts", "*.py"),
                ("Alle Dateien",   "*"),
            ])
        if path:
            self.einmal_path_var.set(path)

    def _einmal_einrichten(self):
        programm = self.einmal_path_var.get().strip()
        if not programm:
            messagebox.showerror("Fehler", "Bitte zuerst ein Script auswaehlen.")
            return
        if not os.path.isfile(programm):
            messagebox.showerror("Fehler",
                f"Datei nicht gefunden:\n{programm}")
            return

        from config import USER_HOME, ORIGINAL_USER
        basename    = os.path.basename(programm)
        autostart_d = os.path.join(os.path.expanduser(f"~{ORIGINAL_USER}"),
                                   ".config", "autostart")
        os.makedirs(autostart_d, exist_ok=True)
        desktop_file = os.path.join(autostart_d, f"run-once-{basename}.desktop")

        use_root     = self.einmal_root_var.get()
        use_terminal = self.einmal_terminal_var.get()
        delay        = self.einmal_delay_var.get().strip()
        try:
            delay_sec = int(delay)
        except ValueError:
            delay_sec = 0

        # Exec-Befehl zusammenbauen
        if programm.endswith('.py'):
            runner = f"python3 \"{programm}\""
        else:
            runner = f"bash \"{programm}\""

        if use_root:
            runner = f"pkexec {runner}"

        if delay_sec > 0:
            runner = f"sleep {delay_sec} && {runner}"

        if use_terminal:
            exec_cmd = (f"sh -c '{runner}; rm -f \"{desktop_file}\"'")
            terminal = "x-terminal-emulator"
            exec_line = f"{terminal} -e {exec_cmd}"
        else:
            exec_line = f"sh -c '{runner}; rm -f \"{desktop_file}\"'"

        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name=Run Once: {basename}\n"
            f"Exec={exec_line}\n"
            "Hidden=false\n"
            "NoDisplay=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )

        try:
            with open(desktop_file, 'w') as f:
                f.write(content)
            # Eigentuemer auf Original-User setzen
            import pwd as _pwd
            uid = _pwd.getpwnam(ORIGINAL_USER).pw_uid
            gid = _pwd.getpwnam(ORIGINAL_USER).pw_gid
            os.chown(desktop_file, uid, gid)
            os.chmod(desktop_file, 0o644)

            self.log_to(self.einmal_log,
                f"Eingerichtet: {desktop_file}\n"
                f"  Script : {programm}\n"
                f"  Root   : {'Ja' if use_root else 'Nein'}\n"
                f"  Terminal: {'Ja' if use_terminal else 'Nein'}\n"
                f"  Delay  : {delay_sec}s\n")
            self.sec.log_action("EINMAL_STARTER", programm,
                                f"root={use_root} delay={delay_sec}s")
            self._einmal_refresh()
            messagebox.showinfo("Eingerichtet",
                f"'{basename}' wird beim naechsten Login einmalig ausgefuehrt\n"
                f"und loescht sich danach selbst aus dem Autostart.")
        except Exception as e:
            self.log_to(self.einmal_log, f"Fehler: {e}\n")
            messagebox.showerror("Fehler", str(e))

    def _einmal_refresh(self):
        if not hasattr(self, 'einmal_tree'):
            return
        self.einmal_tree.delete(*self.einmal_tree.get_children())
        from config import ORIGINAL_USER
        autostart_d = os.path.join(os.path.expanduser(f"~{ORIGINAL_USER}"),
                                   ".config", "autostart")
        try:
            if not os.path.isdir(autostart_d):
                return
            for fname in sorted(os.listdir(autostart_d)):
                if not fname.startswith('run-once-') or not fname.endswith('.desktop'):
                    continue
                fpath = os.path.join(autostart_d, fname)
                exec_line = ''
                is_root   = False
                try:
                    with open(fpath) as f:
                        for line in f:
                            if line.startswith('Exec='):
                                exec_line = line.split('=', 1)[1].strip()
                                is_root   = 'pkexec' in exec_line
                                break
                except Exception:
                    pass
                name    = fname.replace('run-once-', '').replace('.desktop', '')
                status  = "wartet"
                self.einmal_tree.insert('', 'end',
                    values=(name, exec_line[:60], 'Ja' if is_root else 'Nein', status))
        except Exception as e:
            self.log_to(self.einmal_log, f"Fehler beim Lesen: {e}\n")

    def _einmal_loeschen(self):
        sel = self.einmal_tree.selection()
        if not sel:
            messagebox.showinfo("Hinweis", "Bitte einen Eintrag auswaehlen.")
            return
        name = self.einmal_tree.item(sel[0])['values'][0]
        from config import ORIGINAL_USER
        autostart_d  = os.path.join(os.path.expanduser(f"~{ORIGINAL_USER}"),
                                    ".config", "autostart")
        desktop_file = os.path.join(autostart_d, f"run-once-{name}.desktop")
        if not messagebox.askyesno("Loeschen",
            f"Einmal-Starter '{name}' wirklich loeschen?\n{desktop_file}"):
            return
        try:
            os.remove(desktop_file)
            self.log_to(self.einmal_log, f"Geloescht: {desktop_file}\n")
            self._einmal_refresh()
        except Exception as e:
            self.log_to(self.einmal_log, f"Fehler: {e}\n")

    # ══════════════════════════════════════════════════════════════════════
    #  TAB: PENGUINS-EGGS ISO-TOOL
    # ══════════════════════════════════════════════════════════════════════
    def _build_eggs_iso(self, nb):
        import os as _os
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🐧 Eggs-ISO")

        canvas = tk.Canvas(tab, bg=T["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        pane = tk.Frame(canvas, bg=T["bg"])
        win  = canvas.create_window((0, 0), window=pane, anchor='nw')
        pane.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win, width=e.width))
        def _sc(ev):
            if ev.delta: canvas.yview_scroll(int(-1*(ev.delta/120)), "units")
            elif ev.num == 4: canvas.yview_scroll(-1, "units")
            elif ev.num == 5: canvas.yview_scroll(1, "units")
        def _bind_rec(w):
            w.bind("<MouseWheel>", _sc, add="+")
            w.bind("<Button-4>",   _sc, add="+")
            w.bind("<Button-5>",   _sc, add="+")
            for child in w.winfo_children():
                _bind_rec(child)

        _bind_rec(canvas)
        pane.bind("<Configure>", lambda e: _bind_rec(canvas), add="+")

        inner = tk.Frame(pane, bg=T["bg"])
        inner.pack(fill='both', expand=True, padx=12, pady=10)

        # ── Status ───────────────────────────────────────────────────────
        status_f = ttk.LabelFrame(inner, text=" Status ", padding=8)
        status_f.pack(fill='x', pady=(0, 8))
        self._eggs_iso_status_lbl = tk.Label(status_f, text="Prüfe...",
                                              bg=T["bg"], font=('Arial', 10, 'bold'))
        self._eggs_iso_status_lbl.pack(anchor='w')
        self._eggs_iso_version_lbl = tk.Label(status_f, text="",
                                               bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9))
        self._eggs_iso_version_lbl.pack(anchor='w')

        def _find_eggs():
            """eggs in allen bekannten Pfaden suchen – ohne Größencheck."""
            import shutil as _sh, subprocess as _sp
            candidates = []
            # shutil.which sucht im aktuellen PATH
            w = _sh.which("eggs")
            if w:
                candidates.append(w)
            # Alle bekannten Installationspfade (penguins-eggs .deb → /usr/bin/eggs)
            for p in ["/usr/bin/eggs", "/usr/local/bin/eggs",
                      "/opt/penguins-eggs/eggs", "/usr/local/sbin/eggs"]:
                if p not in candidates:
                    candidates.append(p)
            for p in candidates:
                if not _os.path.isfile(p):
                    continue
                # Ausführbar? Testen ob eggs --version klappt
                try:
                    r = _sp.run(
                        ["bash", "-c",
                         f"PATH=/usr/bin:/usr/local/bin:/bin:$PATH {p} --version"],
                        capture_output=True, text=True, timeout=8)
                    if r.returncode == 0 and r.stdout.strip():
                        return p
                    # Auch Exit != 0 akzeptieren wenn Ausgabe kommt
                    out = (r.stdout + r.stderr).strip()
                    if out and "penguins" in out.lower():
                        return p
                except Exception:
                    # Datei existiert aber --version schlägt fehl
                    # Trotzdem zurückgeben (ist installiert, nur Aufruf falsch)
                    if _os.path.isfile(p):
                        return p
            return None

        def _check_eggs():
            import subprocess as _sp
            path = _find_eggs()
            if path:
                try:
                    ver = _sp.run(
                        ["bash", "-c",
                         f"PATH=/usr/bin:/usr/local/bin:/bin:$PATH {path} --version"],
                        capture_output=True, text=True, timeout=5).stdout.strip()
                    self._eggs_iso_status_lbl.config(
                        text=f"🟢 penguins-eggs installiert  ({path})", fg=T["success"])
                    self._eggs_iso_version_lbl.config(text=f"Version: {ver[:100]}")
                except Exception as e:
                    self._eggs_iso_status_lbl.config(
                        text=f"🟡 eggs gefunden ({path}) – Version nicht lesbar",
                        fg=T["warning"])
                    self._eggs_iso_version_lbl.config(text=str(e)[:80])
            else:
                self._eggs_iso_status_lbl.config(
                    text="🔴 penguins-eggs NICHT installiert", fg=T["danger"])
                self._eggs_iso_version_lbl.config(
                    text="Bitte install-peessi-multitool.sh erneut ausführen")

        self.root.after(600, _check_eggs)
        ttk.Button(status_f, text="🔄 Status prüfen",
                   command=_check_eggs).pack(anchor='w', pady=(6, 0))

        # ── ISO-Name für Boot-Manager ─────────────────────────────────────
        name_f = ttk.LabelFrame(inner, text=" ISO-Name (erscheint im Boot-Menü) ", padding=8)
        name_f.pack(fill='x', pady=(0, 8))
        tk.Label(name_f, text=(
            "Dieser Name erscheint in GRUB/rEFInd als Boot-Eintrag.\n"
            "Erlaubte Zeichen: Buchstaben, Zahlen, Bindestrich, Unterstrich."
        ), bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9)).pack(anchor='w')
        name_row = tk.Frame(name_f, bg=T["bg"])
        name_row.pack(fill='x', pady=(6, 0))
        tk.Label(name_row, text="ISO-Name:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 10)).pack(side='left', padx=(0, 8))
        self._eggs_iso_name_var = tk.StringVar(value="PeessiLive")
        ttk.Entry(name_row, textvariable=self._eggs_iso_name_var, width=30).pack(side='left')

        # ── Zielverzeichnis + Temp ────────────────────────────────────────
        dest_f = ttk.LabelFrame(inner, text=" ISO-Zielverzeichnis ", padding=8)
        dest_f.pack(fill='x', pady=(0, 8))

        def _scan_mounts():
            import subprocess as _sp, json as _jn
            opts = ["/home/eggs"]
            try:
                r = _sp.run(
                    ["lsblk", "-J", "-o",
                     "NAME,MOUNTPOINT,MOUNTPOINTS,SIZE,LABEL,TYPE"],
                    capture_output=True, text=True, timeout=8)
                if r.returncode == 0:
                    data = _jn.loads(r.stdout)
                    def _col(devs):
                        for d in devs:
                            mps = d.get("mountpoints") or []
                            if isinstance(mps, str):
                                mps = [mps]
                            mp1 = d.get("mountpoint") or ""
                            if mp1 and mp1 not in mps:
                                mps.append(mp1)
                            for mp in mps:
                                if not mp:
                                    continue
                                label = d.get("label") or ""
                                size  = d.get("size") or ""
                                entry = f"{mp}  [{label or d.get('name','')}  {size}]"                                         if (label or size) else mp
                                existing = [o.split()[0] for o in opts]
                                if mp not in existing:
                                    opts.append(entry)
                            _col(d.get("children") or [])
                    _col(data.get("blockdevices", []))
            except Exception:
                pass
            try:
                with open("/proc/mounts") as _f:
                    for line in _f:
                        parts = line.split()
                        if len(parts) < 2:
                            continue
                        mp = parts[1]
                        existing = [o.split()[0] for o in opts]
                        if mp not in existing and any(
                                mp.startswith(x) for x in
                                ["/media/", "/mnt/", "/run/media/"]):
                            opts.append(mp)
            except Exception:
                pass
            return opts

        lw_lbl = tk.Label(dest_f, text="Erkannte Laufwerke:",
                          bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9))
        lw_lbl.pack(anchor='w')
        lw_f = tk.Frame(dest_f, bg=T["bg"])
        lw_f.pack(fill='x', pady=(2, 6))
        lw_sb = ttk.Scrollbar(lw_f, orient='vertical')
        lw_sb.pack(side='right', fill='y')
        self._eggs_lw_list = tk.Listbox(
            lw_f, height=4, font=('Monospace', 9),
            bg=T.get("bg2", T["bg"]), fg=T["fg"],
            selectbackground=T["accent"],
            yscrollcommand=lw_sb.set)
        self._eggs_lw_list.pack(side='left', fill='x', expand=True)
        lw_sb.config(command=self._eggs_lw_list.yview)

        dest_row = tk.Frame(dest_f, bg=T["bg"])
        dest_row.pack(fill='x')
        tk.Label(dest_row, text="Ziel:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 4))
        self._eggs_dest_var = tk.StringVar(value="/home/eggs")
        self._eggs_dest_cb  = ttk.Combobox(dest_row, textvariable=self._eggs_dest_var,
                                            font=('Arial', 10), width=45)
        self._eggs_dest_cb.pack(side='left', padx=(0, 4))

        def _refresh_dest():
            opts = _scan_mounts()
            self._eggs_dest_cb['values'] = opts
            self._eggs_lw_list.delete(0, 'end')
            for o in opts:
                self._eggs_lw_list.insert('end', o)
            lw_lbl.config(text=f"Erkannte Laufwerke ({len(opts)}):")

        def _on_lw_select(e):
            sel = self._eggs_lw_list.curselection()
            if sel:
                val = self._eggs_lw_list.get(sel[0]).split("[")[0].strip()
                self._eggs_dest_var.set(val)

        self._eggs_lw_list.bind("<<ListboxSelect>>", _on_lw_select)
        ttk.Button(dest_row, text="🔄 Laufwerke suchen",
                   command=_refresh_dest).pack(side='left', padx=(0, 4))
        ttk.Button(dest_row, text="📂",
                   command=lambda: self._eggs_dest_var.set(
                       filedialog.askdirectory(title="Zielverzeichnis wählen")
                       or self._eggs_dest_var.get()
                   )).pack(side='left')
        _refresh_dest()

        # ── Temp-Verzeichnis ──────────────────────────────────────────────
        tmp_f = ttk.LabelFrame(inner,
            text=" Temporäres Arbeitsverzeichnis (optional) ", padding=8)
        tmp_f.pack(fill='x', pady=(0, 8))
        tk.Label(tmp_f, text=(
            "eggs legt temporäre Dateien standardmäßig in /tmp an.\n"
            "Bei großen ISOs (>8 GB) kann das den Systemspeicher füllen.\n"
            "Hier ein externes Laufwerk angeben – leer = Standard (/tmp)"
        ), bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9)).pack(anchor='w')
        tmp_row = tk.Frame(tmp_f, bg=T["bg"])
        tmp_row.pack(fill='x', pady=(6, 0))
        tk.Label(tmp_row, text="Temp:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 4))
        self._eggs_tmp_var = tk.StringVar(value="")
        ttk.Entry(tmp_row, textvariable=self._eggs_tmp_var,
                  width=38).pack(side='left', padx=(0, 4))
        ttk.Button(tmp_row, text="📂",
                   command=lambda: self._eggs_tmp_var.set(
                       filedialog.askdirectory(title="Temp-Verzeichnis wählen")
                       or self._eggs_tmp_var.get()
                   )).pack(side='left', padx=(0, 4))
        ttk.Button(tmp_row, text="✖",
                   command=lambda: self._eggs_tmp_var.set("")).pack(side='left')

        # ── Optionen ──────────────────────────────────────────────────────
        opt_f = ttk.LabelFrame(inner, text=" Optionen ", padding=8)
        opt_f.pack(fill='x', pady=(0, 8))
        self._eggs_calamares_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_f, text="Calamares-Installer einbinden (eggs calamares --install)",
                        variable=self._eggs_calamares_var).pack(anchor='w')
        self._eggs_clean_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_f, text="Vor Erstellung: apt-get clean && autoremove",
                        variable=self._eggs_clean_var).pack(anchor='w')
        self._eggs_shutdown_iso_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_f, text="🔌 Nach Fertigstellung Rechner herunterfahren",
                        variable=self._eggs_shutdown_iso_var).pack(anchor='w')

        # ── Modus-Auswahl ─────────────────────────────────────────────────
        mode_f = ttk.LabelFrame(inner, text=" Modus ", padding=8)
        mode_f.pack(fill='x', pady=(0, 8))
        self._eggs_mode_var = tk.StringVar(value="standard")
        for val, lbl in [
            ("standard", "🖥️  Nur Programme  –  System ohne persönliche Daten/Design"),
            ("design",   "🎨  Programme & Design  –  inkl. Theme, Icons, Wallpaper"),
            ("klon",     "💾  Vollständiger Klon  –  komplettes 1:1-Abbild"),
        ]:
            ttk.Radiobutton(mode_f, text=lbl, value=val,
                            variable=self._eggs_mode_var).pack(anchor='w', pady=2)

        # ── System vorbereiten ────────────────────────────────────────────
        prep_f = ttk.LabelFrame(inner, text=" System vorbereiten ", padding=8)
        prep_f.pack(fill='x', pady=(0, 8))
        tk.Label(prep_f, text=(
            "eggs dad -d analysiert das System und optimiert die eggs-Konfiguration.\n"
            "Empfohlen vor der ersten ISO-Erstellung."
        ), bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9)).pack(anchor='w')

        # ── Ausgabe-Log ───────────────────────────────────────────────────
        log_f = ttk.LabelFrame(inner, text=" Ausgabe ", padding=6)
        log_f.pack(fill='both', expand=True, pady=(0, 8))
        self._eggs_iso_log = self.make_log_widget(log_f, height=16)
        self._eggs_iso_log.pack(fill='both', expand=True)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_f = tk.Frame(inner, bg=T["bg"])
        btn_f.pack(fill='x', pady=(4, 0))
        ttk.Button(btn_f, text="⚙️ System vorbereiten (dad -d)",
                   command=self._eggs_iso_dad).pack(side='left', padx=(0, 6))
        self._eggs_iso_run_btn = ttk.Button(btn_f, text="▶ ISO erstellen",
                                             style='Accent.TButton',
                                             command=self._eggs_iso_start)
        self._eggs_iso_run_btn.pack(side='left', padx=(0, 6))
        ttk.Button(btn_f, text="📋 Log kopieren",
                   command=lambda: self.copy_log(self._eggs_iso_log)).pack(side='left')
        ttk.Button(btn_f, text="🗑 Leeren",
                   command=lambda: self.clear_log(self._eggs_iso_log)).pack(side='left', padx=6)

    def _eggs_iso_dad(self):
        import shutil as _sh, os as _os
        eggs_path = next(
            (p for p in filter(None, [_sh.which("eggs"), "/usr/bin/eggs",
                                       "/usr/local/bin/eggs"])
             if _os.path.isfile(p)), None)
        if not eggs_path:
            messagebox.showerror("eggs fehlt", "penguins-eggs ist nicht installiert.\n"
                "Bitte install-peessi-multitool.sh erneut ausführen.")
            return
        self.run_shell_async(
            f"bash -c 'PATH=/usr/local/bin:/usr/bin:/bin:$PATH {eggs_path} dad -d'",
            self._eggs_iso_log, self._eggs_iso_run_btn)

    def _eggs_iso_start(self):
        import shutil as _sh, os as _os, re as _re
        eggs_path = next(
            (p for p in filter(None, [_sh.which("eggs"), "/usr/bin/eggs",
                                       "/usr/local/bin/eggs"])
             if _os.path.isfile(p)), None)
        if not eggs_path:
            messagebox.showerror("eggs fehlt", "penguins-eggs ist nicht installiert.\n"
                "Bitte install-peessi-multitool.sh erneut ausführen.")
            return

        mode     = self._eggs_mode_var.get()
        dest     = self._eggs_dest_var.get().strip() or "/home/eggs"
        iso_nm   = _re.sub(r'[^a-zA-Z0-9_-]', '',
                           self._eggs_iso_name_var.get().strip()) or "PeessiLive"
        calamares = self._eggs_calamares_var.get()
        clean     = self._eggs_clean_var.get()
        shutdown  = self._eggs_shutdown_iso_var.get()

        mode_txt = {"standard":"Nur Programme","design":"Programme & Design","klon":"Vollklon"}
        if not messagebox.askyesno("ISO erstellen",
            f"Modus    : {mode_txt.get(mode, mode)}\n"
            f"ISO-Name : {iso_nm}\nZiel     : {dest}\n"
            f"Calamares: {'Ja' if calamares else 'Nein'}\n"
            f"Shutdown : {'JA – nach Fertigstellung!' if shutdown else 'Nein'}\n\n"
            "ISO-Erstellung starten? (kann 15–60 Min dauern)"):
            return

        tmp_dir = self._eggs_tmp_var.get().strip() if hasattr(self, "_eggs_tmp_var") else ""
        parts = [
            "set -e",
            f"export PATH=/usr/local/bin:/usr/bin:/bin:$PATH",
        ]
        if tmp_dir and tmp_dir != "/tmp":
            parts.append(f"mkdir -p '{tmp_dir}'")
            parts.append(f"export TMPDIR='{tmp_dir}'")
            parts.append(f"export TMP='{tmp_dir}'")
            parts.append(f"echo 'Temp-Verzeichnis: {tmp_dir}'")
        parts += [
            f"mkdir -p '{dest}'",
        ]
        if clean:
            parts.append("echo '=== Bereinige System ==='; apt-get clean && apt-get autoremove -y")
        if calamares:
            parts.append(f"echo '=== Calamares ==='; {eggs_path} calamares --install")

        if mode == "standard":
            parts.append(f"{eggs_path} produce --standard --prefix custom "
                        f"--basename '{iso_nm}-programmes' --nointeractive")
        elif mode == "design":
            parts.append(f"sudo -E -u {ORIGINAL_USER} {eggs_path} mom --skilling 2>/dev/null || true")
            parts.append(f"{eggs_path} produce --standard --prefix custom "
                        f"--basename '{iso_nm}-design' --nointeractive")
        else:
            parts.append(f"{eggs_path} produce --clone --standard --prefix backup "
                        f"--basename '{iso_nm}-vollbackup' --nointeractive")

        parts.append("echo '=== Verschiebe ISO ==='")
        parts.append(
            f"ISO=$(ls -t /home/eggs/*.iso 2>/dev/null | head -1); "
            f"[ -n \"$ISO\" ] && cp \"$ISO\" '{dest}/' && rm \"$ISO\" && "
            f"echo 'ERFOLG: ISO → {dest}' || echo 'WARNUNG: Keine ISO in /home/eggs gefunden'")
        if shutdown:
            parts.append("echo 'Shutdown in 60s...'; sleep 60; shutdown -h now")

        cmd = "bash -c '" + "; ".join(parts).replace("'", "'\"'\"'") + "'"
        self.clear_log(self._eggs_iso_log)
        self.run_shell_async(cmd, self._eggs_iso_log, self._eggs_iso_run_btn)


    # ══════════════════════════════════════════════════════════════════════
    #  TAB: GRUB CONTROL CENTER
    # ══════════════════════════════════════════════════════════════════════
    def _build_grub_tab(self, nb):
        """GRUB Control Center Tab – Implementierung in gui_grub.py."""
        if _GRUB_AVAILABLE:
            self._grub_tab = GrubTab(nb, self.app, self.theme)
        else:
            # Fallback wenn gui_grub.py fehlt
            T   = self.theme
            tab = ttk.Frame(nb)
            nb.add(tab, text="🔧 GRUB")
            tk.Label(tab,
                text="⚠️  gui_grub.py nicht gefunden.\n\n"
                     "Bitte install-peessi-multitool.sh erneut ausführen.",
                bg=T["bg"], fg=T["danger"],
                font=("Arial", 11)).pack(expand=True)


class NetworkTab(GuiBase):
    def __init__(self, nb_main, app):
        super().__init__(app.root, app.settings, app.theme, app._log_widgets)
        self._build(nb_main)

    def _build(self, nb_main):
        T   = self.theme
        tab = ttk.Frame(nb_main)
        nb_main.add(tab, text="🌐 Netzwerk")
        nb = ttk.Notebook(tab)
        nb.pack(fill='both', expand=True, padx=4, pady=4)
        self._build_interfaces(nb)
        self._build_ping(nb)
        self._build_connections(nb)
        self._build_wlan_passwords(nb)
        self._refresh_interfaces()
        # Verbindungen laden via root.after() in _build_connections

    def _build_interfaces(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="Interfaces")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)
        icols = ('Interface', 'IPv4', 'IPv6', 'MAC', 'Status')
        self.iface_tree = ttk.Treeview(pane, columns=icols, show='headings', height=8)
        iw = {'Interface':100,'IPv4':140,'IPv6':220,'MAC':140,'Status':70}
        for c in icols:
            self.iface_tree.heading(c, text=c)
            self.iface_tree.column(c, width=iw.get(c, 120))
        self.iface_tree.tag_configure('up',   background=T["tag_removable"])
        self.iface_tree.tag_configure('down', background=T["tag_internal"])
        self.iface_tree.pack(fill='x')
        self.iface_detail = self.make_log_widget(pane, height=8)
        self.iface_detail.pack(fill='both', expand=True, pady=(8, 0))
        ttk.Button(pane, text="🔄 Aktualisieren",
                   command=self._refresh_interfaces).pack(anchor='w', pady=(6, 0))

    def _build_ping(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🏓 Ping")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)
        row = tk.Frame(pane, bg=T["bg"])
        row.pack(fill='x', pady=(0, 8))
        tk.Label(row, text="Host:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 6))
        self.ping_host_var = tk.StringVar(value="8.8.8.8")
        ttk.Entry(row, textvariable=self.ping_host_var, width=30
                  ).pack(side='left', padx=(0, 6))
        tk.Label(row, text="Anzahl:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 4))
        self.ping_count_var = tk.StringVar(value="4")
        ttk.Entry(row, textvariable=self.ping_count_var, width=5
                  ).pack(side='left', padx=(0, 8))
        ttk.Button(row, text="▶ Ping", style='Accent.TButton',
                   command=self._run_ping).pack(side='left')
        self.ping_log = self.make_log_widget(pane, height=20)
        self.ping_log.pack(fill='both', expand=True)

    def _build_connections(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🔌 Verbindungen")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        # Status-Label zeigt Anzahl + Zeitstempel
        self.conn_status_lbl = tk.Label(pane, text="",
            bg=T["bg"], fg=T["fg_dim"], font=('Arial', 9))
        self.conn_status_lbl.pack(anchor='w', pady=(0, 4))

        ccols = ('Proto', 'Lokal', 'Remote', 'Status', 'PID/Prozess')
        tree_f = tk.Frame(pane, bg=T["bg"])
        tree_f.pack(fill='both', expand=True)
        csb = ttk.Scrollbar(tree_f, orient='vertical')
        csb.pack(side='right', fill='y')
        hsb = ttk.Scrollbar(tree_f, orient='horizontal')
        hsb.pack(side='bottom', fill='x')
        self.conn_tree = ttk.Treeview(tree_f, columns=ccols, show='headings',
                                       yscrollcommand=csb.set, xscrollcommand=hsb.set)
        csb.config(command=self.conn_tree.yview)
        hsb.config(command=self.conn_tree.xview)
        cw = {'Proto':60,'Lokal':200,'Remote':200,'Status':110,'PID/Prozess':160}
        for c in ccols:
            self.conn_tree.heading(c, text=c)
            self.conn_tree.column(c, width=cw.get(c, 120), minwidth=50)
        self.conn_tree.pack(side='left', fill='both', expand=True)

        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(6, 0))
        ttk.Button(btn_f, text="🔄 Aktualisieren",
                   command=self._refresh_connections).pack(side='left')
        ttk.Button(btn_f, text="📋 Kopieren",
                   command=self._copy_connections).pack(side='left', padx=6)

        # Auto-Refresh: einmalig 800ms nach Programmstart
        self.root.after(800, self._refresh_connections)
        # Und nochmal wenn Tab sichtbar wird
        tab.bind("<Visibility>", lambda e: self.root.after(100, self._refresh_connections))

    def _refresh_interfaces(self):
        for row in self.iface_tree.get_children():
            self.iface_tree.delete(row)
        try:
            r = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
            self.log_to(self.iface_detail, r.stdout, clear=True)
            current = ipv4 = ipv6 = mac = ""
            for line in r.stdout.splitlines():
                m = re.match(r'^\d+:\s+(\S+):', line)
                if m:
                    if current:
                        up  = "up" if "UP" in line else "down"
                        self.iface_tree.insert('', 'end',
                            values=(current, ipv4, ipv6, mac, up),
                            tags=(up,))
                    current = m.group(1).rstrip(':')
                    ipv4 = ipv6 = mac = ""
                mi = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+/\d+)', line)
                if mi: ipv4 = mi.group(1)
                m6 = re.search(r'inet6\s+([0-9a-f:]+/\d+)', line)
                if m6: ipv6 = m6.group(1)
                mm = re.search(r'link/\S+\s+([0-9a-f:]{17})', line)
                if mm: mac  = mm.group(1)
            if current:
                self.iface_tree.insert('', 'end',
                    values=(current, ipv4, ipv6, mac, "—"), tags=())
        except Exception as e:
            self.log_to(self.iface_detail, f"Fehler: {e}\n")

    def _run_ping(self):
        host = self.ping_host_var.get().strip()
        if not host:
            return
        try:
            count = int(self.ping_count_var.get().strip())
        except ValueError:
            count = 4
        self.clear_log(self.ping_log)
        self.log_to(self.ping_log, f"ping {host} ({count}×)...\n")
        def worker():
            try:
                proc = subprocess.Popen(['ping', '-c', str(count), host],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    self.root.after(0, lambda l=line: self.log_to(self.ping_log, l))
                proc.wait()
            except Exception as e:
                self.root.after(0, lambda: self.log_to(self.ping_log, f"Fehler: {e}\n"))
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_connections(self):
        """Lädt Verbindungen asynchron – blockiert die GUI nicht."""
        import re as _re

        def _parse(line):
            parts = line.split()
            if len(parts) < 5:
                return None
            proto  = parts[0]
            state  = parts[1]
            local  = parts[4] if len(parts) > 4 else ""
            remote = parts[5] if len(parts) > 5 else ""
            proc   = ""
            pm = _re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
            if pm:
                proc = f"{pm.group(2)}/{pm.group(1)}"
            return (proto, local, remote, state, proc)

        def worker():
            rows = []
            try:
                r = subprocess.run(["ss", "-tunp"],
                                   capture_output=True, text=True, timeout=10)
                for line in r.stdout.splitlines():
                    line = line.rstrip()
                    if not line or line.startswith(("Netid", "State")):
                        continue
                    result = _parse(line)
                    if result:
                        rows.append(result)
                # Fallback netstat wenn ss leer
                if not rows:
                    r2 = subprocess.run(["netstat", "-tunp"],
                                        capture_output=True, text=True, timeout=10)
                    for line in r2.stdout.splitlines():
                        parts = line.split()
                        if not parts or parts[0] not in ("tcp","tcp6","udp","udp6"):
                            continue
                        if len(parts) < 5:
                            continue
                        rows.append((parts[0], parts[3], parts[4],
                                     parts[5] if len(parts) > 5 else "",
                                     parts[6] if len(parts) > 6 else ""))
            except Exception:
                pass

            def _update():
                for row in self.conn_tree.get_children():
                    self.conn_tree.delete(row)
                for row in rows:
                    self.conn_tree.insert("", "end", values=row)
                lbl = getattr(self, "conn_status_lbl", None)
                if lbl:
                    import datetime as _dt
                    ts = _dt.datetime.now().strftime("%H:%M:%S")
                    lbl.config(text=f"{len(rows)} Verbindung(en)  |  Stand: {ts}")

            self.root.after(0, _update)

        import threading as _th
        _th.Thread(target=worker, daemon=True).start()

    def _conn_sort(self, col):
        try:
            data = [(self.conn_tree.set(c, col), c)
                    for c in self.conn_tree.get_children('')]
            data.sort()
            for i, (_, c) in enumerate(data):
                self.conn_tree.move(c, '', i)
        except Exception:
            pass

    def _copy_connections(self):
        try:
            lines = ["Proto\tLokal\tRemote\tStatus\tPID/Prozess"]
            for child in self.conn_tree.get_children():
                vals = self.conn_tree.item(child)['values']
                lines.append("\t".join(str(v) for v in vals))
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(lines))
            self.root.update()
        except Exception as e:
            messagebox.showerror("Fehler", str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  LOGS & DIAGNOSE TAB
# ══════════════════════════════════════════════════════════════════════════════
    def _build_wlan_passwords(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="\U0001f511 WLAN-Passwoerter")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        desc = ttk.LabelFrame(pane, text=" Beschreibung ", padding=8)
        desc.pack(fill='x', pady=(0, 8))
        tk.Label(desc, text=(
            "Liest gespeicherte WLAN-Passwoerter aus dem NetworkManager aus.\n"
            "Benoetigt Root-Rechte (nmcli --show-secrets)."
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 10), justify='left').pack(anchor='w')

        # Ergebnis-Tabelle
        tree_f = ttk.LabelFrame(pane, text=" Gespeicherte WLAN-Verbindungen ", padding=8)
        tree_f.pack(fill='both', expand=True, pady=(0, 8))

        cols = ('WLAN-Name', 'Passwort', 'Sicherheit', 'BSSID')
        self.wlan_tree = ttk.Treeview(tree_f, columns=cols, show='headings', height=12)
        cw = {'WLAN-Name': 220, 'Passwort': 250, 'Sicherheit': 100, 'BSSID': 160}
        for c in cols:
            self.wlan_tree.heading(c, text=c)
            self.wlan_tree.column(c, width=cw.get(c, 150))
        wsb = ttk.Scrollbar(tree_f, orient='vertical', command=self.wlan_tree.yview)
        self.wlan_tree.configure(yscrollcommand=wsb.set)
        self.wlan_tree.pack(side='left', fill='both', expand=True)
        wsb.pack(side='right', fill='y')

        # Log
        log_f = ttk.LabelFrame(pane, text=" Ausgabe ", padding=6)
        log_f.pack(fill='x', pady=(0, 8))
        self.wlan_log = self.make_log_widget(log_f, height=4)
        self.wlan_log.pack(fill='both', expand=True)

        # Buttons
        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x')
        ttk.Button(btn_f, text="\U0001f50d WLAN-Passwoerter auslesen",
                   style='Accent.TButton',
                   command=self._read_wlan_passwords).pack(side='left', padx=4)
        ttk.Button(btn_f, text="\U0001f4cb Passwort kopieren",
                   command=self._copy_wlan_password).pack(side='left', padx=4)
        ttk.Button(btn_f, text="\U0001f5d1 Liste leeren",
                   command=lambda: self.wlan_tree.delete(
                       *self.wlan_tree.get_children())).pack(side='left', padx=4)

    def _read_wlan_passwords(self):
        self.wlan_tree.delete(*self.wlan_tree.get_children())
        self.clear_log(self.wlan_log)
        self.log_to(self.wlan_log, "Lese WLAN-Verbindungen..." + chr(10))

        def worker():
            import re as _re
            results = []
            try:
                r = subprocess.run(
                    ['nmcli', '-t', '-f', 'NAME', 'connection', 'show'],
                    capture_output=True, text=True)
                names = [n for n in r.stdout.strip().splitlines() if n and n != 'lo']

                for name in names:
                    # DBUS_SESSION_BUS_ADDRESS noetig damit nmcli Secrets lesen kann
                    import os as _os
                    env = dict(_os.environ)
                    # Versuche DBUS-Adresse des Original-Users zu ermitteln
                    from config import ORIGINAL_USER as _USER
                    try:
                        uid_r = subprocess.run(
                            ['id', '-u', _USER], capture_output=True, text=True)
                        uid = uid_r.stdout.strip()
                        dbus = f"unix:path=/run/user/{uid}/bus"
                        env['DBUS_SESSION_BUS_ADDRESS'] = dbus
                    except Exception:
                        pass
                    r2 = subprocess.run(
                        ['nmcli', '--show-secrets', 'connection', 'show', name],
                        capture_output=True, text=True, env=env)
                    details = r2.stdout

                    if '802-11-wireless' not in details:
                        continue

                    psk     = ''
                    sec     = ''
                    bssid   = ''

                    # PSK: Leerzeichen zwischen Doppelpunkt und Wert variabel
                    for line in details.splitlines():
                        line = line.strip()
                        if line.startswith('802-11-wireless-security.psk:'):
                            val = line.split(':', 1)[1].strip()
                            if val and val not in ('<hidden>', '--', ''):
                                psk = val
                        elif line.startswith('802-11-wireless-security.key-mgmt:'):
                            sec = line.split(':', 1)[1].strip()
                        elif line.startswith('802-11-wireless.seen-bssids:'):
                            bssid = line.split(':', 1)[1].strip().split(',')[0]

                    results.append((name, psk or '(kein Passwort)', sec, bssid))
                    self.root.after(0, lambda n=name, p=psk:
                        self.log_to(self.wlan_log,
                            f"  {n}: {'Passwort gefunden' if p else 'offen/kein PSK'}" +
                            chr(10)))

            except Exception as e:
                self.root.after(0, lambda: self.log_to(
                    self.wlan_log, "Fehler: " + str(e) + chr(10)))
                return

            def update_ui():
                for row in results:
                    self.wlan_tree.insert('', 'end', values=row)
                count = len([r for r in results if r[1] != '(kein Passwort)'])
                self.log_to(self.wlan_log,
                    chr(10) + f"{len(results)} WLAN(s) gefunden, "
                    f"{count} mit Passwort." + chr(10))

            self.root.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _copy_wlan_password(self):
        sel = self.wlan_tree.selection()
        if not sel:
            messagebox.showinfo("Hinweis", "Bitte eine WLAN-Verbindung auswaehlen.")
            return
        vals = self.wlan_tree.item(sel[0])['values']
        name = vals[0]
        pwd  = vals[1]
        if pwd == '(kein Passwort)':
            messagebox.showinfo("Kein Passwort",
                f"'{name}' hat kein gespeichertes Passwort.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(str(pwd))
        self.root.update()
        messagebox.showinfo("Kopiert",
            f"Passwort fuer '{name}' in Zwischenablage kopiert.")

class LogsTab(GuiBase):
    def __init__(self, nb_main, app):
        super().__init__(app.root, app.settings, app.theme, app._log_widgets)
        self.sec = app.sec
        self._diag_txt  = ""
        self._diag_html = ""
        self._build(nb_main)

    def _build(self, nb_main):
        T   = self.theme
        tab = ttk.Frame(nb_main)
        nb_main.add(tab, text="📋 Logs & Diagnose")
        nb = ttk.Notebook(tab)
        nb.pack(fill='both', expand=True, padx=4, pady=4)
        self._build_log_viewer(nb)
        self._build_diagnose(nb)

    def _build_log_viewer(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="\U0001f4c4 Log-Viewer")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)

        ctrl = tk.Frame(pane, bg=T["bg"])
        ctrl.pack(fill='x', pady=(0, 8))
        ttk.Button(ctrl, text="\U0001f504 Alle laden",
                   style='Accent.TButton',
                   command=self._load_all_logs).pack(side='left', padx=(0, 8))
        tk.Label(ctrl, text="Suche:", bg=T["bg"], fg=T["fg"],
                 font=('Arial', 9)).pack(side='left', padx=(0, 4))
        self.log_search_var = tk.StringVar()
        se = ttk.Entry(ctrl, textvariable=self.log_search_var, width=22)
        se.pack(side='left', padx=(0, 6))
        se.bind('<Return>', lambda e: self._search_log())
        ttk.Button(ctrl, text="\U0001f50d",
                   command=self._search_log).pack(side='left', padx=(0, 8))
        ttk.Button(ctrl, text="\U0001f5d1 Leeren",
                   command=lambda: self.clear_log(self.log_view)).pack(side='left', padx=4)
        ttk.Button(ctrl, text="\U0001f4cb Kopieren",
                   command=lambda: self.copy_log(self.log_view)).pack(side='left', padx=4)
        ttk.Button(ctrl, text="\U0001f4be Alle Logs speichern",
                   command=self._export_all_logs).pack(side='left', padx=4)

        src_frame = ttk.LabelFrame(pane, text=" Log-Quelle ", padding=6)
        src_frame.pack(fill='x', pady=(0, 8))
        self._log_src_btns = {}
        sources = [
            ("journalctl", "Journal"),
            ("dmesg",      "dmesg"),
            ("syslog",     "syslog"),
            ("kern.log",   "Kernel"),
            ("auth.log",   "Auth"),
            ("peessi-log", "Peessi-Log"),
        ]
        for src_key, src_label in sources:
            btn = tk.Button(src_frame, text=src_label,
                            font=('Arial', 9), bd=0, padx=10, pady=4,
                            cursor='hand2', bg=T["bg2"], fg=T["fg"],
                            relief='flat',
                            command=lambda k=src_key: self._show_log_src(k))
            btn.pack(side='left', padx=3)
            self._log_src_btns[src_key] = btn

        self.log_view = self.make_log_widget(pane, height=24)
        self.log_view.pack(fill='both', expand=True)
        self.log_view.tag_config('error',   foreground=T["danger"])
        self.log_view.tag_config('warning', foreground=T["warning"])
        self.log_view.tag_config('info',    foreground=T["success"])
        self.log_view.tag_config('match',   background=T["sel_bg"],
                                            foreground=T["sel_fg"])
        self.log_view.tag_config('header',  foreground=T["accent"],
                                            font=('Arial', 10, 'bold'))
        self._log_cache  = {}
        self._log_active = None
        tab.bind("<Visibility>", lambda e: self._auto_load_logs())

    def _auto_load_logs(self):
        if not self._log_cache:
            self._load_all_logs()

    def _export_all_logs(self):
        """Alle geladenen Logs in einen wählbaren Ordner speichern."""
        import datetime as _dt
        if not self._log_cache:
            messagebox.showinfo("Hinweis",
                "Keine Logs geladen. Bitte zuerst '🔄 Alle laden' klicken.")
            return
        dest = filedialog.askdirectory(title="Ordner für Logs wählen")
        if not dest:
            return
        ts      = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder  = os.path.join(dest, f"peessi-logs-{ts}")
        os.makedirs(folder, exist_ok=True)
        saved, failed = [], []
        for key, text in self._log_cache.items():
            fname = os.path.join(folder, f"{key}.log")
            try:
                with open(fname, "w", encoding="utf-8", errors="replace") as f:
                    f.write(text)
                saved.append(key)
            except Exception as e:
                failed.append(f"{key}: {e}")
        # Übersichtsdatei
        try:
            with open(os.path.join(folder, "_index.txt"), "w") as f:
                f.write(f"Peeßi's System Multitool – Log-Export\n")
                f.write(f"Datum   : {_dt.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
                f.write(f"Ordner  : {folder}\n\n")
                f.write("Gespeicherte Logs:\n")
                for s in saved:
                    f.write(f"  ✅  {s}.log\n")
                if failed:
                    f.write("\nFehler:\n")
                    for e in failed:
                        f.write(f"  ❌  {e}\n")
        except Exception:
            pass
        msg = f"✅ {len(saved)} Log(s) gespeichert:\n{folder}"
        if failed:
            msg += f"\n\n❌ Fehler ({len(failed)}):\n" + "\n".join(failed)
        messagebox.showinfo("Logs gespeichert", msg)


    def _load_all_logs(self):
        self.clear_log(self.log_view)
        self.log_view.config(state='normal')
        self.log_view.insert(tk.END, "Lade alle Logs..." + chr(10), 'info')
        self.log_view.config(state='disabled')
        self._log_cache  = {}
        self._log_active = None

        def worker():
            jobs = [
                ("journalctl", self._fetch_journalctl),
                ("dmesg",      self._fetch_dmesg),
                ("syslog",     lambda: self._fetch_file("/var/log/syslog")),
                ("kern.log",   lambda: self._fetch_file("/var/log/kern.log")),
                ("auth.log",   lambda: self._fetch_file("/var/log/auth.log")),
                ("peessi-log", self._fetch_peessi_log),
            ]
            for key, fn in jobs:
                try:
                    self._log_cache[key] = fn()
                except Exception as e:
                    self._log_cache[key] = "(Fehler: " + str(e) + ")"
            self.root.after(0, lambda: self._show_log_src("journalctl"))

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_journalctl(self):
        r = subprocess.run(
            ['journalctl', '--no-pager', '-n', '500', '-o', 'short'],
            capture_output=True, text=True, timeout=10)
        return r.stdout or "(journalctl: keine Ausgabe)"

    def _fetch_dmesg(self):
        r = subprocess.run(['dmesg', '--color=never'],
                           capture_output=True, text=True, timeout=10)
        return r.stdout or "(dmesg: keine Ausgabe)"

    def _fetch_file(self, path):
        try:
            r = subprocess.run(['tail', '-n', '500', path],
                               capture_output=True, text=True, timeout=5)
            return r.stdout or "(leer oder nicht lesbar: " + path + ")"
        except Exception as e:
            return "(Fehler: " + str(e) + ")"

    def _fetch_peessi_log(self):
        try:
            logfile = getattr(self.sec, 'log_file', None) or "/tmp/peessi.log"
            with open(logfile) as f:
                return f.read() or "(Peessi-Log ist leer)"
        except Exception as e:
            return "(Peessi-Log nicht lesbar: " + str(e) + ")"

    def _show_log_src(self, src_key):
        T = self.theme
        for key, btn in self._log_src_btns.items():
            btn.config(bg=T["accent"] if key == src_key else T["bg2"],
                       fg="#ffffff"   if key == src_key else T["fg"])
        self._log_active = src_key
        if src_key not in self._log_cache:
            self.clear_log(self.log_view)
            self.log_view.config(state='normal')
            self.log_view.insert(tk.END,
                "Noch nicht geladen – bitte 'Alle laden' klicken." + chr(10), 'warning')
            self.log_view.config(state='disabled')
            return
        titles = {
            "journalctl": "systemd Journal (letzte 500 Eintraege)",
            "dmesg":      "Kernel-Ringpuffer (dmesg)",
            "syslog":     "Syslog (/var/log/syslog)",
            "kern.log":   "Kernel-Log (/var/log/kern.log)",
            "auth.log":   "Auth-Log (/var/log/auth.log)",
            "peessi-log": "Peessi Multitool Audit-Log",
        }
        content = self._log_cache[src_key]
        self.log_view.config(state='normal')
        self.log_view.delete('1.0', tk.END)
        self.log_view.insert(tk.END,
            "==  " + titles.get(src_key, src_key) + "  ==" + chr(10) + chr(10),
            'header')
        for line in content.splitlines(keepends=True):
            ll = line.lower()
            if any(k in ll for k in ('error', 'fehler', 'fail', 'crit')):
                self.log_view.insert(tk.END, line, 'error')
            elif any(k in ll for k in ('warn', 'warnung', 'alert')):
                self.log_view.insert(tk.END, line, 'warning')
            elif any(k in ll for k in ('info', 'notice', 'start', 'ok')):
                self.log_view.insert(tk.END, line, 'info')
            else:
                self.log_view.insert(tk.END, line)
        self.log_view.see(tk.END)
        self.log_view.config(state='disabled')

    def _search_log(self, term=None):
        term = term or self.log_search_var.get().strip()
        if not term:
            return
        self.log_view.tag_remove('match', '1.0', tk.END)
        start = '1.0'
        count = 0
        while True:
            pos = self.log_view.search(term, start, nocase=True, stopindex=tk.END)
            if not pos:
                break
            end = pos + "+" + str(len(term)) + "c"
            self.log_view.tag_add('match', pos, end)
            start = end
            count += 1
        if count:
            first = self.log_view.search(term, '1.0', nocase=True)
            if first:
                self.log_view.see(first)

    def _build_diagnose(self, nb):
        T   = self.theme
        tab = ttk.Frame(nb)
        nb.add(tab, text="🩺 Diagnose")
        pane = tk.Frame(tab, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=12, pady=10)
        desc = ttk.LabelFrame(pane, text=" Beschreibung ", padding=8)
        desc.pack(fill='x', pady=(0, 8))
        tk.Label(desc, text=(
            "Erstellt einen vollständigen Systembericht:\n"
            "Hardware · CPU · RAM · SMART · Partitionen · fstab · Kernel · Netzwerk · Pakete\n"
            "Export als TXT und HTML (→ ~/system_diagnose_DATUM.html)"
        ), bg=T["bg"], fg=T["fg"], font=('Arial', 9), justify='left').pack(anchor='w')
        self.diag_log = self.make_log_widget(pane, height=20)
        self.diag_log.pack(fill='both', expand=True)
        btn_f = tk.Frame(pane, bg=T["bg"])
        btn_f.pack(fill='x', pady=(8, 0))
        self.diag_btn = ttk.Button(btn_f, text="▶ Diagnose erstellen",
                                   style='Accent.TButton', command=self._run_diagnose)
        self.diag_btn.pack(side='right', padx=4)
        ttk.Button(btn_f, text="📂 HTML öffnen",
                   command=self._open_diag_html).pack(side='right', padx=4)
        ttk.Button(btn_f, text="📋 Kopieren",
                   command=lambda: self.copy_log(self.diag_log)).pack(side='left')
        ttk.Button(btn_f, text="🗑 Leeren",
                   command=lambda: self.clear_log(self.diag_log)).pack(side='left', padx=4)

    def _run_diagnose(self):
        self.clear_log(self.diag_log)
        self.diag_btn.config(state='disabled')
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._diag_txt  = str(USER_HOME / f"system_diagnose_{ts}.txt")
        self._diag_html = str(USER_HOME / f"system_diagnose_{ts}.html")
        try:
            open(self._diag_txt, 'w').close()
        except Exception:
            self._diag_txt = f"/tmp/diagnose_{ts}.txt"
        threading.Thread(target=self._diagnose_worker, daemon=True).start()

    def _diagnose_worker(self):
        def log(t):
            self.root.after(0, lambda tx=t: self.log_to(self.diag_log, tx))
            self._diag_write(t)

        def run(args):
            try:
                r = subprocess.run(args, capture_output=True, text=True, timeout=30)
                return r.stdout.strip() or r.stderr.strip()[:200] or "(keine Ausgabe)"
            except Exception as e:
                return f"(Fehler: {e})"

        def section(title):
            bar = "═" * 58
            log(f"\n{bar}\n  {title}\n{bar}\n")

        now = datetime.datetime.now().strftime("%d.%m.%Y  %H:%M:%S")
        log(f"╔══════════════════════════════════════════════════════════╗\n")
        log(f"║    PEEESSI'S SYSTEM MULTITOOL v{VERSION} – DIAGNOSEBERICHT    ║\n")
        log(f"╚══════════════════════════════════════════════════════════╝\n")
        log(f"  Erstellt : {now}\n  User     : {ORIGINAL_USER}\n  Host     : {run(['hostname'])}\n")

        section("1  BETRIEBSSYSTEM & KERNEL")
        for f in ["/etc/linuxmint/info", "/etc/os-release"]:
            if os.path.isfile(f):
                try:
                    with open(f) as fh:
                        for line in fh:
                            if line.strip() and not line.startswith('#'):
                                log(f"  {line.rstrip()}")
                except Exception:
                    pass
                break
        log(f"  Kernel : {run(['uname', '-r'])}")
        log(f"  Uptime : {run(['uptime', '-p'])}")

        section("2  HARDWARE")
        log(run(['hostnamectl']))
        for dmi in ["product_name", "product_version", "board_vendor", "bios_version"]:
            p = f"/sys/class/dmi/id/{dmi}"
            if os.path.isfile(p):
                try:
                    with open(p) as fh:
                        log(f"  {dmi:20s}: {fh.read().strip()}")
                except Exception:
                    pass

        section("3  PROZESSOR")
        seen = set()
        try:
            with open("/proc/cpuinfo") as fh:
                for line in fh:
                    if any(k in line for k in ("model name","cpu MHz","cpu cores")):
                        if line not in seen:
                            log(f"  {line.strip()}")
                            seen.add(line)
        except Exception:
            pass

        section("4  ARBEITSSPEICHER")
        log(run(['free', '-h']))

        section("5  LAUFWERKE")
        log(run(['lsblk', '-o', 'NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT,LABEL,MODEL']))

        section("6  SMART")
        if shutil.which('smartctl'):
            try:
                devs = subprocess.check_output(
                    ['lsblk', '-dno', 'NAME,TYPE'], text=True).strip().splitlines()
                for d in devs:
                    parts = d.split()
                    if len(parts) >= 2 and parts[1] == 'disk':
                        dev = f"/dev/{parts[0]}"
                        log(f"\n── {dev} ──\n")
                        # Nutzt korrigierten smart_engine
                        status, temp, code = query_smart(dev, timeout=8)
                        log(f"    Status: {status}  |  Temp: {temp}  |  Exit-Code: {code}\n")
            except Exception:
                pass
        else:
            log("  smartmontools nicht installiert.")

        section("7  /etc/fstab")
        try:
            with open('/etc/fstab') as fh:
                for line in fh:
                    if line.strip() and not line.startswith('#'):
                        log(f"  {line.rstrip()}")
        except Exception:
            pass

        section("8  NETZWERK")
        log(run(['ip', 'addr', 'show']))
        log(run(['ip', 'route']))

        section("9  SCHLÜSSELPAKETE")
        for pkg in ['python3', 'gddrescue', 'testdisk', 'smartmontools',
                    'hdparm', 'nvme-cli', 'udisks2', 'nala', 'flatpak', 'efibootmgr']:
            r2 = subprocess.run(['dpkg', '-l', pkg], capture_output=True, text=True)
            log(f"  {'✓' if r2.returncode == 0 else '✗'}  {pkg}")

        log(f"\n{'═'*58}\n  Diagnose abgeschlossen: "
            f"{datetime.datetime.now().strftime('%H:%M:%S')}\n"
            f"  TXT:  {self._diag_txt}\n  HTML: {self._diag_html}\n{'═'*58}\n")

        self._export_diag_html()
        try:
            uid = pwd.getpwnam(ORIGINAL_USER).pw_uid
            gid = pwd.getpwnam(ORIGINAL_USER).pw_gid
            for fp in [self._diag_txt, self._diag_html]:
                if os.path.isfile(fp):
                    os.chown(fp, uid, gid)
        except Exception:
            pass
        self.root.after(0, lambda: self.diag_btn.config(state='normal'))
        self.root.after(0, lambda: messagebox.showinfo("Diagnose fertig",
            f"✅ Bericht erstellt!\n\nTXT:  {self._diag_txt}\nHTML: {self._diag_html}"))

    def _diag_write(self, text: str):
        try:
            with open(self._diag_txt, 'a', encoding='utf-8') as f:
                f.write(text)
        except Exception:
            pass

    def _export_diag_html(self):
        try:
            import html as html_mod
            with open(self._diag_txt, 'r', encoding='utf-8') as f:
                txt = f.read()
            safe  = html_mod.escape(txt)
            lines_html = []
            for line in safe.splitlines():
                ll = line.lower()
                if 'failed' in ll or 'error' in ll or '❌' in line:
                    lines_html.append(f'<span class="err">{line}</span>')
                elif 'warn' in ll or '⚠' in line:
                    lines_html.append(f'<span class="warn">{line}</span>')
                elif '✅' in line or '✓' in line:
                    lines_html.append(f'<span class="ok">{line}</span>')
                elif line.startswith(('═','╔','╚')):
                    lines_html.append(f'<span class="head">{line}</span>')
                else:
                    lines_html.append(line)
            body = "\n".join(lines_html)
            ts   = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
            html_content = (
                f'<!DOCTYPE html>\n<html lang="de">\n<head>\n'
                f'<meta charset="UTF-8">\n'
                f'<title>Peeßi Diagnose – {ts}</title>\n'
                f'<style>\n'
                f'body{{background:#1a1a2e;color:#e0e0e0;font-family:monospace;'
                f'font-size:13px;padding:24px;}}\n'
                f'pre{{white-space:pre-wrap;word-break:break-all;}}\n'
                f'.head{{color:#89b4fa;font-weight:bold;}}\n'
                f'.err{{color:#f38ba8;}}\n.warn{{color:#fab387;}}\n.ok{{color:#a6e3a1;}}\n'
                f'h1{{color:#cdd6f4;font-family:sans-serif;border-bottom:2px solid #313244;'
                f'padding-bottom:8px;margin-bottom:16px;}}\n'
                f'.meta{{color:#6c7086;font-size:11px;margin-bottom:20px;}}\n'
                f'</style>\n</head>\n<body>\n'
                f'<h1>🛠️ Peeßi\'s System Multitool – Diagnosebericht</h1>\n'
                f'<div class="meta">Erstellt: {ts} | '
                f'Host: {socket.gethostname()} | User: {ORIGINAL_USER}</div>\n'
                f'<pre>{body}</pre>\n</body>\n</html>'
            )
            with open(self._diag_html, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            print(f"[logs] HTML-Export-Fehler: {e}")

    def _open_diag_html(self):
        if self._diag_html and os.path.isfile(self._diag_html):
            subprocess.Popen(['xdg-open', self._diag_html])
        else:
            messagebox.showinfo("Hinweis", "Bitte zuerst Diagnose erstellen.")


# ══════════════════════════════════════════════════════════════════════════════
#  EINSTELLUNGEN TAB
# ══════════════════════════════════════════════════════════════════════════════
class SettingsTab(GuiBase):
    def __init__(self, nb_main, app):
        super().__init__(app.root, app.settings, app.theme, app._log_widgets)
        self.app = app
        self._build(nb_main)

    def _build(self, nb_main):
        T   = self.theme
        tab = ttk.Frame(nb_main)
        nb_main.add(tab, text="⚙️ Einstellungen")

        # Scrollbarer Bereich
        canvas = tk.Canvas(tab, bg=T["bg"], highlightthickness=0)
        sb     = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        pane_outer = tk.Frame(canvas, bg=T["bg"])
        win = canvas.create_window((0, 0), window=pane_outer, anchor='nw')
        pane_outer.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win, width=e.width))

        pane = tk.Frame(pane_outer, bg=T["bg"])
        pane.pack(fill='both', expand=True, padx=20, pady=16)

        def section(text):
            tk.Frame(pane, bg=T["border"], height=1).pack(fill='x', pady=(14, 4))
            tk.Label(pane, text=text, bg=T["bg"], fg=T["accent"],
                     font=('Arial', 10, 'bold')).pack(anchor='w')

        def row(label, widget_fn):
            f = tk.Frame(pane, bg=T["bg"])
            f.pack(fill='x', pady=4)
            tk.Label(f, text=label, width=32, anchor='w',
                     bg=T["bg"], fg=T["fg"], font=('Arial', 10)).pack(side='left')
            widget_fn(f)
            return f

        def color_row(label, setting_key, default):
            """Zeile mit Farb-Vorschau und Eingabefeld."""
            f = tk.Frame(pane, bg=T["bg"])
            f.pack(fill='x', pady=4)
            tk.Label(f, text=label, width=32, anchor='w',
                     bg=T["bg"], fg=T["fg"], font=('Arial', 10)).pack(side='left')
            var = tk.StringVar(value=self.settings.get(setting_key, default))
            _preview_bg = var.get() if var.get().strip() else T["bg2"]
            preview = tk.Label(f, width=3, bg=_preview_bg, relief='solid', bd=1)
            preview.pack(side='left', padx=(0, 6))
            ent = ttk.Entry(f, textvariable=var, width=10)
            ent.pack(side='left')
            def _update_preview(*_, _p=preview, _v=var, _fb=T["bg2"]):
                try:
                    col = _v.get().strip()
                    _p.config(bg=col if col else _fb)
                except Exception:
                    pass
            var.trace_add('write', _update_preview)
            def _pick():
                from tkinter.colorchooser import askcolor
                result = askcolor(color=var.get(), parent=self.app.root,
                                  title=f"Farbe wählen – {label}")
                if result and result[1]:
                    var.set(result[1])
            ttk.Button(f, text="🎨", width=3, command=_pick).pack(side='left', padx=4)
            tk.Label(f, text="(Hex, z.B. #2c3e50)", bg=T["bg"], fg=T["fg_dim"],
                     font=('Arial', 8)).pack(side='left', padx=4)
            return var

        # ── Abschnitt: Aussehen ──────────────────────────────────────────────
        section("🎨  Aussehen")

        self._set_theme_var = tk.StringVar(value=self.settings.get("theme", "light"))
        row("Theme",
            lambda f: ttk.Combobox(f, textvariable=self._set_theme_var,
                values=["light", "dark"], state='readonly', width=15).pack(side='left'))

        self._set_ui_font_var = tk.IntVar(value=self.settings.get("ui_font_size", 10))
        row("Schriftgröße (UI)",
            lambda f: ttk.Spinbox(f, from_=8, to=18,
                textvariable=self._set_ui_font_var, width=6).pack(side='left'))

        self._set_font_var = tk.IntVar(value=self.settings.get("font_size", 10))
        row("Schriftgröße (Log/Monospace)",
            lambda f: ttk.Spinbox(f, from_=8, to=16,
                textvariable=self._set_font_var, width=6).pack(side='left'))

        self._set_fg_var      = color_row("Schriftfarbe (Haupttext)",
                                          "custom_fg",      "")
        self._set_accent_var  = color_row("Akzentfarbe",
                                          "custom_accent",  "")
        self._set_bg_var      = color_row("Hintergrundfarbe",
                                          "custom_bg",      "")

        tk.Label(pane,
            text="ℹ️  Leer lassen = Theme-Standard verwenden. Neustart empfohlen nach Farbänderung.",
            bg=T["bg"], fg=T["fg_dim"], font=('Arial', 8)).pack(anchor='w', pady=(2, 0))

        # ── Abschnitt: Fenster ───────────────────────────────────────────────
        section("🖥️  Fenster")

        win_sizes = ["1400x900", "1200x800", "1600x1000", "1920x1080", "Maximiert"]
        self._set_winsize_var = tk.StringVar(
            value=self.settings.get("window_size", "1400x900"))
        row("Startgröße",
            lambda f: ttk.Combobox(f, textvariable=self._set_winsize_var,
                values=win_sizes, state='readonly', width=15).pack(side='left'))

        # ── Abschnitt: Verhalten ─────────────────────────────────────────────
        section("⚙️  Verhalten")

        self._set_wipe_var = tk.StringVar(
            value=self.settings.get("default_wipe_method", "quick"))
        row("Standard-Löschmethode",
            lambda f: ttk.Combobox(f, textvariable=self._set_wipe_var,
                values=list(WipeEngine.METHODS.keys()),
                state='readonly', width=20).pack(side='left'))

        self._set_smart_var = tk.IntVar(value=self.settings.get("smart_interval_days", 1))
        row("SMART-Intervall (Tage)",
            lambda f: ttk.Spinbox(f, from_=1, to=30,
                textvariable=self._set_smart_var, width=6).pack(side='left'))

        self._set_notify_var = tk.BooleanVar(value=self.settings.get("notifications", True))
        row("Desktop-Benachrichtigungen",
            lambda f: ttk.Checkbutton(f, variable=self._set_notify_var).pack(side='left'))

        self._set_log_var = tk.IntVar(value=self.settings.get("log_retention_days", 30))
        row("Log-Aufbewahrung (Tage)",
            lambda f: ttk.Spinbox(f, from_=7, to=365,
                textvariable=self._set_log_var, width=6).pack(side='left'))

        tk.Frame(pane, bg=T["border"], height=1).pack(fill='x', pady=14)
        btn_row = tk.Frame(pane, bg=T["bg"])
        btn_row.pack(anchor='w')
        ttk.Button(btn_row, text="💾 Einstellungen speichern",
                   style='Accent.TButton', command=self._save).pack(side='left', padx=(0, 8))
        ttk.Button(btn_row, text="↩️ Auf Standard zurücksetzen",
                   command=self._reset).pack(side='left')

    def _save(self):
        self.settings.update({
            "theme":               self._set_theme_var.get(),
            "font_size":           self._set_font_var.get(),
            "ui_font_size":        self._set_ui_font_var.get(),
            "default_wipe_method": self._set_wipe_var.get(),
            "smart_interval_days": self._set_smart_var.get(),
            "notifications":       self._set_notify_var.get(),
            "log_retention_days":  self._set_log_var.get(),
            "window_size":         self._set_winsize_var.get(),
            "custom_fg":           self._set_fg_var.get().strip(),
            "custom_accent":       self._set_accent_var.get().strip(),
            "custom_bg":           self._set_bg_var.get().strip(),
        })
        save_settings(self.settings)
        # Theme neu laden und ggf. Custom-Farben einsetzen
        new_theme = self._set_theme_var.get()
        self.app.theme = dict(THEMES[new_theme])  # Kopie!
        T = self.app.theme
        if self.settings.get("custom_fg"):
            T["fg"] = T["fg_header"] = self.settings["custom_fg"]
        if self.settings.get("custom_accent"):
            T["accent"] = T["btn_bg"] = self.settings["custom_accent"]
        if self.settings.get("custom_bg"):
            T["bg"] = self.settings["custom_bg"]
        # Fenstergröße anwenden
        ws = self.settings.get("window_size", "1400x900")
        if ws == "Maximiert":
            self.app.root.state('zoomed')
        else:
            try:
                self.app.root.geometry(ws)
            except Exception:
                pass
        self.theme = self.app.theme
        self.apply_theme()
        self.rebuild_log_colors()
        messagebox.showinfo("Gespeichert", "✅ Einstellungen gespeichert.\nNeustart empfohlen für vollständige Wirkung.")

    def _reset(self):
        if not messagebox.askyesno("Zurücksetzen",
                "Alle Einstellungen auf Standardwerte zurücksetzen?"):
            return
        from config import DEFAULT_SETTINGS
        self.settings.update(DEFAULT_SETTINGS)
        self.settings.update({"custom_fg": "", "custom_accent": "", "custom_bg": "",
                               "window_size": "1400x900", "ui_font_size": 10})
        save_settings(self.settings)
        messagebox.showinfo("Zurückgesetzt",
            "✅ Auf Standardwerte zurückgesetzt.\nBitte Programm neu starten.")


# ══════════════════════════════════════════════════════════════════════════════
#  ÜBER-TAB
# ══════════════════════════════════════════════════════════════════════════════
class AboutTab(GuiBase):
    def __init__(self, nb_main, app):
        super().__init__(app.root, app.settings, app.theme, app._log_widgets)
        self._build(nb_main)

    def _build(self, nb_main):
        import base64 as _b64
        from io import BytesIO as _BytesIO
        T   = self.theme
        tab = ttk.Frame(nb_main)
        nb_main.add(tab, text="ℹ️ Über")

        # Scrollbarer Bereich
        canvas = tk.Canvas(tab, bg=T["bg"], highlightthickness=0)
        sb     = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        pane = tk.Frame(canvas, bg=T["bg"])
        win  = canvas.create_window((0, 0), window=pane, anchor='nw')
        pane.bind('<Configure>', lambda e: canvas.configure(
            scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win, width=e.width))

        inner = tk.Frame(pane, bg=T["bg"])
        inner.pack(fill='both', expand=True, padx=40, pady=30)

        # ── Kopfzeile: Avatar links, Info rechts ─────────────────────────────
        header = tk.Frame(inner, bg=T["bg"])
        header.pack(fill='x', pady=(0, 16))

        # Avatar
        _AVATAR_B64 = "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"
        try:
            from PIL import Image as _PILImage, ImageTk as _ImageTk, ImageDraw as _ImageDraw
            img_data = _b64.b64decode(_AVATAR_B64)
            img      = _PILImage.open(_BytesIO(img_data)).convert("RGBA")
            # Runden Rahmen erstellen
            mask = _PILImage.new("L", img.size, 0)
            draw = _ImageDraw.Draw(mask)
            draw.ellipse((0, 0, img.width, img.height), fill=255)
            img.putalpha(mask)
            tk_img = _ImageTk.PhotoImage(img)
            lbl    = tk.Label(header, image=tk_img,
                              bg=T["bg"], bd=0)
            lbl.image = tk_img   # Referenz behalten
            lbl.pack(side='left', padx=(0, 24))
        except Exception:
            # Fallback: Initialen-Kreis wenn PIL nicht verfügbar
            av_canvas = tk.Canvas(header, width=120, height=120,
                                  bg=T["bg"], highlightthickness=0)
            av_canvas.pack(side='left', padx=(0, 24))
            av_canvas.create_oval(5, 5, 115, 115,
                                  fill=T["accent"], outline="")
            av_canvas.create_text(60, 60, text="MP",
                                  fill="#ffffff",
                                  font=('Arial', 32, 'bold'))

        # Info rechts
        info = tk.Frame(header, bg=T["bg"])
        info.pack(side='left', anchor='center')
        tk.Label(info, text=f"🛠️ Peeßi's System Multitool  v{VERSION}",
                 font=('Arial', 20, 'bold'), bg=T["bg"], fg=T["accent"]).pack(anchor='w')
        tk.Label(info, text="Mario Peeß  ·  Großenhain",
                 font=('Arial', 12), bg=T["bg"], fg=T["fg"]).pack(anchor='w', pady=(6, 0))
        email_lbl = tk.Label(info, text="✉️  mapegr@mailbox.org",
                 font=('Arial', 11), bg=T["bg"], fg=T["accent"],
                 cursor='hand2')
        email_lbl.pack(anchor='w')
        email_lbl.bind("<Button-1>", lambda e: webbrowser.open("mailto:mapegr@mailbox.org"))
        tk.Label(info, text="Lizenz: GPLv3 / MIT  ·  Linux Mint / Debian / Ubuntu",
                 font=('Arial', 10), bg=T["bg"], fg=T["fg_dim"]).pack(anchor='w', pady=(4, 0))

        tk.Frame(inner, bg=T["border"], height=1).pack(fill='x', pady=16)

        features = [
            "💾  Datenrettung        –  ddrescue + photorec, Fortschrittsbalken",
            "🧹  Sicheres Löschen   –  dd, DoD 5220.22-M, Gutmann, ATA/NVMe Secure Erase",
            "📊  SMART-Monitor      –  Gesundheitsstatus, Temperatur, SQLite-Verlauf",
            "💿  ISO-Brenner        –  Alle Laufwerke wählbar, SHA256-Prüfung, Verifikation",
            "🔁  USB-Clone          –  1:1-Klon mit cmp-Verifikation (Sub-Tab im ISO-Brenner)",
            "🔗  Partition          –  Einbinden/Aushängen, fstab-Backup automatisch",
            "🖥️  Dashboard          –  CPU, RAM, Swap, Disk, Uptime, bunte Balken",
            "⚙️  System             –  Pflege, Optimierer, Boot-Check, BIOS/EFI, Einmal-Starter",
            "🐧  Eggs-ISO           –  Live-ISO erstellen (Programme/Design/Vollklon), Calamares",
            "🔧  GRUB               –  Boot-Einstellungen, Themes, Backup, System-Analyse (GRUB CC v2.1.1)",
            "🩺  Laufwerk-Diagnose  –  S.M.A.R.T. + Badblocks Oberflächenscan, Log ~/DriveTests/",
            "🌐  Netzwerk           –  Interfaces, Ping, Verbindungen (sortierbar+kopierbar), WLAN-Keys",
            "📋  Logs & Diagnose   –  Viewer mit Farbmarkierung + Suche, HTML-Systembericht",
            "🎨  Dark/Light-Mode   –  Catppuccin Mocha / Standard-Hell, anpassbare Farben",
            "🧹  Freien Speicher löschen  –  sfill + dd, auch auf FAT/NTFS",
            "⚠️  Haftungsausschluss –  Keine Gewährleistung. Backups vor jeder Operation!",
        ]
        for f in features:
            tk.Label(inner, text=f, font=('Arial', 10),
                     bg=T["bg"], fg=T["fg"], anchor='w').pack(anchor='w', pady=2)

        tk.Frame(inner, bg=T["border"], height=1).pack(fill='x', pady=16)
        tk.Label(inner,
            text="Module: config · models · database · security · smart_engine ·\n"
                 "        wipe_engine · recovery_engine · gui_base · gui_drives · gui_system",
            font=('Monospace', 9), bg=T["bg"], fg=T["fg_dim"], justify='left').pack(anchor='w')
