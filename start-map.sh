#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Derive the home from the account we are running as, so no literal username is
# baked into paths. Every step here is optional: $USER is not always exported
# (cron, containers, some login managers) and `getent` is missing on musl and
# minimal images - where `set -e` would otherwise abort with no message at all.
USER_HOME="${ER_USER_HOME:-}"
if [[ -z "$USER_HOME" ]]; then
    account="${USER:-$(id -un 2>/dev/null || true)}"
    USER_HOME="$(getent passwd "$account" 2>/dev/null | cut -d: -f6 || true)"
fi
: "${USER_HOME:=$HOME}"
readonly USER_HOME
readonly STEAM_ROOT="${ER_STEAM_ROOT:-$USER_HOME/.steam/steam}"
readonly PREFIX="${ER_PREFIX:-$STEAM_ROOT/steamapps/compatdata/1245620/pfx}"
readonly PORT="${ER_MAP_PORT:-8099}"

command -v node >/dev/null || {
    printf 'Node.js was not found on PATH.\n' >&2
    exit 1
}

save="${ER_SAVE:-}"
if [[ -z "$save" ]]; then
    shopt -s nullglob
    saves=("$PREFIX"/drive_c/users/steamuser/AppData/Roaming/EldenRing/[0-9]*/ER0000.err)
    if ((${#saves[@]} == 0)); then
        saves=("$PREFIX"/drive_c/users/steamuser/AppData/Roaming/EldenRing/[0-9]*/ER0000.sl2)
    fi
    for candidate in "${saves[@]}"; do
        if [[ -z "$save" || "$candidate" -nt "$save" ]]; then
            save="$candidate"
        fi
    done
fi

test -r "$save" || {
    printf 'No active ER0000.err or ER0000.sl2 was found under: %s\n' "$PREFIX" >&2
    exit 1
}
test -r "$ROOT/web/tiles/manifest.json" || {
    printf 'Map assets are missing. Run ./setup-linux.sh first.\n' >&2
    exit 1
}

display_path() {
    local p="$1"
    printf '%s' "${p/#"$USER_HOME"/\~}"
}

if [[ "${1:-}" == "--check" ]]; then
    printf 'Node: %s\n' "$(command -v node)"
    printf 'Save: %s\n' "$(display_path "$save")"
    printf 'Map assets: %s\n' "$(display_path "$ROOT/web/tiles/manifest.json")"
    exit 0
fi

if command -v xdg-open >/dev/null; then
    (
        for _ in {1..100}; do
            if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
                xdg-open "http://localhost:$PORT" >/dev/null 2>&1
                exit 0
            fi
            sleep 0.1
        done
    ) &
fi

# Prefer the venv setup-linux.sh built. Plenty of distros ship no bare `python`,
# which is what the server would otherwise spawn the memory reader with.
python_bin="$ROOT/cache/python/bin/python"
if [[ ! -x "$python_bin" ]]; then
    python_bin="$(command -v python3 || command -v python || true)"
fi
test -n "$python_bin" || {
    printf 'No Python interpreter found for the live position reader.\n' >&2
    exit 1
}

exec node "$ROOT/server/index.js" --port "$PORT" --save "$save" \
    --python "$python_bin" --live-memory "$@"
