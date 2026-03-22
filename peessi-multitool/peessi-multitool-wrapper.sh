#!/bin/bash
# =============================================================================
# Peeßi's System Multitool – Starter-Wrapper 1.0 Beta
# Fix: pkexec löscht DISPLAY/XAUTHORITY → Fenster erscheint nicht
#
# Installieren: sudo cp peessi-multitool-wrapper.sh /usr/local/bin/peessi-multitool
#               sudo chmod 755 /usr/local/bin/peessi-multitool
# =============================================================================

INSTALL_DIR="/usr/local/lib/peessi-multitool"
VENV_PYTHON="${INSTALL_DIR}/venv/bin/python3"
BIN_ROOT_WRAPPER="/usr/local/bin/peessi-multitool-root"
PROG="${INSTALL_DIR}/main.py"

# venv-Python bevorzugen
if [[ -x "${VENV_PYTHON}" ]]; then
    PY="${VENV_PYTHON}"
else
    PY="python3"
fi

# Bereits Root → direkt starten
if [[ $EUID -eq 0 ]]; then
    exec "${PY}" "${PROG}" "$@"
fi

# Display-Variablen sichern (pkexec löscht diese beim Rechteerhöhen)
_DISP="${DISPLAY:-:0}"
_XAUTH="${XAUTHORITY:-${HOME}/.Xauthority}"
_WAYLAND="${WAYLAND_DISPLAY:-}"
_XDG="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

# Temp-Datei mit Display-Infos für Root-Wrapper
_ENVFILE="$(mktemp /tmp/peessi_env_XXXXXX)"
cat > "${_ENVFILE}" << ENV
DISPLAY=${_DISP}
XAUTHORITY=${_XAUTH}
WAYLAND_DISPLAY=${_WAYLAND}
XDG_RUNTIME_DIR=${_XDG}
ENV
chmod 644 "${_ENVFILE}"

# X11: Root explizit Zugriff auf den Display erlauben
xhost +SI:localuser:root 2>/dev/null || true

# Starten
if command -v pkexec &>/dev/null; then
    exec pkexec env PEESSI_ENV_FILE="${_ENVFILE}" "${BIN_ROOT_WRAPPER}" "$@"
else
    # Fallback: sudo -E (bewahrt Umgebungsvariablen)
    rm -f "${_ENVFILE}"
    exec sudo -E "${PY}" "${PROG}" "$@"
fi
