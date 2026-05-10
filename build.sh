#!/bin/bash
# Kxns Hunter CLI - Linux Build Script
# Run this script: chmod +x build.sh && ./build.sh

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

PYTHON="python3"
OUTPUT_DIR="dist"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --python)
            PYTHON="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Kxns Hunter CLI Build Script         ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$SCRIPT_DIR/$OUTPUT_DIR"

# Check if virtual environment exists
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    PYTHON="$VENV_PYTHON"
    echo -e "${GRAY}Using virtual environment Python: $PYTHON${NC}"
fi

# Install PyInstaller if not present
echo -e "${CYAN}[1/3] Checking PyInstaller...${NC}"
$PYTHON -m pip install pyinstaller --quiet

# Clean previous build
echo -e "${CYAN}[2/3] Cleaning previous build...${NC}"
rm -rf "$DIST_DIR"
rm -rf "$SCRIPT_DIR/build"

# Build executable
echo -e "${CYAN}[3/3] Building executable...${NC}"
SPEC_FILE="$SCRIPT_DIR/kxns-cli.spec"
if [ -f "$SPEC_FILE" ]; then
    $PYTHON -m PyInstaller "$SPEC_FILE" --distpath "$DIST_DIR" --workpath "$SCRIPT_DIR/build" --clean
else
    # Build without spec file
    $PYTHON -m PyInstaller \
        --name "kxns" \
        --onefile \
        --console \
        --distpath "$DIST_DIR" \
        --workpath "$SCRIPT_DIR/build" \
        --clean \
        --hidden-import "kxns_cli" \
        --hidden-import "kosong" \
        --hidden-import "pykaos" \
        --collect-all "kxns_cli" \
        "$SCRIPT_DIR/src/kxns_cli/cli/__main__.py"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Build completed successfully!         ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Output directory: $DIST_DIR${NC}"
echo ""

# List output files
find "$DIST_DIR" -type f | while read -r file; do
    echo -e "${GRAY}  $file${NC}"
done
