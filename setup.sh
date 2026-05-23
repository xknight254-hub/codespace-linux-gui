#!/bin/bash
# ============================================================
#  Native Linux GUI Desktop Setup for GitHub Codespaces
#  XFCE + TigerVNC + noVNC (SSH handled by devcontainer feature)
# ============================================================
set -e

echo "═══════════════════════════════════════════════════"
echo "  Installing Native Linux GUI Desktop (XFCE)"
echo "═══════════════════════════════════════════════════"

export DEBIAN_FRONTEND=noninteractive

# ── Step 1: Update & install desktop environment ──────────
echo ""
echo "[1/4] Updating packages and installing XFCE desktop..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    xfce4 \
    xfce4-terminal \
    xfce4-goodies \
    dbus-x11 \
    xfonts-base \
    fonts-noto \
    firefox-esr \
    2>&1 | tail -3

# ── Step 2: Install TigerVNC server ──────────────────────
echo ""
echo "[2/4] Installing TigerVNC server..."
sudo apt-get install -y -qq \
    tigervnc-standalone-server \
    tigervnc-common \
    2>&1 | tail -3

# ── Step 3: Install noVNC ────────────────────────────────
echo ""
echo "[3/4] Installing noVNC..."
if [ ! -d "/opt/noVNC" ]; then
    sudo git clone --depth 1 https://github.com/novnc/noVNC.git /opt/noVNC 2>&1 | tail -2
fi
pip3 install --quiet websockify 2>/dev/null || true

# ── Step 4: Configure & start VNC + noVNC ────────────────
echo ""
echo "[4/4] Configuring and starting VNC + noVNC..."

VNC_DIR="$HOME/.vnc"
mkdir -p "$VNC_DIR"

# Set VNC password
echo "codespace123" | vncpasswd -f > "$VNC_DIR/passwd" 2>/dev/null
chmod 600 "$VNC_DIR/passwd"

cat > "$VNC_DIR/xstartup" << 'XSTARTUP'
#!/bin/bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1
exec startxfce4
XSTARTUP
chmod +x "$VNC_DIR/xstartup"

# Kill any existing sessions
vncserver -kill :1 2>/dev/null || true
pkill -f "websockify" 2>/dev/null || true
sleep 2

# Start VNC on display :1 (port 5901)
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no 2>&1

sleep 3

# Start noVNC proxy (port 6080 → VNC 5901)
nohup python3 -m websockify --web /opt/noVNC 6080 localhost:5901 > /tmp/novnc.log 2>&1 &
sleep 2

# ── Verify & display info ────────────────────────────────
SSH_PID=$(pgrep -x sshd >/dev/null 2>&1 && echo "running" || echo "stopped - check devcontainer feature")
VNC_PID=$(pgrep -f "Xvnc :1" >/dev/null 2>&1 && echo "running" || echo "stopped")
NOVNC_PID=$(pgrep -f "websockify" >/dev/null 2>&1 && echo "running" || echo "stopped")

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ SETUP COMPLETE!"
echo ""
echo "  🖥️  GUI Desktop (noVNC):"
echo "     → Click Ports tab → port 6080 → Open in Browser"
echo "     → VNC password: codespace123"
echo ""
echo "  🔐 SSH Access:"
echo "     gh codespace ssh --repo xknight254-hub/codespace-linux-gui"
echo ""
echo "  Service status: SSH=$SSH_PID | VNC=$VNC_PID | noVNC=$NOVNC_PID"
echo "═══════════════════════════════════════════════════"
