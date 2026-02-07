#!/bin/bash
# WayVoxtral Installation Script
# Installs system dependencies and sets up the application
#
# Usage: bash scripts/install.sh

set -e

echo "🎙️  WayVoxtral Installer"
echo "========================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root (for sudo commands)
check_sudo() {
    if ! sudo -v &> /dev/null; then
        echo -e "${RED}Error: This script requires sudo access${NC}"
        exit 1
    fi
}

# Install system dependencies
install_system_deps() {
    echo -e "${YELLOW}📦 Installing system dependencies...${NC}"
    
    # Add keyd PPA as it's not in default repos for 24.04
    if ! apt-cache show keyd > /dev/null 2>&1; then
        echo -e "${YELLOW}➕ Adding keyd PPA...${NC}"
        sudo apt install -y software-properties-common
        sudo add-apt-repository -y ppa:keyd-team/ppa
        sudo apt update
    fi

    sudo apt install -y \
        keyd \
        python3-pip \
        python3-venv \
        python3-dev \
        python3-gi \
        python3-gi-cairo \
        gir1.2-gtk-4.0 \
        libgtk-4-dev \
        portaudio19-dev \
        libgirepository-2.0-dev \
        libcairo2-dev \
        wl-clipboard \
        ydotool
    
    echo -e "${GREEN}✓ System dependencies installed${NC}"
}

# Enable and configure keyd
setup_keyd() {
    echo -e "${YELLOW}⌨️  Configuring keyd for global hotkey...${NC}"
    
    # Check if keyd.rvaiya exists (PPA naming) and symlink it to keyd
    if [ ! -f /usr/local/bin/keyd ] && [ -f /usr/bin/keyd.rvaiya ]; then
        echo -e "${YELLOW}🔗 Creating symlink for keyd.rvaiya...${NC}"
        sudo ln -s /usr/bin/keyd.rvaiya /usr/local/bin/keyd
    fi
    
    # Copy keyd config
    sudo cp config/wayvoxtral.conf.example /etc/keyd/wayvoxtral.conf
    
    # Enable and start keyd
    sudo systemctl enable keyd
    sudo systemctl restart keyd
    
    # Reload keyd config
    # Use the symlink or binary directly
    if command -v keyd > /dev/null; then
        sudo keyd reload
    elif command -v keyd.rvaiya > /dev/null; then
        sudo keyd.rvaiya reload
    fi
    
    echo -e "${GREEN}✓ keyd configured (Ctrl+Space → F24)${NC}"
}

# Setup ydotool
setup_ydotool() {
    echo -e "${YELLOW}🔧 Configuring ydotool...${NC}"
    
    # On Ubuntu 24.04, ydotool 0.1.8 doesn't use ydotoold service
    # It requires direct access to /dev/uinput
    
    # Create udev rule for uinput
    echo -e "${YELLOW}📜 Creating udev rule for /dev/uinput...${NC}"
    echo 'KERNEL=="uinput", GROUP="input", MODE="0660"' | sudo tee /etc/udev/rules.d/80-uinput.rules > /dev/null
    
    # Reload udev rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    # Add user to input group for uinput access (if not already)
    sudo usermod -aG input "$USER"
    
    echo -e "${GREEN}✓ ydotool configured (uinput permissions set)${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  ⚠️  ATTENTION: YOU MUST LOG OUT AND BACK IN NOW!${NC}"
    echo -e "${RED}  Group permissions (input) will NOT take effect until you do.${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    sleep 2
}

# Create Python virtual environment
setup_venv() {
    echo -e "${YELLOW}🐍 Setting up Python environment...${NC}"
    
    VENV_PATH="$HOME/.local/share/wayvoxtral/venv"
    
    # Create directory
    mkdir -p "$HOME/.local/share/wayvoxtral"
    
    # Create venv
    python3 -m venv "$VENV_PATH"
    
    # Activate and install
    source "$VENV_PATH/bin/activate"
    pip install --upgrade pip
    pip install -e .
    deactivate
    
    echo -e "${GREEN}✓ Python environment ready${NC}"
}

# Setup configuration
setup_config() {
    echo -e "${YELLOW}⚙️  Setting up configuration...${NC}"
    
    CONFIG_DIR="$HOME/.config/wayvoxtral"
    mkdir -p "$CONFIG_DIR"
    
    if [ ! -f "$CONFIG_DIR/config.json" ]; then
        cp config/config.json.example "$CONFIG_DIR/config.json"
        echo -e "${YELLOW}⚠️  Edit $CONFIG_DIR/config.json to add your Mistral API key${NC}"
    else
        echo -e "${GREEN}✓ Configuration already exists${NC}"
    fi
    
    # Create cache directory
    mkdir -p "$HOME/.cache/wayvoxtral"
}

# Install systemd service
setup_systemd() {
    echo -e "${YELLOW}🔄 Setting up systemd service...${NC}"
    
    SYSTEMD_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SYSTEMD_DIR"
    
    # Copy service file
    cp systemd/wayvoxtral.service "$SYSTEMD_DIR/"
    
    # Reload systemd
    systemctl --user daemon-reload
    
    # Enable service (don't start yet)
    systemctl --user enable wayvoxtral.service
    
    echo -e "${GREEN}✓ Systemd service installed${NC}"
}

# Main installation
main() {
    check_sudo
    
    # Get script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR/.."
    
    install_system_deps
    setup_keyd
    setup_ydotool
    setup_venv
    setup_config
    setup_systemd
    
    echo ""
    echo ""
    echo -e "${GREEN}✅ WayVoxtral installation complete!${NC}"
    echo ""
    echo -e "${RED}❗ CRITICAL STEP: LOG OUT AND BACK IN (REQUIRED FOR PERMISSIONS)${NC}"
    echo ""
    echo "Then follow these steps:"
    echo "  1. Edit ~/.config/wayvoxtral/config.json and add your Mistral API key"
    echo "  2. Start the service: systemctl --user start wayvoxtral"
    echo "  3. Press Ctrl+Space to start recording!"
    echo ""
    echo "Useful commands:"
    echo "  - Check status: systemctl --user status wayvoxtral"
    echo "  - View logs: journalctl --user -u wayvoxtral -f"
    echo "  - Stop service: systemctl --user stop wayvoxtral"
}

main "$@"
