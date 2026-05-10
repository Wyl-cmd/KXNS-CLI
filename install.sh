#!/bin/bash
# Kxns Hunter CLI - Linux Installation Script
# Run this script: chmod +x install.sh && ./install.sh

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

NO_VENV=false
PYTHON="python3"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-venv)
            NO_VENV=true
            shift
            ;;
        --python)
            PYTHON="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Kxns Hunter CLI Installation Script  ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check Python installation
echo -e "${CYAN}[1/4] Checking Python installation...${NC}"
if command -v $PYTHON &> /dev/null; then
    PYTHON_VERSION=$($PYTHON --version 2>&1)
    echo -e "${GRAY}  Found: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}  Error: Python not found. Please install Python 3.12+ first.${NC}"
    exit 1
fi

# Create virtual environment (optional)
VENV_PATH="$(dirname "$0")/.venv"
if [ "$NO_VENV" = false ]; then
    echo -e "${CYAN}[2/4] Creating virtual environment...${NC}"
    if [ -d "$VENV_PATH" ]; then
        echo -e "${GRAY}  Virtual environment already exists, skipping...${NC}"
    else
        $PYTHON -m venv "$VENV_PATH"
        echo -e "${GRAY}  Virtual environment created at: $VENV_PATH${NC}"
    fi
    PYTHON="$VENV_PATH/bin/python"
else
    echo -e "${CYAN}[2/4] Skipping virtual environment creation...${NC}"
fi

# Upgrade pip
echo -e "${CYAN}[3/4] Upgrading pip...${NC}"
$PYTHON -m pip install --upgrade pip --quiet

# Install dependencies
echo -e "${CYAN}[4/4] Installing dependencies...${NC}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REQUIREMENTS_PATH="$SCRIPT_DIR/requirements.txt"
$PYTHON -m pip install -r "$REQUIREMENTS_PATH" --quiet

# Install the package in development mode
echo -e "${GRAY}  Installing kxns-cli in development mode...${NC}"
cd "$SCRIPT_DIR"
$PYTHON -m pip install -e . --quiet

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation completed successfully! ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$NO_VENV" = false ]; then
    echo -e "${YELLOW}To activate the virtual environment, run:${NC}"
    echo -e "  source .venv/bin/activate"
    echo ""
fi

echo -e "${YELLOW}To verify installation, run:${NC}"
echo -e "  kxns --version"
echo -e "  kxns --help"
echo ""
