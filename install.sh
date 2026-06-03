#!/bin/bash
# claude-call installer — checks prerequisites, installs deps, downloads a whisper model.
set -e
cd "$(dirname "$0")"
echo "== claude-call install =="

need() { command -v "$1" >/dev/null 2>&1; }
miss=()
need uv      || miss+=("uv — https://docs.astral.sh/uv/")
need ffmpeg  || miss+=("ffmpeg")
{ need whisper-server || need whisper-cli; } || miss+=("whisper.cpp (whisper-server / whisper-cli)")
need claude  || miss+=("claude — Claude Code CLI, logged in")

if [ ${#miss[@]} -gt 0 ]; then
  echo "Missing prerequisites:"
  for m in "${miss[@]}"; do echo "  - $m"; done
  if [[ "$OSTYPE" == darwin* ]] && need brew; then
    echo
    echo "On macOS, install them with:"
    echo "  brew install uv ffmpeg whisper-cpp portaudio"
    echo "  (and Claude Code: https://docs.claude.com/claude-code)"
  fi
  echo
  echo "Install the missing items, then run ./install.sh again."
  [ "$1" = "--force" ] || exit 1
fi

echo "-- installing python deps (uv sync) --"
uv sync

if [ ! -f "$HOME/.cache/whisper/ggml-small.bin" ]; then
  echo "-- downloading whisper model (small) --"
  ./scripts/download-model.sh small
fi

echo
echo "Done. Start a call from inside any project:"
echo "  $(pwd)/call.sh"
echo
echo "Optional — make it a global command:"
echo "  ln -s \"$(pwd)/call.sh\" /usr/local/bin/claude-call    # then just run: claude-call"
