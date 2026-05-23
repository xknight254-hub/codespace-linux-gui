#!/bin/bash
# ============================================================
#  Native Linux GUI Desktop Setup for GitHub Codespaces
#  Run this in the Codespace terminal
# ============================================================
set -e

echo "═══════════════════════════════════════════════════"
echo "  Installing Native Linux GUI Desktop (XFCE)"
echo "═══════════════════════════════════════════════════"

export DEBIAN_FRONTEND=noninteractive

echo ""
echo "[1/4] Installing XFCE desktop..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    xfce4 xfce4-terminal xfce4-goodies \
    dbus-x11 xfonts-base fonts-noto firefox-esr

echo ""
echo "[2/4] Installing TigerVNC..."
sudo apt-get install -y -qq tigervnc-standalone-server tigervnc-common

echo ""
echo "[3/4] Installing noVNC..."
[ ! -d "/opt/noVNC" ] && sudo git clone -q --depth 1 https://github.com/novnc/noVNC.git /opt/noVNC
pip3 install -q websockify 2>/dev/null || true

echo ""
echo "[4/4] Configuring and starting services..."

# VNC config
mkdir -p ~/.vnc
echo "codespace123" | vncpasswd -f > ~/.vnc/passwd 2>/dev/null
chmod 600 ~/.vnc/passwd
cat > ~/.vnc/xstartup << 'EOF'
#!/bin/bash
unset SESSION_MANAGER; unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1; exec startxfce4
EOF
chmod +x ~/.vnc/xstartup

# Kill existing
vncserver -kill :1 2>/dev/null || true
pkill -f websockify 2>/dev/null || true; sleep 2

# Start VNC
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no
sleep 3

# Start noVNC
nohup python3 -m websockify --web /opt/noVNC 6080 localhost:5901 > /tmp/novnc.log 2>&1 &

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ GUI Ready!"
echo ""
echo "  🖥️  Desktop: Ports tab → 6080 → Globe icon"
echo "     Password: codespace123"
echo ""
echo "  🔐 SSH:  gh codespace ssh -c \$(gh codespace list -q xknight254-hub/codespace-linux-gui -jq.[0].name)"
echo "═══════════════════════════════════════════════════"
