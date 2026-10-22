#!/bin/bash
# Runs the Drakengard runner from game/ with the environment already set by the caller:
#   scripts/run_game.sh <seconds> <log file> [runner exe name]
# Refuses to start while the Valkyrie Profile 2 recomp (vp2s.exe) or another runner is running:
# both games share the CPU, so overlapping runs skew timings and slow-motion checks.
seconds="$1"
log="$2"
exe="${3:-ps2EntryRunner.exe}"
if tasklist 2>/dev/null | grep -qi -E "vp2s\.exe|ps2EntryRunner"; then
    echo "run_game: another game is running, not starting" >&2
    tasklist 2>/dev/null | grep -i -E "vp2s\.exe|ps2EntryRunner" >&2
    exit 3
fi
cd "$(dirname "$0")/../game" || exit 1
timeout "$seconds" "../PS2Recomp/out/build-fast/ps2xRuntime/$exe" D:/Drakengard_Recomp/game/SLES_523.22 > "$log" 2>&1
