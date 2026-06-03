#!/bin/bash
# claude-call — start a voice call with your Claude Code session.
# Run it from inside the project whose session you want to resume.
set -e

# Resolve the real script dir (works through symlinks, e.g. /usr/local/bin/claude-call)
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"; SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# The session to resume = the directory you called from
export CALL_CWD="${CALL_CWD:-$PWD}"

cd "$SCRIPT_DIR"
[ -f .env ] || cp .env.example .env
./build.sh 2>/dev/null || true        # compila o aecbridge se for usar CALL_AEC=1

echo "📞 claude-call — resuming the Claude Code session in: $CALL_CWD"
exec uv run python call.py
