#!/bin/bash
# ============================================================
#  Native Linux GUI Desktop + SSH Setup for GitHub Codespaces
#  No Docker — installs XFCE + TigerVNC + noVNC + SSH directly
# ============================================================
set -e

echo "═══════════════════════════════════════════════════"
echo "  Installing Native Linux GUI Desktop + SSH"
echo "═══════════════════════════════════════════════════"

export DEBIAN_FRONTEND=noninteractive

# ── Step 1: Update & install desktop environment ──────────
echo ""
echo "[1/7] Updating packages and installing XFCE desktop..."
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
echo "[2/7] Installing TigerVNC server..."
sudo apt-get install -y -qq \
    tigervnc-standalone-server \
    tigervnc-common \
    2>&1 | tail -3

# ── Step 3: Install noVNC (HTML5 VNC client) ────────────
echo ""
echo "[3/7] Installing noVNC..."
if [ ! -d "/opt/noVNC" ]; then
    sudo git clone --depth 1 https://github.com/novnc/noVNC.git /opt/noVNC 2>&1 | tail -2
fi
pip3 install --quiet websockify 2>/dev/null || true

# ── Step 4: Install & configure SSH server ───────────────
echo ""
echo "[4/7] Installing and configuring OpenSSH server..."
sudo apt-get install -y -qq openssh-server 2>&1 | tail -2

# Configure SSH
sudo sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Set root password
echo "root:codespace123" | sudo chpasswd

# Start SSH
sudo service ssh start
sudo service ssh enable 2>/dev/null || true

# ── Step 5: Configure VNC ────────────────────────────────
echo ""
echo "[5/7] Configuring VNC server..."
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

# ── Step 6: Start VNC + noVNC ────────────────────────────
echo ""
echo "[6/7] Starting VNC and noVNC services..."

# Kill any existing sessions
vncserver -kill :1 2>/dev/null || true
pkill -f "novnc" 2>/dev/null || true
pkill -f "websockify" 2>/dev/null || true
sleep 2

# Start VNC on display :1 (port 5901)
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no 2>&1

sleep 3

# Start noVNC proxy (port 6080 → VNC 5901)
nohup python3 -m websockify --web /opt/noVNC 6080 localhost:5901 > /tmp/novnc.log 2>&1 &
sleep 2

# ── Step 7: Verify ───────────────────────────────────────
echo ""
echo "[7/7] Verifying services..."
SSH_PID=$(pgrep -x sshd >/dev/null 2>&1 && echo "running" || echo "stopped")
VNC_PID=$(pgrep -f "Xvnc :1" >/dev/null 2>&1 && echo "running" || echo "stopped")
NOVNC_PID=$(pgrep -f "websockify" >/dev/null 2>&1 && echo "running" || echo "stopped")

# Get SSH port and IP
SSH_PORT=$(sudo ss -tlnp | grep sshd | awk '{print $4}' | grep -oP ':\K\d+' | head -1)
HOST_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ SETUP COMPLETE!"
echo ""
echo "  🖥️  GUI Desktop (noVNC):"
echo "     → Ports tab → port 6080 → Open in Browser"
echo "     → VNC password: codespace123"
echo ""
echo "  🔐 SSH Access:"
echo "     ssh root@$HOST_IP -p ${SSH_PORT:-22}"
echo "     Password: codespace123"
echo ""
echo "  Service status:"
echo "     SSH:   $SSH_PID"
echo "     VNC:   $VNC_PID"
echo "     noVNC: $NOVNC_PID"
echo "═══════════════════════════════════════════════════"
