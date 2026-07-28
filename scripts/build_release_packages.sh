#!/usr/bin/env bash
# 构建 kxns 独立二进制 + deb 安装包（本地发布用，不推送）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(python3 - <<'PY'
import tomllib
from pathlib import Path
print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])
PY
)"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
DIST="$ROOT/dist"
ONEFILE="$DIST/onefile"
DEB_ROOT="$DIST/deb/kxns_${VERSION}_${ARCH}"
DEB_OUT="$DIST/kxns_${VERSION}_${ARCH}.deb"

echo "==> Version: $VERSION  Arch: $ARCH"

echo "==> Sync package metadata"
uv sync --reinstall-package kxns-cli

echo "==> Build web UI into package static/"
uv run python scripts/build_web.py

echo "==> PyInstaller one-file binary"
rm -rf "$DIST/kxns" "$DIST/kxns.exe" "$ONEFILE"
mkdir -p "$ONEFILE"
KXNS_BUILD_SHA="$(git rev-parse HEAD 2>/dev/null | cut -c1-12 || true)" \
  uv run pyinstaller --noconfirm kxns.spec
if [[ -f "$DIST/kxns.exe" ]]; then
  mv "$DIST/kxns.exe" "$ONEFILE/"
elif [[ -f "$DIST/kxns" ]]; then
  mv "$DIST/kxns" "$ONEFILE/"
else
  echo "error: pyinstaller output not found in dist/" >&2
  exit 1
fi
chmod +x "$ONEFILE/kxns" 2>/dev/null || true

echo "==> Build deb package"
rm -rf "$DIST/deb"
mkdir -p "$DEB_ROOT/DEBIAN" "$DEB_ROOT/usr/bin" "$DEB_ROOT/usr/share/doc/kxns"

install -m 0755 "$ONEFILE/kxns" "$DEB_ROOT/usr/bin/kxns"

# 便捷入口
cat > "$DEB_ROOT/usr/bin/web" <<'EOF'
#!/bin/sh
exec /usr/bin/kxns web "$@"
EOF
cat > "$DEB_ROOT/usr/bin/scan" <<'EOF'
#!/bin/sh
exec /usr/bin/kxns scan "$@"
EOF
cat > "$DEB_ROOT/usr/bin/doctor" <<'EOF'
#!/bin/sh
exec /usr/bin/kxns doctor "$@"
EOF
chmod 0755 "$DEB_ROOT/usr/bin/web" "$DEB_ROOT/usr/bin/scan" "$DEB_ROOT/usr/bin/doctor"

cat > "$DEB_ROOT/DEBIAN/control" <<EOF
Package: kxns
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: KXNS Hunter <noreply@localhost>
Depends: libc6
Description: KXNS Hunter CLI — AI-assisted penetration testing agent
 Standalone binary packaging of kxns-cli (chat, web UI, scan, doctor).
EOF

cp -f "$ROOT/CHANGELOG.md" "$DEB_ROOT/usr/share/doc/kxns/changelog" 2>/dev/null || true
gzip -f -9 "$DEB_ROOT/usr/share/doc/kxns/changelog" 2>/dev/null || true
if [[ -f "$ROOT/LICENSE" ]]; then
  cp -f "$ROOT/LICENSE" "$DEB_ROOT/usr/share/doc/kxns/copyright"
else
  echo "See project repository for license." > "$DEB_ROOT/usr/share/doc/kxns/copyright"
fi

dpkg-deb --build --root-owner-group "$DEB_ROOT" "$DEB_OUT"

echo "==> Done"
ls -lh "$ONEFILE/kxns" "$DEB_OUT"
"$ONEFILE/kxns" --version || true
