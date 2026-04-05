#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── Detect architecture ────────────────────────────────────────────────────────
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    TARGET="aarch64-apple-darwin"
else
    TARGET="x86_64-apple-darwin"
fi

echo "==> Building for $TARGET"

# ── Activate venv if present ──────────────────────────────────────────────────
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# ── Step 1: PyInstaller sidecar ───────────────────────────────────────────────
echo "==> Building PyInstaller sidecar..."
pip install pyinstaller --quiet
pyinstaller cachecow.spec --noconfirm --clean

# ── Step 2: Stage sidecar for Tauri ──────────────────────────────────────────
echo "==> Staging sidecar..."
mkdir -p src-tauri/binaries
cp dist/cachecow-server "src-tauri/binaries/cachecow-server-$TARGET"
chmod +x "src-tauri/binaries/cachecow-server-$TARGET"

# ── Step 3: Tauri build ───────────────────────────────────────────────────────
# Derive version from the current git tag (e.g. v1.0.0 → 1.0.0).
# Falls back to "dev" when there's no tag pointing at HEAD.
VERSION=$(git tag --points-at HEAD 2>/dev/null | grep '^v' | head -1 | sed 's/^v//')
VERSION=${VERSION:-dev}
echo "==> Building Tauri app (version: $VERSION)..."
cargo tauri build --config "{\"version\":\"$VERSION\"}"

# ── Done ──────────────────────────────────────────────────────────────────────
DMG=$(find src-tauri/target/release/bundle/dmg -name "*.dmg" 2>/dev/null | head -1)
if [ -n "$DMG" ]; then
    echo ""
    echo "==> Done: $DMG"
fi
