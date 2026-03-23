#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: models.py  –  Datenklassen (DriveInfo, DriveScanner, USBInfo)
"""

import os
import re
import json
import subprocess
from typing import Optional, List
from config import ORIGINAL_USER


class DriveInfo:
    def __init__(self, device, model, size, fs_type, mount_point, removable, is_usb):
        self.device      = device
        self.model       = (model or "Unbekannt").strip()
        self.size        = size
        self.fs_type     = fs_type or ""
        self.mount_point = mount_point or ""
        self.removable   = removable
        self.is_usb      = is_usb
        self.is_ssd      = self._detect_ssd()
        self.is_nvme     = device.startswith('/dev/nvme')
        self.is_system_drive = self._is_system_drive()

    def _detect_ssd(self) -> bool:
        name = os.path.basename(self.device)
        rotational = f"/sys/block/{name}/queue/rotational"
        try:
            with open(rotational) as f:
                return f.read().strip() == "0"
        except Exception:
            return (self.device.startswith('/dev/nvme') or
                    self.device.startswith('/dev/mmcblk'))

    def _is_system_drive(self) -> bool:
        system_mounts = ['/', '/boot', '/home', '/usr', '/var', '/tmp', '/efi', '/boot/efi']
        if self.mount_point:
            for m in system_mounts:
                if self.mount_point.startswith(m):
                    return True
        try:
            root_dev = subprocess.run(
                ['findmnt', '-n', '-o', 'SOURCE', '/'],
                capture_output=True, text=True, check=True
            ).stdout.strip()
            if root_dev and root_dev.startswith(self.device):
                return True
        except Exception:
            pass
        return False

    def get_size_human(self) -> str:
        if not self.size:
            return "Unbekannt"
        try:
            b = int(self.size)
        except (ValueError, TypeError):
            # Größe ist bereits ein String wie '238.5G' – direkt zurückgeben
            try:
                import re as _re
                s = str(self.size).strip()
                m = _re.match(r"^([\d.,]+)\s*([KMGTP]?)i?B?$", s, _re.IGNORECASE)
                if m:
                    val  = float(m.group(1).replace(",", "."))
                    unit = m.group(2).upper()
                    mult = {"K":1024,"M":1024**2,"G":1024**3,"T":1024**4,"P":1024**5}.get(unit,1)
                    b = int(val * mult)
                else:
                    return s
            except Exception:
                return str(self.size)
        for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PiB"

    def get_type_label(self) -> str:
        if self.is_nvme:   return "NVMe SSD"
        if self.is_ssd:    return "SSD"
        if self.is_usb:    return "USB"
        if self.removable: return "Wechsel"
        return "HDD"


class DriveScanner:
    def __init__(self, sec):
        self.sec = sec

    def scan(self) -> List[DriveInfo]:
        drives = []
        try:
            r = subprocess.run(
                ['lsblk', '-J', '-b', '-o', 'NAME,MODEL,SIZE,FSTYPE,MOUNTPOINT,TYPE,RM'],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                for dev in json.loads(r.stdout).get('blockdevices', []):
                    if dev.get('type') == 'disk':
                        d = self._make(dev)
                        if d:
                            drives.append(d)
            self.sec.log_action("DRIVE_SCAN", details=f"{len(drives)} drives")
        except Exception as e:
            self.sec.log_action("DRIVE_SCAN_ERROR", details=str(e))
        return drives

    def _is_usb(self, name: str) -> bool:
        try:
            return 'usb' in os.path.realpath(f'/sys/block/{name}')
        except Exception:
            return False

    def _make(self, d: dict) -> Optional[DriveInfo]:
        try:
            name = d.get('name', '')
            if not name:
                return None
            return DriveInfo(
                device      = f"/dev/{name}",
                model       = d.get('model') or "Unbekannt",
                size        = d.get('size', 0),
                fs_type     = d.get('fstype', ''),
                mount_point = d.get('mountpoint', ''),
                removable   = d.get('rm', '0') == '1',
                is_usb      = self._is_usb(name),
            )
        except Exception as e:
            self.sec.log_action("DRIVE_CREATE_ERROR", details=str(e))
            return None


class USBInfo:
    CLASS_MAP = {
        "00":"Unbekannt","01":"Audio","02":"Kommunikation",
        "03":"HID (Maus/Tastatur)","06":"Bildgerät","07":"Drucker",
        "08":"Massenspeicher","09":"Hub","0E":"Video",
        "E0":"WLAN/Bluetooth","FF":"Herstellerspezifisch"
    }

    def __init__(self, sec):
        self.sec = sec

    def get_devices(self) -> list:
        devices = []
        try:
            lines = subprocess.check_output(['lsusb'], timeout=5).decode().splitlines()
            for line in lines:
                m = re.match(
                    r'Bus (\d+) Device (\d+): ID ([0-9a-fA-F]{4}):([0-9a-fA-F]{4}) (.*)', line)
                if m:
                    bus, dev, vid, pid, desc = m.groups()
                    cls = self._get_class(bus, dev)
                    devices.append({
                        'bus': bus, 'device': dev,
                        'vendor_id': vid, 'product_id': pid,
                        'description': desc, 'full_id': f"{vid}:{pid}",
                        'device_class': cls,
                        'device_type': self.CLASS_MAP.get(cls.upper(), f"0x{cls}")
                    })
        except Exception as e:
            self.sec.log_action("USB_SCAN_ERROR", details=str(e))
        return devices

    def _get_class(self, bus, device) -> str:
        try:
            out = subprocess.check_output(
                ['lsusb', '-s', f"{bus}:{device}", '-v'],
                timeout=5, stderr=subprocess.DEVNULL).decode()
            m = re.search(r'bDeviceClass\s+0x([0-9a-fA-F]{2})', out)
            return m.group(1) if m else "00"
        except Exception:
            return "00"

    def get_details(self, full_id: str) -> str:
        try:
            r = subprocess.run(['lsusb', '-v', '-d', full_id],
                               capture_output=True, text=True, timeout=10)
            return r.stdout
        except Exception as e:
            return f"Fehler: {e}"
