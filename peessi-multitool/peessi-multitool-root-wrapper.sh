#!/bin/bash
# =============================================================================
# Peeßi's System Multitool – Root-Wrapper für pkexec 1.0 Beta
# Stellt DISPLAY/XAUTHORITY aus der Temp-Datei des Haupt-Wrappers wieder her
#
# Installieren: sudo cp peessi-multitool-root-wrapper.sh /usr/local/bin/peessi-multitool-root
#               sudo chmod 755 /usr/local/bin/peessi-multitool-root
# =============================================================================

INSTALL_DIR="/usr/local/lib/peessi-multitool"
VENV_PYTHON="${INSTALL_DIR}/venv/bin/python3"
PROG="${INSTALL_DIR}/main.py"

# Display-Variablen aus Temp-Datei laden (vom Haupt-Wrapper geschrieben)
if [[ -n "${PEESSI_ENV_FILE}" && -f "${PEESSI_ENV_FILE}" ]]; then
    while IFS='=' read -r key val; do
        # Kommentare und leere Zeilen überspringen
        [[ -z "${key}" || "${key}" == \#* ]] && continue
        export "${key}=${val}"
    done < "${PEESSI_ENV_FILE}"
    rm -f "${PEESSI_ENV_FILE}"
fi

# Fallback-Werte falls Temp-Datei nicht vorhanden
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/root/.Xauthority}"

# venv-Python bevorzugen
if [[ -x "${VENV_PYTHON}" ]]; then
    exec "${VENV_PYTHON}" "${PROG}" "$@"
else
    exec python3 "${PROG}" "$@"
fi
