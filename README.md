<div align="center">

# Drakengard_Recomp

**A native Windows port of *Drakengard* (PAL, `SLES-52322`), made by statically recompiling the game's PlayStation 2 code to C++.**<br>
Not an emulator: the game's own MIPS R5900 code, rebuilt as a Windows program on a reimplementation of the PS2 hardware.

![Platform](https://img.shields.io/badge/platform-Windows-1b8cff)
![Compiler](https://img.shields.io/badge/compiler-MSVC-1b8cff)
![Based on](https://img.shields.io/badge/based%20on-PS2Recomp-17a35b)
![Status](https://img.shields.io/badge/status-not%20playable%20yet-d01f3c)

</div>

> [!IMPORTANT]
> No game files are included: no ELF, IRX modules, data archives, or code generated from them.
> You need **your own copy** of the PAL release, PS2 ID **`SLES-52322`**. The port is built against that disc's executable:
>
> | File | SHA-1 |
> |---|---|
> | `SLES_523.22` | `3b06fe9b7dfd378a55f481135e273aaaf39604be` |

## Status

**Work in progress, not playable yet.** The game boots through the logos, title screen and menus. **New Game** goes
through the difficulty prompt, the prologue, "Chapter 1 Beginnings" and the mission briefing, into the first mission:
HUD, radar, objective map, in-mission dialogue and textured, lit 3D. The mission runs at about 12 frames per second, there is
no sound yet, and the Chapter 1 opening movie is skipped.

| Milestone | |
|---|:---:|
| Map and recompile the main ELF (about 40,400 functions) | ✅ |
| Boot: EE kernel, the game's own IOP modules, CD reads from the disc files | ✅ |
| Memory card detection and controller | ✅ |
| Logos, title screen and main menu | ✅ |
| New Game: difficulty prompt, prologue, chapter title, mission briefing | ✅ |
| First mission: HUD, radar, dialogue, textured 3D | ✅ |
| Mission at full speed | 🔧 |
| Opening movie (MPEG) | ⏳ |
| Sound and music | ⏳ |
| Combat, dragon flight, later chapters, saving | ⏳ |
| Widescreen, higher resolution | ⏳ |

✅ works · 🔧 in progress · ⏳ not reached yet

[RECOMP_NOTES.md](RECOMP_NOTES.md) records how the port was brought up, every runtime fix and how it was found, the
performance work, and what remains open. [docs/async_vif1_plan.md](docs/async_vif1_plan.md) is the current plan for
running VIF1 and VU1 alongside the EE.

## Goal

A fully playable *Drakengard* as a native executable, from the opening movie to the endings. Accuracy first; once it
is playable, widescreen and higher internal resolution.

## How it works

```
disc files (game/) ──► Ghidra (headless, EE extension) + ExportPS2Functions ──► function map (CSV)
                                           │
                     ps2_recomp + recomp/drakengard_ghidra.toml ──► C++ (one file per function)
                                           │
                          scripts/sync_runner.py ──► PS2Recomp runner + runtime/zz_drakengard_overrides.cpp
                                           │
   PS2Recomp runtime: EE kernel HLE · DMAC · GIF/GS · VIF/VU0/VU1 · IPU ─┼─► ps2EntryRunner.exe
   PS2Recomp IOP:     R3000A interpreter running the game's own IRX · SPU2 · SIO2
```

- Ghidra (with the Emotion Engine extension) maps the functions of `SLES_523.22`; the export script writes them to
  `recomp/ghidra/ghidra_functions_fixed.csv`.
- `recomp/drakengard_ghidra.toml` adds the entry points Ghidra misses: jump and call targets, gap starts and every data
  pointer into code.
- PS2Recomp turns every function into C++; `scripts/sync_runner.py` installs the generated code and the Drakengard
  override module into the runner, copying only changed files.
- `runtime/zz_drakengard_overrides.cpp` holds the game-specific bindings and the test harness hooks.

The PS2Recomp fork lives in `PS2Recomp/` (a separate clone of [boubou666/PS2Recomp](https://github.com/boubou666/PS2Recomp),
branch `main`), shared with the *Valkyrie Profile 2* recompilation. Most fixes made for this port land there, for example the
fast VU1 interpreter, the multi-threaded GS rasterizer and the IOP scheduler.

## Requirements

- Windows 10 or 11, Python 3
- Visual Studio 2022 Build Tools ("Desktop development with C++": MSVC, CMake, Ninja)
- To rebuild the function map only: Ghidra 12.1.4 in `tools\ghidra_12.1.4_PUBLIC`, the Emotion Engine extension for it, and JDK 21
- Your own copy of `SLES-52322` (check the hash above), with the disc's files copied into `game/`

The build scripts currently expect the repository at `D:\Drakengard_Recomp` and the default Build Tools location.

## Build and run

```powershell
git clone https://github.com/boubou666/Drakengard_Recomp.git D:\Drakengard_Recomp
cd D:\Drakengard_Recomp
git clone https://github.com/boubou666/PS2Recomp.git PS2Recomp
scripts\build_tools.bat
PS2Recomp\out\build\ps2xRecomp\ps2_recomp.exe recomp\drakengard_ghidra.toml
python scripts\sync_runner.py
scripts\build_runner.bat
```

`recomp\ghidra\ghidra_run.bat` rebuilds the Ghidra function map from `game\SLES_523.22` if you need it. The first runner build
takes about 40 minutes: the recompiled code is several hundred megabytes of C++.

Run the game from its folder, which the runtime uses as `cdrom0:`:

```powershell
cd game
..\PS2Recomp\out\build-fast\ps2xRuntime\ps2EntryRunner.exe D:\Drakengard_Recomp\game\SLES_523.22
```

Set `PS2X_GS_ASYNC_RASTER=1` to rasterize on worker threads (much faster; it will become the default).

A controller is used when one is connected; otherwise the keyboard (US key positions):

| PS2 button | Keyboard |
|---|---|
| D-pad | Arrow keys or W A S D |
| Cross / Circle / Square / Triangle | X or Space / C or Esc / Z or Numpad 0 / V or Numpad 1 |
| L1 / R1 / L2 / R2 | Q / E / Left Shift / Right Shift |
| Start / Select | Enter / Tab |

| Key | What it does |
|---|---|
| F1 | Runtime debugger |

<details>
<summary><b>Runtime and diagnostic options</b></summary>

| Variable | Effect |
|---|---|
| `PS2X_GS_ASYNC_RASTER=1` | Rasterize on worker threads |
| `PS2X_VIF1_ASYNC=1` | Experimental: run VIF1 transfers and VU1 programs on their own thread |
| `PS2X_FPS_LOG=1` | Print the game's frames per second every 5 s |
| `PS2X_CAPTURE_DIR=<dir>`, `PS2X_CAPTURE_INTERVAL=<s>` | Save the presented frame every few seconds (works minimized) |
| `PS2X_INPUT_SCRIPT=sec:mask:dur;…`, `PS2X_INPUT_SCRIPT_CLOCK=frames` | Scripted pad input for unattended runs, timed in seconds or in game frames (`recomp/input_newgame_frames.txt` plays from boot into the first mission) |
| `PS2X_PAD_SCRIPT=t:BUTTON[/ms],…` | Shared runtime's scripted button presses (seconds from start) |
| `PS2X_PROFILE=<s>`, `PS2X_PROFILE_DELAY`, `PS2X_PROFILE_OUT` | Sampling profiler; `recomp/symbolize_profile.py` names the functions |
| `PS2X_GS_SHADOW_CHECK=1` | A second, synchronous GS receives every command; VRAM is compared regularly |
| `PS2X_VU1_RECORD=<file>` | Record VU1 microprogram runs for the `ps2_vu1_replay` tool (`scripts\build_vu1_replay.bat`) |
| `PS2X_GS_DUMP_AT=<s>` | Log the next GS primitives with their state and the GIF tags that produced them |
| `PS2X_TRACE_CDREAD=1`, `PS2X_DUMP_EE_THREADS=<s>` | Log every CD read; periodically print every guest thread |

`scripts\run_game.sh <seconds> <log>` runs the game for a fixed time and refuses to start while another PS2Recomp game is
running, so measurements stay clean.

</details>

## Known issues

- **The mission is slow:** about 12 frames per second. VU1 runs in an interpreter on the game's own thread, and the GS is a
  software rasterizer; running VIF1/VU1 alongside the EE is the next step.
- **No sound or music yet.**
- **The Chapter 1 opening movie is skipped:** its MPEG stream shows grey, so the movie is passed over.
- **Unchecked against hardware:** the sky band and camera framing in the first mission, and the untextured fog on the ground.

## Repository layout

| Path | Contents |
|---|---|
| `recomp/` | Recompiler configs, Ghidra project scripts and function map, analysis and test scripts, input scripts |
| `runtime/` | Drakengard override module (game-specific bindings, test harness hooks) |
| `scripts/` | Build scripts (tools, runner, unit tests, VU1 replay), runner sync, game launcher |
| `docs/` | Design notes and plans |
| `PS2Recomp/` | PS2Recomp fork (separate clone, not tracked here) |

Everything derived from the game (`game/`, generated code, Ghidra databases, VU1 traces, captures and screenshots) is
git-ignored. Never commit or redistribute it.

## Credits

- [PS2Recomp](https://github.com/ran-j/PS2Recomp) by ran-j and contributors (GPL), the recompiler and runtime this port is built on.
- The *Valkyrie Profile 2: Silmeria* recompilation, developed alongside this port on the same PS2Recomp fork; many runtime
  fixes (GS, VU1, MPEG, SPU2, scheduler) are shared.
- *Drakengard* © Square Enix, developed by Cavia. This is an unofficial fan project, not affiliated with or endorsed by them.
