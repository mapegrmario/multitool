"""
i18n.py – Zweisprachigkeit für Peeßi's System Multitool v4.1
Unterstützte Sprachen: Deutsch (de) | English (en)
Verwendung:
    from i18n import T, set_lang
    set_lang("en")
    print(T("btn_refresh"))   # → "Refresh"
    set_lang("de")
    print(T("btn_refresh"))   # → "Aktualisieren"
"""

# Aktuelle Sprache (wird von set_lang() gesetzt)
_LANG = "de"

# ═══════════════════════════════════════════════════════════════════════════
#  ÜBERSETZUNGSTABELLE
#  Schlüssel: kurze interne ID (snake_case)
#  Werte:     {"de": "...", "en": "..."}
# ═══════════════════════════════════════════════════════════════════════════
_STRINGS: dict[str, dict[str, str]] = {

    # ── Allgemeine Buttons ──────────────────────────────────────────────
    "btn_refresh":        {"de": "🔄 Aktualisieren",       "en": "🔄 Refresh"},
    "btn_start":          {"de": "▶ Starten",               "en": "▶ Start"},
    "btn_stop":           {"de": "⏹ Stopp",                 "en": "⏹ Stop"},
    "btn_cancel":         {"de": "❌ Abbrechen",             "en": "❌ Cancel"},
    "btn_save":           {"de": "💾 Speichern",             "en": "💾 Save"},
    "btn_delete":         {"de": "🗑 Löschen",               "en": "🗑 Delete"},
    "btn_copy":           {"de": "📋 Kopieren",              "en": "📋 Copy"},
    "btn_clear":          {"de": "🗑 Leeren",                "en": "🗑 Clear"},
    "btn_close":          {"de": "Schließen",                "en": "Close"},
    "btn_install":        {"de": "⚙️ Installieren",          "en": "⚙️ Install"},
    "btn_backup":         {"de": "💾 Backup",                "en": "💾 Backup"},
    "btn_restore":        {"de": "♻ Wiederherstellen",       "en": "♻ Restore"},
    "btn_status":         {"de": "🔄 Status",                "en": "🔄 Status"},
    "btn_run_now":        {"de": "▶ Jetzt ausführen",        "en": "▶ Run now"},

    # ── Allgemeine Labels / Meldungen ───────────────────────────────────
    "lbl_device":         {"de": "Laufwerk",                 "en": "Device"},
    "lbl_size":           {"de": "Größe",                    "en": "Size"},
    "lbl_type":           {"de": "Typ",                      "en": "Type"},
    "lbl_model":          {"de": "Modell",                   "en": "Model"},
    "lbl_status":         {"de": "Status",                   "en": "Status"},
    "lbl_path":           {"de": "Pfad",                     "en": "Path"},
    "lbl_name":           {"de": "Name",                     "en": "Name"},
    "lbl_source":         {"de": "Quelle",                   "en": "Source"},
    "lbl_target":         {"de": "Ziel",                     "en": "Target"},
    "lbl_output":         {"de": "Ausgabe",                  "en": "Output"},
    "lbl_options":        {"de": "Optionen",                 "en": "Options"},
    "lbl_info":           {"de": "Information",              "en": "Information"},
    "lbl_warning":        {"de": "Warnung",                  "en": "Warning"},
    "lbl_error":          {"de": "Fehler",                   "en": "Error"},
    "lbl_success":        {"de": "Erfolgreich",              "en": "Success"},
    "lbl_loading":        {"de": "Lade...",                  "en": "Loading..."},
    "lbl_not_installed":  {"de": "Nicht installiert",        "en": "Not installed"},
    "lbl_language":       {"de": "Sprache",                  "en": "Language"},

    # ── Tabs ────────────────────────────────────────────────────────────
    "tab_dashboard":      {"de": "🖥️ Dashboard",             "en": "🖥️ Dashboard"},
    "tab_drives":         {"de": "💿 Laufwerke",             "en": "💿 Drives"},
    "tab_system":         {"de": "⚙️ System",                "en": "⚙️ System"},
    "tab_network":        {"de": "🌐 Netzwerk",              "en": "🌐 Network"},
    "tab_logs":           {"de": "📋 Logs & Diagnose",       "en": "📋 Logs & Diagnostics"},
    "tab_settings":       {"de": "⚙️ Einstellungen",         "en": "⚙️ Settings"},
    "tab_about":          {"de": "ℹ️ Über",                  "en": "ℹ️ About"},
    "tab_advanced":       {"de": "🔧 Erweitert",             "en": "🔧 Advanced"},
    "tab_cleanup":        {"de": "🧹 Systempflege",          "en": "🧹 System Cleanup"},
    "tab_boot":           {"de": "🥾 Boot-Check",            "en": "🥾 Boot Check"},
    "tab_bios":           {"de": "⚙️ BIOS/EFI",             "en": "⚙️ BIOS/EFI"},
    "tab_update_shut":    {"de": "🔄 Update & Shutdown",     "en": "🔄 Update & Shutdown"},
    "tab_once_starter":   {"de": "🚀 Einmal-Starter",        "en": "🚀 Once-Starter"},
    "tab_eggs":           {"de": "🐧 Eggs-ISO",              "en": "🐧 Eggs-ISO"},
    "tab_grub":           {"de": "🔧 GRUB",                  "en": "🔧 GRUB"},
    "tab_recovery":       {"de": "🔍 Datenrettung",          "en": "🔍 Data Recovery"},
    "tab_wipe":           {"de": "🧹 Sicheres Löschen",      "en": "🧹 Secure Erase"},
    "tab_iso":            {"de": "💿 ISO-Brenner",           "en": "💿 ISO Burner"},
    "tab_partition":      {"de": "🔗 Partition einbinden",   "en": "🔗 Mount Partition"},
    "tab_health":         {"de": "🩺 Laufwerk-Diagnose",     "en": "🩺 Drive Health"},
    "tab_smart":          {"de": "📊 S.M.A.R.T.",           "en": "📊 S.M.A.R.T."},
    "tab_badblocks":      {"de": "🔬 Badblocks",             "en": "🔬 Badblocks"},
    "tab_disk_images":    {"de": "💾 Disk-Images",           "en": "💾 Disk Images"},
    "tab_migrate":        {"de": "🔄 Datenmigration",        "en": "🔄 Data Migration"},
    "tab_lvm":            {"de": "💿 LVM",                   "en": "💿 LVM"},
    "tab_raid":           {"de": "🛡️ RAID",                  "en": "🛡️ RAID"},
    "tab_boot_repair":    {"de": "🩹 Boot-Reparatur",        "en": "🩹 Boot Repair"},

    # ── Dashboard ───────────────────────────────────────────────────────
    "dash_cpu":           {"de": "CPU",                      "en": "CPU"},
    "dash_ram":           {"de": "RAM",                      "en": "RAM"},
    "dash_swap":          {"de": "Swap",                     "en": "Swap"},
    "dash_uptime":        {"de": "Laufzeit",                 "en": "Uptime"},
    "dash_drives":        {"de": "Laufwerke",                "en": "Drives"},
    "dash_free":          {"de": "Frei",                     "en": "Free"},
    "dash_used":          {"de": "Belegt",                   "en": "Used"},

    # ── Sicheres Löschen ────────────────────────────────────────────────
    "wipe_method":        {"de": "Lösch-Methode",            "en": "Wipe method"},
    "wipe_passes":        {"de": "Durchgänge",               "en": "Passes"},
    "wipe_confirm":       {"de": "⚠️ WIRKLICH löschen?",    "en": "⚠️ REALLY erase?"},
    "wipe_irreversible":  {"de": "Unwiderruflich – alle Daten werden dauerhaft gelöscht!",
                           "en": "Irreversible – all data will be permanently destroyed!"},
    "wipe_system_prot":   {"de": "⛔ Systemlaufwerk geschützt",
                           "en": "⛔ System device protected"},

    # ── Datenrettung ────────────────────────────────────────────────────
    "rec_source":         {"de": "Quell-Laufwerk",           "en": "Source drive"},
    "rec_target":         {"de": "Zielordner",               "en": "Target folder"},
    "rec_start":          {"de": "▶ Rettung starten",        "en": "▶ Start recovery"},
    "rec_abort":          {"de": "⏹ Abbrechen",              "en": "⏹ Abort"},

    # ── BIOS/EFI ────────────────────────────────────────────────────────
    "bios_entries":       {"de": "Boot-Einträge (efibootmgr)", "en": "Boot entries (efibootmgr)"},
    "bios_active":        {"de": "Aktiv",                    "en": "Active"},
    "bios_order":         {"de": "Boot-Reihenfolge",         "en": "Boot order"},
    "bios_timeout":       {"de": "Timeout (Sek.)",           "en": "Timeout (sec)"},
    "bios_reboot":        {"de": "🔧 Ins BIOS/UEFI neu starten", "en": "🔧 Reboot to BIOS/UEFI"},
    "bios_cleanup":       {"de": "🧹 Veraltete Einträge löschen", "en": "🧹 Remove obsolete entries"},
    "bios_select_hint":   {"de": "→ Eintrag in der Tabelle anklicken",
                           "en": "→ Click an entry in the table"},
    "bios_set_next":      {"de": "🖫 Als nächsten Boot setzen + Neustart",
                           "en": "🖫 Set as next boot + restart"},

    # ── Netzwerk ────────────────────────────────────────────────────────
    "net_interfaces":     {"de": "🔌 Netzwerk-Interfaces",  "en": "🔌 Network Interfaces"},
    "net_ping":           {"de": "📡 Ping",                  "en": "📡 Ping"},
    "net_connections":    {"de": "🔗 Verbindungen",          "en": "🔗 Connections"},
    "net_wlan_keys":      {"de": "🔑 WLAN-Passwörter",      "en": "🔑 WLAN passwords"},
    "net_host":           {"de": "Ziel-Host",                "en": "Target host"},

    # ── Erweitert ────────────────────────────────────────────────────────
    "adv_img_create":     {"de": "💾 Image erstellen",       "en": "💾 Create image"},
    "adv_img_restore":    {"de": "🔄 Image wiederherstellen", "en": "🔄 Restore image"},
    "adv_src_file":       {"de": "Quell-Datei",              "en": "Source file"},
    "adv_dst_file":       {"de": "Ziel-Datei",               "en": "Target file"},
    "adv_compress":       {"de": "Komprimieren mit gzip (.img.gz)", "en": "Compress with gzip (.img.gz)"},
    "adv_mirror":         {"de": "Spiegel (--delete)",       "en": "Mirror (--delete)"},
    "adv_dryrun":         {"de": "Trockenlauf (--dry-run)",  "en": "Dry run (--dry-run)"},
    "adv_hardlinks":      {"de": "Hardlinks erhalten (-H)",  "en": "Preserve hardlinks (-H)"},
    "adv_exclude":        {"de": "Ausschließen",             "en": "Exclude"},
    "adv_mig_start":      {"de": "▶ Migration starten",      "en": "▶ Start migration"},
    "adv_pv_select":      {"de": "Physical Volume auswählen", "en": "Select Physical Volume"},
    "adv_vg_name":        {"de": "Volume Group Name",        "en": "Volume Group name"},
    "adv_lv_name":        {"de": "Logical Volume Name",      "en": "Logical Volume name"},
    "adv_lvm_create":     {"de": "▶ LVM erstellen",          "en": "▶ Create LVM"},
    "adv_lvm_extend":     {"de": "▶ Vergrößern",             "en": "▶ Extend"},
    "adv_raid_create":    {"de": "▶ RAID erstellen",         "en": "▶ Create RAID"},
    "adv_raid_stop":      {"de": "⏹ RAID stoppen",          "en": "⏹ Stop RAID"},
    "adv_grub_install":   {"de": "🔧 GRUB installieren",     "en": "🔧 Install GRUB"},
    "adv_testdisk":       {"de": "▶ TestDisk starten",       "en": "▶ Start TestDisk"},
    "adv_mbr":            {"de": "⚠️ Windows-MBR schreiben", "en": "⚠️ Write Windows MBR"},
    "adv_nwipe":          {"de": "⚠️ nwipe starten",         "en": "⚠️ Start nwipe"},

    # ── Einstellungen ────────────────────────────────────────────────────
    "set_theme":          {"de": "🎨 Theme",                  "en": "🎨 Theme"},
    "set_theme_light":    {"de": "Hell",                      "en": "Light"},
    "set_theme_dark":     {"de": "Dunkel (Catppuccin)",       "en": "Dark (Catppuccin)"},
    "set_window_size":    {"de": "Fenstergröße",              "en": "Window size"},
    "set_save":           {"de": "💾 Einstellungen speichern","en": "💾 Save settings"},
    "set_reset":          {"de": "↺ Zurücksetzen",            "en": "↺ Reset"},
    "set_language":       {"de": "🌐 Sprache / Language",     "en": "🌐 Language / Sprache"},

    # ── Über ─────────────────────────────────────────────────────────────
    "about_title":        {"de": "Peeßi's System Multitool", "en": "Peeßi's System Multitool"},
    "about_desc":         {"de": "Systemverwaltungs-Tool für Linux Mint / Debian / Ubuntu",
                           "en": "System management tool for Linux Mint / Debian / Ubuntu"},
    "about_author":       {"de": "Autor",                    "en": "Author"},
    "about_license":      {"de": "Lizenz",                   "en": "License"},
    "about_hobby":        {"de": "Hobbyprojekt – kein kommerzielles Produkt",
                           "en": "Hobby project – not a commercial product"},
    "about_contact":      {"de": "✉️  Kontakt",              "en": "✉️  Contact"},
    "about_mail_btn":     {"de": "📧 E-Mail senden",         "en": "📧 Send e-mail"},

    # ── Systemwarnungen ──────────────────────────────────────────────────
    "warn_root_needed":   {"de": "⚠️ Benötigt Root-Rechte.", "en": "⚠️ Requires root privileges."},
    "warn_no_efi":        {"de": "efibootmgr nicht installiert oder kein EFI-System.",
                           "en": "efibootmgr not installed or not an EFI system."},
    "warn_irreversible":  {"de": "⚠️ Unwiderruflich!",       "en": "⚠️ Irreversible!"},
    "warn_backup_first":  {"de": "Backups vor jeder Operation!",
                           "en": "Always backup before any operation!"},

    # ── Dialoge ──────────────────────────────────────────────────────────
    "dlg_confirm":        {"de": "Bestätigung",              "en": "Confirmation"},
    "dlg_sure":           {"de": "Wirklich fortfahren?",     "en": "Are you sure?"},
    "dlg_yes":            {"de": "Ja",                       "en": "Yes"},
    "dlg_no":             {"de": "Nein",                     "en": "No"},
    "dlg_ok":             {"de": "OK",                       "en": "OK"},
    "dlg_select_folder":  {"de": "Ordner wählen",            "en": "Select folder"},
    "dlg_select_file":    {"de": "Datei wählen",             "en": "Select file"},
    "dlg_no_device":      {"de": "Bitte ein Laufwerk auswählen.", "en": "Please select a device."},
    "dlg_done":           {"de": "✅ Fertig.",                "en": "✅ Done."},
    "dlg_error":          {"de": "❌ Fehler",                 "en": "❌ Error"},
    "dlg_aborted":        {"de": "⏹ Gestoppt.",              "en": "⏹ Stopped."},
}


# ═══════════════════════════════════════════════════════════════════════════
#  API
# ═══════════════════════════════════════════════════════════════════════════

def set_lang(lang: str) -> None:
    """Setzt die aktive Sprache. Erlaubt: 'de', 'en'."""
    global _LANG
    if lang not in ("de", "en"):
        raise ValueError(f"Unbekannte Sprache: {lang!r}. Erlaubt: 'de', 'en'")
    _LANG = lang


def get_lang() -> str:
    """Gibt die aktuelle Sprache zurück."""
    return _LANG


def T(key: str, **kwargs) -> str:
    """
    Übersetzt einen Schlüssel in die aktuelle Sprache.
    Unbekannte Schlüssel werden mit [key] zurückgegeben.
    Optionale kwargs werden via str.format() eingesetzt.

    Beispiel:
        T("btn_refresh")           → "Aktualisieren"   (de)
        T("btn_refresh")           → "Refresh"          (en)
        T("lbl_size", val="256G")  → "Größe: 256G"      (wenn im String vorhanden)
    """
    entry = _STRINGS.get(key)
    if entry is None:
        return f"[{key}]"
    text = entry.get(_LANG) or entry.get("de") or f"[{key}]"
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def available_languages() -> list[tuple[str, str]]:
    """Gibt verfügbare Sprachen als Liste von (code, Bezeichnung) zurück."""
    return [("de", "Deutsch"), ("en", "English")]


def load_from_settings(settings: dict) -> None:
    """Lädt die Sprache aus dem settings-Dict (aus config.py)."""
    lang = settings.get("language", "de")
    try:
        set_lang(lang)
    except ValueError:
        set_lang("de")
