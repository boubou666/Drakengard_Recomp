#!/bin/bash
# Builds ps2EntryRunner with GCC -> build/gcc/PS2Recomp/ps2xRuntime/ps2EntryRunner.exe
# (CMakeLists.txt: PS2Recomp's runner plus the VU microcode compiled ahead of time).
# On Windows it uses MSYS2 UCRT64 (pacman -S mingw-w64-ucrt-x86_64-{gcc,cmake,ninja,pkgconf,ffmpeg}) and copies
# the DLLs the runner needs next to it, so it also starts from Git Bash, PowerShell or Explorer.
# Usage: scripts/build_runner_gcc.sh [jobs]   (default 10: GCC unity batches of generated code take ~1-2 GB each)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/gcc"
JOBS="${1:-10}"
MSYS2_ROOT="${MSYS2_ROOT:-/c/msys64}"
if [ -d "$MSYS2_ROOT/ucrt64/bin" ]; then
    export PATH="$MSYS2_ROOT/ucrt64/bin:$PATH"
fi

cmake -S "$ROOT" -B "$BUILD" -G Ninja -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
    -DCMAKE_BUILD_TYPE=Fast "-DCMAKE_CXX_FLAGS_FAST=-O2 -DNDEBUG" "-DCMAKE_C_FLAGS_FAST=-O2 -DNDEBUG" \
    -DPS2X_ENABLE_AGRESSIVE_LOGS=OFF -DPS2X_ENABLE_IOP_RPC_TRACE=OFF
cmake --build "$BUILD" --target ps2EntryRunner -j "$JOBS"

BIN_DIR="$BUILD/PS2Recomp/ps2xRuntime"
if [ -x "$MSYS2_ROOT/usr/bin/ldd" ]; then
    # ldd lists every DLL the loader resolves; keep the ones from the UCRT64 prefix (not Windows' own).
    count=0
    for dll in $("$MSYS2_ROOT/usr/bin/ldd" "$BIN_DIR/ps2EntryRunner.exe" | awk '{print $3}' | grep -i "^/ucrt64/bin/.*\.dll$" | sort -u); do
        cp -u "$MSYS2_ROOT$dll" "$BIN_DIR/"
        count=$((count + 1))
    done
    echo "Staged $count DLLs from $MSYS2_ROOT/ucrt64/bin in $BIN_DIR"
fi
