#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build a native Windows minimap2.exe from source, with the MSYS2
# MINGW-w64 toolchain. No conda, no WSL, no msys-2.0.dll dependency.
#
# Usage (from the repository root):
#   bash 03_dependence/windows-x86_64/build_minimap2.sh
#
# Environment:
#   MSYS2_ROOT   MSYS2 installation root           (default: /d/tools/msys2)
#   MINIMAP2_VER minimap2 version to build         (default: 2.31)
#   SRCDIR       where to unpack the source        (default: <repo>/tmp/build)
#   DESTDIR      where to put the binary           (default: <repo>/03_dependence/windows-x86_64/bin)
# ---------------------------------------------------------------------------
set -euo pipefail

MSYS2_ROOT="${MSYS2_ROOT:-/d/tools/msys2}"
MINIMAP2_VER="${MINIMAP2_VER:-2.31}"

# --- locate the repository root -------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

SRCDIR="${SRCDIR:-$REPO_ROOT/tmp/build}"
DESTDIR="${DESTDIR:-$SCRIPT_DIR/bin}"
TARBALL="$REPO_ROOT/tmp/downloads/minimap2-${MINIMAP2_VER}.tar.gz"
URL="https://codeload.github.com/lh3/minimap2/tar.gz/refs/tags/v${MINIMAP2_VER}"

mkdir -p "$SRCDIR" "$DESTDIR"

# --- toolchain -------------------------------------------------------------
export PATH="$MSYS2_ROOT/mingw64/bin:$PATH"
for tool in gcc make ar; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: $tool not found in $MSYS2_ROOT/mingw64/bin" >&2
    echo "Install it with: pacman -S --needed mingw-w64-x86_64-toolchain mingw-w64-x86_64-zlib" >&2
    exit 1
  fi
done

echo "== toolchain =="
gcc  --version | head -1
make --version | head -1

# --- fetch source ----------------------------------------------------------
if [ ! -f "$TARBALL" ]; then
  echo "== downloading minimap2 v${MINIMAP2_VER} =="
  mkdir -p "$(dirname "$TARBALL")"
  curl -L --fail --ssl-no-revoke --retry 5 --retry-all-errors -o "$TARBALL" "$URL"
fi

echo "== unpacking =="
rm -rf "$SRCDIR/minimap2-${MINIMAP2_VER}"
tar xzf "$TARBALL" -C "$SRCDIR"
cd "$SRCDIR/minimap2-${MINIMAP2_VER}"

# --- build -----------------------------------------------------------------
# Notes on the flags:
#   * -std=gnu11  : kalloc.h uses anonymous struct members, which are not part
#                   of gnu17/gnu23; gcc 16 defaults to gnu23 and errors out.
#   * -static ... : fold in libwinpthread and zlib so the resulting
#                   minimap2.exe runs on a machine with no MSYS2 installed.
#                   Upstream links -lpthread, which MINGW-w64 maps to
#                   libwinpthread; -static also removes the msys-2.0.dll
#                   dependency you get when building in the plain MSYS shell.
echo "== building =="
make clean >/dev/null 2>&1 || true
make -j"$(nproc)" \
  CFLAGS="-g -Wall -O2 -std=gnu11 -Wno-error" \
  LIBS="-lm -lz -lpthread -static -static-libgcc" \
  minimap2

# --- install ---------------------------------------------------------------
cp -f minimap2.exe "$DESTDIR/minimap2.exe"
chmod +x "$DESTDIR/minimap2.exe"

echo
echo "== result =="
ls -l "$DESTDIR/minimap2.exe"
"$DESTDIR/minimap2.exe" --version

echo
echo "== dynamic dependencies (should list only Windows system DLLs) =="
if command -v objdump >/dev/null 2>&1; then
  objdump -p "$DESTDIR/minimap2.exe" | grep 'DLL Name' || true
fi

echo
echo "Installed: $DESTDIR/minimap2.exe"
