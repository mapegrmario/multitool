#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: smart_engine.py  –  SMART-Auswertung mit korrekter Exit-Code-Prüfung

smartctl Exit-Codes (Bit-Flags):
  Bit 0 (1)  : Kommando-Fehler
  Bit 1 (2)  : Gerät öffnen fehlgeschlagen
  Bit 2 (4)  : Disk FAILING (Vorhersage)
  Bit 3 (8)  : Pre-failure Attribute unterhalb Schwelle → KRITISCH
  Bit 4 (16) : Letzte Selbsttests schlugen fehl
  Bit 5 (32) : Gerät hat Fehlerprotokoll
  Bit 6 (64) : Gerät führt Selbsttest durch
  Bit 7 (128): Gerät gesperrt

  Code 0  = alles in Ordnung (PASSED)
  Code 4  = nur Vorhersage-Warnung, Hardware noch OK
  Code 8  = KRITISCH: Attribut unter Schwelle (echter Fehler)
  Code 12 = Code 4 + Code 8 kombiniert
"""

import re
import subprocess
from typing import Tuple


# smartctl Exit-Code Bit-Flags
_BIT_DISK_FAILING    = 0x04   # Pre-failure Prediction
_BIT_THRESH_EXCEEDED = 0x08   # Attribut unterhalb Schwelle – echte Gefahr
_BIT_SELFTEST_FAIL   = 0x10   # letzter Selbsttest fehlgeschlagen
_BIT_ERROR_LOG       = 0x20   # Fehlerprotokoll vorhanden


def query_smart(device: str, timeout: int = 10) -> Tuple[str, str, int]:
    """
    Führt smartctl -H -A aus und gibt (status_text, temperatur, exit_code) zurück.

    status_text:
      "✅ PASSED"             – alles in Ordnung
      "⚠️ Warnung (Code N)"   – nur Vorhersage oder Fehlerlog, Laufwerk noch funktionstüchtig
      "❌ FAILED (Code N)"    – Attribut wirklich unterhalb Schwelle → dringend sichern!
      "—"                    – smartctl nicht vorhanden oder Timeout
    """
    if not _smartctl_available():
        return "—", "—", -1

    try:
        r = subprocess.run(
            ['smartctl', '-H', '-A', device],
            capture_output=True, text=True, timeout=timeout
        )
        code = r.returncode
        text = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "—", "—", -1
    except FileNotFoundError:
        return "—", "—", -1
    except Exception:
        return "—", "—", -1

    # Temperatur aus Attributtabelle lesen
    temp = _parse_temperature(r.stdout)

    # Exit-Code sauber auswerten
    if code == 0:
        status = "✅ PASSED"
    elif code & _BIT_THRESH_EXCEEDED:
        # Wirklich kritisch: Attribut unter Schwelle
        status = f"❌ FAILED (Code {code})"
    elif code & (_BIT_DISK_FAILING | _BIT_SELFTEST_FAIL | _BIT_ERROR_LOG):
        # Nur Warnung: Vorhersage oder Fehlerlog, aber noch keine Ausfallschwelle
        status = f"⚠️ Warnung (Code {code})"
    elif code >= 64:
        # Selbsttest läuft oder Gerät gesperrt – unkritisch
        status = f"ℹ️ Info (Code {code})"
    else:
        # Unbekannter Code – konservativ als Warnung einstufen
        status = f"⚠️ Unbekannt (Code {code})"

    return status, temp, code


def query_smart_attributes(device: str, timeout: int = 10) -> list:
    """
    Gibt eine Liste von SMART-Attributen zurück.
    Jedes Element: dict mit id, name, value, worst, thresh, raw, status, tag
    """
    attrs = []
    if not _smartctl_available():
        return attrs

    try:
        r = subprocess.run(
            ['smartctl', '-A', '-H', device],
            capture_output=True, text=True, timeout=timeout
        )
    except Exception:
        return attrs

    for line in r.stdout.splitlines():
        m = re.match(
            r'\s*(\d+)\s+(\S+)\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)\s+\S+\s+\S+\s+\S+\s+(\S+)',
            line
        )
        if not m:
            continue
        id_, name, val, worst, thresh, raw = m.groups()
        v, t = int(val), int(thresh)

        if v <= t:
            status, tag = "❌ KRITISCH", "crit"
        elif v <= t + 10:
            status, tag = "⚠️ Warnung", "warn"
        else:
            status, tag = "", ""

        attrs.append({
            'id': id_, 'name': name,
            'value': val, 'worst': worst, 'thresh': thresh,
            'raw': raw, 'status': status, 'tag': tag
        })

    return attrs


def is_failed(status_text: str) -> bool:
    """True nur bei echtem FAILED (Attribut unter Schwelle), nicht bei Warnungen."""
    return "❌ FAILED" in status_text


def _parse_temperature(output: str) -> str:
    """Liest Temperatur aus smartctl Ausgabe. Sucht Airflow_Temp oder Temperature_*."""
    # Priorität 1: Temperature_Celsius Attributzeile (Spalte raw)
    for line in output.splitlines():
        if re.search(r'Temperature_Celsius|Airflow_Temperature', line, re.IGNORECASE):
            parts = line.split()
            # Raw-Wert ist die letzte Spalte, kann "38 (Min/Max 20/45)" sein
            if parts:
                raw = parts[-1]
                # Nimm nur die führende Zahl
                m = re.match(r'^(\d+)', raw)
                if m:
                    val = int(m.group(1))
                    # Plausibilitätscheck: 1–100°C
                    if 1 <= val <= 100:
                        return f"{val}°C"
    # Priorität 2: "Temperature:" Zeile aus -H Ausgabe
    for line in output.splitlines():
        m = re.search(r'Temperature[:\s]+(\d+)\s*(?:Celsius|C)', line, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 100:
                return f"{val}°C"
    return "—"


def _smartctl_available() -> bool:
    import shutil
    return shutil.which('smartctl') is not None
