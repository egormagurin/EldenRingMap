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
readonly GAME_DIR="${ER_GAME_DIR:-$STEAM_ROOT/steamapps/common/ELDEN RING/Game}"
# Playing a loose-file mod such as Elden Ring Reforged? Point ER_MOD_DIR at the
# folder holding its regulation.bin. There is no reliable place to guess from -
# mods get unpacked wherever you keep them - so this is not auto-detected.
readonly MOD_DIR="${ER_MOD_DIR:-}"
readonly NATIVE_DIR="$ROOT/cache/native-oodle"
readonly SOURCE_DIR="$NATIVE_DIR/source"
readonly BUILD_DIR="$NATIVE_DIR/build"
readonly VENV_DIR="$ROOT/cache/python"
readonly PYTHON="$VENV_DIR/bin/python"
readonly LIB="$BUILD_DIR/liblinoodle.so"
readonly LINOODLE_COMMIT=90b8d825f7f89272f03f52b5d1db4708e07eb83f

# Package name per distro for each command we need, so a missing dependency can
# print the exact line to paste rather than just its own name.
#   command | debian/ubuntu | fedora/rhel | arch | opensuse
readonly PACKAGES="
git|git|git|git|git
cmake|cmake|cmake|cmake|cmake
cc|build-essential|gcc-c++|base-devel|gcc-c++
node|nodejs|nodejs|nodejs|nodejs18
python3|python3|python3|python|python3
venv|python3-venv|python3|python|python3
"

# -> the install command for this machine, or empty if the distro is unknown.
install_hint() {
    local command_name="$1" row field=0
    row="$(printf '%s\n' "$PACKAGES" | grep "^$command_name|" || true)"
    [[ -n "$row" ]] || return 0
    if command -v apt-get >/dev/null; then
        field=2; printf 'sudo apt install '
    elif command -v dnf >/dev/null; then
        field=3; printf 'sudo dnf install '
    elif command -v pacman >/dev/null; then
        field=4; printf 'sudo pacman -S '
    elif command -v zypper >/dev/null; then
        field=5; printf 'sudo zypper install '
    else
        return 0
    fi
    printf '%s\n' "$row" | cut -d'|' -f"$field"
}

missing=()

need_command() {
    local command_name="$1" probe="${2:-$1}"
    command -v "$probe" >/dev/null || missing+=("$command_name")
}

report_missing() {
    ((${#missing[@]})) || return 0
    printf '\nMissing dependencies: %s\n\n' "${missing[*]}" >&2
    local command_name hint
    for command_name in "${missing[@]}"; do
        hint="$(install_hint "$command_name")"
        if [[ -n "$hint" ]]; then
            printf '  %-10s %s\n' "$command_name" "$hint" >&2
        else
            printf '  %-10s (install it with your package manager)\n' "$command_name" >&2
        fi
    done
    printf '\nNode.js 18+ is also available from https://nodejs.org\n' >&2
    exit 1
}

check_host() {
    need_command git
    need_command cmake
    need_command python3
    need_command node
    # Either compiler will build the Oodle shim; clang is only preferred.
    if ! command -v clang >/dev/null && ! command -v cc >/dev/null && \
       ! command -v gcc >/dev/null; then
        missing+=(cc)
    fi
    # A venv is only needed when uv is absent - uv brings its own.
    if ! command -v uv >/dev/null; then
        python3 -c 'import venv, ensurepip' 2>/dev/null || missing+=(venv)
    fi
    report_missing

    # Versions, once we know the commands exist at all.
    python3 - <<'PY' || exit 1
import sys
if sys.version_info < (3, 9):
    sys.exit(f"Python 3.9 or newer is required; this is {sys.version.split()[0]}")
PY
    local node_major
    node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
    if (( node_major < 18 )); then
        printf 'Node.js 18 or newer is required; this is %s\n' \
            "$(node --version 2>/dev/null || echo 'not runnable')" >&2
        printf 'Get it from https://nodejs.org or your package manager.\n' >&2
        exit 1
    fi

    test -r "$GAME_DIR/eldenring.exe" || {
        printf 'Elden Ring was not found at: %s\n' "$GAME_DIR" >&2
        exit 1
    }
    test -r "$GAME_DIR/regulation.bin" || {
        printf 'regulation.bin was not found at: %s\n' "$GAME_DIR" >&2
        exit 1
    }
    test -r "$GAME_DIR/oo2core_6_win64.dll" || {
        printf 'The game Oodle DLL was not found at: %s\n' "$GAME_DIR" >&2
        exit 1
    }
    if [[ -n "$MOD_DIR" && ! -r "$MOD_DIR/regulation.bin" ]]; then
        printf 'ERR mod files were not found at: %s\n' "$MOD_DIR" >&2
        exit 1
    fi
}

display_path() {
    local p="$1"
    printf '%s' "${p/#"$USER_HOME"/\~}"
}

if [[ "${1:-}" == "--check" ]]; then
    check_host
    printf 'Game: %s\n' "$(display_path "$GAME_DIR")"
    printf 'Mod files: %s\n' "$(display_path "${MOD_DIR:-none}")"
    printf 'Native Oodle: %s\n' "$(display_path "$LIB")"
    exit 0
fi

check_host

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
    mkdir -p "$NATIVE_DIR"
    git clone --quiet --recurse-submodules https://github.com/McSimp/linoodle.git "$SOURCE_DIR"
fi
git -C "$SOURCE_DIR" checkout --quiet "$LINOODLE_COMMIT"
git -C "$SOURCE_DIR" submodule update --init --recursive --quiet

if [[ ! -f "$LIB" ]]; then
    # clang is what linoodle is developed against, but gcc builds it fine.
    if command -v clang >/dev/null && command -v clang++ >/dev/null; then
        compilers=(-DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++)
    else
        printf 'clang not found, building the Oodle shim with gcc.\n'
        compilers=(-DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++)
    fi
    jobs="$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"
    cmake -S "$SOURCE_DIR" -B "$BUILD_DIR" \
        -DCMAKE_BUILD_TYPE=Release \
        "${compilers[@]}" \
        '-DCMAKE_CXX_FLAGS=-include cstdint -include utility -Wno-error'
    cmake --build "$BUILD_DIR" --target linoodle -j"$jobs"
fi

mkdir -p "$NATIVE_DIR/runtime"
ln -sfn "$GAME_DIR/oo2core_6_win64.dll" \
    "$NATIVE_DIR/runtime/oo2core_8_win64.dll"

# uv is much faster, but it is a niche tool to demand - fall back to the stdlib
# venv module, which every supported Python already has.
printf '\nInstalling Python packages...\n'
if command -v uv >/dev/null; then
    uv venv --quiet --allow-existing "$VENV_DIR"
    uv pip install --quiet --python "$PYTHON" \
        zstandard pycryptodome pillow texture2ddecoder numpy
else
    [[ -x "$PYTHON" ]] || python3 -m venv "$VENV_DIR"
    "$PYTHON" -m pip install --quiet --upgrade pip
    "$PYTHON" -m pip install --quiet \
        zstandard pycryptodome pillow texture2ddecoder numpy
fi

export ER_GAME_DIR="$GAME_DIR"
export ER_MOD_DIR="$MOD_DIR"
export ER_LINOODLE="$LIB"
cd "$NATIVE_DIR/runtime"

printf '\n[1/6] Extracting base map tiles...\n'
"$PYTHON" "$ROOT/tools/extract_tiles.py" --game-dir "$GAME_DIR"
printf '\n[2/6] Building marker data...\n'
"$PYTHON" "$ROOT/tools/build_markers.py" "$GAME_DIR"
printf '\n[3/6] Indexing map files...\n'
"$PYTHON" "$ROOT/tools/enumerate_maps.py"
printf '\n[4/6] Extracting item locations...\n'
"$PYTHON" "$ROOT/tools/extract_items.py" --game-dir "$GAME_DIR" --mod-dir "$MOD_DIR"
printf '\n[5/6] Extracting map icons...\n'
"$PYTHON" "$ROOT/tools/extract_icons.py" --game-dir "$GAME_DIR" --mod-dir "$MOD_DIR"
# Rune and Ember Pieces are Reforged collectibles - an unmodded game has none,
# so this only runs with a mod directory set.
if [[ -n "$MOD_DIR" ]]; then
    printf '\n[6/6] Extracting Reforged rune/ember pieces...\n'
    "$PYTHON" "$ROOT/tools/extract_pieces.py" --game-dir "$GAME_DIR" --mod-dir "$MOD_DIR"
else
    printf '\n[6/6] Reforged rune/ember pieces - skipped (ER_MOD_DIR not set)\n'
fi

printf '\nSetup complete. Run ./start-map.sh to open the live map.\n'
