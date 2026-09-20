#!/bin/sh
# Install a nanoamp wrapper into a directory on PATH.
set -e

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEST="${1:-$HOME/.local/bin}"
mkdir -p "$DEST"

cat > "$DEST/nanoamp" <<EOF
#!/bin/sh
exec Rscript --vanilla "$SCRIPT_DIR/nanoamp.R" "\$@"
EOF
chmod +x "$DEST/nanoamp"

echo "Installed: $DEST/nanoamp"
case ":$PATH:" in
  *":$DEST:"*) ;;
  *) echo "Note: add $DEST to PATH." ;;
esac
