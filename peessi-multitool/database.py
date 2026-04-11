#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peeßi's System Multitool v4.1
Modul: database.py  –  SMART-Verlaufsdatenbank (SQLite)
"""

import sqlite3
import datetime
from config import SMART_DB_FILE


class SmartDatabase:
    def __init__(self):
        self.db_path = str(SMART_DB_FILE)
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")  # HP-2
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS smart_history (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp   TEXT    NOT NULL,
                        device      TEXT    NOT NULL,
                        attribute   TEXT    NOT NULL,
                        raw_value   INTEGER,
                        normalized  INTEGER
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"[database] SMART-DB Fehler: {e}")

    def record(self, device: str, attributes: dict):
        ts = datetime.datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")  # HP-2
                for attr, vals in attributes.items():
                    conn.execute(
                        "INSERT INTO smart_history "
                        "(timestamp,device,attribute,raw_value,normalized) "
                        "VALUES (?,?,?,?,?)",
                        (ts, device, attr, vals.get("raw"), vals.get("normalized"))
                    )
                conn.commit()
        except Exception as e:
            print(f"[database] SMART write error: {e}")

    def get_history(self, device: str, attribute: str, days: int = 30) -> list:
        since = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")  # HP-2
                rows = conn.execute(
                    "SELECT timestamp, raw_value FROM smart_history "
                    "WHERE device=? AND attribute=? AND timestamp>? ORDER BY timestamp",
                    (device, attribute, since)
                ).fetchall()
            return rows
        except Exception:
            return []

    def get_devices(self) -> list:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")  # HP-2
                rows = conn.execute(
                    "SELECT DISTINCT device FROM smart_history ORDER BY device"
                ).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []

    def get_attributes(self, device: str) -> list:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")  # HP-2
                rows = conn.execute(
                    "SELECT DISTINCT attribute FROM smart_history WHERE device=?",
                    (device,)
                ).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []
