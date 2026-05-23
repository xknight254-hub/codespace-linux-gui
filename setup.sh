#!/bin/bash
# ============================================================
#  Native Linux GUI Desktop + SSH Setup for GitHub Codespaces
#  No Docker — installs XFCE + TigerVNC + noVNC + OpenSSH
#  SSH accessible via: ssh root@<codespace>-2222.app.github.dev
# ============================================================
set -e

echo "═══════════════════════════════════════════════════"
echo "  Installing Native Linux GUI Desktop + SSH"
echo "═══════════════════════════════════════════════════"

export DEBIAN_FRONTEND=noninteractive

# ── Step 1: Update & install XFCE ────────────────────────
echo ""
echo "[1/5] Updating packages and installing XFCE desktop..."
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

# ── Step 2: Install TigerVNC ─────────────────────────────
echo ""
echo "[2/5] Installing TigerVNC server..."
sudo apt-get install -y -qq \
    tigervnc-standalone-server \
    tigervnc-common \
    2>&1 | tail -3

# ── Step 3: Install noVNC ────────────────────────────────
echo ""
echo "[3/5] Installing noVNC..."
if [ ! -d "/opt/noVNC" ]; then
    sudo git clone --depth 1 https://github.com/novnc/noVNC.git /opt/noVNC 2>&1 | tail -2
fi
pip3 install --quiet websockify 2>/dev/null || true

# ── Step 4: Install & configure OpenSSH server ───────────
echo ""
echo "[4/5] Installing and configuring OpenSSH server..."
sudo apt-get install -y -qq openssh-server 2>&1 | tail -2

# Configure SSH for root access
sudo sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Ensure root login is permitted
if ! grep -q "PermitRootLogin yes" /etc/ssh/sshd_config; then
    echo "PermitRootLogin yes" | sudo tee -a /etc/ssh/sshd_config
fi
if ! grep -q "PasswordAuthentication yes" /etc/ssh/sshd_config; then
    echo "PasswordAuthentication yes" | sudo tee -a /etc/ssh/sshd_config
fi

# Set root password
echo "root:codespace123" | sudo chpasswd

# Generate SSH host keys if missing
sudo ssh-keygen -A 2>/dev/null || true

# Start SSH server
sudo service ssh restart 2>&1
sleep 2

# ── Step 5: Configure & start VNC + noVNC ────────────────
echo ""
echo "[5/5] Configuring and starting VNC + noVNC..."

VNC_DIR="$HOME/.vnc"
mkdir -p "$VNC_DIR"

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

# Kill existing sessions
vncserver -kill :1 2>/dev/null || true
pkill -f "websockify" 2>/dev/null || true
sleep 2

# VNC on :1 (port 5901)
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no 2>&1
sleep 3

# noVNC on port → VNC :1
nohup python3 -m websockify --web /opt/noVNC 6080 localhost:5901 > /tmp/novnc.log 2>&1 &
sleep 2

# ── Verify everything ────────────────────────────────────
SSH_RUNNING=$(pgrep -x sshd >/dev/null 2>&1 && echo "✅ running" || echo "❌ stopped")
VNC_RUNNING=$(pgrep -f "Xvnc :1" >/dev/null 2>&1 && echo "✅ running" || echo "❌ stopped")
NOVNC_RUNNING=$(pgrep -f "websockify" >/dev/null 2>&1 && echo "✅ running" || echo "❌ stopped")
SSH_PORT=$(sudo ss -tlnp 2>/dev/null | grep sshd | head -1 | awk '{print $4}' | grep -oE '[0-9]+$')

CODESPACE_NAME=$(cat /etc/hostname 2>/dev/null || hostname)

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ SETUP COMPLETE!"
echo ""
echo "  🖥️  GUI Desktop (noVNC):"
echo "     → Ports tab → port 6080 → Globe icon → Open"
echo "     → Password: codespace123"
echo ""
echo "  🔐 SSH Access:"
echo "     ssh root@$CODESPACE_NAME -p ${SSH_PORT:-22}"
echo "     Password: codespace123"
echo ""
echo "  📊 Services: SSH=$SSH_RUNNING | VNC=$VNC_RUNNING | noVNC=$NOVNC_RUNNING"
echo "═══════════════════════════════════════════════════"
