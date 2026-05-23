#!/bin/bash
# === Codespace Linux GUI + SSH Setup ===
# Run these commands inside your GitHub Codespace terminal

set -e

echo "🧹 Cleaning up old configs..."
rm -f compose.yml docker-compose.yml

echo "📝 Writing docker-compose.yml..."
cat > docker-compose.yml << 'COMPOSE_EOF'
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

echo "🐳 Starting containers..."
docker-compose up -d

echo ""
echo "⏳ Waiting for containers to start..."
sleep 15

echo ""
echo "📊 Container status:"
docker-compose ps

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ SETUP COMPLETE!"
echo ""
echo "  🖥️  GUI Desktop:  Click Ports tab → port 7080 → Open in Browser"
echo "  🔐 SSH Access:    ssh root@$(hostname -I | awk '{print $1}') -p 2222"
echo "                    Password: toor"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
