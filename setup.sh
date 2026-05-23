#!/bin/bash
# === Codespace Linux GUI + SSH Setup ===
# This script runs inside the GitHub Codespace via postCreateCommand

set -e

WORKSPACE="/workspaces/codespace-linux-gui"

echo "🧹 Cleaning up old configs..."
rm -f "$WORKSPACE/compose.yml" "$WORKSPACE/docker-compose.yml"

echo "📝 Writing docker-compose.yml..."
cat > "$WORKSPACE/docker-compose.yml" << 'COMPOSE_EOF'
version: "3.8"

services:
  debian-desktop:
    image: lscr.io/linuxserver/webtop:debian-xfce
    container_name: debian_gui
    privileged: true
    networks:
      - gui-net
    ports:
      - "7080:3000"
    shm_size: "2gb"
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=UTC
    restart: unless-stopped

  sshd:
    build:
      context: .
      dockerfile: Dockerfile.ssh
    container_name: gui_ssh
    networks:
      - gui-net
    ports:
      - "2222:22"
    shm_size: "2gb"
    privileged: true
    restart: unless-stopped

networks:
  gui-net:
    driver: bridge
COMPOSE_EOF

echo "🐳 Building SSH container and starting services..."
cd "$WORKSPACE"
docker-compose build sshd
docker-compose up -d

echo ""
echo "⏳ Waiting for services to initialize..."
sleep 20

echo ""
echo "📊 Container status:"
docker-compose ps

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ SETUP COMPLETE!"
echo ""
echo "  🖥️  GUI Desktop:"
echo "     Click Ports tab → port 7080 → Open in Browser"
echo "     (or open the forwarded URL in a new tab)"
echo ""
echo "  🔐 SSH Access:"
echo "     ssh root@localhost -p 2222"
echo "     Password: toor"
echo ""
echo "  💡 To SSH from outside, use the Codespace SSH URL"
echo "     (see GitHub → Codespaces → Connect via SSH)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
