#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: config.py  –  Konstanten, Themes, Einstellungen
"""

import os
import json
import getpass
import pwd
from pathlib import Path

VERSION = "1.0 Alpha"

# ── Benutzer & Pfade ──────────────────────────────────────────────────────────
def get_original_user() -> str:
    if os.environ.get('SUDO_USER'):
        return os.environ['SUDO_USER']
    if 'PKEXEC_UID' in os.environ:
        try:
            return pwd.getpwuid(int(os.environ['PKEXEC_UID'])).pw_name
        except (KeyError, ValueError):
            pass
    return os.environ.get('USER', getpass.getuser())

ORIGINAL_USER = get_original_user()
USER_HOME     = Path(os.path.expanduser(f"~{ORIGINAL_USER}"))
RECOVERY_ROOT = USER_HOME / "Datenrettung_Ergebnisse"
CONFIG_DIR    = USER_HOME / ".config" / "peessi-multitool"
CONFIG_FILE   = CONFIG_DIR / "settings.json"
SMART_DB_FILE = CONFIG_DIR / "smart_history.db"
ERROR_LOG_FILE= str(USER_HOME / "peessi_multitool_fehler.log")
INSTALL_DIR   = Path("/usr/local/lib/peessi-multitool")

CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def get_lib_dir() -> str:
    if 'PEESSI_APPDIR' in os.environ and os.path.isdir(os.environ['PEESSI_APPDIR']):
        return os.environ['PEESSI_APPDIR']
    if os.path.isdir(str(INSTALL_DIR)):
        return str(INSTALL_DIR)
    return os.path.dirname(os.path.abspath(__file__))

LIB_DIR = get_lib_dir()

# ── Themes ───────────────────────────────────────────────────────────────────
THEMES = {
    "light": {
        "bg": "#f0f0f0", "bg2": "#ffffff", "bg_header": "#2c3e50",
        "fg": "#2c3e50", "fg_header": "#ffffff", "fg_dim": "#7f8c8d",
        "accent": "#3498db", "accent2": "#2980b9",
        "success": "#27ae60", "warning": "#e67e22", "danger": "#e74c3c",
        "log_bg": "#f8f9fa", "log_fg": "#2c3e50",
        "sel_bg": "#3498db", "sel_fg": "#ffffff", "border": "#dee2e6",
        "tag_system": "#f9e79f", "tag_internal": "#f5b7b1",
        "tag_removable": "#a9dfbf", "btn_bg": "#3498db", "btn_fg": "#ffffff",
    },
    "dark": {
        "bg": "#1e1e2e", "bg2": "#2a2a3e", "bg_header": "#11111b",
        "fg": "#cdd6f4", "fg_header": "#cdd6f4", "fg_dim": "#6c7086",
        "accent": "#89b4fa", "accent2": "#74c7ec",
        "success": "#a6e3a1", "warning": "#fab387", "danger": "#f38ba8",
        "log_bg": "#181825", "log_fg": "#cdd6f4",
        "sel_bg": "#89b4fa", "sel_fg": "#1e1e2e", "border": "#313244",
        "tag_system": "#45475a", "tag_internal": "#3d2436",
        "tag_removable": "#1e3a2e", "btn_bg": "#89b4fa", "btn_fg": "#1e1e2e",
    }
}

DEFAULT_SETTINGS = {
    "theme": "light", "font_size": 10,
    "ui_font_size": 10,
    "default_wipe_method": "quick", "smart_interval_days": 1,
    "notifications": True, "backup_target": str(USER_HOME / "Backups"),
    "log_retention_days": 30,
    "window_size": "1400x900",
    "custom_fg": "", "custom_accent": "", "custom_bg": "",
}

def load_settings() -> dict:
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                merged = DEFAULT_SETTINGS.copy()
                merged.update(data)
                return merged
    except Exception:
        pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"[config] Einstellungen nicht speicherbar: {e}")
