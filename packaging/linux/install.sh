#!/usr/bin/env bash
# Abydex installer for Linux (per user, no root needed).
#   curl -fsSL https://raw.githubusercontent.com/nDumitru/abydex/main/packaging/linux/install.sh | bash
# or, from an extracted release / clone:  ./packaging/linux/install.sh
set -euo pipefail

APP="${XDG_DATA_HOME:-$HOME/.local/share}/abydex/app"
BIN="$HOME/.local/bin"
SRC="${ABYDEX_SRC:-}"

PY="$(command -v python3 || true)"
[ -z "$PY" ] && { echo "Ai nevoie de Python 3.10+ (ex: sudo apt install python3 python3-venv)"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || { echo "Python prea vechi (minim 3.10)."; exit 1; }
"$PY" -m venv --help >/dev/null 2>&1 || { echo "Lipseste venv (ex: sudo apt install python3-venv)"; exit 1; }

if [ -z "$SRC" ]; then
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
  if [ -n "$HERE" ] && [ -f "$HERE/../../pyproject.toml" ]; then SRC="$HERE/../.."
  else SRC="git+https://github.com/nDumitru/abydex.git"; fi
fi

echo "Instalez Abydex in $APP ..."
"$PY" -m venv "$APP"
"$APP/bin/python" -m pip install --upgrade pip >/dev/null
"$APP/bin/python" -m pip install "$SRC"

mkdir -p "$BIN" "$HOME/.local/share/applications"
ln -sf "$APP/bin/abydex" "$BIN/abydex"
cat > "$HOME/.local/share/applications/abydex.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Abydex
Comment=AI local pentru printare 3D
Exec=$APP/bin/abydex ui
Terminal=true
Categories=Graphics;3DGraphics;Engineering;
DESK

echo
echo "Gata! Porneste cu:  abydex ui   (sau din meniul de aplicatii: Abydex)"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "Adauga $BIN in PATH (ex: echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.bashrc)";; esac
