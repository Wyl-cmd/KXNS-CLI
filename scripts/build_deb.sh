#!/bin/bash
# Kxns Hunter CLI - Debian Package Build Script
# Usage: ./scripts/build_deb.sh [--output dist/]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
OUTPUT_DIR="$ROOT_DIR/dist"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo "Building Debian package..."

# Ensure binary exists
BINARY="$OUTPUT_DIR/kxns"
if [[ ! -f "$BINARY" ]]; then
    echo "Binary not found at $BINARY"
    echo "Run ./build.sh first to build the executable."
    exit 1
fi

# Extract version from pyproject.toml
VERSION="$(grep -E '^version\s*=\s*"' "$ROOT_DIR/pyproject.toml" | head -1 | sed -E 's/.*"([^"]+)".*/\1/')"
if [[ -z "$VERSION" ]]; then
    echo "Failed to extract version from pyproject.toml"
    exit 1
fi

echo "Package version: $VERSION"

# Prepare package structure
PKG_DIR="$OUTPUT_DIR/kxns_${VERSION}_amd64"
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/doc/kxns"
mkdir -p "$PKG_DIR/usr/share/applications"

cp "$BINARY" "$PKG_DIR/usr/bin/kxns"
chmod 755 "$PKG_DIR/usr/bin/kxns"

# Control file
cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: kxns
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.12)
Maintainer: Kxns Hunter Team <dev@kxns.io>
Description: Kxns Hunter CLI - A penetration testing focused AI agent CLI tool.
 Kxns Hunter CLI provides an AI-powered penetration testing assistant
 with web interface, scan orchestration, and Kali Linux integration.
EOF

# Copy docs
cp "$ROOT_DIR/README.md" "$PKG_DIR/usr/share/doc/kxns/"
cp "$ROOT_DIR/CHANGELOG.md" "$PKG_DIR/usr/share/doc/kxns/" 2>/dev/null || true

# Build .deb
dpkg-deb --build "$PKG_DIR"

# Move final deb to output dir
mv "$OUTPUT_DIR/kxns_${VERSION}_amd64.deb" "$OUTPUT_DIR/kxns_${VERSION}_amd64.deb"

echo "Debian package built: $OUTPUT_DIR/kxns_${VERSION}_amd64.deb"
