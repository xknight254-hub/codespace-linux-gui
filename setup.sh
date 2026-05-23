#!/bin/bash
# ============================================================
#  Native Linux GUI Desktop + SSH Setup for GitHub Codespaces
#  No Docker — installs XFCE + TigerVNC + noVNC directly
# ============================================================
set -e

echo "═══════════════════════════════════════════════════"
echo "  Installing Native Linux GUI Desktop (XFCE)"
echo "═══════════════════════════════════════════════════"

# ── Step 1: Update & install desktop environment ──────────
echo ""
echo "[1/6] Updating packages and installing XFCE desktop..."
export DEBIAN_FRONTEND=noninteractive
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
echo "[2/6] Installing TigerVNC server..."
sudo apt-get install -y -qq \
    tigervnc-standalone-server \
    tigervnc-common \
    2>&1 | tail -3

# ── Step 3: Install noVNC (HTML5 VNC client) ────────────
echo ""
echo "[3/6] Installing noVNC..."
if [ ! -d "/opt/noVNC" ]; then
    sudo git clone --depth 1 https://github.com/novnc/noVNC.git /opt/noVNC 2>&1 | tail -2
fi
if [ ! -d "/opt/websockify" ]; then
    sudo git clone --depth 1 https://github.com/novnc/websockify /opt/websockify 2>&1 | tail -2
fi
# Install websockify Python deps
pip3 install --quiet websockify 2>/dev/null || true

# ── Step 4: Configure VNC ────────────────────────────────
echo ""
echo "[4/6] Configuring VNC server..."
VNC_DIR="$HOME/.vnc"
mkdir -p "$VNC_DIR"

# Set VNC password (default: "password")
echo "password" | vncpasswd -f > "$VNC_DIR/passwd" 2>/dev/null
chmod 600 "$VNC_DIR/passwd"

# Create xstartup script
cat > "$VNC_DIR/xstartup" << 'XSTARTUP'
#!/bin/bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XKL_XMODMAP_DISABLE=1
exec startxfce4
XSTARTUP
chmod +x "$VNC_DIR/xstartup"

# ── Step 5: Start VNC + noVNC ────────────────────────────
echo ""
echo "[5/6] Starting VNC and noVNC services..."

# Kill any existing VNC sessions
vncserver -kill :1 2>/dev/null || true
pkill -f "novnc" 2>/dev/null || true
pkill -f "websockify.*6080" 2>/dev/null || true
sleep 2

# Start VNC server on display :1 (port 5901)
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no 2>&1

sleep 3

# Start noVNC proxy (port 6080 → VNC port 5901)
nohup websockify --web /opt/noVNC 6080 localhost:5901 > /tmp/novnc.log 2>&1 &
sleep 2

# ── Step 6: Verify and display info ──────────────────────
echo ""
echo "[6/6] Verifying services..."
VNC_PID=$(pgrep -f "Xvnc :1" 1>/dev/null && echo "running" || echo "stopped")
NOVNC_PID=$(pgrep -f "websockify.*6080" 1>/dev/null && echo "running" || echo "stopped")

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ SETUP COMPLETE!"
echo ""
echo "  🖥️  GUI Desktop (noVNC):"
echo "     → Click the Ports tab → port 6080 → Open in Browser"
echo "     → Or open the forwarded URL in a new tab"
echo "     → VNC password: password"
echo ""
echo "  🔐 SSH Access (native Codespace SSH):"
echo "     → In a terminal, run:"
echo "         gh codespace ssh --repo xknight254-hub/codespace-linux-gui"
echo "     → Or go to: github.com → Codespaces → Connect via SSH"
echo "     → Username: root (or codespace)"
echo ""
echo "  VNC status: $VNC_PID | noVNC status: $NOVNC_PID"
echo "═══════════════════════════════════════════════════"
