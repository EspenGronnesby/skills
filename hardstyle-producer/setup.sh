#!/usr/bin/env bash
# hardstyle-producer setup (macOS/Linux). Installs ONLY into an isolated venv inside this skill folder.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-}"
for c in python3.12 python3.11 python3; do
  if [ -z "$PY" ] && command -v "$c" >/dev/null; then PY="$c"; fi
done
[ -z "$PY" ] && { echo "Fant ikke Python 3.11/3.12. Mac: brew install python@3.12"; exit 1; }
echo "Bruker $($PY --version)"
command -v ffmpeg >/dev/null || echo "ADVARSEL: ffmpeg mangler (trengs for MP3). Mac: brew install ffmpeg"
"$PY" -m venv "$HERE/.venv"
"$HERE/.venv/bin/pip" install -q --upgrade pip
"$HERE/.venv/bin/pip" install -q -r "$HERE/requirements.txt"
"$HERE/.venv/bin/pip" install -q --no-deps "basic-pitch==0.4.0"
chmod +x "$HERE/bin/hsp"
mkdir -p "$HOME/.claude/commands"
cp "$HERE"/commands/*.md "$HOME/.claude/commands/"
echo "Kjører selvtest ..."
"$HERE/bin/hsp" diagnose | tail -5
"$HERE/.venv/bin/python" "$HERE/tests/selftest.py"
