#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "=== [1/4] Clearing package locks & reconfiguring dpkg ==="
pkill -f apt || true
pkill -f dpkg || true
dpkg --configure -a
apt-get clean

echo "=== [2/4] Optimizing Repository Mirrors (termux-change-repo) ==="
if command -v termux-change-repo &>/dev/null; then
    termux-change-repo
else
    pkg install -y termux-tools
    termux-change-repo
fi

echo "=== [3/4] Refreshing Core Package Indices & Toolsets ==="
pkg update -y || apt-get update --fix-missing -y

echo "=== [4/4] Upgrading All Binaries & Libraries (Non-Stalling) ==="
pkg upgrade -o Dpkg::Options::="--force-confold" -o Dpkg::Options::="--force-confdef" -y || \
apt-get upgrade -o Dpkg::Options::="--force-confold" -o Dpkg::Options::="--force-confdef" -y

echo "=== [VERIFIED] Termux Sovereign Environment Fully Upgraded ==="
