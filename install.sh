#!/bin/bash
# piSolar Installation Script
# Installs piSolar runtime to a target system
# Usage: ./install.sh [install_dir]

set -e  # Exit on error

# Configuration
INSTALL_DIR="${1:-/opt/pisolar}"
CONFIG_DIR="/etc/pisolar"
SYSTEMD_DIR="/etc/systemd/system"
PYTHON_MIN_VERSION="3.11"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== piSolar Installation Script ===${NC}"
echo "Install directory: $INSTALL_DIR"
echo "Config directory: $CONFIG_DIR"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}Warning: Not running as root. Some operations may require sudo.${NC}"
    SUDO="sudo"
else
    SUDO=""
fi

# Check Python version
echo -e "${GREEN}[1/7] Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Found Python $PYTHON_VERSION"

if [ "$(printf '%s\n' "$PYTHON_MIN_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$PYTHON_MIN_VERSION" ]; then
    echo -e "${RED}Error: Python $PYTHON_MIN_VERSION or higher required${NC}"
    exit 1
fi

# Create installation directory
echo -e "${GREEN}[2/7] Creating installation directory...${NC}"
$SUDO mkdir -p "$INSTALL_DIR"

# Copy application files (excluding development files)
echo -e "${GREEN}[3/7] Copying application files...${NC}"
echo "Copying source files..."
$SUDO cp -r src/pisolar "$INSTALL_DIR/"

echo "Copying requirements.txt..."
$SUDO cp requirements.txt "$INSTALL_DIR/"

# Create and setup virtual environment
echo -e "${GREEN}[4/7] Setting up virtual environment...${NC}"
cd "$INSTALL_DIR"
$SUDO python3 -m venv .venv

# Activate venv and install dependencies
echo -e "${GREEN}[5/7] Installing dependencies...${NC}"
$SUDO .venv/bin/pip install --upgrade pip
$SUDO .venv/bin/pip install --no-cache-dir -r requirements.txt

# Install the package
echo "Installing pisolar package..."
cat > "$INSTALL_DIR/setup.py" << 'EOF'
from setuptools import setup, find_packages

setup(
    name="pisolar",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[],
    entry_points={
        'console_scripts': [
            'pisolar=pisolar.cli:main',
        ],
    },
)
EOF

$SUDO .venv/bin/pip install -e .

# Setup configuration
echo -e "${GREEN}[6/7] Setting up configuration...${NC}"
if [ -d "config" ]; then
    $SUDO mkdir -p "$CONFIG_DIR"
    
    if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
        echo "Copying config.yaml..."
        $SUDO cp config/config.yaml "$CONFIG_DIR/"
    else
        echo "config.yaml already exists, skipping (backup saved as config.yaml.new)"
        $SUDO cp config/config.yaml "$CONFIG_DIR/config.yaml.new"
    fi
    
    if [ ! -f "$CONFIG_DIR/logging.yaml" ]; then
        echo "Copying logging.yaml..."
        $SUDO cp config/logging.yaml "$CONFIG_DIR/"
    else
        echo "logging.yaml already exists, skipping (backup saved as logging.yaml.new)"
        $SUDO cp config/logging.yaml "$CONFIG_DIR/logging.yaml.new"
    fi
else
    echo -e "${YELLOW}Warning: config directory not found in source${NC}"
fi

# Setup systemd service
echo -e "${GREEN}[7/7] Setting up systemd service...${NC}"
if [ -f "systemd/pisolar.service" ]; then
    # Update service file with correct paths
    $SUDO cp systemd/pisolar.service "$SYSTEMD_DIR/pisolar.service"
    
    # Update paths in service file
    $SUDO sed -i "s|ExecStart=.*|ExecStart=$INSTALL_DIR/.venv/bin/pisolar -c $CONFIG_DIR/config.yaml -l $CONFIG_DIR/logging.yaml run|g" "$SYSTEMD_DIR/pisolar.service"
    $SUDO sed -i "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g" "$SYSTEMD_DIR/pisolar.service"
    
    echo "Reloading systemd daemon..."
    $SUDO systemctl daemon-reload
    
    echo -e "${YELLOW}Service installed but not enabled. To enable and start:${NC}"
    echo "  sudo systemctl enable pisolar"
    echo "  sudo systemctl start pisolar"
else
    echo -e "${YELLOW}Warning: systemd/pisolar.service not found${NC}"
fi

# Test installation
echo ""
echo -e "${GREEN}=== Testing Installation ===${NC}"
if $INSTALL_DIR/.venv/bin/pisolar --help &> /dev/null; then
    echo -e "${GREEN}✓ pisolar CLI is working${NC}"
else
    echo -e "${RED}✗ pisolar CLI test failed${NC}"
    exit 1
fi

# Cleanup
echo ""
echo -e "${GREEN}=== Cleanup ===${NC}"
$SUDO rm -f "$INSTALL_DIR/setup.py"

# Summary
echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo "Installation directory: $INSTALL_DIR"
echo "Config directory: $CONFIG_DIR"
echo ""
echo "Next steps:"
echo "  1. Review and edit configuration: $CONFIG_DIR/config.yaml"
echo "  2. Review and edit logging: $CONFIG_DIR/logging.yaml"
echo "  3. Test the service: $INSTALL_DIR/.venv/bin/pisolar check"
echo "  4. Enable service: sudo systemctl enable pisolar"
echo "  5. Start service: sudo systemctl start pisolar"
echo "  6. Check status: sudo systemctl status pisolar"
echo ""
echo -e "${GREEN}Installation successful!${NC}"
