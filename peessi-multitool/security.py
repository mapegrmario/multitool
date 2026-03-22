#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: security.py  –  SecurityManager, Audit-Log, fstab-Backup
"""

import os
import shutil
import datetime
import getpass
from typing import Optional
from config import ORIGINAL_USER


class SecurityManager:
    def __init__(self):
        self.log_file = f"/var/log/peessi_multitool_{ORIGINAL_USER}.log"
        self._init_log()

    def _init_log(self):
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            if not os.path.exists(self.log_file):
                with open(self.log_file, 'w') as f:
                    f.write(f"Peeßi's System Multitool v4.1 – Audit Log\n{'='*45}\n\n")
        except PermissionError:
            self.log_file = f"/tmp/peessi_multitool_{ORIGINAL_USER}.log"
            try:
                with open(self.log_file, 'w') as f:
                    f.write("Peeßi's System Multitool v4.1 – Audit Log\n\n")
            except Exception:
                self.log_file = None

    def log_action(self, action: str, device: str = None, details: str = None):
        if not self.log_file:
            return
        ts    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user  = getpass.getuser()
        entry = f"[{ts}] USER:{user} | {action}"
        if device:  entry += f" | DEV:{device}"
        if details: entry += f" | {details}"
        try:
            with open(self.log_file, 'a') as f:
                f.write(entry + "\n")
        except Exception:
            pass

    @staticmethod
    def backup_fstab() -> Optional[str]:
        """Erstellt ein Backup von /etc/fstab vor jeder Änderung."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f"/etc/fstab.bak.{ts}"
        try:
            shutil.copy2("/etc/fstab", backup)
            return backup
        except Exception:
            return None
