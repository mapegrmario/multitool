#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: wipe_engine.py  –  Sicheres Löschen (dd, shred, ATA/NVMe Secure Erase)
"""

import os
import re
import subprocess
import threading
from typing import Callable, Optional


class WipeEngine:
    METHODS = {
        'quick':             {'name': 'Schnell (Nullen, 1×)',          'passes': 1},
        'dod':               {'name': 'DoD 5220.22-M (3 Durchgänge)',  'passes': 3},
        'gutmann':           {'name': 'Gutmann (35 Durchgänge)',        'passes': 35},
        'secure_erase_hdd':  {'name': 'ATA Secure Erase (HDD)',         'passes': 1},
        'secure_erase_nvme': {'name': 'NVMe Secure Erase (SSD)',        'passes': 1},
    }
    SSD_RECOMMENDED = ('secure_erase_hdd', 'secure_erase_nvme', 'quick')

    def __init__(self, sec, progress_cb: Optional[Callable] = None):
        self.sec         = sec
        self.progress_cb = progress_cb
        self.is_wiping   = False
        self.should_stop = False

    def _log(self, msg: str):
        if self.progress_cb:
            self.progress_cb(msg)

    def wipe(self, drive, method: str = 'quick') -> bool:
        if self.is_wiping:
            return False
        self.is_wiping   = True
        self.should_stop = False
        try:
            if not self._unmount(drive.device):
                self._log("❌ Unmount fehlgeschlagen – Abbruch.")
                return False
            if method == 'secure_erase_hdd':
                ok = self._ata_secure_erase(drive)
            elif method == 'secure_erase_nvme':
                ok = self._nvme_secure_erase(drive)
            elif method == 'quick':
                ok = self._dd_wipe(drive)
            else:
                ok = self._shred_wipe(drive, method)
            self.sec.log_action("WIPE_" + ("OK" if ok else "FAIL"), drive.device, method)
            return ok
        except Exception as e:
            self.sec.log_action("WIPE_ERROR", drive.device, str(e))
            return False
        finally:
            self.is_wiping = False

    def _unmount(self, device: str) -> bool:
        try:
            base = os.path.basename(device)
            r = subprocess.run(['lsblk', '-ln', '-o', 'NAME,MOUNTPOINT'],
                               capture_output=True, text=True, timeout=10)
            for line in r.stdout.strip().split('\n'):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    name, mnt = parts
                    if name.startswith(base) and mnt and mnt != '[SWAP]':
                        part = f"/dev/{name}"
                        self._log(f"Unmounte {part}...")
                        res = subprocess.run(['umount', part],
                                             capture_output=True, timeout=15)
                        if res.returncode != 0:
                            res2 = subprocess.run(
                                ['udisksctl', 'unmount', '-b', part],
                                capture_output=True, timeout=15)
                            if res2.returncode != 0:
                                self._log(f"⚠️ Konnte {part} nicht unmounten.")
                                return False
            return True
        except Exception as e:
            self._log(f"Unmount-Fehler: {e}")
            return False

    def _ata_secure_erase(self, drive) -> bool:
        dev = drive.device
        self._log(f"ATA Secure Erase auf {dev}...")
        try:
            subprocess.run(['hdparm', '--user-master', 'u',
                            '--security-set-pass', 'p', dev],
                           check=True, capture_output=True, timeout=30)
            subprocess.run(['hdparm', '--user-master', 'u',
                            '--security-erase', 'p', dev],
                           check=True, capture_output=True, timeout=7200)
            self._log("✅ ATA Secure Erase abgeschlossen.")
            return True
        except subprocess.CalledProcessError as e:
            self._log(f"❌ Fehler: {e.stderr.decode() if e.stderr else 'unbekannt'}")
            return False

    def _nvme_secure_erase(self, drive) -> bool:
        dev = drive.device
        if not dev.startswith('/dev/nvme'):
            self._log("❌ Kein NVMe-Gerät.")
            return False
        self._log(f"NVMe Secure Erase auf {dev}...")
        try:
            subprocess.run(['nvme', 'format', dev, '--ses=1'],
                           check=True, capture_output=True, timeout=7200)
            self._log("✅ NVMe Secure Erase abgeschlossen.")
            return True
        except subprocess.CalledProcessError as e:
            self._log(f"❌ Fehler: {e.stderr.decode() if e.stderr else 'unbekannt'}")
            return False

    def _dd_wipe(self, drive) -> bool:
        dev = drive.device
        try:
            total = 0
            try:
                total = int(subprocess.check_output(
                    ['blockdev', '--getsize64', dev], timeout=5).decode().strip())
            except Exception:
                pass

            proc = subprocess.Popen(
                ['dd', 'if=/dev/zero', f'of={dev}', 'bs=4M', 'status=progress'],
                stderr=subprocess.PIPE, universal_newlines=True
            )
            for line in proc.stderr:
                if self.should_stop:
                    proc.terminate()
                    self._log("⛔ Abgebrochen.")
                    return False
                line = line.strip()
                if line and ('byte' in line.lower() or 'GB' in line or 'MB' in line):
                    m = re.search(r'(\d+)\s+bytes', line)
                    if m and total > 0:
                        pct = min(int(int(m.group(1)) / total * 100), 100)
                        self._log(f"dd: {line}  [{pct}%]")
                    else:
                        self._log(f"dd: {line}")
            proc.wait()
            return proc.returncode == 0
        except Exception as e:
            self._log(f"dd-Fehler: {e}")
            return False

    def _shred_wipe(self, drive, method: str) -> bool:
        passes = self.METHODS.get(method, {}).get('passes', 1)
        try:
            proc = subprocess.Popen(
                ['shred', '-vfz', f'-n{passes}', drive.device],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            for line in proc.stdout:
                if self.should_stop:
                    proc.terminate()
                    self._log("⛔ Abgebrochen.")
                    return False
                self._log(line.strip())
            proc.wait()
            return proc.returncode == 0
        except Exception as e:
            self._log(f"shred-Fehler: {e}")
            return False

    def stop(self):
        self.should_stop = True
