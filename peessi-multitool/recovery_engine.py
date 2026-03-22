#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: recovery_engine.py  –  Datenrettung via ddrescue + photorec
"""

import os
import re
import time
import shutil
import subprocess
import threading
from typing import Optional, Callable
from config import RECOVERY_ROOT, ORIGINAL_USER


class RecoveryEngine:
    def __init__(self, sec, progress_cb: Optional[Callable] = None,
                 progress_pct_cb: Optional[Callable] = None):
        self.sec           = sec
        self.progress_cb   = progress_cb
        self.progress_pct  = progress_pct_cb
        self.is_recovering = False
        self.should_stop   = False
        self.current_proc  = None

    def _log(self, msg: str):
        if self.progress_cb:
            self.progress_cb(msg)

    def recover(self, source_dev: str) -> bool:
        if self.is_recovering:
            return False
        self.is_recovering = True
        self.should_stop   = False
        self.current_proc  = None

        try:
            import datetime
            now         = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
            session_dir = RECOVERY_ROOT / f"Rettung_{now}"
            session_dir.mkdir(parents=True, exist_ok=True)
            self._chown_dir(RECOVERY_ROOT)
            self._chown_dir(session_dir)

            img_file  = session_dir / "sicherung.img"
            map_file  = session_dir / "protokoll.map"
            log_file  = session_dir / "debug.log"
            files_dir = session_dir / "Wiederhergestellte_Dateien"
            files_dir.mkdir(exist_ok=True)

            total_bytes = 0
            try:
                total_bytes = int(subprocess.check_output(
                    ['blockdev', '--getsize64', source_dev], timeout=5
                ).decode().strip())
            except Exception:
                pass

            # Phase 1: SMART
            self._log("── Phase 1: SMART-Diagnose ──")
            self.sec.log_action("RECOVERY_START", source_dev)
            r = subprocess.run(['smartctl', '-a', source_dev],
                               capture_output=True, text=True)
            for line in r.stdout.splitlines():
                if any(k in line for k in ('Reallocated', 'Pending', 'Uncorrectable')):
                    self._log(f"SMART: {line.strip()}")
            if self.should_stop:
                return self._abort(source_dev)

            # Phase 2: ddrescue schnell
            self._log("── Phase 2: ddrescue (Durchlauf 1 – schnell) ──")
            self.sec.log_action("RECOVERY_PHASE2", source_dev)
            cmd1 = ['ddrescue', '-n', '-v', source_dev, str(img_file), str(map_file)]
            if not self._run_ddrescue(cmd1, log_file, total_bytes, phase_offset=0):
                return False
            if self.should_stop:
                return self._abort(source_dev)

            # Phase 3: ddrescue intensiv
            self._log("── Phase 3: ddrescue (Durchlauf 2 – intensiv) ──")
            self.sec.log_action("RECOVERY_PHASE3", source_dev)
            cmd2 = ['ddrescue', '-r3', '-v', source_dev, str(img_file), str(map_file)]
            if not self._run_ddrescue(cmd2, log_file, total_bytes, phase_offset=50):
                return False
            if self.should_stop:
                return self._abort(source_dev)

            # Phase 4: photorec
            self._log("── Phase 4: Dateiwiederherstellung (photorec) ──")
            self.sec.log_action("RECOVERY_PHASE4", source_dev)
            photorec_cmd = [
                'photorec', '/log', '/d', str(files_dir),
                '/cmd', str(img_file), 'partition_none,search'
            ]
            proc = subprocess.Popen(photorec_cmd,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1)
            self.current_proc = proc
            for line in proc.stdout:
                if self.should_stop:
                    proc.terminate()
                    break
                if any(k in line for k in ('Recovered', 'ext2', 'FAT', 'NTFS')):
                    self._log(f"photorec: {line.strip()}")
            proc.wait()
            self.current_proc = None

            if self.should_stop:
                return self._abort(source_dev, "photorec")

            if self.progress_pct:
                self.progress_pct(100)

            self._log("✅ RETTUNG ERFOLGREICH ABGESCHLOSSEN!")
            self.sec.log_action("RECOVERY_COMPLETED", source_dev)
            self._chown_tree(session_dir)

            try:
                subprocess.run(['sudo', '-u', ORIGINAL_USER, 'xdg-open', str(files_dir)],
                               timeout=5)
            except Exception:
                pass
            return True

        except Exception as e:
            self._log(f"❌ KRITISCHER FEHLER: {e}")
            self.sec.log_action("RECOVERY_ERROR", source_dev, str(e))
            return False
        finally:
            self.is_recovering = False
            self.current_proc  = None

    def _run_ddrescue(self, cmd, log_file, total_bytes, phase_offset=0) -> bool:
        try:
            with open(log_file, "a") as lf:
                lf.write(f"\n--- {' '.join(cmd)}\n")
        except Exception:
            pass

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1)
        self.current_proc = proc
        for line in proc.stdout:
            if self.should_stop:
                proc.terminate()
                break
            try:
                with open(log_file, "a") as lf:
                    lf.write(line)
            except Exception:
                pass
            if 'rescued:' in line:
                self._log(f"ddrescue: {line.strip()}")
                pct = self._parse_ddrescue_pct(line, total_bytes)
                if pct is not None and self.progress_pct:
                    self.progress_pct(phase_offset + pct / 2)
        proc.wait()
        self.current_proc = None
        return not self.should_stop

    def _parse_ddrescue_pct(self, line: str, total_bytes: int):
        m = re.search(r'rescued:\s+([\d.]+)\s*(B|kB|MB|GB|TB)', line, re.IGNORECASE)
        if m and total_bytes > 0:
            val  = float(m.group(1))
            unit = m.group(2).upper()
            mult = {'B':1,'KB':1024,'MB':1024**2,'GB':1024**3,'TB':1024**4}.get(unit, 1)
            return min(val * mult / total_bytes * 100, 100.0)
        return None

    def _abort(self, device, stage=""):
        self._log(f"⛔ Rettung abgebrochen{' (' + stage + ')' if stage else ''}.")
        self.sec.log_action("RECOVERY_ABORTED", device, stage)
        return False

    def _chown_dir(self, path):
        try:
            shutil.chown(path, user=ORIGINAL_USER, group=ORIGINAL_USER)
        except Exception:
            pass

    def _chown_tree(self, root):
        try:
            for r, dirs, files in os.walk(root):
                for d in dirs:
                    self._chown_dir(os.path.join(r, d))
                for f in files:
                    self._chown_dir(os.path.join(r, f))
        except Exception:
            pass

    def stop(self):
        self.should_stop = True
        if self.current_proc and self.current_proc.poll() is None:
            self._log("⛔ Abbruch – bitte warten...")
            self.current_proc.terminate()
            def _force():
                time.sleep(5)
                if self.current_proc and self.current_proc.poll() is None:
                    self.current_proc.kill()
            threading.Thread(target=_force, daemon=True).start()
