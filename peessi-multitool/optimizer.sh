#!/bin/bash
# Peeßi's System Multitool – Optimierer
# Wird von gui_system.py aufgerufen

set -uo pipefail

echo "=== 1. Kernel-Tuning ==="
CONF=/etc/sysctl.d/99-peessi-optimizer.conf

{
echo "vm.swappiness = 10"
echo "vm.vfs_cache_pressure = 50"
echo "vm.dirty_ratio = 10"
echo "vm.dirty_background_ratio = 5"
echo "net.core.default_qdisc = fq"

if modprobe tcp_bbr 2>/dev/null && \
   grep -q bbr /proc/sys/net/ipv4/tcp_available_congestion_control 2>/dev/null; then
    echo "net.ipv4.tcp_congestion_control = bbr"
    echo "✓ BBR TCP-Modul verfügbar und aktiviert."
else
    echo "# BBR nicht verfügbar – cubic bleibt aktiv"
    echo "⚠ BBR nicht verfügbar – Standard-TCP bleibt aktiv."
fi
} | tee "$CONF"

sysctl --system 2>&1 | grep -E "Applying|error" || true
echo "✓ Kernel-Parameter gesetzt."

echo ""
echo "=== 2. Swap-Datei (dynamisch) ==="
RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if   [ "$RAM_MB" -le 2048 ]; then SWAP_MB=4096
elif [ "$RAM_MB" -le 4096 ]; then SWAP_MB=4096
elif [ "$RAM_MB" -le 8192 ]; then SWAP_MB=8192
else SWAP_MB=4096
fi
FREE_MB=$(df / | awk 'NR==2{print int($4/1024)}')

if [ "$FREE_MB" -lt $((SWAP_MB+1024)) ]; then
    echo "⚠ Nicht genug freier Speicher für ${SWAP_MB}MB Swap (frei: ${FREE_MB}MB). Übersprungen."
else
    swapoff -a 2>/dev/null || true
    [ -f /swapfile ] && rm /swapfile
    dd if=/dev/zero of=/swapfile bs=1M count="$SWAP_MB" status=progress
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q /swapfile /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
    echo "✓ ${SWAP_MB}MB Swap aktiv (RAM: ${RAM_MB}MB)."
fi

echo ""
echo "=== 3. Firefox Low-Memory-Policies (optional) ==="
if command -v firefox >/dev/null 2>&1 || [ -d /etc/firefox ]; then
    mkdir -p /etc/firefox/policies
    cat > /etc/firefox/policies/policies.json << 'JSON'
{
  "policies": {
    "Preferences": {
      "browser.tabs.unloadOnLowMemory": true,
      "browser.low_commit_space_threshold_mb": 2048
    }
  }
}
JSON
    echo "✓ Firefox Low-Memory-Policies gesetzt."
else
    echo "ℹ Firefox nicht installiert – übersprungen."
fi

echo ""
echo "✅ Optimierung abgeschlossen."
