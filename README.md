# Drakengard (EU) static recompilation

Work in progress: running Drakengard (PAL, SLES-52322) natively on PC by statically recompiling the PS2 game with
[PS2Recomp](https://github.com/ran-j/PS2Recomp). The game boots, plays through the menus and the prologue, and
reaches the first mission with textured 3D (about 10 fps for now).

This repository holds the project around the recompiler, not the game:
- `recomp/` - recompiler configs, the Ghidra function-map export and analysis scripts
- `runtime/zz_drakengard_overrides.cpp` - game-specific runtime bindings and test harness hooks
- `scripts/` - build scripts (Windows, MSVC + Ninja)
- `RECOMP_NOTES.md` - how to rebuild, what was fixed and why, current status

It contains no game data: no ISO, no extracted files, no recompiled game code. You need your own copy of the game.

The runtime changes made for this game are in the PS2Recomp fork
[boubou666/PS2Recomp](https://github.com/boubou666/PS2Recomp), branch `main`, shared with a
Valkyrie Profile 2 recompilation.
